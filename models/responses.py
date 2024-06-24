from pydantic import BaseModel


class NotificationResponse(BaseModel):
    to_number: list[str] | str
    message: str
    method: str


class NotificationErrorResponse(BaseModel):
    to_number: list[str] | str
    message: str
    method: str
    error: str
    error_desc: str
