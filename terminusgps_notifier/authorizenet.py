from authorizenet import apicontractsv1
from lxml.objectify import ObjectifiedElement
from terminusgps.authorizenet import api
from terminusgps.authorizenet.service import AuthorizenetService


def get_authorizenet_service() -> AuthorizenetService:
    """
    Returns an Authorizenet service object for safely interacting with the Authorizenet API.

    :returns: An Authorizenet service object.
    :rtype: :py:obj:`~terminusgps.authorizenet.service.AuthorizenetService`

    """
    return AuthorizenetService()


def get_customer_profile_by_email(email: str) -> ObjectifiedElement:
    """Returns a customer profile from Authorizenet by email address."""
    service = get_authorizenet_service()
    return service.execute(api.get_customer_profile(email=email))


def get_customer_profile_by_id(id: str) -> ObjectifiedElement:
    """Returns a customer profile from Authorizenet by id."""
    service = get_authorizenet_service()
    return service.execute(api.get_customer_profile(customer_profile_id=id))


def create_customer_profile(
    email: str, merchant_id: str, description: str
) -> ObjectifiedElement:
    """Creates a customer profile in Authorizenet."""
    contract = apicontractsv1.customerProfileType()
    contract.email = email
    contract.merchantCustomerId = merchant_id
    contract.description = description
    service = get_authorizenet_service()
    return service.execute(api.create_customer_profile(contract))
