import asyncio
import logging
import typing
import urllib.parse
import warnings

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.template.response import TemplateResponse
from django.utils.dateparse import parse_date
from django.utils.decorators import method_decorator
from django.utils.module_loading import import_string
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import RedirectView, View
from terminusgps.wialon.session import WialonAPIError, WialonSession

from terminusgps_notifier import constants, forms
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
    if access_token := request.GET.get("access_token"):
        customer = await Customer.objects.aget(user=request.user)
        customer.token = access_token
        customer.save(update_fields=["access_token"])
        token_saved = True
    return TemplateResponse(
        request=request,
        template=kwargs["template_name"],
        context={"token_saved": token_saved},
    )


async def _get_timestamp(request: HttpRequest, field: str) -> int:
    if field not in request.POST:
        return 0
    try:
        parsed = parse_date(request.POST[field])
        return int(parsed.timestamp())
    except ValueError:
        return 0


async def _get_txt(request: HttpRequest) -> str:
    user = await request.auser()
    return urllib.parse.urlencode(
        {
            "user_id": user.pk,
            "unit_id": "%UNIT_ID%",
            "message": request.POST["message"],
            "msg_time_int": "%MSG_TIME_INT%",
            "location": "%LOCATION%",
            "unit_name": "%UNIT%",
        },
        safe="%",
    )


async def _get_sch(request: HttpRequest) -> dict[str, int]:
    schedule = {}
    schedule["f1"] = 0
    schedule["f2"] = 0
    schedule["t1"] = 0
    schedule["t2"] = 0
    schedule["m"] = 0
    schedule["y"] = 0
    schedule["w"] = 0
    return schedule


async def _get_tz(request: HttpRequest) -> int:
    if "timezone" not in request.POST:
        return 0
    try:
        return int(request.POST["timezone"])
    except ValueError:
        return 0


async def _get_trg(request: HttpRequest) -> dict[str, typing.Any]:
    p = {}
    trigger_form_fields = forms.get_trigger_form_fields()
    for field in request.POST:
        if field in trigger_form_fields:
            p[field] = request.POST[field]
    return {"t": request.POST["trigger"], "p": p}


async def _get_act(request: HttpRequest) -> list[dict[str, typing.Any]]:
    url = urllib.parse.urljoin(
        "https://api.terminusgps.com/v3/notify/", f"/{request.POST['method']}/"
    )
    return [{"t": "push_messages", "p": {"url": url, "get": 0}}]


async def _get_un(request: HttpRequest) -> list[int]:
    un = []
    input = request.POST.getlist("units", [])
    if not input:
        return []
    for unit_id in input:
        try:
            un.append(int(unit_id))
        except ValueError:
            continue
    return un


@never_cache
@htmx_template("terminusgps_notifier/create_notification.html")
async def create_notification(request: HttpRequest, **kwargs) -> HttpResponse:
    async def get_wialon_api_parameters(
        request: HttpRequest,
    ) -> dict[str, typing.Any]:
        params = {}
        params["itemId"] = int(request.POST["resource"])
        params["id"] = 0
        params["callMode"] = "create"
        params["n"] = request.POST["name"]
        params["txt"] = await _get_txt(request)
        params["ta"] = await _get_timestamp(request, "ta")
        params["td"] = await _get_timestamp(request, "td")
        params["ma"] = 0
        params["mmtd"] = 3600
        params["cdt"] = 0
        params["mast"] = 0
        params["mpst"] = 0
        params["cp"] = 0
        params["fl"] = 0
        params["tz"] = await _get_tz(request)
        params["la"] = "en"
        params["un"] = await _get_un(request)
        params["d"] = request.POST.get("d", "")
        params["sch"] = await _get_sch(request)
        params["ctrl_sch"] = await _get_sch(request)
        params["trg"] = await _get_trg(request)
        params["act"] = await _get_act(request)
        return params

    if request.method == "POST":
        try:
            user = await request.auser()
            token = await Customer.objects.aget_token_from_user(user)
            params = await get_wialon_api_parameters(request)
            with WialonSession(token=token) as session:
                session.wialon_api.resource_update_notification(**params)
                return redirect(
                    "terminusgps_notifier:list notification",
                    kwargs={"resource_id": request.POST["resource"]},
                )
        except WialonAPIError as error:
            msg = f"Failed to create notification for user: '{user}'"
            logger.error(msg)
            logger.error(error)
            messages.error(request, msg)
        except Customer.DoesNotExist as error:
            msg = f"No associated customer for user: '{user}'"
            logger.error(msg)
            logger.error(error)
            messages.error(request, msg)

    context = {}
    context["triggers"] = forms.WialonNotificationTrigger.choices
    context["timezones"] = constants.TIMEZONES
    return render(request, kwargs["template_name"], context=context)


@htmx_template("terminusgps_notifier/select_resource.html")
async def select_resource(request: HttpRequest, **kwargs) -> HttpResponse:
    async def get_resources_from_wialon(customer: Customer) -> list:
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
        user = await request.auser()
        customer = await Customer.objects.afrom_user(user)
        resource_list = await get_resources_from_wialon(customer)
    except WialonAPIError as error:
        msg = f"Failed to get resources from Wialon for user: {user}"
        logger.error(msg)
        logger.error(error)
        messages.error(request, msg)
        resource_list = []
    context = {}
    context["resource_list"] = resource_list
    return render(request, kwargs["template_name"], context=context)


@htmx_template("terminusgps_notifier/select_units.html")
async def select_units(request: HttpRequest, **kwargs) -> HttpResponse:
    async def get_items_from_wialon(customer: Customer) -> list:
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
        user = await request.auser()
        customer = await Customer.objects.afrom_user(user)
        items_list = await get_items_from_wialon(customer)
    except WialonAPIError as error:
        logger.error(f"Failed to get items from Wialon for user: {user}")
        logger.error(error)
        items_list = []
    context = {}
    context["items_list"] = items_list
    return render(request, kwargs["template_name"], context=context)


@htmx_template("terminusgps_notifier/trigger_parameters.html")
async def trigger_parameters(request: HttpRequest, **kwargs) -> HttpResponse:
    async def get_form(trigger: str | None = None):
        if not trigger:
            logger.error(f"No trigger provided: '{trigger}'")
            raise Http404()
        elif trigger not in forms.WialonNotificationTrigger:
            logger.error(f"Invalid trigger: '{trigger}'")
            raise Http404()
        else:
            form_class = forms.TRIGGER_FORMS_MAP[trigger]
            return form_class()

    form = await get_form(request.GET.get("trigger"))
    return render(request, kwargs["template_name"], context={"form": form})


@htmx_template("terminusgps_notifier/list_notification.html")
async def list_notification(request: HttpRequest, **kwargs) -> HttpResponse:
    async def get_notifications_from_wialon(customer: Customer) -> list:
        with WialonSession(token=customer.token) as session:
            params = {}
            params["itemId"] = kwargs["resource_id"]
            return session.wialon_api.resource_get_notification_data(**params)

    try:
        user = await request.auser()
        customer = await Customer.objects.afrom_user(user)
        notification_list = await get_notifications_from_wialon(customer)
    except WialonAPIError as error:
        msg = f"Failed to get notifications from Wialon for resource: #{kwargs['resource_id']}"
        logger.error(msg)
        logger.error(error)
        notification_list = []

    context = {}
    context["notification_list"] = notification_list
    context["resource_id"] = kwargs["resource_id"]
    return render(request, kwargs["template_name"], context=context)


@htmx_template("terminusgps_notifier/detail_notification.html")
async def detail_notification(request: HttpRequest, **kwargs) -> HttpResponse:
    async def get_notification_data_from_wialon(customer: Customer) -> list:
        with WialonSession(token=customer.token) as session:
            params = {}
            params["itemId"] = kwargs["resource_id"]
            params["col"] = [kwargs["notification_id"]]
            return session.wialon_api.resource_get_notification_data(**params)

    try:
        user = await request.auser()
        customer = await Customer.objects.afrom_user(user)
        response = await get_notification_data_from_wialon(customer)
        notification = response[0]
    except WialonAPIError as error:
        resource_id = kwargs["resource_id"]
        notification_id = kwargs["notification_id"]
        msg = f"Failed to get data from Wialon for notification: '#{resource_id}:{notification_id}'"
        logger.error(msg)
        logger.error(error)
        notification = None
    context = {}
    context["notification"] = notification
    return render(request, kwargs["template_name"], context=context)


@htmx_template("terminusgps_notifier/home.html")
async def home(request: HttpRequest, **kwargs) -> HttpResponse:
    return render(request, kwargs["template_name"], context={})


@htmx_template("terminusgps_notifier/dashboard.html")
async def dashboard(request: HttpRequest, **kwargs) -> HttpResponse:
    @sync_to_async
    def has_token(customer: Customer) -> bool:
        return customer.token is not None

    @sync_to_async
    def has_subscription(customer: Customer) -> bool:
        return customer.subscription is not None

    user = await request.auser()
    customer = await Customer.objects.afrom_user(user)
    context = {}
    context["customer"] = customer
    context["has_token"] = await has_token(customer)
    context["has_subscription"] = await has_subscription(customer)
    return render(request, kwargs["template_name"], context=context)


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
