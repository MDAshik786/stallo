import uuid
from datetime import datetime

import uuid_utils
from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uuid7() -> uuid.UUID:
    return uuid.UUID(str(uuid_utils.uuid7()))


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Seller(Base, TimestampMixin):
    __tablename__ = "sellers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    store_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    category_slug: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    attributes: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        CheckConstraint("price_paise > 0", name="ck_products_price_positive"),
        CheckConstraint("stock_quantity >= 0", name="ck_products_stock_non_negative"),
        CheckConstraint(
            "status in ('draft','published','archived')", name="ck_products_status"
        ),
        Index("ix_products_seller_status", "seller_id", "status"),
    )

class AgentRun(Base, TimestampMixin):
    """One seller utterance and everything that followed from it.

    The run is a persisted state machine, not React state — a suspension
    survives a page refresh, a closed tab, and tomorrow morning.

        running -> awaiting_input    -> running -> completed
                -> awaiting_approval -> running -> completed
                                     -> rejected
                -> failed
    """

    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="running")
    utterance: Mapped[str] = mapped_column(Text, nullable=False)

    # what the agent is waiting for, rendered by the UI as buttons
    suspension: Mapped[dict | None] = mapped_column(JSONB)
    # conversation so far, so a resume continues rather than restarts
    messages: Mapped[list | None] = mapped_column(JSONB)
    reply: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "status in ('running','awaiting_input','awaiting_approval',"
            "'completed','rejected','failed')",
            name="ck_agent_runs_status",
        ),
        Index("ix_agent_runs_seller_created", "seller_id", "created_at"),
    )


class AgentAction(Base):
    """Append-only audit log. The source of truth for what the agent did.

    One log carries agent actions and (later) consent changes, which is what
    makes "every action is inspectable and undoable" a property of the system
    rather than a claim in a README.
    """

    __tablename__ = "agent_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL")
    )

    tool: Mapped[str] = mapped_column(String(64), nullable=False)
    args: Mapped[dict | None] = mapped_column(JSONB)
    result: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="success")

    # undo is a property of the log, not a feature bolted onto the UI
    undoable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    inverse: Mapped[dict | None] = mapped_column(JSONB)
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("status in ('success','failed','refused')", name="ck_agent_actions_status"),
        Index("ix_agent_actions_seller_created", "seller_id", "created_at"),
    )
