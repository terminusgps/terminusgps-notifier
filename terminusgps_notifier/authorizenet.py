from authorizenet import apicontractsv1
from django.http import HttpRequest
from django.urls import reverse
from lxml.objectify import ObjectifiedElement
from terminusgps.authorizenet import api
from terminusgps.authorizenet.service import (
    AuthorizenetError,
    AuthorizenetService,
)


def get_authorizenet_service() -> AuthorizenetService:
    """
    Returns an Authorizenet service object for safely interacting with the Authorizenet API.

    :returns: An Authorizenet service object.
    :rtype: :py:obj:`~terminusgps.authorizenet.service.AuthorizenetService`

    """
    return AuthorizenetService()


def get_subscription_page_token(
    request: HttpRequest, customer_profile_id: str
) -> str:
    settings_list = []
    return ""


def get_customer_profile_page_token(
    request: HttpRequest, customer_profile_id: str
) -> str:
    settings_list = [
        apicontractsv1.settingType(
            settingName=apicontractsv1.settingNameEnum.hostedProfileSaveButtonText,
            settingValue="Save",
        ),
        apicontractsv1.settingType(
            settingName=apicontractsv1.settingNameEnum.hostedProfileReturnUrl,
            settingValue=request.build_absolute_uri(
                reverse("terminusgps_notifier:dashboard")
            ),
        ),
        apicontractsv1.settingType(
            settingName=apicontractsv1.settingNameEnum.hostedProfileReturnUrlText,
            settingValue="Go Back",
        ),
        apicontractsv1.settingType(
            settingName=apicontractsv1.settingNameEnum.hostedProfilePageBorderVisible,
            settingValue="true",
        ),
        apicontractsv1.settingType(
            settingName=apicontractsv1.settingNameEnum.hostedProfileHeadingBgColor,
            settingValue="#ffc7b6",
        ),
        apicontractsv1.settingType(
            settingName=apicontractsv1.settingNameEnum.hostedProfilePaymentOptions,
            settingValue="showAll",
        ),
        apicontractsv1.settingType(
            settingName=apicontractsv1.settingNameEnum.hostedProfileValidationMode,
            settingValue="testMode",
        ),
        apicontractsv1.settingType(
            settingName=apicontractsv1.settingNameEnum.hostedProfileBillingAddressOptions,
            settingValue="showBillingAddress",
        ),
        apicontractsv1.settingType(
            settingName=apicontractsv1.settingNameEnum.hostedProfileCardCodeRequired,
            settingValue="true",
        ),
        apicontractsv1.settingType(
            settingName=apicontractsv1.settingNameEnum.hostedProfileManageOptions,
            settingValue="showAll",
        ),
    ]

    settings = apicontractsv1.ArrayOfSetting()
    for setting in settings_list:
        settings.setting.append(setting)
    service = get_authorizenet_service()
    response = service.execute(
        api.get_accept_customer_profile_page(
            customer_profile_id=int(customer_profile_id), settings=settings
        )
    )
    return str(response.token)


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


def get_subscription_status(id: int) -> str:
    """
    Returns the status for an Authorizenet subscription by id.

    Possible statuses:

        * "active"
        * "expired"
        * "suspended"
        * "canceled"
        * "terminated"

    :param id: A subscription id.
    :type id: int
    :returns: The subscription's current status.
    :rtype: str

    """
    service = get_authorizenet_service()
    response = service.execute(api.get_subscription_status(id))
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
        return status in ("active", "canceled")
    except AuthorizenetError as error:
        if error.code == "E00035":
            return False
        else:
            raise
