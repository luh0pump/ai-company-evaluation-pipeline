"""Small, stateless web surface. Live operations are deliberately CLI-only in V1."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import Settings
from .portfolio import ASSETS, DemoResult, prompt_preview, run_demo


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    application = FastAPI(debug=False, docs_url=None, redoc_url=None, openapi_url=None)
    templates = Jinja2Templates(directory=str(ASSETS / "templates"))
    application.mount("/static", StaticFiles(directory=str(ASSETS / "static")), name="static")

    @application.middleware("http")
    async def boundary(request: Request, call_next):
        # V1 accepts no user input, including in local mode. Do not buffer uploads.
        try:
            response = None
            if request.method in {"POST", "PUT", "PATCH"}:
                async for chunk in request.stream():
                    if chunk:
                        response = JSONResponse(
                            {"detail": "This demo accepts no request body; use the bundled dataset."},
                            status_code=413 if len(chunk) > 1024 else 400,
                        )
                        break
            if response is None:
                response = await call_next(request)
        except Exception:
            # Never expose or log exception messages, credentials or browser tracebacks.
            response = JSONResponse({"detail": "The demo could not complete. Please try again."}, status_code=500)
        response.headers.update({
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Cache-Control": "no-store",
        })
        return response

    @application.get("/health")
    def health():
        return {"status": "ok", "mode": settings.mode}

    @application.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return templates.TemplateResponse(request=request, name="index.html", context={
            "mode": settings.mode, "prompt": prompt_preview(),
        })

    @application.post("/api/demo/run", response_model=DemoResult)
    def demo(request: Request):
        if request.query_params:
            return JSONResponse({"detail": "Demo configuration is fixed; query parameters are not accepted."}, status_code=400)
        return run_demo()

    return application


app = create_app()
