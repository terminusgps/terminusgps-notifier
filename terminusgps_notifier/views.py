import asyncio
import logging
import warnings

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.module_loading import import_string
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView, RedirectView, TemplateView, View
from terminusgps.mixins import HtmxTemplateResponseMixin
from terminusgps.wialon.session import WialonSession

from terminusgps_notifier import forms
from terminusgps_notifier.dispatchers import NotificationDispatcher
from terminusgps_notifier.mixins import CustomerContextMixin
from terminusgps_notifier.models import TerminusGPSNotifierCustomer
from terminusgps_notifier.validators import validate_e164_phone_number
from terminusgps_notifier.wialon import get_phone_numbers

logger = logging.getLogger(__name__)


class HtmxTemplateView(
    HtmxTemplateResponseMixin, CustomerContextMixin, TemplateView
):
    """A view which renders a partial template on htmx request."""

    content_type = "text/html"
    http_method_names = ["get"]


class ProtectedHtmxTemplateView(
    LoginRequiredMixin,
    HtmxTemplateResponseMixin,
    CustomerContextMixin,
    TemplateView,
):
    """A view which renders a partial template on htmx request, behind authentication."""

    content_type = "text/html"
    http_method_names = ["get"]


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

    async def send_notifications(
        self, phones: list[str], dispatchers: list[NotificationDispatcher]
    ) -> HttpResponse:
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
async def wialon_callback(request: HttpRequest) -> HttpResponse:
    token_saved = False
    form = forms.WialonTokenForm(request.GET)
    if form.is_valid():
        customer, _ = await TerminusGPSNotifierCustomer.objects.aget_or_create(
            user=request.user
        )
        customer.token = form.cleaned_data["access_token"]
        await customer.asave(update_fields=["token"])
        token_saved = True
    template_name = "terminusgps_notifier/wialon_callback.html"
    return render(request, template_name, context={"token_saved": token_saved})


class WialonNotificationCreateView(
    HtmxTemplateResponseMixin, CustomerContextMixin, FormView
):
    content_type = "text/html"
    form_class = forms.WialonNotificationCreateForm
    http_method_names = ["get", "post"]
    template_name = "terminusgps_notifier/wialonnotification_create.html"

    def get_form(self, form_class=None) -> forms.WialonNotificationCreateForm:
        form = super().get_form(form_class=form_class)
        form.fields["resource"].choices = []
        form.fields["units"].choices = []
        return form
