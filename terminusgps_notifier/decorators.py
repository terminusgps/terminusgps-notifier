import functools

from django.http import HttpRequest

__all__ = ["htmx_template"]


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
