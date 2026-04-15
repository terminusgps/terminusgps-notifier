import asyncio
import logging
import typing
import warnings

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.utils.decorators import method_decorator
from django.utils.module_loading import import_string
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView, View
from shapeshifter.views import MultiFormView
from terminusgps.mixins import HtmxTemplateResponseMixin
from terminusgps.wialon.session import WialonAPIError, WialonSession

from terminusgps_notifier import forms
from terminusgps_notifier.dispatchers import NotificationDispatcher
from terminusgps_notifier.models import TerminusGPSNotifierCustomer
from terminusgps_notifier.validators import validate_e164_phone_number
from terminusgps_notifier.wialon import get_phone_numbers

logger = logging.getLogger(__name__)


class HtmxTemplateView(HtmxTemplateResponseMixin, TemplateView):
    """A view which renders a partial template on htmx request."""

    content_type = "text/html"
    http_method_names = ["get"]


class ProtectedHtmxTemplateView(
    LoginRequiredMixin, HtmxTemplateResponseMixin, TemplateView
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


class WialonCallbackView(HtmxTemplateResponseMixin, TemplateView):
    content_type = "text/html"
    http_method_names = ["get"]

    async def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        form = forms.WialonTokenForm(request.GET)
        if not form.is_valid():
            return HttpResponse(status=406)
        customer, _ = await TerminusGPSNotifierCustomer.objects.aget_or_create(
            user=request.user
        )
        customer.token = form.cleaned_data["access_token"]
        await customer.asave(update_fields=["token"])
        return super().get(request, *args, **kwargs)


class WialonNotificationCreateView(HtmxTemplateResponseMixin, MultiFormView):
    content_type = "text/html"
    http_method_names = ["get", "post"]
    form_classes = (forms.WialonResourceSelectForm,)


class WialonNotificationListView(HtmxTemplateResponseMixin, TemplateView):
    content_type = "text/html"
    http_method_names = ["get"]
    template_name = "terminusgps_notifier/wialonnotification_list.html"

    def get_resources(self) -> list[dict]:
        try:
            customer = TerminusGPSNotifierCustomer.objects.get(
                user=self.request.user
            )
        except TerminusGPSNotifierCustomer.DoesNotExist:
            return []
        try:
            with WialonSession(token=customer.token) as session:
                response = session.wialon_api.core_search_items(
                    **{
                        "spec": {
                            "itemsType": "avl_resource",
                            "propName": "sys_name",
                            "propValueMask": "*",
                            "propType": "property",
                            "sortType": "sys_name",
                        },
                        "force": 0,
                        "from": 0,
                        "to": 0,
                        "flags": 1025,
                    }
                )
                return response["items"]
        except WialonAPIError:
            # TODO: Error handling
            return []

    def get_context_data(self, **kwargs) -> dict[str, typing.Any]:
        context = super().get_context_data(**kwargs)
        context["resource_list"] = self.get_resources()
        return context


class CustomerMessageCountView(HtmxTemplateResponseMixin, TemplateView):
    content_type = "text/html"
    http_method_names = ["get"]

    def get_messages_count_and_limit(self) -> tuple[int | None, int | None]:
        try:
            customer = TerminusGPSNotifierCustomer.objects.get(
                user=self.request.user
            )
            return (customer.messages_count, customer.messages_limit)
        except TerminusGPSNotifierCustomer.DoesNotExist:
            return (None, None)

    def get_context_data(self, **kwargs) -> dict[str, typing.Any]:
        value, max = self.get_messages_count_and_limit()
        context = super().get_context_data(**kwargs)
        context["value"] = value
        context["max"] = max
        return context
