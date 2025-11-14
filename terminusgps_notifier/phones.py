from django.core.cache import cache
from terminusgps.wialon import flags
from terminusgps.wialon.session import WialonSession


def get_phone_numbers(unit_id: str, session: WialonSession) -> list[str]:
    """
    Returns a list of the unit's assigned phone numbers.

    :param unit_id: Wialon unit id.
    :type unit_id: str
    :param session: Active Wialon API session.
    :type session: ~terminusgps.wialon.session.WialonSession
    :returns: A list of unit phone numbers.
    :rtype: list[str]

    """
    driver_phones = get_driver_phone_numbers(unit_id, session)
    cfield_phones = get_cfield_phone_numbers(unit_id, session)
    return list(frozenset(driver_phones + cfield_phones))


def get_driver_phone_numbers(
    unit_id: str, session: WialonSession
) -> list[str]:
    """
    Returns a list of the unit's attached driver phone numbers.

    :param unit_id: Wialon unit id.
    :type unit_id: str
    :param session: Active Wialon API session.
    :type session: ~terminusgps.wialon.session.WialonSession
    :returns: A list of phone numbers.
    :rtype: list[str]

    """
    cache_key = f"{unit_id}_get_driver_phone_numbers"
    if cached_driver_phones := cache.get(cache_key):
        return cached_driver_phones
    response = session.wialon_api.resource_get_unit_drivers(
        **{"unitId": unit_id}
    )
    phones = [driver[0].get("ph") for driver in response.values()]
    cache.set(cache_key, phones)
    return phones


def get_cfield_phone_numbers(
    unit_id: str, session: WialonSession, cfield_key: str = "to_number"
) -> list[str]:
    """
    Returns a list of the unit's attached driver phone numbers.

    :param unit_id: Wialon unit id.
    :type unit_id: str
    :param session: Active Wialon API session.
    :type session: ~terminusgps.wialon.session.WialonSession
    :param cfield_key: Custom field key containing a comma-separated list of phone numbers. Default is :py:obj:`"to_number"`.
    :type cfield_key: str
    :returns: A list of phone numbers.
    :rtype: list[str]

    """
    cache_key = f"{unit_id}_get_cfield_phone_numbers"
    if cached_cfield_phones := cache.get(cache_key):
        return cached_cfield_phones
    response = session.wialon_api.core_search_item(
        **{"id": unit_id, "flags": flags.DataFlag.UNIT_CUSTOM_FIELDS}
    )
    phones = []
    dirty_phones = [
        cfield["v"]
        for cfield in response["item"]["flds"].values()
        if cfield["n"] == cfield_key
    ]
    for num in dirty_phones:
        phones.extend(num.split(",")) if "," in num else phones.append(num)
    cache.set(cache_key, phones)
    return phones
