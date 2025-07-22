from django.http import HttpRequest, HttpResponse
from django.views.generic import View


class CheckHealthView(View):
    content_type = "text/plain"
    http_method_names = ["get"]

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        return HttpResponse(b"I'm alive", status=200)
