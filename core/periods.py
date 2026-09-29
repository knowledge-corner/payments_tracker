import datetime

from django.utils import timezone


def financial_year_start(today):
    """Indian financial year starts on 1 April."""
    year = today.year if today.month >= 4 else today.year - 1
    return datetime.date(year, 4, 1)


PERIODS = [("month", "This month"), ("fy", "This FY"), ("all", "All time")]


def period_range(key, today=None):
    today = today or timezone.localdate()
    if key == "month":
        return today.replace(day=1), today
    if key == "fy":
        return financial_year_start(today), today
    return None, today


def month_start(d):
    return d.replace(day=1)


def add_months(d, n):
    m = d.month - 1 + n
    return datetime.date(d.year + m // 12, m % 12 + 1, 1)
