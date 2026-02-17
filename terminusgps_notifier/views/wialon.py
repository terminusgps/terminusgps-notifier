from django.http import HttpRequest
from django.views.generic import ListView
from terminusgps.mixins import HtmxTemplateResponseMixin

from terminusgps_notifier.models import WialonResource


class WialonObjectListView(HtmxTemplateResponseMixin, ListView):
    content_type = "text/html"
    allow_empty = True
    http_method_names = ["get"]
    model = None

    def setup(self, request: HttpRequest, *args, **kwargs) -> None:
        if "resource_id" not in kwargs:
            raise ValueError("'resource_id' kwarg is required.")
        self.resource = WialonResource.objects.get(pk=kwargs["resource_id"])
        super().setup(request, *args, **kwargs)
