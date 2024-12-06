from wialon.api import Wialon, WialonError

from settings import WIALON_TOKEN


class WialonSession:
    def __init__(self, token: str | None = None, sid: str | None = None) -> None:
        self.token = token
        self.wialon_api = Wialon(
            scheme="https", host="hst-api.wialon.com", port=443, sid=sid
        )

    @property
    def id(self) -> str | None:
        return self.wialon_api.sid

    @property
    def token(self) -> str | None:
        return self._token

    @token.setter
    def token(self, value: str | None) -> None:
        self._token = value if value else WIALON_TOKEN

    def __enter__(self) -> "WialonSession":
        try:
            self.login(self.token)
        except WialonError:
            print("Failed to login to the Wialon API")
        return self

    def __exit__(self, exc_type, exc_value, exc_tb) -> None:
        self.logout()
        return

    def _deconstruct_login_response(self, login_response: dict) -> None:
        self.wialon_api.sid = login_response.get("eid", "")
        self.username = login_response.get("user", {}).get("nm")
        self.uid = login_response.get("user", {}).get("id")
        self.base_url = login_response.get("base_url", "")
        self.gis_sid = login_response.get("gis_sid", "")
        self.host = login_response.get("host", "")
        self.hw_gp_ip = login_response.get("hw_gw_ip", "")
        self.video_service_url = login_response.get("video_service_url", "")
        self.wsdk_version = login_response.get("wsdk_version", "")
        return

    def login(self, token: str | None = None) -> None:
        """Logs into the Wialon API and starts a new session."""
        if not token:
            raise ValueError("No Wialon API token provided.")
        try:
            login_response = self.wialon_api.token_login(
                **{"token": token, "fl": sum([0x1, 0x2, 0x20])}
            )
        except WialonError as e:
            raise e
        else:
            self._deconstruct_login_response(login_response)
            print(f"Logged into session #{self.id}'")

    def logout(self) -> None:
        """Logs out of the Wialon API and raises an error if the session was not destroyed."""
        sid: str = str(self.id)
        logout_response = self.wialon_api.core_logout({})
        if logout_response.get("error") != 0:
            print(f"Failed to properly destroy session #{sid}")
