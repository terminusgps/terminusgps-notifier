from typing import Any
from urllib.parse import quote_plus
from wialon import WialonError

import wialonapi.flags as flag
from wialonapi.items.base import WialonBase
from wialonapi.utils import clean_phone_numbers


class WialonUnit(WialonBase):
    def create(self, **kwargs) -> None:
        if kwargs.get("creator_id") is None:
            raise ValueError("Tried to create unit but creator id was none.")
        if kwargs.get("name") is None:
            raise ValueError("Tried to create unit but name was none.")
        if kwargs.get("hw_type") is None:
            raise ValueError("Tried to create unit but hw_type was none.")

        response = self.session.wialon_api.core_create_unit(
            **{
                "creatorId": kwargs["creator_id"],
                "name": kwargs["name"],
                "hwTypeId": kwargs["hw_type"],
                "dataFlags": flag.DATAFLAG_UNIT_BASE,
            }
        )
        self._id = response.get("item", {}).get("id")

    def populate(self) -> None:
        super().populate()
        search_result = self.session.wialon_api.core_search_item(
            **{"id": self.id, "flags": flag.DATAFLAG_UNIT_ADVANCED_PROPERTIES}
        )
        self.unique_id = search_result.get("uid", "")
        self.phone = search_result.get("ph", "")
        self.is_active = bool(search_result.get("act", 0))

    def set_access_password(self, access_password: str) -> None:
        self.session.wialon_api.unit_update_access_password(
            **{"itemId": self.id, "accessPassword": access_password}
        )

    def activate(self) -> None:
        self.session.wialon_api.unit_set_active(
            **{"itemId": self.id, "active": int(True)}
        )

    def deactivate(self) -> None:
        self.session.wialon_api.unit_set_active(
            **{"itemId": self.id, "active": int(False)}
        )

    def assign_phone(self, phone: str) -> None:
        self.session.wialon_api.unit_update_phone(
            **{"itemId": self.id, "phoneNumber": quote_plus(phone)}
        )

    def _get_fields(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        try:
            item = self.session.wialon_api.core_search_item(
                **{
                    "id": self.id,
                    "flags": sum(
                        [
                            flag.DATAFLAG_UNIT_CUSTOM_FIELDS,
                            flag.DATAFLAG_UNIT_ADMIN_FIELDS,
                        ]
                    ),
                }
            ).get("item")
        except WialonError as e:
            raise e
        else:
            return item.get("aflds").values(), item.get("flds").values()

    def get_phone_numbers(self) -> list[str]:
        try:
            admin_fields, custom_fields = self._get_fields()
        except WialonError as e:
            raise e
        else:
            phone_numbers = []
            for field in admin_fields:
                if field.get("n") == "to_number":
                    phone_numbers.append(field.get("v"))
            for field in custom_fields:
                if field.get("n") == "to_number":
                    phone_numbers.append(field.get("v"))
            return clean_phone_numbers(phone_numbers)
