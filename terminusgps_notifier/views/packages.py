from django import forms
from django.core.exceptions import ValidationError
from django.db.models import F, QuerySet
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, ListView
from terminusgps.mixins import HtmxTemplateResponseMixin

from terminusgps_notifier.models import (
    MessagePackage,
    TerminusGPSNotifierCustomer,
)


class MessagePackageListView(HtmxTemplateResponseMixin, ListView):
    allow_empty = True
    content_type = "text/html"
    http_method_names = ["get"]
    model = MessagePackage
    template_name = "terminusgps_notifier/messagepackage_list.html"

    def get_queryset(self) -> QuerySet:
        qs = self.model.objects.all()
        if not hasattr(self.request, "user"):
            return qs.none()

        try:
            customer = TerminusGPSNotifierCustomer.objects.get(
                user=self.request.user
            )
            return qs.filter(customer=customer)
        except TerminusGPSNotifierCustomer.DoesNotExist:
            return qs.none()


class MessagePackageCreateView(HtmxTemplateResponseMixin, CreateView):
    content_type = "text/html"
    fields = ["price", "limit", "customer"]
    http_method_names = ["get", "post"]
    model = MessagePackage
    success_url = reverse_lazy("terminusgps_notifier:list message packages")

    def form_valid(self, form: forms.ModelForm) -> HttpResponse:
        try:
            self.object = form.save(commit=True)
            if subscription := self.object.customer.subscription:
                subscription.amount = F("amount") + self.object.price
                subscription.save(push=True)
            return HttpResponseRedirect(self.success_url)
        except TerminusGPSNotifierCustomer.DoesNotExist:
            form.add_error(
                None,
                ValidationError(
                    _("Something went wrong. Please try again later."),
                    code="invalid",
                ),
            )
            return self.form_invalid(form=form)
