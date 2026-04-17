import asyncio
import functools
import logging
import warnings

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseRedirect,
)
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.module_loading import import_string
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import RedirectView, TemplateView, View
from terminusgps.mixins import HtmxTemplateResponseMixin
from terminusgps.wialon.session import WialonAPIError, WialonSession

from terminusgps_notifier import forms
from terminusgps_notifier.dispatchers import NotificationDispatcher
from terminusgps_notifier.models import Customer
from terminusgps_notifier.validators import validate_e164_phone_number
from terminusgps_notifier.wialon import get_phone_numbers

logger = logging.getLogger(__name__)


def htmx_template(template_name: str):
    def request_is_htmx(request: HttpRequest) -> bool:
        hx_request = bool(request.headers.get("HX-Request"))
        hx_boosted = bool(request.headers.get("HX-Boosted"))
        return hx_request and not hx_boosted

    def decorator(view_func):
        @functools.wraps(view_func)
        async def wrapper(request, *args, **kwargs):
            if request_is_htmx(request):
                kwargs["template_name"] = template_name + "#main"
            else:
                kwargs["template_name"] = template_name
            return await view_func(request, *args, **kwargs)

        return wrapper

    return decorator


class HtmxTemplateView(HtmxTemplateResponseMixin, TemplateView):
    """A view which renders a partial template on htmx request."""

    content_type = "text/html"
    http_method_names = ["get"]


class ProtectedHtmxTemplateView(
    LoginRequiredMixin, HtmxTemplateResponseMixin, TemplateView
):
    """A view which renders a partial template on htmx request, behind authentication."""

    content_type = "text/html"
    http_method_names = ["get"]


class HealthCheckView(View):
    content_type = "text/plain"
    http_method_names = ["get"]

    async def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Responds with status code 200."""
        return HttpResponse("I'm alive\n".encode("utf-8"), status=200)


@method_decorator(csrf_exempt, name="dispatch")
class NotificationDispatchView(View):
    content_type = "text/plain"
    http_method_names = ["get", "post"]

    @staticmethod
    async def clean_phones(phones: list[str]) -> list[str]:
        cleaned = []
        for phone in phones:
            try:
                validate_e164_phone_number(phone)
                cleaned.append(phone)
            except ValidationError:
                logger.warning(f"Improperly formatted phone number: {phone}")
                continue
        return cleaned

    async def get_phones(
        self, form: forms.NotificationDispatchForm
    ) -> list[str]:
        with WialonSession(token=settings.WIALON_TOKEN) as session:
            dirty_phones = await get_phone_numbers(form, session)
            return await self.clean_phones(dirty_phones)

    async def get_dispatchers(
        self, form: forms.NotificationDispatchForm
    ) -> list[NotificationDispatcher]:
        return [dispatcher(form) for dispatcher in self.dispatcher_classes]

    async def send_notifications(self, phones, dispatchers) -> HttpResponse:
        for dispatcher in dispatchers:
            try:
                tasks = [
                    dispatcher.send_notification(
                        to_number=phone, method=self.kwargs["method"]
                    )
                    for phone in phones
                ]
                await asyncio.gather(*tasks)
                logger.info(f"Dispatched via {type(dispatcher).__name__}")
                return HttpResponse(status=200)
            except Exception as error:
                logger.warning(
                    f"{type(dispatcher).__name__} failed: '{error}'"
                )
        logger.error(
            f"All dispatchers failed for method: '{self.kwargs['method']}'"
        )
        return HttpResponse(status=500)

    async def dispatch(
        self, request: HttpRequest, *args, **kwargs
    ) -> HttpResponse:
        try:
            method = kwargs.get("method")
            if method not in settings.NOTIFICATION_DISPATCHERS:
                raise ValueError(f"Invalid method: '{method}'")
            self.dispatcher_classes = []
            for dispatcher_path in settings.NOTIFICATION_DISPATCHERS[method]:
                dispatcher_cls = import_string(dispatcher_path)
                self.dispatcher_classes.append(dispatcher_cls)
            return await super().dispatch(request, *args, **kwargs)
        except ImportError as e:
            raise ImproperlyConfigured(e)
        except ValueError as e:
            raise Http404(e)

    async def post(
        self, request: HttpRequest, *args, **kwargs
    ) -> HttpResponse:
        """
        Dispatches notifications to target phone numbers.

        Returns 200 if notifications were queued successfully.

        Returns 500 if all dispatchers failed to queue notifications.

        Returns 4XX in any other case.

        """
        form = forms.NotificationDispatchForm(request.POST)
        if not form.is_valid():
            return HttpResponse(status=406)
        phones = await self.get_phones(form)
        if not phones:
            return HttpResponse(status=200)
        dispatchers = await self.get_dispatchers(form)
        return await self.send_notifications(phones, dispatchers)

    async def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Deprecated. Use POST instead."""
        warnings.warn(
            f"{type(self).__name__}.get() will return 405 in the future, use {type(self).__name__}.post() instead",
            category=FutureWarning,
            stacklevel=2,
        )
        form = forms.NotificationDispatchForm(request.GET)
        if not form.is_valid():
            return HttpResponse(status=406)
        phones = await self.get_phones(form)
        if not phones:
            return HttpResponse(status=200)
        dispatchers = await self.get_dispatchers(form)
        return await self.send_notifications(phones, dispatchers)


async def wialon_login(request: HttpRequest) -> HttpResponse:
    return RedirectView.as_view(
        url="https://hosting.terminusgps.com/login.html",
        permanent=True,
        query_string=True,
    )(request)


@never_cache
@htmx_template("terminusgps_notifier/wialon_callback.html")
async def wialon_callback(request: HttpRequest, **kwargs) -> HttpResponse:
    token_saved = False
    access_token = request.GET.get("access_token")
    if access_token is not None:
        customer = Customer.objects.afrom_user(request.user)
        customer.token = access_token
        await customer.asave(update_fields=["token"])
        token_saved = True
    return render(
        request, kwargs["template_name"], context={"token_saved": token_saved}
    )


@htmx_template("terminusgps_notifier/wialonnotification_create.html")
async def create_notification(request: HttpRequest, **kwargs) -> HttpResponse:
    if request.method == "POST":
        api_kwargs = {
            "itemId": request.POST.get("resource"),
            "id": 0,
            "callMode": "create",
            "n": request.POST.get("name"),
        }
        print(f"{api_kwargs = }")
    return render(request, kwargs["template_name"], context={})


@htmx_template("terminusgps_notifier/wialonresource_select.html")
async def select_resource(request: HttpRequest, **kwargs) -> HttpResponse:
    async def get_wialon_response(request: HttpRequest) -> dict:
        user = await request.auser()
        customer = await Customer.objects.afrom_user(user=user)
        with WialonSession(token=customer.token) as session:
            return session.wialon_api.core_search_items(
                **{
                    "spec": {
                        "itemsType": "avl_resource",
                        "propName": "sys_name",
                        "propValueMask": "*",
                        "propType": "property",
                        "sortType": "sys_name",
                    },
                    "force": 0,
                    "from": 0,
                    "to": 0,
                    "flags": 1,
                }
            )

    try:
        response = await get_wialon_response(request)
        choices = response["items"]
    except WialonAPIError as error:
        response = error
        choices = []
    if request.POST:
        return HttpResponseRedirect(
            reverse(
                "terminusgps_notifier:select units",
                kwargs={"resource_id": request.POST["resource_id"]},
            )
        )
    return render(
        request, kwargs["template_name"], context={"choices": choices}
    )


@htmx_template("terminusgps_notifier/wialonunit_select.html")
async def select_units(request: HttpRequest, **kwargs) -> HttpResponse:
    async def get_wialon_response(request: HttpRequest) -> dict:
        user = await request.auser()
        customer = await Customer.objects.aget(user=user)
        with WialonSession(token=customer.token) as session:
            return session.wialon_api.core_search_items(
                **{
                    "spec": {
                        "itemsType": request.POST.get(
                            "items_type", "avl_unit"
                        ),
                        "propName": "sys_name",
                        "propValueMask": "*",
                        "propType": "property",
                        "sortType": "sys_name",
                    },
                    "force": 0,
                    "from": 0,
                    "to": 0,
                    "flags": 1,
                }
            )

    return render(request, kwargs["template_name"], context={})


@htmx_template("terminusgps_notifier/wialonaction_select.html")
async def select_action(request: HttpRequest, **kwargs) -> HttpResponse:
    return render(request, kwargs["template_name"], context={})


@htmx_template("terminusgps_notifier/wialontrigger_select.html")
async def select_trigger(request: HttpRequest, **kwargs) -> HttpResponse:
    return render(request, kwargs["template_name"], context={})
