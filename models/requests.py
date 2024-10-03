from fastapi import Form
from typing import Annotated, Optional
from pydantic import BaseModel


class NotificationRequest(BaseModel):
    unit_id: Annotated[Optional[int], Form()] = Form(...)
    to_number: Annotated[Optional[str], Form()] = Form(...)
    message: Annotated[str, Form()]
