from django.core.cache import cache
from terminusgps.wialon import flags
from terminusgps.wialon.session import WialonSession

# TODO: Add logging to these functions


def get_phone_numbers(unit_id: str, wialon_token: str) -> list[str]:
    """
    Returns a list of the unit's assigned phone numbers.

    :param unit_id: Wialon unit id.
    :type unit_id: str
    :param wialon_token: Active Wialon API token.
    :type wialon_token: str
    :returns: A list of unit phone numbers.
    :rtype: list[str]

    """
    driver_phones = get_driver_phone_numbers(unit_id, wialon_token)
    cfield_phones = get_cfield_phone_numbers(unit_id, wialon_token)
    return list(frozenset(driver_phones + cfield_phones))


def get_driver_phone_numbers(unit_id: str, wialon_token: str) -> list[str]:
    """
    Returns a list of the unit's attached driver phone numbers.

    :param unit_id: Wialon unit id.
    :type unit_id: str
    :param wialon_token: Active Wialon API token.
    :type wialon_token: str
    :returns: A list of unique phone numbers.
    :rtype: list[str]

    """
    cache_key = f"{wialon_token[-16:]}_{unit_id}_get_driver_phone_numbers"
    if cached_driver_phones := cache.get(cache_key):
        return cached_driver_phones
    with WialonSession(token=wialon_token) as session:
        response = session.wialon_api.resource_get_unit_drivers(
            **{"unitId": unit_id}
        )
        if response.values():
            phones = [driver[0].get("ph") for driver in response.values()]
            cache.set(cache_key, phones)
        else:
            phones = []
        return phones


def get_cfield_phone_numbers(
    unit_id: str, wialon_token: str, cfield_key: str = "to_number"
) -> list[str]:
    """
    Returns a list of the unit's attached driver phone numbers.

    :param unit_id: Wialon unit id.
    :type unit_id: str
    :param wialon_token: Active Wialon API token.
    :type wialon_token: str
    :param cfield_key: Custom field key containing a comma-separated list of phone numbers. Default is :py:obj:`"to_number"`.
    :type cfield_key: str
    :returns: A list of unique phone numbers.
    :rtype: list[str]

    """
    cache_key = f"{wialon_token[-16:]}_{unit_id}_get_cfield_phone_numbers"
    if cached_cfield_phones := cache.get(cache_key):
        return cached_cfield_phones
    with WialonSession(token=wialon_token) as session:
        response = session.wialon_api.core_search_item(
            **{"id": unit_id, "flags": flags.DataFlag.UNIT_CUSTOM_FIELDS}
        )
        if flds := response.get("item", {}).get("flds", {}).values():
            dirty_phones = [
                cfield["v"] for cfield in flds if cfield["n"] == cfield_key
            ]
            phones = []
            for num in dirty_phones:
                if "," in num:
                    phones.extend(num.split(","))
                else:
                    phones.append(num)
            cache.set(cache_key, phones)
        else:
            phones = []
        return phones
