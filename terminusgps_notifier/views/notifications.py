from django.views.generic import CreateView
from terminusgps.mixins import HtmxTemplateResponseMixin

from terminusgps_notifier.models import WialonNotification


class WialonNotificationCreateView(HtmxTemplateResponseMixin, CreateView):
    content_type = "text/html"
    http_method_names = ["get"]
    model = WialonNotification
    fields = [
        "n",
        "ta",
        "td",
        "ma",
        "mmtd",
        "cdt",
        "mast",
        "mpst",
        "cp",
        "fl",
        "tz",
        "la",
        "d",
        "sch",
        "ctrl_sch",
        "trg",
        "act",
    ]
