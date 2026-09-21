from dataclasses import dataclass, field
from typing import Any, Literal
from pydantic import BaseModel, Field


class ExtractedFact(BaseModel):
    value: Any
    kind: Literal["observation", "context", "action", "result", "goal", "judgement"]

class StateUpdate(BaseModel):
    """
    表示“这一轮用户输入新提供了什么信息”
    """
    user_name: str | None = None
    phone_last4: str | None = None
    order_no: str | None = None
    product: str | None = None
    issue: str | None = None
    facts: dict[str, ExtractedFact] = Field(default_factory=dict)

@dataclass
class SupportState:
    """
    表示“当前整个客服任务已经确认的业务状态”
    """
    user_name: str | None = None
    customer_id: str | None = None
    identity_verified: bool = False
    phone_last4: str | None = None
    order_no: str | None = None
    product: str | None = None
    product_id: str | None = None
    owned_products: list[dict] = field(default_factory=list)
    ownership_lookup_completed: bool = False
    issue: str | None = None

    stage: str = "identify_user"

    attempted_steps: list[str] = field(default_factory=list)

    resolved: bool = False
    diagnostic_facts: dict = field(default_factory=dict)

    warranty_status: str | None = None
    ticket_id: str | None = None

    # Multimodal state
    image_received: bool = False
    dock_visible: bool | None = None
    indicator_on: bool | None = None
    contacts_dirty: bool | None = None
    robot_on_dock: bool | None = None
