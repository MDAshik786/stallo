from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.routes import agent, orders, products
from app.config import settings

_is_local = settings.stallo_env == "local"

app = FastAPI(
    title="Stallo API",
    docs_url="/docs" if _is_local else None,
    redoc_url="/redoc" if _is_local else None,
    openapi_url="/openapi.json" if _is_local else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(agent.router)
app.include_router(orders.router)


@app.exception_handler(IntegrityError)
def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """A database constraint rejected the write. That is a bad request, not a
    server fault — surface it as 400 rather than leaking a 500."""
    return JSONResponse(status_code=400, content={"detail": "constraint violation"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.stallo_env}
