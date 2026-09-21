from typing import Any, Literal
from pydantic import BaseModel, Field


class VisionFieldUpdate(BaseModel):
    key: str
    label: str
    value: Any = None
    status: Literal["recognized", "unclear", "failed"]
    source: str = "image"

class VisionUpdate(BaseModel):
    fields: list[VisionFieldUpdate] = Field(default_factory=list)
    reshoot_target: str | None = None
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    dock_visible: bool | None = None
    indicator_on: bool | None = None
    contacts_dirty: bool | None = None
    robot_on_dock: bool | None = None
    observation: str | None = None
