"""The demo's HTTP API (FastAPI). Local only: `HOST` is loopback and is not an option."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from plantgraph.demo.app.answering import (
    UnknownBenchmarkQuestion,
    benchmark_question,
    benchmark_view,
)
from plantgraph.demo.app.api_models import (
    AppStatus,
    AskRequest,
    BenchmarkView,
    JobStatus,
    PlantRequest,
    PlantStatus,
    QuestionSummary,
    TagLookup,
)
from plantgraph.demo.app.corpus_runtime import read_drawing_index
from plantgraph.demo.app.live_cascades import NO_API_KEY
from plantgraph.demo.app.results import ResultsView, results_view
from plantgraph.demo.app.state import (
    AppState,
    Busy,
    CorpusNotReady,
    PlantNotLoaded,
    UnknownCorpus,
    UnknownJob,
)
from plantgraph.demo.app.store_loader import PLANT_LOAD_FAILED, StoreChanged, StoreUnreachable
from plantgraph.demo.drawing.models import DrawingIndex

#: The server listens on this address only: the demo is never reachable from another machine.
HOST = "127.0.0.1"
#: How long a browser may reuse the drawing PDF without asking again (one day).
PDF_CACHE_CONTROL = "private, max-age=86400"
STATIC_DIR = Path(__file__).parent / "static"

# Each domain error -> (HTTP status, error code). The page shows the English text of the code
# (`labels.en.json`, `error_codes`); the English `message` is for the folded technical details.
_ERROR_OF: dict[type[Exception], tuple[int, str]] = {
    UnknownCorpus: (404, "unknown_corpus"),
    UnknownJob: (404, "unknown_job"),
    UnknownBenchmarkQuestion: (404, "unknown_question"),
    CorpusNotReady: (409, "corpus_not_ready"),
    Busy: (409, "busy"),
    PlantNotLoaded: (409, "plant_not_loaded"),
    StoreChanged: (409, "store_changed"),
    StoreUnreachable: (409, "store_unreachable"),
}
#: The code of a missing page, PDF or drawing-index file (not an `_ERROR_OF` exception).
MISSING_FILE = "missing_file"
#: The code of `/api/results` when the config names no report files.
RESULTS_NOT_CONFIGURED = "results_not_configured"
#: Every code the API can send (`no_api_key` arrives as a corpus's `error_code`, `plant_load_failed`
#: as the plant status's `error`); the label table must have a text for each.
ERROR_CODES: frozenset[str] = frozenset(code for _, code in _ERROR_OF.values()) | {
    MISSING_FILE,
    RESULTS_NOT_CONFIGURED,
    NO_API_KEY,
    PLANT_LOAD_FAILED,
}


def _http_error(status: int, code: str, message: str) -> HTTPException:
    """An HTTP error whose body is `{"detail": {"code": ..., "message": ...}}`."""
    return HTTPException(status, detail={"code": code, "message": message})


def _call[T](action: Callable[[], T]) -> T:
    """Run `action`, turning the app's domain errors into HTTP errors."""
    try:
        return action()
    except tuple(_ERROR_OF) as error:
        status, code = _ERROR_OF[type(error)]
        raise _http_error(status, code, str(error)) from error


def create_app(state: AppState) -> FastAPI:
    """The API over one `AppState`."""
    app = FastAPI(title="Plant-scale P&ID demo")

    @app.get("/")
    def page() -> FileResponse:
        index = STATIC_DIR / "index.html"
        if not index.exists():
            raise _http_error(
                404, MISSING_FILE, f"expected the page at {index}, found no such file"
            )
        return FileResponse(index)

    @app.get("/api/status")
    def status() -> AppStatus:
        return state.status()

    @app.get("/corpora/{corpus_id}/drawings.pdf")
    def drawings_pdf(corpus_id: str) -> FileResponse:
        path = _call(lambda: state.configured_corpus(corpus_id)).pdf_path
        if not path.exists():
            raise _http_error(404, MISSING_FILE, f"expected the drawing PDF at {path}, found none")
        # "inline" asks the browser to show the PDF in its viewer instead of downloading it;
        # "private, max-age" lets a fresh iframe per jump reuse the cached file (the page's `?v=`
        # stamp makes a new page load fetch it again)
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=f"{corpus_id}-drawings.pdf",
            content_disposition_type="inline",
            headers={"Cache-Control": PDF_CACHE_CONTROL},
        )

    @app.get("/api/corpora/{corpus_id}/index")
    def drawing_index(corpus_id: str) -> DrawingIndex:
        corpus = _call(lambda: state.configured_corpus(corpus_id))
        try:
            return read_drawing_index(corpus)
        except FileNotFoundError as error:
            raise _http_error(404, MISSING_FILE, str(error)) from error

    @app.get("/api/corpora/{corpus_id}/questions")
    def questions(corpus_id: str) -> list[QuestionSummary]:
        return list(_call(lambda: state.question_list(corpus_id)))

    @app.get("/api/corpora/{corpus_id}/questions/{question_id}")
    def question_detail(corpus_id: str, question_id: str) -> BenchmarkView:
        def build() -> BenchmarkView:
            corpus = state.ready_corpus(corpus_id)
            return benchmark_view(corpus, benchmark_question(corpus, question_id))

        return _call(build)

    @app.get("/api/corpora/{corpus_id}/tags")
    def tags(corpus_id: str, q: str = Query(min_length=1, max_length=64)) -> TagLookup:
        return _call(lambda: state.tag_lookup(corpus_id, q))

    @app.get("/api/results")
    def results() -> ResultsView:
        sources = state.config.results
        if sources is None:
            raise _http_error(
                404, RESULTS_NOT_CONFIGURED, "expected a `results` entry in the demo config"
            )
        try:
            return results_view(sources)
        except FileNotFoundError as error:
            raise _http_error(404, MISSING_FILE, str(error)) from error

    @app.get("/api/plant")
    def plant() -> PlantStatus:
        return state.plant_status()

    @app.post("/api/plant", status_code=202)
    def switch_plant(request: PlantRequest, response: Response) -> PlantStatus:
        status = _call(lambda: state.start_plant_switch(request.corpus_id))
        if status.loading is None:  # the plant was already in the database: nothing was started
            response.status_code = 200
        return status

    @app.post("/api/ask")
    def ask(request: AskRequest) -> dict[str, str]:
        return {"job_id": _call(lambda: state.start_ask(request))}

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str) -> JobStatus:
        return _call(lambda: state.job_status(job_id))

    # the page's own files (app.js, app.css); mounted last so the API routes above win
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
