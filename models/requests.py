from pydantic import BaseModel


class NotificationRequest(BaseModel):
    unit_id: str
    message: str
