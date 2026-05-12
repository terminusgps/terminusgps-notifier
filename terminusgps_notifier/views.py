import asyncio
import logging
import urllib.parse
import warnings

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.forms import Form
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.module_loading import import_string
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
    require_POST,
)
from django.views.generic import RedirectView, View
from terminusgps.wialon.session import WialonAPIError, WialonSession

from terminusgps_notifier import constants, forms
from terminusgps_notifier.decorators import HtmxHttpRequest, htmx_template
from terminusgps_notifier.dispatchers import NotificationDispatcher
from terminusgps_notifier.models import Profile
from terminusgps_notifier.validators import validate_e164_phone_number
from terminusgps_notifier.wialon import (
    create_notification,
    get_notification_data,
    search_item,
    search_items,
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


class TerminusGPSNotifierLoginView(LoginView):
    next_page = reverse_lazy("terminusgps_notifier:dashboard")
    redirect_authenticated_user = True
    template_name = "terminusgps_notifier/login.html"


class TerminusGPSNotifierLogoutView(LogoutView):
    next_page = reverse_lazy("terminusgps_notifier:home")
    template_name = "terminusgps_notifier/logged_out.html"


@require_GET
def wialon_login(request: HttpRequest) -> HttpResponse:
    return RedirectView.as_view(
        url="https://hosting.terminusgps.com/login.html",
        permanent=True,
        query_string=True,
    )(request)


@require_GET
@never_cache
@htmx_template("terminusgps_notifier/wialon_callback.html")
def wialon_callback(request: HtmxHttpRequest) -> HttpResponse:
    profile = get_object_or_404(Profile, user=request.user)
    token_saved = False
    if access_token := request.GET.get("access_token"):
        profile.token = access_token
        profile.save(update_fields=["token"])
        token_saved = True
    context = {"token_saved": token_saved}
    return TemplateResponse(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/home.html")
def home(request: HtmxHttpRequest) -> HttpResponse:
    context = {}
    return TemplateResponse(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/contact.html")
def contact(request: HtmxHttpRequest) -> HttpResponse:
    context = {}
    return TemplateResponse(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/terms.html")
def terms(request: HtmxHttpRequest) -> HttpResponse:
    context = {}
    return TemplateResponse(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/privacy.html")
def privacy(request: HtmxHttpRequest) -> HttpResponse:
    context = {}
    return TemplateResponse(request, request.template_name, context=context)


@require_GET
def source_code(request: HtmxHttpRequest) -> HttpResponse:
    return RedirectView.as_view(
        url="https://github.com/terminusgps/terminusgps-notifier",
        permanent=True,
    )(request)


@require_GET
@htmx_template("terminusgps_notifier/dashboard.html")
def dashboard(request: HtmxHttpRequest) -> HttpResponse:
    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=request.user)
    if profile.checkout_id is not None:
        client = stripe.StripeClient(settings.STRIPE_API_KEY)
        session = client.v1.checkout.sessions.retrieve(profile.checkout_id)
        profile.customer_id = session.customer
        profile.subscription_id = session.subscription
        profile.checkout_id = None
        profile.save()
        messages.success(request, "Subscription successfully created.")
    redirect_uri = request.build_absolute_uri(
        reverse("terminusgps_notifier:wialon callback")
    )
    context = {"profile": profile, "redirect_uri": redirect_uri}
    return TemplateResponse(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/list_resources.html")
def list_resources(request: HtmxHttpRequest) -> HttpResponse:
    context = {}
    try:
        profile = get_object_or_404(Profile, user=request.user)
        with WialonSession(token=profile.token) as session:
            response = search_items(
                session=session,
                items_type="avl_resource",
                prop_name="sys_name",
                prop_value_mask="*",
                sort_type="sys_name",
                prop_type="property",
                flags=1025,
            )
            context["resource_list"] = response["items"]
    except WialonAPIError as error:
        if error.code == 6:
            msg = "Failed to retrieve resources from Wialon. Is your Wialon account connected?"
        else:
            msg = str(error)
        messages.warning(request, msg)
        context["resource_list"] = []
    return TemplateResponse(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/detail_resources.html")
def detail_resources(
    request: HtmxHttpRequest, resource_id: int
) -> HttpResponse:
    context = {}
    try:
        profile = get_object_or_404(Profile, user=request.user)
        with WialonSession(token=profile.token) as session:
            response = search_item(session=session, id=resource_id, flags=1025)
            context["resource"] = response["item"]
    except WialonAPIError as error:
        print(error)
        context["resource"] = {}
    return TemplateResponse(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/detail_notifications.html")
def detail_notifications(
    request: HtmxHttpRequest, resource_id: int, notification_id: int
) -> HttpResponse:
    def get_notification_method(notification: dict) -> str | None:
        for action in notification["act"]:
            if (
                action["t"] == "push_messages"
                and "api.terminusgps.com" in action["p"]["url"]
            ):
                split_url = urllib.parse.urlsplit(action["p"]["url"])
                parts = list(filter(None, split_url.path.split("/")))
                return parts[-1]

    context = {}
    try:
        profile = get_object_or_404(Profile, user=request.user)
        with WialonSession(token=profile.token) as session:
            response = get_notification_data(
                session, resource_id, [notification_id]
            )
            context["notification"] = response[0]
            context["method"] = get_notification_method(response[0])
    except WialonAPIError as error:
        print(error)
        context["notification"] = {}
        context["method"] = None
    return TemplateResponse(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/select/resources.html")
def select_resources(request: HtmxHttpRequest) -> HttpResponse:
    context = {}
    try:
        profile = get_object_or_404(Profile, user=request.user)
        with WialonSession(token=profile.token) as session:
            response = search_items(
                session=session,
                items_type="avl_resource",
                prop_name="sys_name",
                prop_value_mask="*",
                sort_type="sys_name",
                prop_type="property",
            )
            context["options"] = response["items"]
    except WialonAPIError as error:
        print(error)
        context["options"] = []
    return TemplateResponse(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/select/units.html")
def select_units(request: HtmxHttpRequest, resource_id: int) -> HttpResponse:
    context = {}
    try:
        profile = get_object_or_404(Profile, user=request.user)
        with WialonSession(token=profile.token) as session:
            response = search_items(
                session=session,
                items_type=str(request.GET.get("items_type", "avl_unit")),
                prop_name="sys_name,sys_billing_account_guid",
                prop_value_mask=f"*,{resource_id}",
                sort_type="sys_name",
                prop_type="property,property",
            )
            context["options"] = response["items"]
    except WialonAPIError as error:
        print(error)
        context["options"] = []
    return TemplateResponse(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/detail_units.html")
def detail_units(request: HtmxHttpRequest, unit_id: int) -> HttpResponse:
    context = {}
    try:
        profile = get_object_or_404(Profile, user=request.user)
        with WialonSession(token=profile.token) as session:
            response = search_item(session, unit_id)
            context["unit"] = response["item"]
    except WialonAPIError as error:
        print(error)
        context["unit"] = {}
    return TemplateResponse(request, request.template_name, context=context)


@require_GET
@htmx_template("terminusgps_notifier/trigger_parameters.html")
def trigger_parameters(request: HtmxHttpRequest) -> HttpResponse:
    trigger = str(request.GET.get("trigger"))
    if trigger in forms.WialonNotificationTrigger:
        form_cls = forms.TRIGGER_FORMS_MAP[trigger]
    else:
        form_cls = Form
    context = {"form": form_cls()}
    return TemplateResponse(request, request.template_name, context=context)


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/forms/units.html")
def units_form(request: HtmxHttpRequest, resource_id: int) -> HttpResponse:
    if request.method == "POST":
        units_list = request.POST.getlist("units", [])
        request.session["units_list"] = units_list
        return redirect(
            "terminusgps_notifier:trigger form", resource_id=resource_id
        )
    context = {"resource_id": resource_id}
    return TemplateResponse(request, request.template_name, context=context)


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/forms/trigger.html")
def trigger_form(request: HtmxHttpRequest, resource_id: int) -> HttpResponse:
    if request.method == "POST":
        t = request.POST["trigger"]
        p = {
            field: request.POST[field]
            for field in request.POST
            if field not in ("trigger", "csrfmiddlewaretoken")
        }
        request.session["trg"] = {"t": t, "p": p}
        return redirect(
            "terminusgps_notifier:create notifications",
            resource_id=resource_id,
        )
    context = {
        "resource_id": resource_id,
        "triggers": forms.WialonNotificationTrigger.choices,
    }
    return TemplateResponse(request, request.template_name, context=context)


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/create_notifications.html")
def create_notifications(
    request: HtmxHttpRequest, resource_id: int
) -> HttpResponse:
    if request.method == "POST":
        try:
            profile = get_object_or_404(Profile, user=request.user)
            with WialonSession(token=profile.token) as session:
                txt = urllib.parse.urlencode(
                    {
                        "user_id": request.user.pk,
                        "unit_id": "%UNIT_ID%",
                        "message": str(request.POST["message"]),
                        "msg_time_int": "%MSG_TIME_INT%",
                        "location": "%LOCATION%",
                        "unit_name": "%UNIT%",
                    },
                    safe="%",
                )
                act = [
                    {
                        "t": "push_messages",
                        "p": {
                            "url": urllib.parse.urljoin(
                                "https://api.terminusgps.com/",
                                f"/v3/notify/{request.POST['method']}/",
                            ),
                            "get": 0,
                        },
                    }
                ]
                sch = {
                    "f1": 0,
                    "f2": 0,
                    "t1": 0,
                    "t2": 0,
                    "m": 0,
                    "w": 0,
                    "y": 0,
                }
                response = create_notification(
                    session,
                    resource_id=resource_id,
                    n=str(request.POST["n"]),
                    txt=txt,
                    ta=0,
                    td=0,
                    ma=int(request.POST["ma"]),
                    mmtd=int(request.POST["mmtd"]),
                    cdt=int(request.POST["cdt"]),
                    mast=int(request.POST["mast"]),
                    mpst=int(request.POST["mpst"]),
                    cp=int(request.POST["cp"]),
                    fl=int(request.POST["fl"]),
                    tz=int(request.POST["tz"]),
                    la=str(request.POST["la"]),
                    un=request.session.get("units_list", []),
                    sch=sch,
                    ctrl_sch=sch,
                    trg=request.session.get("trg", {}),
                    act=act,
                )
                return redirect(
                    "terminusgps_notifier:detail notifications",
                    resource_id=resource_id,
                    notification_id=response[0],
                )
        except WialonAPIError as error:
            messages.error(request, error)
    context = {"resource_id": resource_id, "timezones": constants.TIMEZONES}
    return TemplateResponse(request, request.template_name, context=context)


@require_GET
def create_subscription(request: HtmxHttpRequest) -> HttpResponse:
    client = stripe.StripeClient(settings.STRIPE_API_KEY)
    profile = get_object_or_404(Profile, user=request.user)
    checkout_session = client.v1.checkout.sessions.create(
        params={
            "line_items": [
                {"price": "price_1TVx8iGphupvKam1plxSWh2D", "quantity": 1}
            ],
            "mode": "subscription",
            "success_url": request.build_absolute_uri(
                reverse("terminusgps_notifier:dashboard")
            ),
        }
    )
    profile.checkout_id = checkout_session.id
    profile.save(update_fields=["checkout_id"])
    return redirect(checkout_session.url)


@require_GET
@htmx_template("terminusgps_notifier/detail_subscription.html")
def detail_subscription(request: HtmxHttpRequest) -> HttpResponse:
    client = stripe.StripeClient(settings.STRIPE_API_KEY)
    profile = get_object_or_404(Profile, user=request.user)
    if profile.subscription_id:
        subscription = client.v1.subscriptions.retrieve(
            profile.subscription_id
        )
        context = {"subscription": subscription.to_dict()}
    else:
        context = {"subscription": None}
    return TemplateResponse(request, request.template_name, context=context)


@require_POST
def cancel_subscription(request: HtmxHttpRequest) -> HttpResponse:
    client = stripe.StripeClient(settings.STRIPE_API_KEY)
    profile = get_object_or_404(Profile, user=request.user)
    client.v1.subscriptions.cancel(profile.subscription_id)
    profile.subscription_id = None
    profile.save(update_fields=["subscription_id"])
    messages.success(request, "Subscription succesfully canceled.")
    return redirect("terminusgps_notifier:dashboard")
