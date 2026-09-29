from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def indian_grouping(n: int) -> str:
    """12345678 -> '1,23,45,678' (Indian lakh/crore grouping)."""
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups + [tail])
    return ("-" if n < 0 else "") + s


@register.filter
def inr(value, symbol="₹"):
    """Format a number as rupees without paise, e.g. ₹1,25,000."""
    if value in (None, ""):
        value = 0
    try:
        amount = Decimal(value).quantize(Decimal("1"))
    except (InvalidOperation, TypeError, ValueError):
        return value
    return f"{symbol}{indian_grouping(int(amount))}"


@register.inclusion_tag("partials/status_badge.html")
def status_badge(case):
    return {"label": case.payment_status_label, "badge": case.payment_status_badge}


@register.simple_tag(takes_context=True)
def querystring_with(context, **kwargs):
    """Rebuild the current query string with some keys replaced (for filters / pagination)."""
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else "?"
