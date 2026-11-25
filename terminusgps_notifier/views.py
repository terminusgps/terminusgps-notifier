import asyncio
import logging

from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView, redirect_to_login
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.cache import (
    cache_control,
    cache_page,
    never_cache,
)
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
    require_POST,
)
from django.views.decorators.vary import vary_on_headers
from django.views.generic import RedirectView
from terminusgps.wialon.session import WialonAPIError, WialonSession

from terminusgps_notifier import forms
from terminusgps_notifier.constants import TIMEZONES
from terminusgps_notifier.decorators import (
    HtmxHttpRequest,
    htmx_template,
    persistent_wialon_session,
)
from terminusgps_notifier.dispatchers import get_dispatchers
from terminusgps_notifier.models import DispatchLog, Profile
from terminusgps_notifier.wialon import (
    create_notification,
    generate_act,
    generate_txt,
    get_geozones,
    get_items,
    get_notifications,
    get_resources,
    get_session,
    get_unit,
)

logger = logging.getLogger(__name__)


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
        tasks = [
            dispatcher.send_notification(to_number=phone, method=method)
            for phone in phones
        ]
        try:
            await asyncio.gather(*tasks)
        except Exception as error:
            logger.error(f"{type(dispatcher).__name__} failed: '{error}'")
        else:
            return HttpResponse(
                f"Dispatched via {type(dispatcher).__name__}".encode("utf-8"),
                status=200,
            )
    return HttpResponse(
        f"All dispatchers failed for method: '{method}'".encode("utf-8"),
        status=500,
    )


@require_POST
@csrf_exempt
@never_cache
def command(request: HttpRequest, unit_id: int) -> HttpResponse:
    form = forms.CommandExecutionForm(request.POST)
    if not form.is_valid():
        logger.error("Invalid form data")
        return HttpResponse(status=400)
    if form.cleaned_data.get("dry_run", False):
        logger.debug(
            "Successfully sent '%s' to %s",
            form.cleaned_data["command"],
            unit_id,
        )
        return HttpResponse(status=200)
    profile = get_object_or_404(Profile, user__pk=form.cleaned_data["user_id"])
    if not profile.token:
        logger.error("Failed to retrieve token for %s", profile)
        return HttpResponse(status=403)
    with WialonSession(token=profile.token) as session:
        try:
            session.wialon_api.unit_exec_cmd(
                **{
                    "itemId": unit_id,
                    "commandName": form.cleaned_data["command"],
                    "linkType": form.cleaned_data.get("link_type", ""),
                    "param": "",
                    "timeout": 300,
                    "flags": 0,
                }
            )
            logger.debug(
                "Successfully sent '%s' to %s",
                form.cleaned_data["command"],
                unit_id,
            )
        except WialonAPIError as error:
            logger.critical(error)
            return HttpResponse(status=500)
        return HttpResponse(status=200)


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
        * 200 - If phone numbers were found and all notifications were queued successfully.

    """
    if method not in settings.NOTIFICATION_DISPATCHERS:
        return HttpResponse("Invalid method".encode("utf-8"), status=404)
    form = forms.NotificationDispatchForm(request.POST)
    if not form.is_valid():
        return HttpResponse(status=406)
    profile = get_object_or_404(Profile, user__pk=form.cleaned_data["user_id"])
    if not profile.user.is_staff:
        if not profile.has_active_subscription():
            return HttpResponse(
                "Invalid subscription".encode("utf-8"), status=403
            )
        if not profile.has_available_messages():
            return HttpResponse("Messages maxed".encode("utf-8"), status=403)
    phones = profile.get_wialon_destination_phone_numbers(
        form.cleaned_data["unit_id"]
    )
    if not phones:
        return HttpResponse("No phones found".encode("utf-8"), status=204)
    dispatchers = get_dispatchers(form, method)
    response = send_notifications(method, phones, dispatchers)
    if response.status_code == 200:
        profile.update_messages_count_and_save(len(phones))
        DispatchLog.objects.create(
            user_id=form.cleaned_data["user_id"],
            unit_id=form.cleaned_data["unit_id"],
            message=form.cleaned_data["message"],
            msg_time_int=form.cleaned_data["msg_time_int"],
            phones=phones,
            method=method,
            pub_date=timezone.now(),
        )
    return response


class TerminusGPSNotifierLoginView(LoginView):
    next_page = reverse_lazy("terminusgps_notifier:dashboard")
    redirect_authenticated_user = True
    template_name = "terminusgps_notifier/login.html"


class TerminusGPSNotifierLogoutView(LogoutView):
    next_page = reverse_lazy("terminusgps_notifier:home")
    template_name = "terminusgps_notifier/logged_out.html"


@vary_on_headers("HX-Request")
@cache_page(60 * 5)
@csrf_protect
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


@never_cache
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


@cache_page(60 * 5)
@require_GET
@htmx_template("terminusgps_notifier/home.html")
def home(request: HtmxHttpRequest) -> HttpResponse:
    return TemplateResponse(request, request.template_name)


@cache_page(60 * 5)
@require_GET
@htmx_template("terminusgps_notifier/contact.html")
def contact(request: HtmxHttpRequest) -> HttpResponse:
    return TemplateResponse(request, request.template_name)


@cache_page(60 * 5)
@require_GET
@htmx_template("terminusgps_notifier/terms.html")
def terms(request: HtmxHttpRequest) -> HttpResponse:
    return TemplateResponse(request, request.template_name)


@cache_page(60 * 5)
@require_GET
@htmx_template("terminusgps_notifier/privacy.html")
def privacy(request: HtmxHttpRequest) -> HttpResponse:
    return TemplateResponse(request, request.template_name)


@require_GET
def source_code(request: HtmxHttpRequest) -> HttpResponse:
    return RedirectView.as_view(
        url="https://github.com/terminusgps/terminusgps-notifier",
        permanent=True,
    )(request)


@login_required
@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/cancel_subscription.html")
def cancel_subscription(request: HtmxHttpRequest) -> HttpResponse:
    return TemplateResponse(request, request.template_name, status=403)


@login_required
@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/create_subscription.html")
def create_subscription(request: HtmxHttpRequest) -> HttpResponse:
    return TemplateResponse(request, request.template_name, status=403)


@vary_on_headers("HX-Request")
@cache_control(private=True)
@cache_page(60 * 3)
@login_required
@require_GET
@htmx_template("terminusgps_notifier/dashboard.html")
def dashboard(request: HtmxHttpRequest) -> HttpResponse:
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if access_token := request.GET.get("access_token"):
        profile.set_wialon_api_token_and_save(access_token)
        messages.success(request, "Wialon account connected successfully!")
    return TemplateResponse(
        request,
        request.template_name,
        {
            "profile": profile,
            "subscribed": profile.has_active_subscription(),
            "wialon_redirect_uri": request.build_absolute_uri(
                reverse("terminusgps_notifier:dashboard")
            ),
        },
    )


@login_required
@require_GET
@persistent_wialon_session
@cache_control(private=True)
@htmx_template("terminusgps_notifier/detail_notifications.html")
def detail_notifications(
    request: HtmxHttpRequest, resource_id: str, notification_id: str
) -> HttpResponse:
    wialon_sid = request.session["wialon_sid"]
    try:
        response = get_notifications(
            wialon_sid, resource_id, [notification_id]
        )
    except WialonAPIError as error:
        logger.error(error)
        messages.error(request, error)
        object = None
    else:
        object = response[0]
    context = {"object": object}
    return TemplateResponse(request, request.template_name, context)


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
@htmx_template("terminusgps_notifier/hosted_profile.html")
def authorizenet_hosted_profile_page(request: HtmxHttpRequest) -> HttpResponse:
    return TemplateResponse(request, request.template_name, {})


@login_required
@cache_page(60 * 5)
@cache_control(private=True)
@require_GET
@persistent_wialon_session
@htmx_template("terminusgps_notifier/list_resources.html")
def list_resources(request: HtmxHttpRequest) -> HttpResponse:
    wialon_sid = request.session["wialon_sid"]
    force_refresh = request.GET.get("refresh") == "on"
    try:
        response = get_resources(wialon_sid, force_refresh)
    except WialonAPIError as error:
        logger.error(error)
        messages.error(request, error)
        object_list = []
    else:
        object_list = response["items"]
    context = {"object_list": object_list}
    return TemplateResponse(request, request.template_name, context)


@login_required
@cache_page(60 * 5)
@cache_control(private=True)
@require_GET
@persistent_wialon_session
@htmx_template("terminusgps_notifier/select_resources.html")
def select_resources(request: HtmxHttpRequest) -> HttpResponse:
    wialon_sid = request.session["wialon_sid"]
    force_refresh = request.GET.get("refresh") == "on"
    try:
        response = get_resources(wialon_sid, force_refresh)
    except WialonAPIError as error:
        logger.error(error)
        messages.error(request, error)
        object_list = []
    else:
        object_list = response["items"]
    context = {"object_list": object_list}
    return TemplateResponse(request, request.template_name, context)


@login_required
@require_GET
@persistent_wialon_session
@cache_control(private=True)
@htmx_template("terminusgps_notifier/select_geofences.html")
def select_geofences(
    request: HtmxHttpRequest, resource_id: str
) -> HttpResponse:
    try:
        response = get_geozones(request.session["wialon_sid"], resource_id)
    except WialonAPIError as error:
        logger.error(error)
        messages.error(request, error)
        object_list = []
    else:
        object_list = [
            (f"{zone['id']}:{zone['ct']}", zone["n"]) for zone in response
        ]
    return TemplateResponse(
        request, request.template_name, {"object_list": object_list}
    )


@login_required
@require_GET
@persistent_wialon_session
@cache_control(private=True)
@htmx_template("terminusgps_notifier/list_notifications.html")
def list_notifications(
    request: HtmxHttpRequest, resource_id: str
) -> HttpResponse:
    try:
        response = get_notifications(
            request.session["wialon_sid"], resource_id
        )
    except WialonAPIError as error:
        logger.error(error)
        messages.error(request, error)
        object_list = []
    else:
        object_list = response["items"]
    context = {"object_list": object_list}
    return TemplateResponse(request, request.template_name, context)


@vary_on_headers("HX-Request")
@cache_page(60 * 5)
@cache_control(private=True)
@login_required
@require_GET
@persistent_wialon_session
@htmx_template("terminusgps_notifier/detail_resources.html")
def detail_resources(
    request: HtmxHttpRequest, resource_id: str
) -> HttpResponse:
    params = {"id": resource_id, "flags": 1025}
    try:
        session = get_session(request.session["wialon_sid"])
        response = session.wialon_api.core_search_item(**params)
    except WialonAPIError as error:
        logger.error(error)
        messages.error(request, error)
        object = None
    else:
        object = response["item"]
    context = {"object": object}
    return TemplateResponse(request, request.template_name, context)


@vary_on_headers("HX-Request")
@cache_page(60 * 5)
@cache_control(private=True)
@login_required
@require_GET
@persistent_wialon_session
@htmx_template("terminusgps_notifier/select_units.html")
def select_units(request: HtmxHttpRequest) -> HttpResponse:
    if not request.GET.get("resource"):
        raise Http404()
    wialon_sid = request.session["wialon_sid"]
    resource_id = str(request.GET.get("resource"))
    items_type = str(request.GET.get("items_type", "avl_unit"))
    force_refresh = request.GET.get("refresh") == "on"
    try:
        response = get_items(
            wialon_sid, resource_id, items_type, force_refresh
        )
    except WialonAPIError as error:
        logger.error(error)
        messages.warning(request, error)
        object_list = []
    else:
        object_list = response["items"]
    context = {"object_list": object_list}
    return TemplateResponse(request, request.template_name, context)


@login_required
@require_GET
@htmx_template("terminusgps_notifier/detail_subscription.html")
def detail_subscription(request: HtmxHttpRequest) -> HttpResponse:
    return TemplateResponse(request, request.template_name, {})


@login_required
@persistent_wialon_session
@require_http_methods(["GET", "POST"])
@cache_control(private=True)
@htmx_template("terminusgps_notifier/create_notification/step_one.html")
def create_notification_step_one(request: HtmxHttpRequest) -> HttpResponse:
    if request.method == "POST":
        un = request.POST.getlist("units", [])
        itemId = request.POST.get("resource")
        request.session["step_one_data"] = {"un": un, "itemId": itemId}
        return redirect("terminusgps_notifier:create notification step two")

    wialon_sid = request.session["wialon_sid"]
    forced_refresh = request.GET.get("refresh") == "on"
    try:
        response = get_resources(wialon_sid, forced_refresh)
    except WialonAPIError as error:
        logger.error(error)
        object_list = []
    else:
        object_list = response["items"]
    return TemplateResponse(
        request,
        request.template_name,
        {"object_list": object_list, "selected": request.GET.get("resource")},
    )


@login_required
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


@login_required
@require_http_methods(["GET", "POST"])
@cache_control(private=True)
@htmx_template("terminusgps_notifier/create_notification/step_three.html")
def create_notification_step_three(request: HtmxHttpRequest) -> HttpResponse:
    if request.method == "POST":
        n = request.POST["name"]
        txt = generate_txt(request.user.pk, request.POST["message"])
        act = generate_act(request.POST["method"])
        request.session["step_three_data"] = {"n": n, "txt": txt, "act": act}
        return redirect("terminusgps_notifier:create notification step four")
    return TemplateResponse(request, request.template_name, {})


@login_required
@require_http_methods(["GET", "POST"])
@cache_control(private=True)
@htmx_template("terminusgps_notifier/create_notification/step_four.html")
def create_notification_step_four(request: HtmxHttpRequest) -> HttpResponse:
    initial = {
        "ma": 0,
        "cdt": 0,
        "mpst": 0,
        "mast": 0,
        "cp": 3600,
        "mmtd": 3600,
    }
    form = forms.CreateNotificationStepFourForm(initial=initial)
    if request.method == "POST":
        form = forms.CreateNotificationStepFourForm(
            data=request.POST, initial=initial
        )
        if form.is_valid():
            request.session["step_four_data"] = form.cleaned_data
            return redirect(
                "terminusgps_notifier:create notification step review"
            )
    context = {"timezones": TIMEZONES, "form": form}
    return TemplateResponse(request, request.template_name, context)


@login_required
@persistent_wialon_session
@require_http_methods(["GET", "POST"])
@cache_control(private=True)
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
    wialon_sid = request.session["wialon_sid"]
    params["id"] = 0
    params["callMode"] = "create"
    if request.method == "POST":
        try:
            create_notification(wialon_sid, params)
        except WialonAPIError as error:
            logger.error(error)
            messages.error(request, error)
        else:
            request.session.pop("step_one_data", None)
            request.session.pop("step_two_data", None)
            request.session.pop("step_three_data", None)
            request.session.pop("step_four_data", None)
            messages.success(request, "Notification successfully created!")
            return redirect(
                "terminusgps_notifier:detail resources",
                resource_id=params["itemId"],
            )
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


@vary_on_headers("HX-Request")
@cache_control(private=True)
@require_GET
@persistent_wialon_session
@htmx_template("terminusgps_notifier/unit_name.html")
def unit_name(request: HtmxHttpRequest, unit_id: int) -> HttpResponse:
    try:
        response = get_unit(request.session["wialon_sid"], unit_id)
    except WialonAPIError as error:
        logger.error(error)
        name = None
    else:
        name = response["item"]["nm"]
    return TemplateResponse(request, request.template_name, {"name": name})
