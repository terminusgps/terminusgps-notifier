from urllib.parse import quote_plus

from wialonapi.items.base import WialonBase


class WialonDriver(WialonBase):
    def create(self, **kwargs) -> None:
        if kwargs.get("resource") is None:
            raise ValueError("Tried to create driver but resource was none.")
        if kwargs.get("name") is None:
            raise ValueError("Tried to create driver but name was none.")
        if kwargs.get("phone_number") is None:
            raise ValueError("Tried to create driver but phone_number was none.")
        if kwargs.get("mobile_password") is None:
            raise ValueError("Tried to create driver but mobile_password was none.")

        self.phone_number = kwargs["phone_number"]
        self.name = kwargs["name"]
        self.mobile_password = kwargs["mobile_password"]
        self.resource = kwargs["resource"]

        response = self.session.wialon_api.resource_update_driver(
            **{
                "itemId": self.resource.id,
                "id": 0,
                "callMode": "create",
                "n": self.name,
                "p": quote_plus(self.phone_number),
                "pwd": self.mobile_password,
                "f": 4,
            }
        )
        self._id = response.get("item", {}).get("id")
