from pydantic import BaseModel

class VisionUpdate(BaseModel):
    dock_visible: bool | None = None
    indicator_on: bool | None = None
    contacts_dirty: bool | None = None
    robot_on_dock: bool | None = None
    observation: str | None = None
