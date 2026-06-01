import datetime

from django import template

register = template.Library()


@register.filter
def timestamp_to_datetime(timestamp: int) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(timestamp, datetime.UTC)
