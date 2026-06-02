import datetime
import logging

from authorizenet import apicontractsv1
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.utils.dateparse import parse_date
from lxml.objectify import ObjectifiedElement
from terminusgps.authorizenet import api
from terminusgps.authorizenet.service import (
    AuthorizenetError,
    AuthorizenetService,
)

from . import constants

logger = logging.getLogger(__name__)


def get_authorizenet_service() -> AuthorizenetService:
    """
    Returns an Authorizenet service object for safely interacting with the Authorizenet API.

    :returns: An Authorizenet service object.
    :rtype: :py:obj:`~terminusgps.authorizenet.service.AuthorizenetService`

    """
    return AuthorizenetService()


def get_hosted_profile_page_url() -> str:
    """Returns the Authorizenet hosted profile page URL."""
    return (
        "https://accept.authorize.net/customer/manage"
        if not settings.DEBUG
        else "https://test.authorize.net/customer/manage"
    )


def get_customer_profile_by_id(id: str) -> ObjectifiedElement:
    """
    Returns a customer profile from Authorizenet by id.

    :param id: An Authorizenet customer profile id.
    :type id: str
    :returns: A customer profile.
    :rtype: :py:obj:`~lxml.objectify.ObjectifiedElement`

    """
    service = get_authorizenet_service()
    return service.execute(
        api.get_customer_profile(customer_profile_id=int(id))
    )


def get_customer_profile(email: str) -> ObjectifiedElement:
    """
    Returns a customer profile from Authorizenet by email address.

    :param email: An email address.
    :type email: str
    :returns: A customer profile.
    :rtype: :py:obj:`~lxml.objectify.ObjectifiedElement`

    """
    service = get_authorizenet_service()
    return service.execute(api.get_customer_profile(email=email))


def create_customer_profile(
    email: str, merchant_id: str, description: str
) -> ObjectifiedElement:
    """
    Creates a customer profile from Authorizenet.

    If one already existed for the provided email, instead return the existing customer profile.

    :param email: An email address.
    :type email: str
    :param merchant_id: A merchant-designated customer id.
    :type merchant_id: str
    :param description: A short customer description.
    :type description: str
    :returns: A customer profile object.
    :rtype: :py:obj:`~lxml.objectify.ObjectifiedElement`

    """
    try:
        return get_customer_profile(email)
    except AuthorizenetError as error:
        if error.code != "E00040":  # Record not found
            raise

    contract = apicontractsv1.customerProfileType()
    contract.email = email
    contract.merchantCustomerId = merchant_id
    contract.description = description
    service = get_authorizenet_service()
    return service.execute(api.create_customer_profile(contract))


def get_next_subscription_payment_date(id: int | None) -> datetime.date | None:
    """
    Returns the next date the subscription will be collected on.

    Returns :py:obj:`None` if no subscription was found.

    :param id: A subscription id.
    :type id: int | None
    :returns: The next payment date for the subscription.
    :rtype: ~datetime.date | None

    """
    if not id:
        return
    anet_service = get_authorizenet_service()
    anet_request = api.get_subscription(id)
    try:
        response = anet_service.execute(anet_request)
    except AuthorizenetError as error:
        logger.error(error)
        return
    else:
        start_str = str(response.subscription.paymentSchedule.startDate)
        start = parse_date(start_str)
        today = datetime.date.today()
        return start.replace(month=today.month) + relativedelta(months=1)


def get_subscription_status(id: int | None) -> str | None:
    """
    Returns the status for an Authorizenet subscription by id.

    Possible statuses:

        * "active"
        * "expired"
        * "suspended"
        * "canceled"
        * "terminated"

    :param id: A subscription id.
    :type id: int | None
    :returns: The subscription's current status.
    :rtype: str | None

    """
    service = get_authorizenet_service()
    try:
        response = service.execute(api.get_subscription_status(id))
    except AuthorizenetError as error:
        logger.error(error)
        return
    else:
        return str(response.status)


def subscription_is_active(id: int | None) -> bool:
    """
    Returns whether a subscription is active by id.

    :returns: Whether the subscription is active.
    :rtype: bool

    """
    if not id:
        return False
    try:
        status = get_subscription_status(id)
    except AuthorizenetError as error:
        if error.code == constants.SUBSCRIPTION_NOT_FOUND:
            return False
        raise
    else:
        return status in ("active", "canceled")
