import asyncio
import logging
import typing
import urllib.parse
import warnings

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.forms import Form
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.module_loading import import_string
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods
from django.views.generic import RedirectView, View
from terminusgps.wialon.session import WialonAPIError, WialonSession

from terminusgps_notifier import forms
from terminusgps_notifier.decorators import htmx_template
from terminusgps_notifier.dispatchers import NotificationDispatcher
from terminusgps_notifier.models import Customer
from terminusgps_notifier.validators import validate_e164_phone_number
from terminusgps_notifier.wialon import get_phone_numbers

logger = logging.getLogger(__name__)


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


@require_GET
async def wialon_login(request: HttpRequest) -> HttpResponse:
    return RedirectView.as_view(
        url="https://hosting.terminusgps.com/login.html",
        permanent=True,
        query_string=True,
    )(request)


@require_GET
@never_cache
@htmx_template("terminusgps_notifier/wialon_callback.html")
async def wialon_callback(request: HttpRequest) -> HttpResponse:
    user = await request.auser()
    customer, _ = await Customer.objects.aget_or_create(user=user)
    token_saved = False
    if access_token := request.GET.get("access_token"):
        customer.token = access_token
        await customer.asave(update_fields=["token"])
        token_saved = True
    context = {"token_saved": token_saved}
    return TemplateResponse(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/home.html")
async def home(request: HttpRequest) -> HttpResponse:
    context = {}
    return render(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/contact.html")
async def contact(request: HttpRequest) -> HttpResponse:
    context = {}
    return render(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/terms.html")
async def terms(request: HttpRequest) -> HttpResponse:
    context = {}
    return render(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/privacy.html")
async def privacy(request: HttpRequest) -> HttpResponse:
    context = {}
    return render(request, request.template_name, context=context)


@require_GET
async def source_code(request: HttpRequest) -> HttpResponse:
    return RedirectView.as_view(
        url="https://github.com/terminusgps/terminusgps-notifier",
        permanent=True,
    )(request)


@require_GET
@htmx_template("terminusgps_notifier/dashboard.html")
async def dashboard(request: HttpRequest, **kwargs) -> HttpResponse:
    def get_redirect_uri(request: HttpRequest) -> str:
        return request.build_absolute_uri(
            reverse("terminusgps_notifier:wialon callback")
        )

    @sync_to_async
    def get_customer_data(request: HttpRequest) -> dict[str, typing.Any]:
        customer = Customer.objects.get(user=request.user)
        context = {}
        context["redirect_uri"] = get_redirect_uri(request)
        context["username"] = customer.user.username
        context["has_token"] = customer.token is not None
        context["has_subscription"] = customer.subscription is not None
        context["messages_count"] = customer.messages_count
        context["messages_limit"] = customer.messages_limit
        return context

    try:
        context = await get_customer_data(request)
    except Customer.DoesNotExist:
        context = {}
    return render(request, request.template_name, context=context)


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/select_resource.html")
async def select_resource(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        return redirect(
            reverse(
                "terminusgps_notifier:select units",
                kwargs={"resource_id": request.POST["resource"]},
            )
        )
    try:
        user = await request.auser()
        customer = await Customer.objects.aget(user=user)
        with WialonSession(token=customer.token) as session:
            params = {"spec": {}, "force": 0, "from": 0, "to": 0, "flags": 1}
            params["spec"]["itemsType"] = "avl_resource"
            params["spec"]["propName"] = "sys_name"
            params["spec"]["propValueMask"] = "*"
            params["spec"]["propType"] = "property"
            params["spec"]["sortType"] = "sys_name"
            response = session.wialon_api.core_search_items(**params)
    except WialonAPIError:
        response = {"items": []}

    context = {}
    context["item_list"] = response["items"]
    return render(request, request.template_name, context=context)


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/select_units.html")
async def select_units(request: HttpRequest, resource_id: int) -> HttpResponse:
    if request.method == "POST":
        units = [int(id) for id in request.POST["units"]]
        await request.session.aset("units", units)
        await request.session.aset("resource", resource_id)
        return redirect(reverse("terminusgps_notifier:select trigger"))
    try:
        items_type = request.GET.get("items_type", "avl_unit")
        user = await request.auser()
        customer = await Customer.objects.aget(user=user)
        with WialonSession(token=customer.token) as session:
            params = {"spec": {}, "force": 0, "from": 0, "to": 0, "flags": 1}
            params["spec"]["itemsType"] = items_type
            params["spec"]["propName"] = "sys_name,sys_billing_account_guid"
            params["spec"]["propValueMask"] = f"*,{resource_id}"
            params["spec"]["propType"] = "property"
            params["spec"]["sortType"] = "sys_name"
            response = session.wialon_api.core_search_items(**params)
    except WialonAPIError:
        response = {"items": []}

    context = {}
    context["item_list"] = response["items"]
    context["resource_id"] = resource_id
    return render(request, request.template_name, context=context)


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/select_trigger.html")
async def select_trigger(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        non_parameter_fields = ("trigger", "csrfmiddlewaretoken")
        t = request.POST["trigger"]
        p = {}
        for field in request.POST:
            if field not in non_parameter_fields:
                p[field] = request.POST[field]
        await request.session.aset("trg", {"t": t, "p": p})
        print(f"{await request.session.aget("trg") = }")
        print(f"{await request.session.aget("units") = }")
        print(f"{await request.session.aget("resource_id") = }")
        return redirect(reverse("terminusgps_notifier:create notification"))
    context = {"triggers": forms.WialonNotificationTrigger.choices}
    return render(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/trigger_parameters.html")
async def trigger_parameters(request: HttpRequest) -> HttpResponse:
    async def get_form_cls(trigger: str) -> type[Form]:
        if trigger in forms.TRIGGER_FORMS_MAP:
            return forms.TRIGGER_FORMS_MAP[trigger]
        return Form

    context = {}
    if trigger := request.GET.get("trigger"):
        form_cls = await get_form_cls(trigger)
        context["form"] = form_cls()
    return render(request, request.template_name, context=context)


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/create_notification.html")
async def create_notification(request: HttpRequest) -> HttpResponse:
    async def get_txt(user: AbstractBaseUser, message: str) -> str:
        return urllib.parse.urlencode(
            {
                "user_id": user.pk,
                "unit_id": "%UNIT_ID%",
                "msg_time_int": "%MSG_TIME_INT%",
                "location": "%LOCATION%",
                "unit_name": "%UNIT%",
            },
            safe="%",
        )

    async def get_act(method: str) -> list[dict]:
        url = urllib.parse.urljoin(
            "https://api.terminusgps.com/v3/notify/", f"/{method}/"
        )
        return [{"t": "send_messages", "p": {"url": url, "get": 0}}]

    async def get_sch(request: HttpRequest) -> dict[str, int]:
        schedule = {}
        schedule["f1"] = 0
        schedule["f2"] = 0
        schedule["t1"] = 0
        schedule["t2"] = 0
        schedule["w"] = 0
        schedule["m"] = 0
        schedule["y"] = 0
        return schedule

    if request.POST:
        try:
            user = await request.auser()
            customer = await Customer.objects.aget(user=user)
            with WialonSession(token=customer.token) as session:
                params = {"id": 0, "callMode": "create"}
                params["itemId"] = int(await request.session.aget("resource"))
                params["n"] = str(request.POST["n"])
                params["txt"] = await get_txt(user, request.POST["message"])
                params["ta"] = int(request.POST["ta"])
                params["td"] = int(request.POST["td"])
                params["ma"] = int(request.POST["ma"])
                params["mmtd"] = int(request.POST["mmtd"])
                params["cdt"] = int(request.POST["cdt"])
                params["mast"] = int(request.POST["mast"])
                params["mpst"] = int(request.POST["mpst"])
                params["cp"] = int(request.POST["cp"])
                params["fl"] = int(request.POST["fl"])
                params["la"] = str(request.POST["la"])
                params["un"] = await request.session.aget("units", [])
                params["sch"] = await get_sch(request)
                params["ctrl_sch"] = await get_sch(request)
                params["trg"] = await request.session.aget("trigger")
                params["act"] = await get_act(request.POST["method"])
                response = session.wialon_api.resource_update_notification(
                    **params
                )
        except WialonAPIError as error:
            print(f"{error = }")
    context = {}
    return render(request, request.template_name, context=context)
