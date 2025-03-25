from pydantic import BaseModel


class NotificationResponse(BaseModel):
    unit_id: str
    phones: list[str]
    message: str
    method: str


class NotificationErrorResponse(BaseModel):
    phones: list[str]
    unit_id: str
    message: str
    method: str
    error: str
    error_desc: str


class HeartbeatResponse(BaseModel):
    uptime: str


class HeartbeatErrorResponse(BaseModel):
    error: Exception
    error_desc: str
