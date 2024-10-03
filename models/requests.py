from pydantic import BaseModel


class NotificationRequest(BaseModel):
    unit_id: int | None = None
    to_number: str | None = None
    message: str
