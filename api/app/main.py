from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.routes import products
from app.config import settings

app = FastAPI(title="Stallo API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)


@app.exception_handler(IntegrityError)
def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """A database constraint rejected the write. That is a bad request, not a
    server fault — surface it as 400 rather than leaking a 500."""
    return JSONResponse(status_code=400, content={"detail": "constraint violation"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.stallo_env}
