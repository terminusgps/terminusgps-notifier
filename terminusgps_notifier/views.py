import asyncio
import functools
import logging
import urllib.parse
import warnings

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.module_loading import import_string
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import RedirectView, View
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

    def outer_wrapper(view_func):
        @functools.wraps(view_func)
        async def inner_wrapper(request, *args, **kwargs):
            if request_is_htmx(request):
                kwargs["template_name"] = template_name + "#main"
            else:
                kwargs["template_name"] = template_name
            return await view_func(request, *args, **kwargs)

        return inner_wrapper

    return outer_wrapper


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
    try:
        access_token = request.GET.get("access_token")
        if access_token is not None:
            customer = await Customer.objects.aget(user=request.user)
            customer.token = access_token
            customer.save(update_fields=["access_token"])
        return render(
            request,
            kwargs["template_name"],
            context={"error": None, "token_saved": True},
        )
    except ValidationError as error:
        return render(
            request,
            kwargs["template_name"],
            context={"error": error, "token_saved": False},
        )


@htmx_template("terminusgps_notifier/create_notification.html")
async def create_notification(request: HttpRequest, **kwargs) -> HttpResponse:
    async def get_notification_txt(user_id: int, message: str) -> str:
        return urllib.parse.urlencode(
            {
                "user_id": user_id,
                "unit_id": "%UNIT_ID%",
                "msg_time_int": "%MSG_TIME_INT%",
                "location": "%LOCATION%",
                "message": message,
            }
        )

    if request.method == "POST":
        user = await request.auser()
        message = request.POST["message"]
        kwargs = {
            "itemId": request.POST["resource"],
            "id": 0,
            "callMode": "create",
            "n": request.POST["name"],
            "txt": await get_notification_txt(user.pk, message),
            "ta": request.POST["ta"],
            "td": request.POST["td"],
            "ma": request.POST["ma"],
            "mmtd": request.POST["mmtd"],
            "cdt": request.POST["cdt"],
            "mast": request.POST["mast"],
            "mpst": request.POST["mpst"],
            "cp": request.POST["cp"],
            "fl": request.POST["fl"],
            "tz": request.POST["tz"],
            "la": request.POST["la"],
            "un": request.POST["units"],
            "d": request.POST["d"],
            "sch": request.POST["sch"],
            "ctrl_sch": request.POST["ctrl_sch"],
            "trg": ...,
            "act": [],
        }

    return render(request, kwargs["template_name"], context={})


@htmx_template("terminusgps_notifier/select_resource.html")
async def select_resource(request: HttpRequest, **kwargs) -> HttpResponse:
    async def get_resources_from_wialon(request: HttpRequest) -> list:
        user = await request.auser()
        customer = await Customer.objects.afrom_user(user)
        with WialonSession(token=customer.token) as session:
            params = {"spec": {}, "force": 0, "from": 0, "to": 0, "flags": 1}
            params["spec"]["itemsType"] = "avl_resource"
            params["spec"]["propName"] = "sys_name"
            params["spec"]["propValueMask"] = "*"
            params["spec"]["propType"] = "property"
            params["spec"]["sortType"] = "sys_name"
            response = session.wialon_api.core_search_items(**params)
            return response["items"]

    try:
        resource_list = await get_resources_from_wialon(request)
    except WialonAPIError as error:
        print(error)
        resource_list = []
    context = {}
    context["resource_list"] = resource_list
    return render(request, kwargs["template_name"], context=context)


@htmx_template("terminusgps_notifier/select_units.html")
async def select_units(request: HttpRequest, **kwargs) -> HttpResponse:
    async def get_items_from_wialon(request: HttpRequest) -> list:
        user = await request.auser()
        customer = await Customer.objects.afrom_user(user)
        with WialonSession(token=customer.token) as session:
            params = {"spec": {}, "force": 0, "from": 0, "to": 0, "flags": 1}
            params["spec"]["itemsType"] = request.GET["items_type"]
            params["spec"]["propName"] = "sys_name,sys_billing_account_guid"
            params["spec"]["propValueMask"] = f"*,{request.GET['resource']}"
            params["spec"]["propType"] = "property,property"
            params["spec"]["sortType"] = "sys_name"
            response = session.wialon_api.core_search_items(**params)
            return response["items"]

    try:
        items_list = await get_items_from_wialon(request)
    except WialonAPIError as error:
        print(error)
        items_list = []
    context = {}
    context["items_list"] = items_list
    return render(request, kwargs["template_name"], context=context)


@htmx_template("terminusgps_notifier/home.html")
async def home(request: HttpRequest, **kwargs) -> HttpResponse:
    return render(request, kwargs["template_name"], context={})


@htmx_template("terminusgps_notifier/dashboard.html")
async def dashboard(request: HttpRequest, **kwargs) -> HttpResponse:
    return render(request, kwargs["template_name"], context={})


@htmx_template("terminusgps_notifier/contact.html")
async def contact(request: HttpRequest, **kwargs) -> HttpResponse:
    return render(request, kwargs["template_name"], context={})


@htmx_template("terminusgps_notifier/terms.html")
async def terms(request: HttpRequest, **kwargs) -> HttpResponse:
    return render(request, kwargs["template_name"], context={})


@htmx_template("terminusgps_notifier/privacy.html")
async def privacy(request: HttpRequest, **kwargs) -> HttpResponse:
    return render(request, kwargs["template_name"], context={})


async def source_code(request: HttpRequest) -> HttpResponse:
    return RedirectView.as_view(
        url="https://github.com/terminusgps/terminusgps-notifier",
        permanent=True,
    )(request)
