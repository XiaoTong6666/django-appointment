import datetime

from django import template

from appointment.utils.date_time import format_time_with_chinese_period

register = template.Library()


@register.filter
def chinese_ampm(value):
    if isinstance(value, (datetime.datetime, datetime.time)):
        return format_time_with_chinese_period(value)
    return value
