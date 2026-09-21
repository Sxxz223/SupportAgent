"""Public HTTP request and response schemas."""
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class SessionResponse(BaseModel):
    session_id: str


class SessionRestoreResponse(BaseModel):
    session_id: str
    stage: str
    messages: list[dict[str, Any]] = Field(default_factory=list)
    taskUpdates: list[dict[str, Any]] = Field(default_factory=list)
    focusTaskId: str | None = None
    focusPath: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    interaction: dict[str, Any] | None = None
    emotionState: dict[str, str] | None = None
    agentState: dict[str, str] | None = None
    turnId: str | None = None
    caseVersion: int = 0


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ActivityRequest(BaseModel):
    activity: Literal["typing", "idle", "choice", "image_selected", "focus", "leave"]
    detail: str | None = Field(default=None, max_length=120)


class ChatResponse(BaseModel):
    reply: str
    stage: str
    turnId: str | None = None
    caseVersion: int | None = None
    factsUpdate: dict[str, Any] | None = None
    interaction: dict[str, Any] | None = None
    taskDecision: dict[str, Any] | None = None
    taskUpdates: list[dict[str, Any]] | None = None
    taskChange: dict[str, Any] | None = None
    focusTaskId: str | None = None
    focusChanged: bool | None = None
    focusChangeReason: str | None = None
    focusPath: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    agentState: dict[str, str] | None = None
    emotionState: dict[str, str] | None = None
    visionResult: dict[str, Any] | None = None


class CustomerCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    phone_last4: str = Field(pattern=r"^\d{4}$")


class CustomerUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    phone_last4: str | None = Field(default=None, pattern=r"^\d{4}$")


class CustomerResponse(BaseModel):
    customer_id: str
    name: str
    phone_last4: str
    created_at: str
    updated_at: str


class ProductResponse(BaseModel):
    product_id: str
    display_name: str
    model: str
    category: str
    rag_namespace: str
    aliases: list[str]


class OrderCreateRequest(BaseModel):
    order_no: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    purchase_date: date
    warranty_until: date | None = None
    status: Literal["active", "returned", "replaced"] = "active"


class OrderUpdateRequest(BaseModel):
    product_id: str | None = Field(default=None, min_length=1)
    purchase_date: date | None = None
    warranty_until: date | None = None
    status: Literal["active", "returned", "replaced"] | None = None


class OrderResponse(BaseModel):
    order_no: str
    customer_id: str
    product_id: str
    purchase_date: str
    warranty_until: str | None
    status: str
    created_at: str
    updated_at: str
    product: ProductResponse


class CustomerDetailResponse(CustomerResponse):
    orders: list[OrderResponse]
