import functools

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import AbstractBaseUser
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from terminusgps.wialon.session import WialonSession
from wialon.api import WialonError

from .models import Profile

__all__ = ["htmx_template", "wialon_session"]


class HtmxHttpRequest(HttpRequest):
    template_name: str


def valid_subscription_required():
    def user_has_subscription(user: AbstractBaseUser) -> bool:
        if user.is_anonymous:
            return False
        else:
            profile = get_object_or_404(Profile, user=user)
            return profile.subscription_id is not None

    def get_subscription_status(user: AbstractBaseUser) -> str:
        profile = get_object_or_404(Profile, user=user)
        client = stripe.StripeClient(settings.STRIPE_API_KEY)
        subscription = client.v1.subscriptions.retrieve(
            profile.subscription_id
        )
        return str(subscription.status)

    def outer_wrapper(view_func):
        @functools.wraps(view_func)
        def inner_wrapper(request, *args, **kwargs) -> HttpResponse:
            if user := getattr(request, "user", None):
                if user_has_subscription(user):
                    status = get_subscription_status(user)
                    print(f"{status = }")
                    return view_func(request, *args, **kwargs)
            msg = "You need to subscribe to do that."
            messages.warning(request, msg)
            return redirect("terminusgps_notifier:dashboard")

        return inner_wrapper

    return outer_wrapper


def wialon_session():
    def get_wialon_api_token(request: HttpRequest) -> str | None:
        if not hasattr(request, "user"):
            return
        if request.user.is_anonymous:
            return
        profile = get_object_or_404(Profile, user=request.user)
        return profile.token

    def wialon_sid_is_valid(sid: str | None) -> bool:
        session = WialonSession(sid=sid)
        try:
            session.wialon_api.avl_evts()
            return True
        except WialonError:
            return False

    def outer_wrapper(view_func):
        @functools.wraps(view_func)
        def inner_wrapper(request, *args, **kwargs):
            wialon_api_token = get_wialon_api_token(request)
            if not wialon_api_token:
                messages.warning(
                    request,
                    "You need to connect your Wialon account to do that.",
                )
                return redirect("terminusgps_notifier:dashboard")
            if not wialon_sid_is_valid(request.session.get("wialon_sid")):
                session = WialonSession(sid=None)
                session.token_login(token=wialon_api_token)
                request.session["wialon_sid"] = session.id
            return view_func(request, *args, **kwargs)

        return inner_wrapper

    return outer_wrapper


def wialon_token_required():
    def user_has_wialon_token(user: AbstractBaseUser) -> bool:
        if user.is_anonymous:
            return False
        else:
            profile = get_object_or_404(Profile, user=user)
            return bool(profile.token)

    def outer_wrapper(view_func):
        @functools.wraps(view_func)
        def inner_wrapper(request, *args, **kwargs) -> HttpResponse:
            if user := getattr(request, "user", None):
                if user_has_wialon_token(user):
                    return view_func(request, *args, **kwargs)
            msg = "You need to connect your Wialon account to do that."
            messages.warning(request, msg)
            return redirect("terminusgps_notifier:dashboard")

        return inner_wrapper

    return outer_wrapper


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
