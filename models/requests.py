from pydantic import BaseModel


class NotificationRequest(BaseModel):
    to_number: str
    message: str
