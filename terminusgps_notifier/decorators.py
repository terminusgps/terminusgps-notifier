import datetime
import functools

from asgiref.sync import sync_to_async
from django.contrib import messages
from django.contrib.auth.models import AbstractBaseUser
from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse

from .models import Customer

__all__ = [
    "htmx_template",
    "wialon_token_required",
    "active_subscription_required",
]


def active_subscription_required():
    @sync_to_async
    def user_has_active_subscription(user: AbstractBaseUser) -> bool:
        try:
            customer = Customer.objects.get(user=user)
            if customer.subscription is None:
                return False
            if customer.subscription.expires_on is not None:
                today = datetime.date.today()
                if today >= customer.subscription.expires_on:
                    return False
            return customer.subscription.status == "active"
        except Customer.DoesNotExist:
            return False

    def outer_wrapper(view_func):
        @functools.wraps(view_func)
        async def inner_wrapper(request, *args, **kwargs):
            user = await request.auser()
            if not await user_has_active_subscription(user):
                msg = "You need an active subscription to perform that action."
                messages.warning(request, msg)
                return redirect(reverse("terminusgps_notifier:dashboard"))
            return await view_func(request, *args, **kwargs)

        return inner_wrapper

    return outer_wrapper


def wialon_token_required():
    @sync_to_async
    def user_has_wialon_token(user: AbstractBaseUser) -> bool:
        try:
            customer = Customer.objects.get(user=user)
            return customer.token is not None
        except Customer.DoesNotExist:
            return False

    def outer_wrapper(view_func):
        @functools.wraps(view_func)
        async def inner_wrapper(request, *args, **kwargs):
            user = await request.auser()
            if not await user_has_wialon_token(user):
                msg = "You need to connect your Wialon account to perform that action."
                messages.warning(request, msg)
                return redirect(reverse("terminusgps_notifier:dashboard"))
            return await view_func(request, *args, **kwargs)

        return inner_wrapper

    return outer_wrapper


def htmx_template(template_name: str):
    def request_is_htmx(request: HttpRequest) -> bool:
        hx_request = bool(request.headers.get("HX-Request"))
        hx_boosted = bool(request.headers.get("HX-Boosted"))
        return hx_request and not hx_boosted

    def outer_wrapper(view_func):
        @functools.wraps(view_func)
        async def inner_wrapper(request, *args, **kwargs):
            if request_is_htmx(request):
                request.template_name = template_name + "#main"
            else:
                request.template_name = template_name
            return await view_func(request, *args, **kwargs)

        return inner_wrapper

    return outer_wrapper
