import functools

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect

from .models import Customer

__all__ = ["htmx_template"]


class HtmxHttpRequest(HttpRequest):
    template_name: str


def wialon_token_required():
    def request_user_has_wialon_token(request: HtmxHttpRequest) -> bool:
        if not hasattr(request, "user"):
            return False
        if request.user.is_anonymous:
            return False
        else:
            customer, _ = Customer.objects.get_or_create(user=request.user)
            return customer.token is not None

    def outer_wrapper(view_func):
        @functools.wraps(view_func)
        def inner_wrapper(request, *args, **kwargs) -> HttpResponse:
            if request_user_has_wialon_token(request):
                return view_func(request, *args, **kwargs)
            else:
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
