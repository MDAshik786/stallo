from fastapi import FastAPI

from app.config import settings

app = FastAPI(title="Stallo API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.stallo_env}