import asyncio
import logging
import typing
import warnings

from asgiref.sync import sync_to_async
from django.conf import settings
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
from terminusgps_notifier.wialon import (
    get_items,
    get_notification_data,
    get_phone_numbers,
    get_resources,
)

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
async def dashboard(request: HttpRequest) -> HttpResponse:
    @sync_to_async
    def get_customer_data(request: HttpRequest) -> dict[str, typing.Any]:
        customer, _ = Customer.objects.get_or_create(user=request.user)
        context = {}
        context["username"] = customer.user.username
        context["has_token"] = customer.token is not None
        context["has_subscription"] = customer.subscription is not None
        context["messages_count"] = customer.messages_count
        context["messages_limit"] = customer.messages_limit
        return context

    context = {}
    location = reverse("terminusgps_notifier:wialon callback")
    context["redirect_uri"] = request.build_absolute_uri(location)
    context.update(await get_customer_data(request))
    return render(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/list_resources.html")
async def list_resources(request: HttpRequest) -> HttpResponse:
    context = {}
    try:
        user = await request.auser()
        customer, _ = await Customer.objects.aget_or_create(user=user)
        with WialonSession(token=customer.token) as session:
            response = await get_resources(session)
            context["resource_list"] = response["items"]
    except WialonAPIError as error:
        print(error)
        context["resource_list"] = []
    return render(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/detail_resources.html")
async def detail_resources(
    request: HttpRequest, resource_id: int
) -> HttpResponse:
    context = {"resource_id": resource_id}
    return render(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/list_notifications.html")
async def list_notifications(
    request: HttpRequest, resource_id: int
) -> HttpResponse:
    context = {}
    try:
        user = await request.auser()
        customer, _ = await Customer.objects.aget_or_create(user=user)
        with WialonSession(token=customer.token) as session:
            response = await get_notification_data(session, resource_id)
            context["notifications_list"] = response
    except WialonAPIError as error:
        print(error)
        context["notifications_list"] = []
    return render(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/detail_notifications.html")
async def detail_notifications(
    request: HttpRequest, resource_id: int, notification_id: int
) -> HttpResponse:
    context = {}
    try:
        user = await request.auser()
        customer, _ = await Customer.objects.aget_or_create(user=user)
        with WialonSession(token=customer.token) as session:
            response = await get_notification_data(
                session, resource_id, [notification_id]
            )
            context["notification_data"] = response[0]
    except WialonAPIError as error:
        print(error)
        context["notification_data"] = {}
    return render(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/select_units_options.html")
async def select_units_options(
    request: HttpRequest, resource_id: int
) -> HttpResponse:
    context: dict[str, typing.Any] = {}
    try:
        user = await request.auser()
        customer, _ = await Customer.objects.aget_or_create(user=user)
        with WialonSession(token=customer.token) as session:
            items_type = str(request.GET.get("items_type", "avl_unit"))
            response = await get_items(session, resource_id, items_type)
            context["items_list"] = response["items"]
    except WialonAPIError as error:
        print(error)
        context["items_list"] = []
    return render(request, request.template_name, context=context)


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/select_units_form.html")
async def select_units_form(
    request: HttpRequest, resource_id: int
) -> HttpResponse:
    async def clean_units_list(units_list: list[str]) -> list[int]:
        cleaned = []
        for id in units_list:
            if id.isdigit():
                cleaned.append(int(id))
        return cleaned

    if request.POST:
        user_input = request.POST.getlist("units", [])
        units_list = await clean_units_list(user_input)
        await request.session.aset("units_list", units_list)
        return redirect("terminusgps_notifier:select triggers form")
    else:
        context = {"resource_id": resource_id}
        return render(request, request.template_name, context=context)


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/select_triggers_form.html")
async def select_triggers_form(request: HttpRequest) -> HttpResponse:
    if request.POST:
        parameter_fields = [
            field
            for field in request.POST.keys()
            if field not in ("csrfmiddlewaretoken", "trigger")
        ]
        t = request.POST["trigger"]
        p = {field: request.POST[field] for field in parameter_fields}
        await request.session.aset("trg", {"t": t, "p": p})
        return redirect("terminusgps_notifier:create notification form")
    else:
        context = {"triggers": forms.WialonNotificationTrigger.choices}
        return render(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/trigger_parameters.html")
async def trigger_parameters(request: HttpRequest) -> HttpResponse:
    async def get_form_cls(trigger: str) -> Form:
        if trigger not in forms.TRIGGER_FORMS_MAP:
            raise ValueError(f"Invalid trigger: '{trigger}'")
        return forms.TRIGGER_FORMS_MAP[trigger]

    try:
        trigger = str(request.GET.get("trigger"))
        form_cls = await get_form_cls(trigger)
    except ValueError:
        form_cls = Form
    context = {"form": form_cls()}
    return render(request, request.template_name, context=context)
