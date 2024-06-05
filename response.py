from pydantic import BaseModel


class NotificationResponse(BaseModel):
    to_number: str
    message: str
    method: str
    success: bool

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "to_number": "+17133049421",
                    "message": "Hello! Your vehicle John's Ride had its ignition switched on near Gary, Indiana.",
                    "method": "call",
                    "success": True,
                },
                {
                    "to_number": "+18322835634",
                    "message": "Hello! Your vehicle Peter's Ride was detected entering forbidden geofence Kansas. This incident occured after hours.",
                    "method": "sms",
                    "success": True,
                },
                {
                    "to_number": "+18324667085",
                    "message": "Hello! Your vehicle Todd's Ride was detected possibly in-tow.",
                    "method": "call",
                    "success": False,  # Call wasn't made but it was logged.
                },
            ],
        }
