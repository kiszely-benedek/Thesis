"""Replay agreement (T6): a toy cascade over a fake cache; nothing is ever sent or written back.

The toy plant has no database tier, so the policy has two `context_rag` tiers (`first`, `second`)
and isolation-from-upstream questions start at `second`, as in the real `cascade_v4_iso`.
"""

# ruff: noqa: F811  (imported pytest fixtures are re-declared as test arguments)
from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Iterator
from pathlib import Path

import httpx2
import pytest

from plantgraph.demo.app.need_routing import route_question, split_by_start
from plantgraph.demo.app.replay_agreement import (
    ReplaySetup,
    _refuse_output_beside_cache,
    replay_corpus,
)
from plantgraph.demo.app.replay_models import (
    Agreement,
    CorpusReplay,
    OfflineResult,
    live_result,
)
from plantgraph.demo.app.replay_report import (
    ReplayReport,
    check_freeze,
    render_markdown,
    write_report,
)
from plantgraph.llm.fake_transport import FakeTransport
from plantgraph.qa.cascade.labels import anchor_finder
from plantgraph.qa.cascade.live_build import open_live_cascade
from plantgraph.qa.cascade.live_models import LiveAnswer
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.models import FinalAnswer, Question
from qa_harness_toy import CORPUS_ID
from test_demo_app import Env, env, scripted_transport, toy  # noqa: F401
from test_demo_routed_live import (
    ISOLATE_UPSTREAM,
    PLAIN_QUESTION,
    _primer_copy_of,
    _two_context_tiers,
)


def _client(transport: FakeTransport) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(transport.handler))


def _variant(env: Env, question_id: str, text: str) -> Question:
    return env.answerable.model_copy(update={"question_id": question_id, "text": text})


class Replay:
    """A toy corpus whose stored cache holds the replies to two of three questions."""

    def __init__(self, env: Env, tmp_path: Path) -> None:
        corpus = env.config.corpora[0]
        run = corpus.tier_runs["answer"]
        self.policy = _two_context_tiers()
        self.tier_runs = {"first": run, "second": _primer_copy_of(run)}
        artifacts = load_corpus_artifacts(CORPUS_ID, corpus.ingest_json)
        self.view = NetworkxGraphView(CORPUS_ID, artifacts.localized_sheets, artifacts.resolution)
        self.routed = _variant(env, "q-routed", ISOLATE_UPSTREAM)
        self.plain = _variant(env, "q-plain", PLAIN_QUESTION)
        self.uncached = _variant(env, "q-uncached", "Which sheet is the valve V-1 drawn on?")
        self.cache = tmp_path / "stored" / "cache.sqlite"
        self.cache.parent.mkdir()
        self.work_dir = tmp_path / "work"
        self.work_dir.mkdir()
        self.truth = self._store_answers([self.routed, self.plain])
        # the replay's own client: any request it sends is recorded, and the tests expect none
        self.sent = FakeTransport(default_reply=scripted_transport().default_reply)
        self.client = _client(self.sent)

    def _store_answers(self, questions: list[Question]) -> dict[str, OfflineResult]:
        """Answer the questions with paid calls once, so the cache holds exactly their replies."""
        routed = split_by_start(self.policy)
        finder = anchor_finder(self.view)
        truth: dict[str, OfflineResult] = {}
        for question in questions:
            route = route_question(question.text, finder, routed)
            opened = open_live_cascade(
                corpus_id=CORPUS_ID,
                policy=routed.by_start[route.start_index],
                view=self.view,
                load_plan=None,
                tier_run_dirs=self.tier_runs,
                cache_path=self.cache,
                calls_log_path=self.work_dir / "paid.jsonl",
                allow_paid_calls=True,
                http_client=_client(scripted_transport()),
            )
            with opened:
                answer = opened.cascade.ask(question)
            assert isinstance(answer, LiveAnswer)
            truth[question.question_id] = live_result(answer, route.need_label)
        return truth

    def setup(
        self,
        offline: dict[str, OfflineResult],
        questions: list[Question],
        *,
        routed_only: bool = False,
        cache_source: Path | None = None,
    ) -> ReplaySetup:
        return ReplaySetup(
            corpus_id=CORPUS_ID,
            policy=self.policy,
            view=self.view,
            load_plan=None,
            tier_run_dirs=self.tier_runs,
            questions=questions,
            offline=offline,
            cutoff_s=120.0,
            routed_only=routed_only,
            cache_source=cache_source or self.cache,
            work_dir=self.work_dir,
            http_client=self.client,
        )


@pytest.fixture
def replay(env: Env, tmp_path: Path) -> Iterator[Replay]:
    fixture = Replay(env, tmp_path)
    yield fixture
    os.chmod(fixture.cache, stat.S_IWRITE | stat.S_IREAD)  # a test made it read-only


def _by_id(result: CorpusReplay) -> dict[str, Agreement]:
    return {row.question_id: row.agreement for row in result.rows}


def test_agreeing_and_disagreeing_rows_are_counted(replay: Replay) -> None:
    other_answer = FinalAnswer(answer="NOT-THE-STORED-ANSWER", not_present=False)
    wrong = replay.truth["q-plain"].model_copy(update={"final_answer": other_answer})
    offline = {"q-routed": replay.truth["q-routed"], "q-plain": wrong}

    result = replay_corpus(replay.setup(offline, [replay.routed, replay.plain]))

    assert (result.n_agree, result.n_disagree, result.n_miss) == (1, 1, 0)
    assert _by_id(result) == {"q-routed": Agreement.AGREE, "q-plain": Agreement.DISAGREE}
    plain = next(row for row in result.rows if row.question_id == "q-plain")
    assert plain.differs == ("final_answer",)


def test_a_cache_miss_is_reported_and_nothing_is_sent(replay: Replay) -> None:
    offline = {**replay.truth, "q-uncached": replay.truth["q-plain"]}

    result = replay_corpus(replay.setup(offline, [replay.routed, replay.plain, replay.uncached]))

    assert (result.n_agree, result.n_disagree, result.n_miss) == (2, 0, 1)
    missed = next(row for row in result.rows if row.agreement is Agreement.MISS)
    assert missed.question_id == "q-uncached" and missed.missing_tier == "first"
    assert replay.sent.requests == []


def test_the_original_cache_is_only_read_never_written(replay: Replay) -> None:
    before = hashlib.sha256(replay.cache.read_bytes()).hexdigest()
    os.chmod(replay.cache, stat.S_IREAD)  # opening it for writing would now fail

    result = replay_corpus(replay.setup(replay.truth, [replay.routed, replay.plain]))

    assert result.cache_sha256_before == result.cache_sha256_after == before
    assert (replay.work_dir / "cache_copy.sqlite").exists()  # the replay used the copy


def test_routed_only_runs_the_later_start_cascade_alone(replay: Replay) -> None:
    offline = {"q-routed": replay.truth["q-routed"]}

    result = replay_corpus(
        replay.setup(offline, [replay.routed, replay.plain, replay.uncached], routed_only=True)
    )

    assert [row.question_id for row in result.rows] == ["q-routed"]
    assert result.rows[0].routed and result.n_agree == 1


def test_routed_only_with_no_routed_question_is_an_error(replay: Replay) -> None:
    offline = {"q-plain": replay.truth["q-plain"]}

    with pytest.raises(ValueError, match="to be routed"):
        replay_corpus(replay.setup(offline, [replay.plain], routed_only=True))


def test_a_different_label_is_a_disagreement(replay: Replay) -> None:
    other = replay.truth["q-plain"].model_copy(update={"need_label": None})

    result = replay_corpus(replay.setup({"q-plain": other}, [replay.plain]))

    assert result.rows[0].differs == ("need_label",)


def test_a_missing_cache_file_is_an_error(replay: Replay, tmp_path: Path) -> None:
    setup = replay.setup(replay.truth, [replay.routed], cache_source=tmp_path / "none.sqlite")

    with pytest.raises(FileNotFoundError, match="stored cache"):
        replay_corpus(setup)


def _write_freeze_list(tmp_path: Path, content: bytes, recorded: bytes) -> Path:
    """`a.txt` holds `content`; the list records the hash of `recorded`, and also a missing file."""
    (tmp_path / "a.txt").write_bytes(content)
    digest = hashlib.sha256(recorded).hexdigest()
    listing = tmp_path / "E9.sha256"
    listing.write_text(f"{digest} *a.txt\n{digest} *gone.txt\n", encoding="utf-8")
    return listing


def test_the_freeze_check_counts_changed_and_missing_files(tmp_path: Path) -> None:
    check = check_freeze(_write_freeze_list(tmp_path, b"x", recorded=b"y"), tmp_path)

    assert (check.n_files, check.n_mismatch, check.passed) == (2, 2, False)
    assert check.mismatched == ("a.txt", "gone.txt")


def test_the_freeze_check_passes_when_every_hash_holds(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"x")
    listing = tmp_path / "E9.sha256"
    listing.write_text(f"{hashlib.sha256(b'x').hexdigest()} *a.txt\n", encoding="utf-8")

    assert check_freeze(listing, tmp_path).passed


def test_a_malformed_freeze_line_is_refused(tmp_path: Path) -> None:
    listing = tmp_path / "E9.sha256"
    listing.write_text("not-a-hash a.txt\n", encoding="utf-8")

    with pytest.raises(ValueError, match="sha256"):
        check_freeze(listing, tmp_path)


def test_the_report_records_the_freeze_result_and_the_counts(
    replay: Replay, tmp_path: Path
) -> None:
    result = replay_corpus(replay.setup(replay.truth, [replay.routed, replay.plain]))
    freeze = check_freeze(_write_freeze_list(tmp_path, b"x", recorded=b"y"), tmp_path)
    report = ReplayReport(freeze=freeze, corpora=(result,))

    json_path, markdown_path = write_report(report, tmp_path / "out")

    assert ReplayReport.model_validate_json(json_path.read_text(encoding="utf-8")) == report
    text = render_markdown(report)
    assert "E9 freeze check: FAIL" in text
    assert f"| {CORPUS_ID} | all | 2 | 2 | 0 | 0 | 0 |" in text
    assert markdown_path.read_text(encoding="utf-8") == text


def test_the_output_may_not_go_beside_the_stored_cache(tmp_path: Path) -> None:
    cache = tmp_path / "m6a" / "cache.sqlite"

    with pytest.raises(SystemExit):
        _refuse_output_beside_cache(tmp_path / "m6a" / "report", cache)
    _refuse_output_beside_cache(tmp_path / "demo" / "report", cache)
