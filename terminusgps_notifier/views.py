import asyncio
import copy
import decimal
import logging
import urllib.parse

from asgiref.sync import async_to_sync
from authorizenet import apicontractsv1
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView, redirect_to_login
from django.db import transaction
from django.db.models import F
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.module_loading import import_string
from django.views.decorators.cache import cache_control, never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
    require_POST,
)
from django.views.generic import RedirectView
from terminusgps.authorizenet import api
from terminusgps.authorizenet.service import AuthorizenetError
from terminusgps.wialon.session import WialonAPIError

from terminusgps_notifier import constants, forms
from terminusgps_notifier.authorizenet import (
    create_customer_profile,
    get_authorizenet_service,
    get_customer_profile_by_id,
    get_hosted_profile_page_url,
    subscription_is_active,
)
from terminusgps_notifier.decorators import (
    HtmxHttpRequest,
    htmx_template,
    persistent_wialon_session,
)
from terminusgps_notifier.dispatchers import NotificationDispatcher
from terminusgps_notifier.models import Profile
from terminusgps_notifier.wialon import (
    create_notification,
    get_geozones,
    get_items,
    get_notifications,
    get_phones,
    get_resources,
    get_session,
)

logger = logging.getLogger(__name__)


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


@require_POST
@csrf_exempt
@never_cache
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
    if not subscription_is_active(profile.subscription_id):
        return HttpResponse("Invalid subscription".encode("utf-8"), status=403)
    if profile.messages_count > profile.messages_limit:
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
            user = form.save(commit=True)
            user.email = form.cleaned_data["email"]
            user.first_name = form.cleaned_data["first_name"]
            user.last_name = form.cleaned_data["last_name"]
            user.save(update_fields=["first_name", "last_name", "email"])
            return redirect_to_login(
                next=reverse("terminusgps_notifier:dashboard"),
                login_url=reverse("terminusgps_notifier:login"),
            )
    else:
        form = forms.UserCreationForm({})
    return TemplateResponse(request, request.template_name, {"form": form})


@require_GET
def health_check(request: HttpRequest) -> HttpResponse:
    return HttpResponse("I'm alive".encode("utf-8"), status=200)


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


@require_POST
@transaction.atomic
def refresh_authorizenet_customer_profile(
    request: HtmxHttpRequest, customer_profile_id: str
) -> HttpResponse:
    try:
        profile = get_object_or_404(Profile, profile_id=customer_profile_id)
        anet_response = get_customer_profile_by_id(customer_profile_id)
        profile.user.email = str(anet_response.profile.email)
        profile.user.save(update_fields=["email"])
        profile.profile_id = str(anet_response.profile.customerProfileId)
        profile.merchant_id = str(anet_response.profile.merchantCustomerId)
        profile.description = str(anet_response.profile.description)
        update_fields = ["profile_id", "merchant_id", "description"]
        profile.save(update_fields=update_fields)
        return HttpResponse(status=200)
    except AuthorizenetError as error:
        logger.error(error)
        messages.error(request, error)
        return HttpResponse(status=500)


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/cancel_subscription.html")
def cancel_subscription(request: HtmxHttpRequest) -> HttpResponse:
    profile = get_object_or_404(Profile, user=request.user)
    if not profile.subscription_id:
        messages.warning(request, "No subscription to cancel.")
        return redirect("terminusgps_notifier:dashboard")
    if request.method == "POST":
        anet_request = api.cancel_subscription(profile.subscription_id)
        anet_service = get_authorizenet_service()
        try:
            anet_service.execute(anet_request)
            messages.success(request, "Subscription successfully canceled.")
            return redirect("terminusgps_notifier:dashboard")
        except AuthorizenetError as error:
            logger.error(error)
            messages.error(request, error)
    return TemplateResponse(request, request.template_name, {})


@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/create_subscription.html")
def create_subscription(request: HtmxHttpRequest) -> HttpResponse:
    payment_choices = []
    address_choices = []
    profile = get_object_or_404(Profile, user=request.user)
    anet_request = api.get_customer_profile(profile.profile_id)
    anet_service = get_authorizenet_service()

    try:
        anet_response = anet_service.execute(anet_request)
        for aprofile in anet_response.profile.shipToList:
            value = str(aprofile.customerAddressId)
            label = str(aprofile.address)
            address_choices.append((value, label))
        for pprofile in anet_response.profile.paymentProfiles:
            value = str(pprofile.customerPaymentProfileId)
            label = f"{pprofile.payment.creditCard.cardType} {pprofile.payment.creditCard.cardNumber}"
            payment_choices.append((value, label))
    except AuthorizenetError as error:
        logger.error(error)
        messages.error(request, error)

    if request.method == "GET":
        form = forms.SubscriptionCreationForm(
            payment_choices=payment_choices,
            address_choices=address_choices,
            data={},
        )
    else:
        form = forms.SubscriptionCreationForm(
            payment_choices=payment_choices,
            address_choices=address_choices,
            data=request.POST,
        )
        if form.is_valid():
            address_id = form.cleaned_data["address_id"]
            payment_id = form.cleaned_data["payment_id"]
            interval = apicontractsv1.paymentScheduleTypeInterval()
            interval.length = 1
            interval.unit = "months"
            schedule = apicontractsv1.paymentScheduleType()
            schedule.interval = interval
            schedule.startDate = timezone.now()
            schedule.totalOccurrences = 9999
            schedule.trialOccurrences = 0
            customer_profile = apicontractsv1.customerProfileIdType()
            customer_profile.customerProfileId = profile.profile_id
            customer_profile.customerAddressId = address_id
            customer_profile.customerPaymentProfileId = payment_id
            contract = apicontractsv1.ARBSubscriptionType()
            contract.paymentSchedule = schedule
            contract.profile = customer_profile
            contract.amount = decimal.Decimal("60.00")
            contract.trialAmount = decimal.Decimal("0.00")
            anet_request = api.create_subscription(contract)
            try:
                anet_response = anet_service.execute(anet_request)
                profile.subscription_id = anet_response.subscriptionId
                profile.save(update_fields=["subscription_id"])
                return redirect("terminusgps_notifier:dashboard")
            except AuthorizenetError as error:
                logger.error(error)
                messages.error(request, error)
    return TemplateResponse(request, request.template_name, {"form": form})


@require_GET
@cache_control(private=True)
@htmx_template("terminusgps_notifier/dashboard.html")
def dashboard(request: HtmxHttpRequest) -> HttpResponse:
    update_fields = []
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if access_token := request.GET.get("access_token"):
        profile.token = str(access_token)
        update_fields.append("token")
        messages.success(request, "Wialon account connected successfully!")
    if not profile.profile_id:
        anet_response = create_customer_profile(
            email=profile.user.email,
            merchant_id=f"{profile.user.first_name} {profile.user.last_name}",
            description=f"{profile.user.first_name} {profile.user.last_name}'s Customer Profile",
        )
        profile.profile_id = str(anet_response.profile.customerProfileId)
        profile.merchant_id = str(anet_response.profile.merchantCustomerId)
        profile.description = str(anet_response.profile.description)
        update_fields.extend(("profile_id", "merchant_id", "description"))
    if update_fields:
        profile.save(update_fields=update_fields)
    return TemplateResponse(
        request,
        request.template_name,
        {
            "profile": profile,
            "subscribed": subscription_is_active(profile.subscription_id),
            "wialon_redirect_uri": request.build_absolute_uri(
                reverse("terminusgps_notifier:dashboard")
            ),
        },
    )


@require_GET
@persistent_wialon_session
@cache_control(private=True)
@htmx_template("terminusgps_notifier/detail_notifications.html")
def detail_notifications(
    request: HtmxHttpRequest, resource_id: str, notification_id: str
) -> HttpResponse:
    try:
        wialon_sid = request.session["wialon_sid"]
        response = get_notifications(
            wialon_sid, resource_id, [notification_id]
        )
    except WialonAPIError as error:
        logger.error(error)
        messages.error(request, error)
        response = [{}]
    context = {"object": response[0]}
    return TemplateResponse(request, request.template_name, context)


@require_http_methods(["GET", "POST"])
@never_cache
@htmx_template("terminusgps_notifier/hosted_profile.html")
def authorizenet_hosted_profile_page(request: HtmxHttpRequest) -> HttpResponse:
    profile = get_object_or_404(Profile, user=request.user)
    profile_id = int(profile.profile_id)
    settings = copy.copy(constants.HOSTED_PROFILE_PAGE_SETTINGS)
    anet_request = api.get_accept_customer_profile_page(profile_id, settings)
    anet_service = get_authorizenet_service()

    try:
        anet_response = anet_service.execute(anet_request)
        token = str(anet_response.token)
    except AuthorizenetError as error:
        logger.error(error)
        token = None
    return TemplateResponse(
        request,
        request.template_name,
        {"token": token, "url": get_hosted_profile_page_url()},
    )


@require_GET
@cache_control(private=True)
@persistent_wialon_session
@htmx_template("terminusgps_notifier/list_resources.html")
def list_resources(request: HtmxHttpRequest) -> HttpResponse:
    try:
        wialon_sid = request.session["wialon_sid"]
        force_refresh = request.GET.get("refresh") == "on"
        response = get_resources(wialon_sid, force_refresh)
    except WialonAPIError as error:
        logger.error(error)
        messages.error(request, error)
        response = {"items": []}
    context = {"object_list": response["items"]}
    return TemplateResponse(request, request.template_name, context)


@require_GET
@cache_control(private=True)
@persistent_wialon_session
@htmx_template("terminusgps_notifier/select_resources.html")
def select_resources(request: HtmxHttpRequest) -> HttpResponse:
    try:
        wialon_sid = request.session["wialon_sid"]
        force_refresh = request.GET.get("refresh") == "on"
        response = get_resources(wialon_sid, force_refresh)
    except WialonAPIError as error:
        logger.error(error)
        messages.error(request, error)
        response = {"items": []}
    context = {"object_list": response["items"]}
    return TemplateResponse(request, request.template_name, context)


@require_GET
@cache_control(private=True)
@persistent_wialon_session
@htmx_template("terminusgps_notifier/select_geofences.html")
def select_geofences(
    request: HtmxHttpRequest, resource_id: str
) -> HttpResponse:
    try:
        wialon_sid = request.session["wialon_sid"]
        response = get_geozones(wialon_sid, resource_id)
    except WialonAPIError as error:
        logger.error(error)
        messages.error(request, error)
        response = []
    context = {"object_list": response}
    return TemplateResponse(request, request.template_name, context)


@require_GET
@cache_control(private=True)
@persistent_wialon_session
@htmx_template("terminusgps_notifier/list_notifications.html")
def list_notifications(
    request: HtmxHttpRequest, resource_id: str
) -> HttpResponse:
    try:
        wialon_sid = request.session["wialon_sid"]
        response = get_notifications(wialon_sid, resource_id)
    except WialonAPIError as error:
        logger.error(error)
        messages.error(request, error)
        response = {"items": []}
    context = {"object_list": response["items"]}
    return TemplateResponse(request, request.template_name, context)


@require_GET
@cache_control(private=True)
@persistent_wialon_session
@htmx_template("terminusgps_notifier/detail_resources.html")
def detail_resources(
    request: HtmxHttpRequest, resource_id: str
) -> HttpResponse:
    try:
        wialon_sid = request.session["wialon_sid"]
        session = get_session(wialon_sid)
        params = {"id": resource_id, "flags": 1025}
        response = session.wialon_api.core_search_item(**params)
    except WialonAPIError as error:
        logger.error(error)
        messages.error(request, error)
        response = {"item": {}}
    context = {"object": response["item"]}
    return TemplateResponse(request, request.template_name, context)


@require_GET
@cache_control(private=True)
@persistent_wialon_session
@htmx_template("terminusgps_notifier/select_units.html")
def select_units(request: HtmxHttpRequest) -> HttpResponse:
    if not request.GET.get("resource"):
        raise Http404()
    try:
        wialon_sid = request.session["wialon_sid"]
        resource_id = str(request.GET.get("resource"))
        items_type = str(request.GET.get("items_type", "avl_unit"))
        force_refresh = request.GET.get("refresh") == "on"
        response = get_items(
            wialon_sid, resource_id, items_type, force_refresh
        )
    except WialonAPIError as error:
        logger.error(error)
        messages.warning(request, error)
        response = {"items": []}
    context = {"object_list": response["items"]}
    return TemplateResponse(request, request.template_name, context)


@require_GET
@htmx_template("terminusgps_notifier/detail_subscription.html")
def detail_subscription(request: HtmxHttpRequest) -> HttpResponse:
    profile = get_object_or_404(Profile, user=request.user)
    subscription_id = int(profile.subscription_id)
    include_transactions = request.GET.get("include_transactions") == "on"
    anet_request = api.get_subscription(subscription_id, include_transactions)
    anet_service = get_authorizenet_service()

    try:
        anet_response = anet_service.execute(anet_request)
        subscription = anet_response.subscription
    except AuthorizenetError as error:
        logger.error(error)
        messages.error(request, error)
        subscription = None
    context = {"object": subscription}
    return TemplateResponse(request, request.template_name, context)


@require_http_methods(["GET", "POST"])
@cache_control(private=True)
@persistent_wialon_session
@htmx_template("terminusgps_notifier/create_notification/step_one.html")
def create_notification_step_one(request: HtmxHttpRequest) -> HttpResponse:
    if request.method == "POST":
        un = request.POST.getlist("units", [])
        itemId = int(request.POST["resource"])
        request.session["step_one_data"] = {"un": un, "itemId": itemId}
        return redirect("terminusgps_notifier:create notification step two")
    try:
        wialon_sid = request.session["wialon_sid"]
        forced_refresh = request.GET.get("refresh") == "on"
        response = get_resources(wialon_sid, forced_refresh)
    except WialonAPIError as error:
        logger.error(error)
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
@cache_control(private=True)
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
@cache_control(private=True)
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
    return TemplateResponse(request, request.template_name, {})


@require_http_methods(["GET", "POST"])
@cache_control(private=True)
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
@cache_control(private=True)
@persistent_wialon_session
@htmx_template("terminusgps_notifier/create_notification/step_review.html")
def create_notification_step_review(request: HtmxHttpRequest) -> HttpResponse:
    def get_wialon_api_parameters(request: HtmxHttpRequest) -> dict:
        step_one = request.session.get("step_one_data", {})
        step_two = request.session.get("step_two_data", {})
        step_three = request.session.get("step_three_data", {})
        step_four = request.session.get("step_four_data", {})
        sch = {"f1": 0, "f2": 0, "t1": 0, "t2": 0, "m": 0, "y": 0, "w": 0}
        ctrl_sch = {"f1": 0, "f2": 0, "t1": 0, "t2": 0, "m": 0, "y": 0, "w": 0}
        schedules = {"sch": sch, "ctrl_sch": ctrl_sch}
        return step_one | step_two | step_three | step_four | schedules

    params = get_wialon_api_parameters(request)
    if request.method == "POST":
        try:
            wialon_sid = request.session["wialon_sid"]
            create_notification(wialon_sid, params)
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
            logger.error(error)
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
