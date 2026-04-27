import asyncio
import logging
import warnings

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.module_loading import import_string
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods
from django.views.generic import RedirectView, View
from terminusgps.wialon.session import WialonAPIError, WialonSession
from terminusgps_payments.models import Subscription

from terminusgps_notifier import forms
from terminusgps_notifier.decorators import htmx_template
from terminusgps_notifier.dispatchers import NotificationDispatcher
from terminusgps_notifier.models import Customer
from terminusgps_notifier.validators import validate_e164_phone_number
from terminusgps_notifier.wialon import get_phone_numbers

logger = logging.getLogger(__name__)


@sync_to_async
def get_customer_username(customer: Customer) -> str:
    return customer.user.username


@sync_to_async
def get_customer_token(customer: Customer) -> str | None:
    return customer.token


@sync_to_async
def get_customer_subscription(customer: Customer) -> Subscription | None:
    return customer.subscription


@sync_to_async
def get_customer_messages_limit(customer: Customer) -> int:
    return customer.messages_limit


@sync_to_async
def get_customer_messages_count(customer: Customer) -> int:
    return customer.messages_count


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


@never_cache
@require_GET
@htmx_template("terminusgps_notifier/wialon_callback.html")
async def wialon_callback(request: HttpRequest, **kwargs) -> HttpResponse:
    user = await request.auser()
    customer, _ = await Customer.objects.aget_or_create(user=user)
    token_saved = False
    if access_token := request.GET.get("access_token"):
        customer.token = access_token
        await customer.asave(update_fields=["token"])
        token_saved = True
    context = {"token_saved": token_saved}
    return render(request, kwargs["template_name"], context=context)


@require_GET
@htmx_template("terminusgps_notifier/home.html")
async def home(request: HttpRequest, **kwargs) -> HttpResponse:
    return render(request, kwargs["template_name"], context={})


@require_GET
@htmx_template("terminusgps_notifier/contact.html")
async def contact(request: HttpRequest, **kwargs) -> HttpResponse:
    return render(request, kwargs["template_name"], context={})


@require_GET
@htmx_template("terminusgps_notifier/terms.html")
async def terms(request: HttpRequest, **kwargs) -> HttpResponse:
    return render(request, kwargs["template_name"], context={})


@require_GET
@htmx_template("terminusgps_notifier/privacy.html")
async def privacy(request: HttpRequest, **kwargs) -> HttpResponse:
    return render(request, kwargs["template_name"], context={})


@require_GET
@htmx_template("terminusgps_notifier/navbar.html")
async def navbar(request: HttpRequest, **kwargs) -> HttpResponse:
    return render(
        request,
        kwargs["template_name"],
        context={"user": await request.auser()},
    )


@require_GET
async def source_code(request: HttpRequest) -> HttpResponse:
    return RedirectView.as_view(
        url="https://github.com/terminusgps/terminusgps-notifier",
        permanent=True,
    )(request)


@never_cache
@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/create_notification.html")
async def create_notification(request: HttpRequest, **kwargs) -> HttpResponse:
    if request.method == "GET":
        pass
    elif request.method == "POST":
        pass
    return render(request, kwargs["template_name"], context={})


@require_GET
@htmx_template("terminusgps_notifier/select_resource.html")
async def select_resource(request: HttpRequest, **kwargs) -> HttpResponse:
    try:
        resource_list = []
        user = await request.auser()
        customer = await Customer.objects.aget(user=user)
        token = await get_customer_token(customer)
        with WialonSession(token=token) as session:
            params = {"spec": {}, "force": 0, "from": 0, "to": 0, "flags": 1}
            params["spec"]["itemsType"] = "avl_resource"
            params["spec"]["propName"] = "sys_name"
            params["spec"]["propValueMask"] = "*"
            params["spec"]["propType"] = "property"
            params["spec"]["sortType"] = "sys_name"
            response = session.wialon_api.core_search_items(**params)
            resource_list = response["items"]
    except WialonAPIError as error:
        msg = f"Failed to get resources from Wialon for user: {user}"
        logger.error(msg)
        logger.error(error)
        messages.error(request, msg)
    except Customer.DoesNotExist:
        msg = f"No associated customer for user: {user}"
        logger.error(msg)
        messages.error(request, msg)

    context = {"resource_list": resource_list}
    return render(request, kwargs["template_name"], context=context)


@require_GET
@htmx_template("terminusgps_notifier/select_units.html")
async def select_units(request: HttpRequest, **kwargs) -> HttpResponse:
    try:
        items_list = []
        user = await request.auser()
        customer = await Customer.objects.aget(user)
        token = await get_customer_token(customer)
        with WialonSession(token=token) as session:
            params = {"spec": {}, "force": 0, "from": 0, "to": 0, "flags": 1}
            params["spec"]["itemsType"] = request.GET["items_type"]
            params["spec"]["propName"] = "sys_name,sys_billing_account_guid"
            params["spec"]["propValueMask"] = f"*,{request.GET['resource']}"
            params["spec"]["propType"] = "property,property"
            params["spec"]["sortType"] = "sys_name"
            response = session.wialon_api.core_search_items(**params)
            items_list = response["items"]
    except WialonAPIError as error:
        logger.error(f"Failed to get items from Wialon for user: {user}")
        logger.error(error)
    except Customer.DoesNotExist:
        msg = f"No associated customer for user: {user}"
        logger.error(msg)
        messages.error(request, msg)

    context = {"items_list": items_list}
    return render(request, kwargs["template_name"], context=context)


@require_GET
@htmx_template("terminusgps_notifier/list_notification.html")
async def list_notification(request: HttpRequest, **kwargs) -> HttpResponse:
    try:
        notification_list = []
        user = await request.auser()
        customer = await Customer.objects.aget(user)
        token = await get_customer_token(customer)
        with WialonSession(token=token) as session:
            notification_list = (
                session.wialon_api.resource_get_notification_data(
                    **{"itemId": kwargs["resource_id"]}
                )
            )
    except WialonAPIError as error:
        msg = f"Failed to get notifications from Wialon for resource: #{kwargs['resource_id']}"
        logger.error(msg)
        logger.error(error)
    except Customer.DoesNotExist:
        msg = f"No associated customer for user: {user}"
        logger.error(msg)
        messages.error(request, msg)

    context = {
        "notification_list": notification_list,
        "resource_id": kwargs["resource_id"],
    }
    return render(request, kwargs["template_name"], context=context)


@require_GET
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


@require_GET
@htmx_template("terminusgps_notifier/dashboard.html")
async def dashboard(request: HttpRequest, **kwargs) -> HttpResponse:
    return render(request, kwargs["template_name"], context={})


@require_GET
@htmx_template("terminusgps_notifier/stats.html")
async def stats(request: HttpRequest, **kwargs) -> HttpResponse:
    try:
        user = await request.auser()
        customer = await Customer.objects.aget(user=user)
        username = await get_customer_username(customer)
        has_token = bool(await get_customer_token(customer))
        has_subscription = bool(await get_customer_subscription(customer))
        messages_count = await get_customer_messages_count(customer)
        messages_limit = await get_customer_messages_limit(customer)
    except Customer.DoesNotExist:
        username = None
        has_token = False
        has_subscription = False
        messages_count = 0
        messages_limit = 0

    context = {}
    context["username"] = username
    context["has_token"] = has_token
    context["has_subscription"] = has_subscription
    context["messages_count"] = messages_count
    context["messages_limit"] = messages_limit
    context["redirect_uri"] = request.build_absolute_uri(
        reverse("terminusgps_notifier:wialon callback")
    )
    return render(request, kwargs["template_name"], context=context)
