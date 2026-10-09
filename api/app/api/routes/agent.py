import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent import runner
from app.api.deps import get_seller_id
from app.db import get_db
from app.models import AgentAction, AgentRun

router = APIRouter(prefix="/agent", tags=["agent"])


class StartRun(BaseModel):
    utterance: str = Field(min_length=1, max_length=2000)


class ResumeRun(BaseModel):
    answer: str | None = None
    approved: bool | None = None


class RunOut(BaseModel):
    id: uuid.UUID
    status: str
    utterance: str
    suspension: dict | None
    reply: str | None
    error: str | None
    results: list[dict] | None
    messages: list[dict] | None

    @classmethod
    def of(cls, run: AgentRun) -> "RunOut":
        return cls(id=run.id, status=run.status, utterance=run.utterance,
                   suspension=run.suspension, reply=run.reply, error=run.error,
                   results=run.results, messages=run.messages)


def _load(db: Session, seller_id: uuid.UUID, run_id: uuid.UUID) -> AgentRun:
    run = db.scalars(
        select(AgentRun).where(AgentRun.id == run_id, AgentRun.seller_id == seller_id)
    ).one_or_none()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    return run


@router.post("/runs", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def start_run(body: StartRun, db: Session = Depends(get_db),
              seller_id: uuid.UUID = Depends(get_seller_id)) -> RunOut:
    return RunOut.of(runner.start(db, seller_id, body.utterance.strip()))


@router.post("/runs/{run_id}/resume", response_model=RunOut)
def resume_run(run_id: uuid.UUID, body: ResumeRun, db: Session = Depends(get_db),
               seller_id: uuid.UUID = Depends(get_seller_id)) -> RunOut:
    run = _load(db, seller_id, run_id)
    if run.status not in ("awaiting_input", "awaiting_approval"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"run is {run.status}, not waiting")
    return RunOut.of(runner.resume(db, seller_id, run, body.answer, body.approved))


@router.get("/runs", response_model=list[RunOut])
def list_runs(limit: int = Query(default=20, ge=1, le=100),
              db: Session = Depends(get_db),
              seller_id: uuid.UUID = Depends(get_seller_id)) -> list[RunOut]:
    """Recent runs, oldest first — the conversation, rebuilt from the server.

    The client holds no transcript of its own. Navigating away and back, or
    reloading, replays this; a run still awaiting an answer comes back with
    its suspension intact and is resumable.
    """
    rows = list(db.scalars(
        select(AgentRun).where(AgentRun.seller_id == seller_id)
        .order_by(AgentRun.created_at.desc()).limit(limit)
    ))
    return [RunOut.of(r) for r in reversed(rows)]


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db),
            seller_id: uuid.UUID = Depends(get_seller_id)) -> RunOut:
    return RunOut.of(_load(db, seller_id, run_id))


class ActionOut(BaseModel):
    id: uuid.UUID
    tool: str
    status: str
    args: dict | None
    result: dict | None
    undoable: bool
    undone: bool
    duration_ms: int | None
    created_at: str


@router.get("/actions", response_model=list[ActionOut])
def list_actions(limit: int = Query(default=25, ge=1, le=100),
                 db: Session = Depends(get_db),
                 seller_id: uuid.UUID = Depends(get_seller_id)) -> list[ActionOut]:
    """The audit log. Everything the agent did, newest first."""
    rows = db.scalars(
        select(AgentAction).where(AgentAction.seller_id == seller_id)
        .order_by(AgentAction.created_at.desc()).limit(limit)
    )
    return [
        ActionOut(
            id=a.id, tool=a.tool, status=a.status, args=a.args, result=a.result,
            undoable=bool(a.undoable and a.undone_at is None),
            undone=a.undone_at is not None, duration_ms=a.duration_ms,
            created_at=a.created_at.isoformat(),
        )
        for a in rows
    ]
