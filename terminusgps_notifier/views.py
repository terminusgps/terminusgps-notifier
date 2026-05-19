import asyncio
import logging
import urllib.parse
import warnings

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.module_loading import import_string
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods
from django.views.generic import RedirectView, View
from terminusgps.wialon.session import WialonAPIError, WialonSession

from terminusgps_notifier import forms
from terminusgps_notifier.decorators import (
    HtmxHttpRequest,
    htmx_template,
    persistent_wialon_session,
)
from terminusgps_notifier.dispatchers import NotificationDispatcher
from terminusgps_notifier.models import Profile
from terminusgps_notifier.validators import validate_e164_phone_number

logger = logging.getLogger(__name__)


def get_stripe_client() -> stripe.StripeClient:
    return stripe.StripeClient(settings.STRIPE_API_KEY)


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
@htmx_template("terminusgps_notifier/home.html")
def home(request: HtmxHttpRequest) -> HttpResponse:
    return TemplateResponse(request, request.template_name, context={})


@require_GET
@htmx_template("terminusgps_notifier/contact.html")
def contact(request: HtmxHttpRequest) -> HttpResponse:
    return TemplateResponse(request, request.template_name, context={})


@require_GET
@htmx_template("terminusgps_notifier/terms.html")
def terms(request: HtmxHttpRequest) -> HttpResponse:
    return TemplateResponse(request, request.template_name, context={})


@require_GET
@htmx_template("terminusgps_notifier/privacy.html")
def privacy(request: HtmxHttpRequest) -> HttpResponse:
    return TemplateResponse(request, request.template_name, context={})


@require_GET
def source_code(request: HtmxHttpRequest) -> HttpResponse:
    return RedirectView.as_view(
        url="https://github.com/terminusgps/terminusgps-notifier",
        permanent=True,
    )(request)


@require_GET
@htmx_template("terminusgps_notifier/dashboard.html")
def dashboard(request: HtmxHttpRequest) -> HttpResponse:
    @transaction.atomic
    def save_subscription_to_profile(
        request: HtmxHttpRequest, profile: Profile
    ) -> Profile:
        stripe_client = get_stripe_client()
        checkout_id = str(profile.checkout_id)
        session = stripe_client.v1.checkout.sessions.retrieve(checkout_id)
        if not session.subscription:
            profile.checkout_id = None
            update_fields = ["checkout_id"]
            messages.warning(request, "Subcription creation failed.")
        else:
            profile.checkout_id = None
            profile.customer_id = session.customer
            profile.subscription_id = session.subscription
            update_fields = ["checkout_id", "customer_id", "subscription_id"]
            messages.success(request, "Subscription created succesfully.")
        profile.save(update_fields=update_fields)
        return profile

    @transaction.atomic
    def save_wialon_api_token_to_profile(
        request: HtmxHttpRequest, profile: Profile
    ) -> Profile:
        profile.token = str(request.GET.get("access_token"))
        profile.save(update_fields=["token"])
        messages.success(request, "Wialon account connected successfully.")
        return profile

    profile, _ = Profile.objects.get_or_create(user=request.user)
    if profile.checkout_id:
        save_subscription_to_profile(request, profile)
    if request.GET.get("access_token"):
        save_wialon_api_token_to_profile(request, profile)
    context = {
        "profile": profile,
        "wialon_redirect_uri": request.build_absolute_uri(
            reverse("terminusgps_notifier:dashboard")
        ),
    }
    return TemplateResponse(request, request.template_name, context=context)


@require_GET
@persistent_wialon_session
@htmx_template("terminusgps_notifier/list_resources.html")
def list_resources(request: HtmxHttpRequest) -> HttpResponse:
    try:
        session = WialonSession(sid=request.session["wialon_sid"])
        params = {"spec": {}, "force": 0, "from": 0, "to": 0, "flags": 1}
        params["spec"]["itemsType"] = "avl_resource"
        params["spec"]["propName"] = "sys_name"
        params["spec"]["propValueMask"] = "*"
        params["spec"]["propType"] = "property"
        params["spec"]["sortType"] = "sys_name"
        response = session.wialon_api.core_search_items(**params)
        resource_list = response["items"]
    except WialonAPIError as error:
        messages.error(request, error)
        resource_list = None
    context = {"resource_list": resource_list}
    return TemplateResponse(request, request.template_name, context=context)


@require_GET
@persistent_wialon_session
@htmx_template("terminusgps_notifier/list_notifications.html")
def list_notifications(
    request: HtmxHttpRequest, resource_id: str
) -> HttpResponse:
    try:
        session = WialonSession(sid=request.session["wialon_sid"])
        params = {"itemId": resource_id}
        response = session.wialon_api.resource_get_notification_data(**params)
    except WialonAPIError as error:
        messages.error(request, error)
        response = None
    context = {"response": response}
    return TemplateResponse(request, request.template_name, context=context)


@require_GET
@persistent_wialon_session
@htmx_template("terminusgps_notifier/detail_resources.html")
def detail_resources(
    request: HtmxHttpRequest, resource_id: str
) -> HttpResponse:
    try:
        session = WialonSession(sid=request.session["wialon_sid"])
        params = {"id": resource_id, "flags": 1025}
        response = session.wialon_api.core_search_item(**params)
    except WialonAPIError as error:
        messages.error(request, error)
        response = None
    context = {"response": response}
    return TemplateResponse(request, request.template_name, context=context)


@require_GET
@persistent_wialon_session
@htmx_template("terminusgps_notifier/select_units.html")
def select_units(request: HtmxHttpRequest, resource_id: str) -> HttpResponse:
    try:
        session = WialonSession(sid=request.session["wialon_sid"])
        params = {"spec": {}, "force": 0, "from": 0, "to": 0, "flags": 1}
        params["spec"]["itemsType"] = request.GET.get("items_type", "avl_unit")
        params["spec"]["propName"] = "sys_name,sys_billing_account_guid"
        params["spec"]["propValueMask"] = f"*,{resource_id}"
        params["spec"]["propType"] = "property,property"
        params["spec"]["sortType"] = "sys_name"
        response = session.wialon_api.core_search_items(**params)
    except WialonAPIError as error:
        messages.warning(request, error)
        response = {"items": []}
    context = {"object_list": response["items"]}
    return TemplateResponse(request, request.template_name, context=context)


@require_GET
def create_subscription(request: HtmxHttpRequest) -> HttpResponse:
    stripe = get_stripe_client()
    profile = get_object_or_404(Profile, user=request.user)
    checkout_session = stripe.v1.checkout.sessions.create(
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


@never_cache
@require_GET
def billing_portal(request: HtmxHttpRequest, customer_id: str) -> HttpResponse:
    stripe_client = get_stripe_client()
    session = stripe_client.v1.billing_portal.sessions.create(
        {
            "customer": customer_id,
            "return_url": request.build_absolute_uri(
                reverse("terminusgps_notifier:dashboard")
            ),
        }
    )
    return redirect(session.url)


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/create_notification_step_one.html")
def create_notification_step_one(
    request: HtmxHttpRequest, resource_id: str
) -> HttpResponse:
    if request.method == "POST":
        units_list = request.POST.getlist("units", [])
        step_one_data = {"un": units_list, "itemId": resource_id}
        request.session["step_one_data"] = step_one_data
        return redirect("terminusgps_notifier:create notification step two")
    context = {"resource_id": resource_id}
    return TemplateResponse(request, request.template_name, context=context)


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/create_notification_step_two.html")
def create_notification_step_two(request: HtmxHttpRequest) -> HttpResponse:
    if request.method == "POST":
        p = {}
        for field in request.POST:
            if field not in ("csrfmiddlewaretoken", "t"):
                p.update({field: request.POST[field]})
        trg = {"t": request.POST["t"], "p": p}
        request.session["step_two_data"] = {"trg": trg}
        return redirect("terminusgps_notifier:create notification step three")
    context = {"triggers": forms.WialonNotificationTrigger.choices}
    return TemplateResponse(request, request.template_name, context=context)


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/create_notification_step_three.html")
def create_notification_step_three(request: HtmxHttpRequest) -> HttpResponse:
    def generate_txt(request: HtmxHttpRequest) -> str:
        return urllib.parse.urlencode(
            {
                "user_id": request.user.pk,
                "unit_id": "%UNIT_ID%",
                "message": request.POST["message"],
                "msg_time_int": "%MSG_TIME_INT%",
                "location": "%LOCATION%",
                "unit_name": "%UNIT%",
            },
            safe="%",
        )

    def generate_act(request: HtmxHttpRequest) -> list[dict]:
        url = urllib.parse.urljoin(
            "https://api.terminusgps.com/",  # TODO: Retrieve host programatically
            f"/v3/notify/{request.POST['method']}/",
        )
        return [{"t": "send_messages", "p": {"url": url, "get": 0}}]

    if request.method == "POST":
        n = request.POST["name"]
        txt = generate_txt(request)
        act = generate_act(request)
        request.session["step_three_data"] = {"n": n, "txt": txt, "act": act}
        return redirect("terminusgps_notifier:create notification step four")
    else:
        return TemplateResponse(request, request.template_name, context={})


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/create_notification_step_four.html")
def create_notification_step_four(request: HtmxHttpRequest) -> HttpResponse:
    return TemplateResponse(request, request.template_name, context={})


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/create_notification_step_review.html")
def create_notification_step_review(request: HtmxHttpRequest) -> HttpResponse:
    return TemplateResponse(request, request.template_name, context={})


@require_GET
@htmx_template("terminusgps_notifier/forms/trigger_parameters.html")
def trigger_parameters_form(request: HtmxHttpRequest) -> HttpResponse:
    if not request.GET.get("t"):
        raise Http404()
    t = str(request.GET.get("t"))
    if t not in forms.WialonNotificationTrigger:
        raise Http404()
    form_cls = forms.TRIGGER_FORMS_MAP[t]
    context = {"form": form_cls()}
    return TemplateResponse(request, request.template_name, context=context)
