import functools

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import AbstractBaseUser
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect

from .models import Profile

__all__ = ["htmx_template", "active_subscription_required"]


class HtmxHttpRequest(HttpRequest):
    template_name: str


def active_subscription_required(view_func=None):
    def user_has_subscription(user: AbstractBaseUser) -> bool:
        if user.is_anonymous:
            return False
        else:
            profile = get_object_or_404(Profile, user=user)
            return profile.subscription_id is not None

    def get_subscription_from_stripe(user: AbstractBaseUser) -> dict:
        profile = get_object_or_404(Profile, user=user)
        subscription_id = profile.subscription_id
        stripe_client = stripe.StripeClient(settings.STRIPE_API_KEY)
        subscription = stripe_client.v1.subscriptions.retrieve(subscription_id)
        return subscription.to_dict()

    def outer_wrapper(view_func):
        @functools.wraps(view_func)
        def inner_wrapper(request, *args, **kwargs) -> HttpResponse:
            if user := getattr(request, "user", None):
                if user_has_subscription(user):
                    subscription = get_subscription_from_stripe(user)
                    if subscription.get("status", "expired") == "active":
                        return view_func(request, *args, **kwargs)
            msg = "You need to subscribe to do that."
            messages.warning(request, msg)
            return redirect("terminusgps_notifier:dashboard")

        return inner_wrapper

    if view_func is None:
        return outer_wrapper
    else:
        return outer_wrapper(view_func)


def htmx_template(template_name: str):
    def request_is_htmx(request: HttpRequest) -> bool:
        hx_request = bool(request.headers.get("HX-Request"))
        hx_boosted = bool(request.headers.get("HX-Boosted"))
        return hx_request and not hx_boosted

    def outer_wrapper(view_func):
        @functools.wraps(view_func)
        def inner_wrapper(request, *args, **kwargs):
            if request_is_htmx(request):
                request.template_name = template_name + "#main"
            else:
                request.template_name = template_name
            return view_func(request, *args, **kwargs)

        return inner_wrapper

    return outer_wrapper
