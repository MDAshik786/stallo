"""
Stallo agent tool vocabulary.

Three rules encoded here, in order of importance:

  1. No tool takes a seller_id. Tenant scope is injected server-side from the
     authenticated session AFTER validation. The model chooses which query and
     what filters; it never chooses whose data.

  2. Tools that change live state (publish, delete) are RESUME_ONLY — they are
     not in the schema sent to the model and can only execute on the resume
     path with a valid approval token. Approval is structural, not textual.

  3. There is no bulk-destructive tool. Anything a seller can only sensibly do
     once (wipe the catalogue) lives in the UI behind a typed store name.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Exposure(str, Enum):
    READ = "read"
    WRITE = "write"
    CONTROL = "control"
    RESUME_ONLY = "resume_only"


class CategorySlug(str, Enum):
    FLOWERS = "flowers"
    VALENTINES = "valentines"
    GIFTS = "gifts"
    CHOCOLATES = "chocolates"
    PLANTS = "plants"
    HOME_DECOR = "home-decor"
    FESTIVE = "festive"


class Money(BaseModel):
    """The model transcribes the amount as written. The backend converts to paise."""

    amount: Decimal = Field(description="Amount exactly as the seller stated it, e.g. 899 or 1299.50")
    currency: Literal["INR"] = "INR"


class VariantSpec(BaseModel):
    attributes: dict[str, str] = Field(description='e.g. {"color": "red"} or {"size": "small"}')
    price: Money | None = None
    stock_quantity: int | None = Field(None, ge=0)


# ── Product ──────────────────────────────────────────────────────────────

class CreateProduct(BaseModel):
    """Create a product as a DRAFT. Drafts are not visible to shoppers, so this
    needs no approval. Only publishing does."""

    name: str = Field(max_length=120)
    price: Money
    category_slug: CategorySlug | None = None
    description: str | None = Field(None, max_length=2000)
    stock_quantity: int | None = Field(None, ge=0)
    attributes: dict[str, Any] | None = None


class UpdateProduct(BaseModel):
    """Update a draft product. Updating a PUBLISHED product routes through
    request_confirmation instead — it changes what shoppers see."""

    product_id: str
    name: str | None = Field(None, max_length=120)
    price: Money | None = None
    category_slug: CategorySlug | None = None
    description: str | None = Field(None, max_length=2000)
    stock_quantity: int | None = Field(None, ge=0)
    attributes: dict[str, Any] | None = None


class GetProduct(BaseModel):
    product_id: str


class ListProducts(BaseModel):
    status: Literal["draft", "published", "archived"] | None = None
    category_slug: CategorySlug | None = None
    limit: int = Field(20, ge=1, le=100)


class PreviewProduct(BaseModel):
    product_id: str


# ── Variants ─────────────────────────────────────────────────────────────

class AddVariant(BaseModel):
    """The 20-variant cap is a database constraint, not prompt knowledge.
    Call this and let the backend reject if it would be exceeded."""

    product_id: str
    variants: list[VariantSpec] = Field(min_length=1)


class UpdateVariant(BaseModel):
    """One tool, optional fields — not update_variant_price / _stock / _color."""

    variant_id: str
    price: Money | None = None
    stock_quantity: int | None = Field(None, ge=0)
    attributes: dict[str, str] | None = None
    image_id: str | None = None


# ── Images ───────────────────────────────────────────────────────────────

class GenerateProductImage(BaseModel):
    product_id: str
    style_hint: str | None = None


class GenerateVariantImage(BaseModel):
    variant_id: str
    style_hint: str | None = None


# ── Analytics ────────────────────────────────────────────────────────────

class QueryRevenue(BaseModel):
    """No limit, sort, or free-text parameter. The query builder owns those."""

    start_date: str = Field(description="ISO date, YYYY-MM-DD")
    end_date: str = Field(description="ISO date, YYYY-MM-DD")
    category_slug: CategorySlug | None = None
    group_by: Literal["day", "week", "month", "category"] = "day"
    comparison: Literal["none", "previous_period", "previous_year"] = "none"


class QueryProductSales(BaseModel):
    start_date: str
    end_date: str
    category_slug: CategorySlug | None = None
    sort: Literal["quantity_desc", "quantity_asc", "revenue_desc", "revenue_asc"] = "quantity_desc"
    limit: int = Field(10, ge=1, le=50)


class QueryOrders(BaseModel):
    status: Literal["pending", "paid", "shipped", "delivered", "cancelled"] | None = None
    limit: int = Field(10, ge=1, le=50)


class GetAgentActionHistory(BaseModel):
    limit: int = Field(10, ge=1, le=50)


# ── Agent control ────────────────────────────────────────────────────────

class Option(BaseModel):
    value: str
    label: str


class RequestChoice(BaseModel):
    """Suspends the run: state becomes awaiting_input. Use for a missing required
    field OR a pick-one. Covers images too — there is no request_image_choice."""

    field: str = Field(description="Schema field name being resolved, e.g. name, price, image, variant_id, date_range")
    prompt: str
    options: list[Option] | None = None
    product_id: str | None = None
    variant_id: str | None = None


class RequestConfirmation(BaseModel):
    """Suspends the run: state becomes awaiting_approval. The seller's button
    click — never their typed text — releases the pending write."""

    action: Literal["publish_product", "unpublish_product", "delete_product", "delete_variant", "update_published_product"]
    target_id: str
    summary: str = Field(description="Plain-language description of what will happen")


class UndoAction(BaseModel):
    """No arguments. The server resolves the last undoable action for this
    seller from the audit log — the model must not pick an id."""


class Refuse(BaseModel):
    reason: Literal[
        "out_of_scope",
        "unsupported_capability",
        "bulk_destructive_unsupported",
        "invalid_value",
        "not_undoable",
    ]
    message: str


# ── Resume-only (never sent to the model) ────────────────────────────────

class PublishProduct(BaseModel):
    product_id: str


class DeleteProduct(BaseModel):
    product_id: str


class DeleteVariant(BaseModel):
    variant_id: str


REGISTRY: dict[str, tuple[type[BaseModel], Exposure]] = {
    "list_products":            (ListProducts,          Exposure.READ),
    "get_product":              (GetProduct,            Exposure.READ),
    "preview_product":          (PreviewProduct,        Exposure.READ),
    "query_revenue":            (QueryRevenue,          Exposure.READ),
    "query_product_sales":      (QueryProductSales,     Exposure.READ),
    "query_orders":             (QueryOrders,           Exposure.READ),
    "get_agent_action_history": (GetAgentActionHistory, Exposure.READ),

    "create_product":           (CreateProduct,         Exposure.WRITE),
    "update_product":           (UpdateProduct,         Exposure.WRITE),
    "add_variant":              (AddVariant,            Exposure.WRITE),
    "update_variant":           (UpdateVariant,         Exposure.WRITE),
    "generate_product_image":   (GenerateProductImage,  Exposure.WRITE),
    "generate_variant_image":   (GenerateVariantImage,  Exposure.WRITE),
    "undo_action":              (UndoAction,            Exposure.WRITE),

    "request_choice":           (RequestChoice,         Exposure.CONTROL),
    "request_confirmation":     (RequestConfirmation,   Exposure.CONTROL),
    "refuse":                   (Refuse,                Exposure.CONTROL),

    "publish_product":          (PublishProduct,        Exposure.RESUME_ONLY),
    "delete_product":           (DeleteProduct,         Exposure.RESUME_ONLY),
    "delete_variant":           (DeleteVariant,         Exposure.RESUME_ONLY),
}

_DESCRIPTIONS = {
    "list_products": "List this seller's products, optionally filtered by status or category.",
    "get_product": "Fetch one product including its description and variants.",
    "preview_product": "Render how a draft product will look in the storefront.",
    "query_revenue": "Revenue over a date range, optionally by category, optionally compared to a prior period.",
    "query_product_sales": "Per-product sales over a date range, sorted by quantity or revenue.",
    "query_orders": "Recent orders for this store, newest first, optionally filtered by status.",
    "get_agent_action_history": "Recent actions taken by the agent on this store, newest first.",
    "create_product": "Create a new product as a draft. Drafts are not visible to shoppers.",
    "update_product": "Update fields on an existing draft product.",
    "add_variant": "Add one or more variants (colour, size, ...) to a product.",
    "update_variant": "Update price, stock, attributes, or image of a single variant.",
    "generate_product_image": "Generate a product image with AI and attach it to the product.",
    "generate_variant_image": "Generate an image for one specific variant.",
    "undo_action": "Undo the seller's most recent undoable agent action. Takes no arguments.",
    "request_choice": (
        "Ask the seller for a missing value or to pick between options, then wait. "
        "Use whenever a required field is absent or a reference like 'it' or 'the red one' "
        "is ambiguous. Never guess."
    ),
    "request_confirmation": (
        "Ask the seller to approve an action that changes what shoppers see, then wait. "
        "Required before publishing, unpublishing, deleting, or editing a published product."
    ),
    "refuse": "Decline a request that is out of scope, unsupported, invalid, or not undoable.",
    "publish_product": "INTERNAL. Executes only on the approval-resume path.",
    "delete_product": "INTERNAL. Executes only on the approval-resume path.",
    "delete_variant": "INTERNAL. Executes only on the approval-resume path.",
}

MODEL_VISIBLE = {Exposure.READ, Exposure.WRITE, Exposure.CONTROL}


def to_anthropic_tools(strict: bool = False) -> list[dict[str, Any]]:
    """Tool definitions for the Messages API — RESUME_ONLY tools are excluded.

    strict=False by default: Pydantic already validates every tool input
    server-side, and strict mode constrains the JSON Schema shapes that
    nested models can emit.
    """
    tools: list[dict[str, Any]] = []
    for name, (model, exposure) in REGISTRY.items():
        if exposure not in MODEL_VISIBLE:
            continue
        schema = model.model_json_schema()
        schema.pop("title", None)
        schema.setdefault("type", "object")
        if strict:
            schema["additionalProperties"] = False
            schema.setdefault("required", [])
        tools.append({
            "name": name,
            "description": _DESCRIPTIONS[name],
            "input_schema": schema,
            **({"strict": True} if strict else {}),
        })
    return tools


def validate_tool_input(name: str, raw: dict[str, Any]) -> BaseModel:
    """Parse a tool_use.input into its typed model. Raises for RESUME_ONLY names."""
    if name not in REGISTRY:
        raise ValueError(f"unknown tool: {name}")
    model, exposure = REGISTRY[name]
    if exposure is Exposure.RESUME_ONLY:
        raise PermissionError(f"{name} is not model-callable; it runs only on the approval-resume path")
    return model.model_validate(raw)
