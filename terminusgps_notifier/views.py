import asyncio
import logging
import urllib.parse

import stripe
from asgiref.sync import async_to_sync
from authorizenet import apicontractsv1
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView, redirect_to_login
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.utils.module_loading import import_string
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
    require_POST,
)
from django.views.generic import RedirectView
from terminusgps.authorizenet import api
from terminusgps.authorizenet.service import (
    AuthorizenetError,
    AuthorizenetService,
)
from terminusgps.wialon.session import WialonAPIError, WialonSession

from terminusgps_notifier import constants, forms
from terminusgps_notifier.decorators import (
    HtmxHttpRequest,
    htmx_template,
    persistent_wialon_session,
)
from terminusgps_notifier.dispatchers import NotificationDispatcher
from terminusgps_notifier.models import Profile
from terminusgps_notifier.validators import validate_e164_phone_number
from terminusgps_notifier.wialon import get_phone_numbers_by_id

logger = logging.getLogger(__name__)


def clean_phones(phones: list[str]) -> list[str]:
    """
    Cleans and returns a list of E.164 format phone numbers.

    :param phones: A list of phone numbers.
    :type phones: list[str]
    :returns: A list of properly formatted E.164 phone numbers.
    :rtype: list[str]

    """
    cleaned = []
    for phone in phones:
        try:
            validate_e164_phone_number(phone)
            cleaned.append(phone)
        except ValidationError as error:
            logger.warning(error.message)
            continue
    return cleaned


def get_phones(token: str | None, unit_id: int) -> list[str]:
    """
    Calls the Wialon API and returns a list of phone numbers assigned to a unit.

    Returns an empty list if something went wrong during the Wialon API call.

    :param token: A Wialon API token. If not provided, immediately returns an empty list.
    :type token: str | None
    :param unit_id: A Wialon unit id.
    :type unit_id: int
    :returns: A list of phone numbers assigned to the Wialon unit.
    :rtype: list[str]

    """
    if token is None:
        return []
    try:
        with WialonSession(token=token) as session:
            dirty_phones = get_phone_numbers_by_id(unit_id, session)
            return clean_phones(dirty_phones)
    except WialonAPIError as error:
        logger.error(error)
        return []


def get_dispatchers(
    form: forms.NotificationDispatchForm, method: str
) -> list[NotificationDispatcher]:
    """
    Returns a list of notification dispatchers.

    :param form: A valid notification dispatch form.
    :type form: :py:obj:`~django.forms.Form`
    :param method: A notification method.
    :type method: str
    :raises ValueError: If the provided method was invalid.
    :returns: A list of notification dispatcher objects.
    :rtype: list[NotificationDispatcher]

    """
    if method not in settings.NOTIFICATION_DISPATCHERS:
        raise ValueError(f"Invalid method: '{method}'")
    dispatcher_classes = []
    for dispatcher_path in settings.NOTIFICATION_DISPATCHERS[method]:
        dispatcher_cls = import_string(dispatcher_path)
        dispatcher_classes.append(dispatcher_cls)
    return [dispatcher(form) for dispatcher in dispatcher_classes]


@async_to_sync
async def send_notifications(method, phones, dispatchers) -> HttpResponse:
    """
    Sends notifications to target phone numbers using dispatchers.

    :param method: A notification method.
    :type method: str
    :param phones: A list of E.164 formatted phone numbers.
    :type phones: list[str]
    :param dispatchers: A list of notification dispatchers.
    :type dispatchers: list[NotificationDispatcher]
    :returns: An HTTP response with status code 200 if successful delivery.
    :rtype: :py:obj:`~django.http.HttpResponse`

    """
    for dispatcher in dispatchers:
        try:
            tasks = [
                dispatcher.send_notification(to_number=phone, method=method)
                for phone in phones
            ]
            await asyncio.gather(*tasks)
            return HttpResponse(
                f"Dispatched via {type(dispatcher).__name__}".encode("utf-8"),
                status=200,
            )
        except Exception as error:
            logger.warning(f"{type(dispatcher).__name__} failed: '{error}'")
    return HttpResponse(
        f"All dispatchers failed for method: '{method}'".encode("utf-8"),
        status=500,
    )


def get_subscription_status(profile: Profile) -> str | None:
    """
    Returns the current subscription status for a profile.

    If the profile is associated with a staff user, always returns "active".

    :param profile: A user profile.
    :type profile: :py:obj:`~terminusgps_notifier.models.Profile`
    :returns: The profile's subscription status, if any.
    :rtype: str | None

    """
    if profile.user.is_staff:
        return "active"
    if profile.subscription_id is None:
        return
    stripe_client = get_stripe_client()
    response = stripe_client.v1.subscriptions.retrieve(profile.subscription_id)
    return str(response.status)


def get_stripe_client() -> stripe.StripeClient:
    """Returns an authenticated stripe client."""
    return stripe.StripeClient(settings.STRIPE_API_KEY)


def get_wialon_session(sid: str) -> WialonSession:
    """Returns a Wialon API session based on the provided session id."""
    return WialonSession(sid=sid)


@require_POST
@csrf_exempt
def notify(request: HttpRequest, method: str) -> HttpResponse:
    """
    Delivers notifications to destination phone numbers via `method`.

    Returns:

        * 403 - If the user had an invalid subscription.
        * 403 - If the user was maxed out on messages for the payment period.
        * 404 - If the provided method was invalid.
        * 404 - If the user didn't have an associated profile.
        * 406 - If the provided form data was invalid.
        * 500 - If something went wrong dispatching notifications.
        * 204 - If the Wialon unit didn't have any phone numbers assigned.
        * 200 - If phone numbers were phone and all notifications were queued successfully.

    """
    if method not in settings.NOTIFICATION_DISPATCHERS:
        return HttpResponse("Invalid method".encode("utf-8"), status=404)
    form = forms.NotificationDispatchForm(request.POST)
    if not form.is_valid():
        return HttpResponse(status=406)
    profile = get_object_or_404(Profile, user__pk=form.cleaned_data["user_id"])
    status = get_subscription_status(profile)
    if status != "active":
        return HttpResponse("Invalid subscription".encode("utf-8"), status=403)
    if profile.messages_count >= profile.messages_limit:
        return HttpResponse("Messages maxed".encode("utf-8"), status=403)
    phones = get_phones(profile.token, form.cleaned_data["unit_id"])
    if not phones:
        return HttpResponse("No phones found".encode("utf-8"), status=204)
    dispatchers = get_dispatchers(form, method)
    response = send_notifications(method, phones, dispatchers)
    if response.status_code == 200:
        profile.messages_count = F("messages_count") + len(phones)
        profile.save(update_fields=["messages_count"])
    return response


class TerminusGPSNotifierLoginView(LoginView):
    next_page = reverse_lazy("terminusgps_notifier:dashboard")
    redirect_authenticated_user = True
    template_name = "terminusgps_notifier/login.html"


class TerminusGPSNotifierLogoutView(LogoutView):
    next_page = reverse_lazy("terminusgps_notifier:home")
    template_name = "terminusgps_notifier/logged_out.html"


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/register.html")
def register(request: HtmxHttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = forms.UserCreationForm(request.POST)
        if form.is_valid():
            form.save(commit=True)
            return redirect_to_login(
                next=reverse("terminusgps_notifier:dashboard"),
                login_url=reverse("terminusgps_notifier:login"),
            )
    else:
        form = forms.UserCreationForm({})
    return TemplateResponse(request, request.template_name, {"form": form})


@require_GET
def health_check(request: HttpRequest) -> HttpResponse:
    return HttpResponse("I'm alive\n".encode("utf-8"), status=200)


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
    return TemplateResponse(request, request.template_name, {})


@require_GET
@htmx_template("terminusgps_notifier/contact.html")
def contact(request: HtmxHttpRequest) -> HttpResponse:
    return TemplateResponse(request, request.template_name, {})


@require_GET
@htmx_template("terminusgps_notifier/terms.html")
def terms(request: HtmxHttpRequest) -> HttpResponse:
    return TemplateResponse(request, request.template_name, {})


@require_GET
@htmx_template("terminusgps_notifier/privacy.html")
def privacy(request: HtmxHttpRequest) -> HttpResponse:
    return TemplateResponse(request, request.template_name, {})


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
    return TemplateResponse(request, request.template_name, context)


@require_GET
@persistent_wialon_session
@htmx_template("terminusgps_notifier/detail_notifications.html")
def detail_notifications(
    request: HtmxHttpRequest, resource_id: str, notification_id: str
) -> HttpResponse:
    try:
        session = get_wialon_session(request.session["wialon_sid"])
        params = {"itemId": resource_id, "col": [notification_id]}
        response = session.wialon_api.resource_get_notification_data(**params)
    except WialonAPIError as error:
        messages.error(request, error)
        response = [{}]
    context = {"object": response[0]}
    return TemplateResponse(request, request.template_name, context)


@require_GET
@persistent_wialon_session
@htmx_template("terminusgps_notifier/list_resources.html")
def list_resources(request: HtmxHttpRequest) -> HttpResponse:
    try:
        session = get_wialon_session(request.session["wialon_sid"])
        params = {"spec": {}, "force": 0, "from": 0, "to": 0, "flags": 1}
        params["spec"]["itemsType"] = "avl_resource"
        params["spec"]["propName"] = "sys_name"
        params["spec"]["propValueMask"] = "*"
        params["spec"]["propType"] = "property"
        params["spec"]["sortType"] = "sys_name"
        response = session.wialon_api.core_search_items(**params)
    except WialonAPIError as error:
        messages.error(request, error)
        response = {"items": []}
    context = {"object_list": response["items"]}
    return TemplateResponse(request, request.template_name, context)


@require_GET
@persistent_wialon_session
@htmx_template("terminusgps_notifier/select_resources.html")
def select_resources(request: HtmxHttpRequest) -> HttpResponse:
    try:
        session = get_wialon_session(request.session["wialon_sid"])
        params = {"spec": {}, "force": 0, "from": 0, "to": 0, "flags": 1}
        params["spec"]["itemsType"] = "avl_resource"
        params["spec"]["propName"] = "sys_name"
        params["spec"]["propValueMask"] = "*"
        params["spec"]["propType"] = "property"
        params["spec"]["sortType"] = "sys_name"
        response = session.wialon_api.core_search_items(**params)
    except WialonAPIError as error:
        messages.error(request, error)
        response = {"items": []}
    context = {"object_list": response["items"]}
    return TemplateResponse(request, request.template_name, context)


@require_GET
@persistent_wialon_session
@htmx_template("terminusgps_notifier/select_geofences.html")
def select_geofences(
    request: HtmxHttpRequest, resource_id: str
) -> HttpResponse:
    try:
        session = WialonSession(sid=request.session["wialon_sid"])
        params = {"itemId": resource_id}
        response = session.wialon_api.resource_get_zone_data(**params)
    except WialonAPIError as error:
        messages.error(request, error)
        response = []
    context = {"object_list": response}
    return TemplateResponse(request, request.template_name, context)


@require_GET
@persistent_wialon_session
@htmx_template("terminusgps_notifier/list_notifications.html")
def list_notifications(
    request: HtmxHttpRequest, resource_id: str
) -> HttpResponse:
    try:
        session = get_wialon_session(request.session["wialon_sid"])
        params = {"itemId": resource_id}
        response = session.wialon_api.resource_get_notification_data(**params)
    except WialonAPIError as error:
        messages.error(request, error)
        response = {"items": []}
    context = {"object_list": response["items"]}
    return TemplateResponse(request, request.template_name, context)


@require_GET
@persistent_wialon_session
@htmx_template("terminusgps_notifier/detail_resources.html")
def detail_resources(
    request: HtmxHttpRequest, resource_id: str
) -> HttpResponse:
    try:
        session = get_wialon_session(request.session["wialon_sid"])
        params = {"id": resource_id, "flags": 1025}
        response = session.wialon_api.core_search_item(**params)
    except WialonAPIError as error:
        messages.error(request, error)
        response = {"item": {}}
    context = {"object": response["item"]}
    return TemplateResponse(request, request.template_name, context)


@require_GET
@persistent_wialon_session
@htmx_template("terminusgps_notifier/select_units.html")
def select_units(request: HtmxHttpRequest) -> HttpResponse:
    if not request.GET.get("resource"):
        raise Http404()
    try:
        session = get_wialon_session(request.session["wialon_sid"])
        params = {"spec": {}, "force": 0, "from": 0, "to": 0, "flags": 1}
        params["spec"]["itemsType"] = request.GET.get("items_type", "avl_unit")
        params["spec"]["propName"] = "sys_name,sys_billing_account_guid"
        params["spec"]["propValueMask"] = f"*,{request.GET['resource']}"
        params["spec"]["propType"] = "property,property"
        params["spec"]["sortType"] = "sys_name"
        response = session.wialon_api.core_search_items(**params)
    except WialonAPIError as error:
        messages.warning(request, error)
        response = {"items": []}
    context = {"object_list": response["items"]}
    return TemplateResponse(request, request.template_name, context)


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/create_subscription.html")
def create_subscription(request: HtmxHttpRequest) -> HttpResponse:
    profile = get_object_or_404(Profile, user=request.user)
    if request.method == "POST":
        form = forms.CreateSubscriptionForm(request.POST)
        paymentSchedule = apicontractsv1.paymentScheduleType()
        paymentSchedule.interval = apicontractsv1.paymentScheduleTypeInterval()
        paymentSchedule.interval.length = "1"
        paymentSchedule.interval.unit = "months"
        profile = apicontractsv1.customerProfileIdType()
        profile.customerProfileId = profile.customer_profile_id
        profile.customerPaymentProfileId = form.cleaned_data["payment_id"]
        profile.customerAddressId = form.cleaned_data["address_id"]
        contract = apicontractsv1.ARBSubscriptionType()
        contract.name = "Terminus GPS Notifier"
        contract.paymentSchedule = paymentSchedule
        contract.amount = "60.00"
        contract.trialAmount = "0.00"
        contract.profile = profile
        try:
            service = AuthorizenetService()
            response = service.execute(api.create_subscription(contract))
        except AuthorizenetError as error:
            messages.error(request, error)
            response = None
    context = {}
    return TemplateResponse(request, request.template_name, context)


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
@persistent_wialon_session
@htmx_template("terminusgps_notifier/create_notification/step_one.html")
def create_notification_step_one(request: HtmxHttpRequest) -> HttpResponse:
    if request.method == "POST":
        un = request.POST.getlist("units", [])
        itemId = int(request.POST["resource"])
        request.session["step_one_data"] = {"un": un, "itemId": itemId}
        return redirect("terminusgps_notifier:create notification step two")
    try:
        session = get_wialon_session(request.session["wialon_sid"])
        params = {"spec": {}, "force": 0, "from": 0, "to": 0, "flags": 1}
        params["spec"]["itemsType"] = "avl_resource"
        params["spec"]["propName"] = "sys_name"
        params["spec"]["propValueMask"] = "*"
        params["spec"]["propType"] = "property"
        params["spec"]["sortType"] = "sys_name"
        response = session.wialon_api.core_search_items(**params)
    except WialonAPIError as error:
        messages.error(request, error)
        response = {"items": []}
    return TemplateResponse(
        request,
        request.template_name,
        {
            "object_list": response["items"],
            "selected": request.GET.get("resource"),
        },
    )


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/create_notification/step_two.html")
def create_notification_step_two(request: HtmxHttpRequest) -> HttpResponse:
    if request.method == "POST":
        p = {}
        for field in request.POST:
            if field not in ("csrfmiddlewaretoken", "t"):
                p.update({field: request.POST[field]})
        trg = {"t": request.POST["t"], "p": p}
        request.session["step_two_data"] = {"trg": trg}
        return redirect("terminusgps_notifier:create notification step three")
    else:
        context = {"triggers": forms.WialonNotificationTrigger.choices}
        return TemplateResponse(request, request.template_name, context)


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/create_notification/step_three.html")
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
            "https://api.terminusgps.com/",
            f"/v3/notify/{request.POST['method']}/",
        )
        return [{"t": "push_messages", "p": {"url": url, "get": 0}}]

    if request.method == "POST":
        n = request.POST["name"]
        txt = generate_txt(request)
        act = generate_act(request)
        request.session["step_three_data"] = {"n": n, "txt": txt, "act": act}
        return redirect("terminusgps_notifier:create notification step four")
    else:
        return TemplateResponse(request, request.template_name, {})


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/create_notification/step_four.html")
def create_notification_step_four(request: HtmxHttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = forms.CreateNotificationStepFourForm(request.POST)
        if form.is_valid():
            request.session["step_four_data"] = form.cleaned_data
            return redirect(
                "terminusgps_notifier:create notification step review"
            )
    else:
        initial = {}
        initial["ma"] = 0
        initial["cdt"] = 0
        initial["mpst"] = 0
        initial["mast"] = 0
        initial["cp"] = 3600
        initial["mmtd"] = 3600
        form = forms.CreateNotificationStepFourForm(initial=initial)
    context = {"timezones": constants.TIMEZONES, "form": form}
    return TemplateResponse(request, request.template_name, context)


@require_http_methods(["GET", "POST"])
@persistent_wialon_session
@htmx_template("terminusgps_notifier/create_notification/step_review.html")
def create_notification_step_review(request: HtmxHttpRequest) -> HttpResponse:
    def get_resource_update_notification_params(
        request: HtmxHttpRequest,
    ) -> dict:
        step_one = dict(request.session.get("step_one_data", {}))
        step_two = dict(request.session.get("step_two_data", {}))
        step_three = dict(request.session.get("step_three_data", {}))
        step_four = dict(request.session.get("step_four_data", {}))
        sch = {"f1": 0, "f2": 0, "t1": 0, "t2": 0, "m": 0, "y": 0, "w": 0}
        ctrl_sch = {"f1": 0, "f2": 0, "t1": 0, "t2": 0, "m": 0, "y": 0, "w": 0}
        schedules = {"sch": sch, "ctrl_sch": ctrl_sch}
        return step_one | step_two | step_three | step_four | schedules

    params = get_resource_update_notification_params(request)
    if request.method == "POST":
        try:
            session = get_wialon_session(request.session["wialon_sid"])
            session.wialon_api.resource_update_notification(**params)
            request.session.pop("step_one_data", None)
            request.session.pop("step_two_data", None)
            request.session.pop("step_three_data", None)
            request.session.pop("step_four_data", None)
            messages.success(request, "Notification successfully created!")
            return redirect(
                "terminusgps_notifier:detail resources",
                resource_id=params["itemId"],
            )
        except WialonAPIError as error:
            messages.error(request, error)
    context = {"params": params}
    return TemplateResponse(request, request.template_name, context)


@require_GET
@htmx_template("terminusgps_notifier/trigger_parameters.html")
def trigger_parameters_form(request: HtmxHttpRequest) -> HttpResponse:
    t = request.GET.get("t")
    if t is None:
        raise Http404()
    if str(t) not in forms.WialonNotificationTrigger:
        raise Http404()
    form_cls = forms.TRIGGER_FORMS_MAP[str(t)]
    context = {"form": form_cls()}
    return TemplateResponse(request, request.template_name, context)
