from wialon import WialonError

import wialonapi.flags as flag
from wialonapi.items.base import WialonBase


class WialonResource(WialonBase):
    def create(self, **kwargs) -> None:
        if kwargs.get("creator_id") is None:
            raise ValueError("Tried to create a resource but creator_id was none.")
        if kwargs.get("name") is None:
            raise ValueError("Tried to create a resource but name was none.")

        try:
            response = self.session.wialon_api.core_create_resource(
                **{
                    "creatorId": kwargs["creator_id"],
                    "name": kwargs["name"],
                    "dataFlags": flag.DATAFLAG_RESOURCE_BASE,
                }
            )
        except WialonError as e:
            raise e
        else:
            self._id = response.get("item", {}).get("id")
