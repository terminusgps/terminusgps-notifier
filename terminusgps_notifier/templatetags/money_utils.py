import decimal

from django import template

register = template.Library()


@register.filter
def pennies_to_dollars(pennies: int) -> decimal.Decimal:
    return decimal.Decimal(pennies) / decimal.Decimal(100)
