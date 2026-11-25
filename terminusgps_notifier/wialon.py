import logging
import os
import typing
import urllib.parse
from collections.abc import Sequence

import wialon
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from terminusgps.wialon import flags

logger = logging.getLogger(__name__)

UNKNOWN = 6


class WialonAPIError(Exception):
    """Raised when a Wialon API call fails."""

    def __init__(self, message, *args, **kwargs) -> None:
        self.message = message
        self._code = int(getattr(message, "_code", UNKNOWN))
        super().__init__(message, *args, **kwargs)

    @property
    def code(self) -> int:
        return self._code


class Wialon(wialon.api.Wialon):
    def call(self, action_name, *argc, **kwargs) -> dict[str, typing.Any]:
        try:
            result = super().call(action_name, *argc, **kwargs)
        except wialon.api.WialonError as e:
            raise WialonAPIError(e)
        return result


class WialonSession:
    def __init__(
        self,
        scheme: str = "https",
        host: str = "hst-api.wialon.com",
        port: int = 443,
        sid: str | None = None,
        token: str | None = None,
    ) -> None:
        self._uid = None
        self._wialon_api = Wialon(scheme=scheme, host=host, port=port, sid=sid)
        self._token = token if token else os.getenv("WIALON_TOKEN")
        self._username = None
        self._gis_sid = None

    def __str__(self) -> str:
        return f"Session #{self.id}"

    def __repr__(self) -> str:
        return f"{self.__class__}(sid={self.id})"

    def __enter__(self) -> "WialonSession":
        if not self.id:
            if not self._token:
                raise WialonAPIError("No token provided")
            self.token_login(token=self._token)
        return self

    def __exit__(self, *args, **kwargs) -> None:
        if not self.id:
            self.logout()

    def token_login(self, token: str) -> None:
        response = self.wialon_api.token_login(
            **{"token": token, "flags": 0x1}
        )
        self.wialon_api.sid = response.get("eid")
        self._username = response.get("au")
        self._uid = response.get("user", {}).get("id")
        self._gis_sid = response.get("gis_sid")

    def logout(self) -> None:
        if sid := self.wialon_api.sid:
            response = self.wialon_api.core_logout({})
            if not int(response.get("error")) == 0:
                raise WialonAPIError(
                    f"Failed to logout of the Wialon API session #{sid}",
                    code=int(response.get("error")),
                )
            self.wialon_api.sid = None

    @property
    def wialon_api(self) -> Wialon:
        return self._wialon_api

    @property
    def uid(self) -> str | None:
        return self._uid

    @property
    def username(self) -> str | None:
        return self._username

    @property
    def gis_sid(self) -> str | None:
        return self._gis_sid

    @property
    def id(self) -> str | None:
        return self.wialon_api.sid


def generate_txt(user_id: int | None, message: str) -> str:
    return urllib.parse.urlencode(
        {
            "user_id": user_id,
            "unit_id": "%UNIT_ID%",
            "message": message,
            "msg_time_int": "%MSG_TIME_INT%",
            "location": "%LOCATION%",
            "unit_name": "%UNIT%",
        },
        safe="%",
    )


def generate_act(method: str) -> list[dict]:
    url = urllib.parse.urljoin(
        "https://api.terminusgps.com/", f"/v3/notify/{method}/"
    )
    return [{"t": "push_messages", "p": {"url": url, "get": 0}}]


def validate_e164_phone_number(value: str) -> None:
    """Raises :py:exec:`~django.core.exceptions.ValidationError` if the value wasn't a properly formatted E.164 phone number."""
    if not value:
        raise ValidationError(
            "Invalid E.164 phone number: '%(value)s'",
            code="invalid",
            params={"value": value},
        )
    if not value.startswith("+"):
        raise ValidationError(
            _("E.164 phone number must start with a '+', got '%(char)s'"),
            code="invalid",
            params={"char": value[0]},
        )
    if not value.removeprefix("+").isdigit():
        raise ValidationError(
            _(
                "E.164 phone number must be entirely digits following '+', got '%(value)s'"
            ),
            code="invalid",
            params={"value": value.removeprefix("+")},
        )
    if len(value.removeprefix("+")) > 15:
        raise ValidationError(
            _(
                "E.164 phone number cannot be greater than 15 characters in length, got %(len)s."
            ),
            code="invalid",
            params={"len": len(value.removeprefix("+"))},
        )


def get_session(sid: str) -> WialonSession:
    """
    Returns a Wialon API session object based on the provided session id for safely interacting with the Wialon API.

    :param sid: A Wialon API session id.
    :type sid: str
    :returns: A resumed Wialon API session.
    :rtype: :py:obj:`~terminusgps.wialon.session.WialonSession`

    """
    return WialonSession(sid=sid)


def clean_phones(phones: list[str]) -> list[str]:
    """
    Cleans and returns a list of E.164 format phone numbers.

    :param phones: A list of phone numbers.
    :type phones: list[str]
    :returns: A list of properly formatted E.164 phone numbers.
    :rtype: list[str]

    """
    cleaned = []
    for phone in phones:
        try:
            validate_e164_phone_number(phone)
            cleaned.append(phone)
        except ValidationError as error:
            logger.warning(error.message)
            continue
    return cleaned


def get_phone_numbers_by_id(
    unit_id: int, session: WialonSession, timeout: int = 300
) -> list[str]:
    """
    Returns a list of unit assigned phone numbers by id.

    :param form: A Wialon notification dispatch form.
    :type form: ~terminusgps_notifier.forms.WialonNotificationDispatchForm
    :param session: Active Wialon API session.
    :type session: ~terminusgps.wialon.session.WialonSession
    :param timeout: Cache timeout in seconds. Default is ``300`` (5min).
    :type timeout: int
    :returns: A list of phone numbers.
    :rtype: list[str]

    """
    driver_phones = get_driver_phone_numbers(unit_id, session)
    cfield_phones = get_cfield_phone_numbers(unit_id, session)
    return list(frozenset(driver_phones + cfield_phones))


def get_phones(token: str | None, unit_id: int) -> list[str]:
    """
    Calls the Wialon API and returns a list of phone numbers assigned to a unit.

    Returns an empty list if something went wrong during the Wialon API call.

    :param token: A Wialon API token. If not provided, immediately returns an empty list.
    :type token: str | None
    :param unit_id: A Wialon unit id.
    :type unit_id: int
    :returns: A list of phone numbers assigned to the Wialon unit.
    :rtype: list[str]

    """
    if token is None:
        return []
    with WialonSession(token=token) as session:
        try:
            dirty_phones = get_phone_numbers_by_id(unit_id, session)
        except WialonAPIError as error:
            logger.error(error)
            return []
        return clean_phones(dirty_phones)


def get_driver_phone_numbers(
    unit_id: int, session: WialonSession
) -> list[str]:
    """
    Returns a list of the unit's attached driver phone numbers.

    :param unit_id: Wialon unit id.
    :type unit_id: int
    :param session: Active Wialon API session.
    :type session: ~terminusgps.wialon.session.WialonSession
    :returns: A list of phone numbers.
    :rtype: list[str]

    """
    try:
        logger.debug(
            "Calling the Wialon API to retrieve driver phones for unit #%s...",
            unit_id,
        )
        drivers = session.wialon_api.resource_get_unit_drivers(
            **{"unitId": unit_id}
        )
        return (
            [driver[0].get("ph") for driver in drivers.values()]
            if drivers.values()
            else []
        )
    except WialonAPIError as e:
        logger.warning(e)
        return []


def get_cfield_phone_numbers(
    unit_id: int, session: WialonSession, cfield_key: str = "to_number"
) -> list[str]:
    """
    Returns a list of the unit's attached driver phone numbers.

    :param unit_id: Wialon unit id.
    :type unit_id: int
    :param session: Active Wialon API session.
    :type session: ~terminusgps.wialon.session.WialonSession
    :param cfield_key: Custom field key containing a comma-separated list of phone numbers. Default is :py:obj:`"to_number"`.
    :type cfield_key: str
    :returns: A list of phone numbers.
    :rtype: list[str]

    """
    try:
        logger.debug(
            "Calling the Wialon API to retrieve cfield phones for unit #%s...",
            unit_id,
        )
        search = session.wialon_api.core_search_item(
            **{"id": unit_id, "flags": flags.DataFlag.UNIT_CUSTOM_FIELDS}
        )
        if item := search.get("item"):
            if cfields := item.get("flds"):
                for cfield in cfields.values():
                    if cfield["n"] == cfield_key:
                        return (
                            cfield["v"].split(",")
                            if "," in cfield["v"]
                            else [cfield["v"]]
                        )
        return []
    except WialonAPIError as e:
        logger.warning(e)
        return []


def get_resources(wialon_sid: str, force: bool = False) -> dict:
    """
    Returns a dictionary of Wialon resources.

    :param wialon_sid: A Wialon API session id.
    :type wialon_sid: str
    :param force: Whether to force a Wialon API call or not. Default is :py:obj:`False`.
    :type force: bool
    :returns: A `core/search_items` response dictionary.
    :rtype: dict

    """
    session = get_session(wialon_sid)
    params = {"spec": {}, "force": int(force), "from": 0, "to": 0, "flags": 1}
    params["spec"]["itemsType"] = "avl_resource"
    params["spec"]["propName"] = "sys_name"
    params["spec"]["propValueMask"] = "*"
    params["spec"]["propType"] = "property"
    params["spec"]["sortType"] = "sys_name"
    return session.wialon_api.core_search_items(**params)


def get_items(
    wialon_sid: str, resource_id: str, items_type: str, force: bool = False
) -> dict:
    """
    Returns a dictionary of Wialon items.

    Items types:

    +-------------+------------------+
    | name        | value            |
    +=============+==================+
    | Units       | "avl_unit"       |
    +-------------+------------------+
    | Unit Groups | "avl_unit_group" |
    +-------------+------------------+

    :param wialon_sid: A Wialon API session id.
    :type wialon_sid: str
    :param resource_id: A Wialon resource id.
    :type resource_id: str
    :param items_type: The Wialon items type to retrieve.
    :type items_type: str
    :param force: Whether to force a Wialon API call or not. Default is :py:obj:`False`.
    :type force: bool
    :returns: A `core/search_items` response dictionary.
    :rtype: dict

    """
    session = get_session(wialon_sid)
    params = {"spec": {}, "force": int(force), "from": 0, "to": 0, "flags": 1}
    params["spec"]["itemsType"] = items_type
    params["spec"]["propName"] = "sys_name,sys_billing_account_guid"
    params["spec"]["propValueMask"] = f"*,{resource_id}"
    params["spec"]["propType"] = "property,property"
    params["spec"]["sortType"] = "sys_name"
    return session.wialon_api.core_search_items(**params)


def get_geozones(wialon_sid: str, resource_id: str) -> dict:
    session = get_session(wialon_sid)
    params = {"itemId": resource_id}
    return session.wialon_api.resource_get_zone_data(**params)


def get_notifications(
    wialon_sid: str,
    resource_id: str,
    notification_ids: Sequence[str] | None = None,
) -> dict:
    session = get_session(wialon_sid)
    params = {"itemId": resource_id}
    if notification_ids is not None:
        params["col"] = notification_ids
    return session.wialon_api.resource_get_notification_data(**params)


def create_notification(wialon_sid: str, params: dict) -> dict:
    session = get_session(wialon_sid)
    return session.wialon_api.resource_update_notification(**params)


def get_unit(wialon_sid: str, unit_id: int) -> dict:
    session = get_session(wialon_sid)
    params = {"id": unit_id, "flags": 1}
    return session.wialon_api.core_search_item(**params)
