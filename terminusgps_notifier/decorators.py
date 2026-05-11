import functools

from django.contrib import messages
from django.contrib.auth.models import AbstractBaseUser
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect

from .models import Profile

__all__ = ["htmx_template", "wialon_token_required"]


class HtmxHttpRequest(HttpRequest):
    template_name: str


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
