import typing
from datetime import date

from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic.base import ContextMixin
from terminusgps_payments.models import Subscription

from terminusgps_notifier.models import TerminusGPSNotifierCustomer


def get_customer(request) -> TerminusGPSNotifierCustomer | None:
    if hasattr(request, "user") and request.user.is_authenticated:
        customer, _ = TerminusGPSNotifierCustomer.objects.get_or_create(
            user=request.user
        )
        return customer


def get_subscription(request) -> Subscription | None:
    customer = get_customer(request)
    if customer is not None:
        return customer.subscription


class CustomerContextMixin(ContextMixin):
    """Adds :py:attr:`customer` to the view context."""

    def get_context_data(self, **kwargs) -> dict[str, typing.Any]:
        context = super().get_context_data(**kwargs)
        context["customer"] = get_customer(self.request)
        return context


class ActiveSubscriptionRequiredMixin(UserPassesTestMixin):
    """TODO"""

    def test_func(self) -> bool:
        subscription = get_subscription(self.request)
        if subscription is None:
            return False
        elif subscription.status == "active":
            return True
        else:
            if subscription.expires_on is None:
                return False
            return subscription.expires_on > date.today()
