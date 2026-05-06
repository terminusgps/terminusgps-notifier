from terminusgps.authorizenet import api
from terminusgps.authorizenet.service import (
    AuthorizenetError,
    AuthorizenetService,
)

from .models import Customer


def get_subscription_status(customer: Customer) -> str | None:
    if customer.subscription_id is None:
        return
    try:
        service = AuthorizenetService()
        response = service.execute(
            api.get_subscription_status(
                subscription_id=customer.subscription_id
            )
        )
        return str(response.status)
    except AuthorizenetError as error:
        print(error)
        return
