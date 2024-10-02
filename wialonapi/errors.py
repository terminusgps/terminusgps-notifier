from typing import Optional

from wialon.api import WialonError


class WialonBaseError(Exception):
    def __init__(
        self, message: str, wialon_error: Optional[WialonError] = None
    ) -> None:
        self.wialon_error = wialon_error
        super().__init__(message)


class WialonLoginError(WialonBaseError):
    def __init__(self, token: str, wialon_error: Optional[WialonError] = None) -> None:
        message = f"Failed to login to the Wialon API with token '{token}'."
        if wialon_error is not None:
            message += str(wialon_error)
        super().__init__(message=message, wialon_error=wialon_error)


class WialonLogoutError(WialonBaseError):
    def __init__(
        self, session_id: str, wialon_error: Optional[WialonError] = None
    ) -> None:
        message = f"Failed to logout of Wialon API session '#{session_id}'."
        if wialon_error is not None:
            message += str(wialon_error)
        super().__init__(message=message, wialon_error=wialon_error)


class WialonTokenNotFoundError(WialonBaseError):
    def __init__(
        self, token: Optional[str] = None, wialon_error: Optional[WialonError] = None
    ) -> None:
        message = f"Failed to retrieve Wialon API token, got: '{token}'."
        if wialon_error is not None:
            message += str(wialon_error)
        super().__init__(message=message, wialon_error=wialon_error)
