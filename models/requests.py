from pydantic import BaseModel


class NotificationRequest(BaseModel):
    unit_id: str
    to_number: str
    message: str
