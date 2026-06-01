import functools

import wialon.api
from django.contrib import messages
from django.contrib.auth.models import AbstractBaseUser
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from terminusgps.wialon.session import WialonSession

from .models import Profile

__all__ = [
    "htmx_template",
    "active_subscription_required",
    "persistent_wialon_session",
]


class HtmxHttpRequest(HttpRequest):
    template_name: str


def get_wialon_api_token_from_user(user: AbstractBaseUser) -> str | None:
    profile = get_object_or_404(Profile, user=user)
    return profile.token


def wialon_session_is_valid(sid: str | None = None) -> bool:
    if sid is None:
        return False
    try:
        session = WialonSession(sid=sid)
        session.wialon_api.avl_evts()
        return True
    except wialon.api.WialonError as error:
        if error._code == 1:
            return False
        else:
            raise


def active_subscription_required(view_func=None):

    def outer_wrapper(view_func):
        @functools.wraps(view_func)
        def inner_wrapper(request, *args, **kwargs) -> HttpResponse:
            # TODO: Check Authorizenet subscription
            msg = "You need to subscribe to do that."
            messages.warning(request, msg)
            return redirect("terminusgps_notifier:dashboard")

        return inner_wrapper

    if view_func is None:
        return outer_wrapper
    else:
        return outer_wrapper(view_func)


def persistent_wialon_session(view_func=None):

    def outer_wrapper(view_func):
        @functools.wraps(view_func)
        def inner_wrapper(request, *args, **kwargs) -> HttpResponse:
            sid = request.session.pop("wialon_sid", None)
            token = get_wialon_api_token_from_user(request.user)
            if wialon_session_is_valid(sid):
                # Resume Wialon API session
                request.session["wialon_sid"] = sid
            elif token:
                # Refresh Wialon API session
                session = WialonSession(sid=None)
                session.token_login(token=token)
                request.session["wialon_sid"] = session.id
            else:
                msg = "You need to connect your Wialon account to do that."
                messages.error(request, msg)
                return redirect("terminusgps_notifier:dashboard")
            return view_func(request, *args, **kwargs)

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
