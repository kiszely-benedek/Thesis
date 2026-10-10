"""The demo's HTTP API (FastAPI). Local only: `HOST` is loopback and is not an option."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException
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
    QuestionSummary,
)
from plantgraph.demo.app.corpus_runtime import read_drawing_index
from plantgraph.demo.app.state import (
    AppState,
    Busy,
    CorpusNotReady,
    UnknownCorpus,
    UnknownJob,
)
from plantgraph.demo.drawing.models import DrawingIndex

#: The server listens on this address only: the demo is never reachable from another machine.
HOST = "127.0.0.1"
STATIC_DIR = Path(__file__).parent / "static"

# which HTTP status each domain error means
_STATUS_OF: dict[type[Exception], int] = {
    UnknownCorpus: 404,
    UnknownJob: 404,
    UnknownBenchmarkQuestion: 404,
    CorpusNotReady: 409,
    Busy: 409,
}


def _call[T](action: Callable[[], T]) -> T:
    """Run `action`, turning the app's domain errors into HTTP errors."""
    try:
        return action()
    except tuple(_STATUS_OF) as error:
        raise HTTPException(_STATUS_OF[type(error)], detail=str(error)) from error


def create_app(state: AppState) -> FastAPI:
    """The API over one `AppState`."""
    app = FastAPI(title="Plant-scale P&ID demo")

    @app.get("/")
    def page() -> FileResponse:
        index = STATIC_DIR / "index.html"
        if not index.exists():
            raise HTTPException(404, detail=f"expected the page at {index}, found no such file")
        return FileResponse(index)

    @app.get("/api/status")
    def status() -> AppStatus:
        return state.status()

    @app.get("/corpora/{corpus_id}/drawings.pdf")
    def drawings_pdf(corpus_id: str) -> FileResponse:
        path = _call(lambda: state.configured_corpus(corpus_id)).pdf_path
        if not path.exists():
            raise HTTPException(404, detail=f"expected the drawing PDF at {path}, found none")
        # "inline" asks the browser to show the PDF in its viewer instead of downloading it
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=f"{corpus_id}-drawings.pdf",
            content_disposition_type="inline",
        )

    @app.get("/api/corpora/{corpus_id}/index")
    def drawing_index(corpus_id: str) -> DrawingIndex:
        corpus = _call(lambda: state.configured_corpus(corpus_id))
        try:
            return read_drawing_index(corpus)
        except FileNotFoundError as error:
            raise HTTPException(404, detail=str(error)) from error

    @app.get("/api/corpora/{corpus_id}/questions")
    def questions(corpus_id: str) -> list[QuestionSummary]:
        return list(_call(lambda: state.question_list(corpus_id)))

    @app.get("/api/corpora/{corpus_id}/questions/{question_id}")
    def question_detail(corpus_id: str, question_id: str) -> BenchmarkView:
        def build() -> BenchmarkView:
            corpus = state.ready_corpus(corpus_id)
            return benchmark_view(corpus, benchmark_question(corpus, question_id))

        return _call(build)

    @app.post("/api/ask")
    def ask(request: AskRequest) -> dict[str, str]:
        return {"job_id": _call(lambda: state.start_ask(request))}

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str) -> JobStatus:
        return _call(lambda: state.job_status(job_id))

    # the page's own files (app.js, app.css); mounted last so the API routes above win
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
