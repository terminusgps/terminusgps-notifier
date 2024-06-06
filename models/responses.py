from pydantic import BaseModel


class NotificationResponse(BaseModel):
    to_number: list[str] | str
    message: str
    method: str
    success: bool
