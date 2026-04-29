# date_time.py
# Path: appointment/utils/date_time.py

"""
Author: Adams Pierre David
Since: 2.0.0
"""

import datetime

from django.utils import timezone
from django.utils.translation import gettext_lazy as _, ngettext


def combine_date_and_time(date, time) -> datetime.datetime:
    """Combine a date and a time into a datetime object.

    :param date: The date.
    :param time: The time.
    :return: A datetime object.
    """
    return datetime.datetime.combine(date, time)


def convert_12_hour_time_to_24_hour_time(time_to_convert) -> str:
    """Convert a 12-hour time to a 24-hour time.

    :param time_to_convert: The time to convert.
    :return: The converted time.
    :raises ValueError: If the input time is not in the correct format or is invalid.
    """
    if isinstance(time_to_convert, (datetime.datetime, datetime.time)):
        return time_to_convert.strftime('%H:%M:%S')
    elif isinstance(time_to_convert, str):
        time_str = normalize_period_text(time_to_convert)
        for fmt in ['%I:%M %p', '%p %I:%M', '%H:%M:%S', '%H:%M']:
            try:
                return datetime.datetime.strptime(time_str, fmt).strftime('%H:%M:%S')
            except ValueError:
                pass
        raise ValueError(f"Invalid time format: {time_to_convert}")
    else:
        raise ValueError(f"Unsupported data type for time conversion: {type(time_to_convert)}")


def convert_24_hour_time_to_12_hour_time(time_to_convert) -> str:
    """Convert a 24-hour time to a 12-hour time.

    :param time_to_convert: The time to convert in 'HH:MM' or 'HH:MM:SS' format, or a datetime.time object.
    :return: The converted time in Chinese 12-hour format, e.g. '上午 10:00' or '下午 01:00'.
    :raises ValueError: If the input time is not in the correct format or is invalid.
    """
    # Handle datetime.time object directly
    if isinstance(time_to_convert, datetime.time):
        return format_time_with_chinese_period(time_to_convert)

    # Handle string input
    for source_fmt in ['%H:%M:%S', '%H:%M']:
        try:
            # Parse the input string according to the 24-hour format
            parsed_time = datetime.datetime.strptime(time_to_convert, source_fmt)
            # Convert and return the time in 12-hour format
            include_seconds = source_fmt == '%H:%M:%S'
            return format_time_with_chinese_period(parsed_time.time(), include_seconds=include_seconds)
        except ValueError:
            continue  # Try the next format if there was a parsing error

    # If input was not datetime.time and did not match string formats, raise an error
    raise ValueError(f"Invalid 24-hour time format: {time_to_convert}")


def format_time_with_chinese_period(time_to_format, include_seconds=False) -> str:
    """Format a time value with Chinese 上午/下午 markers."""
    if isinstance(time_to_format, datetime.datetime):
        time_to_format = timezone.localtime(time_to_format).time() if timezone.is_aware(time_to_format) else time_to_format.time()
    if not isinstance(time_to_format, datetime.time):
        raise ValueError(f"Unsupported data type for time formatting: {type(time_to_format)}")

    period = '上午' if time_to_format.hour < 12 else '下午'
    hour = time_to_format.hour % 12 or 12
    fmt = f"{hour:02d}:{time_to_format.minute:02d}"
    if include_seconds:
        fmt = f"{fmt}:{time_to_format.second:02d}"
    return f"{period} {fmt}"


def normalize_period_text(time_str: str) -> str:
    """Normalize Chinese time periods to AM/PM so existing parsers still accept submitted values."""
    return (
        time_str.strip()
        .replace('上午', 'AM')
        .replace('下午', 'PM')
        .upper()
    )


def convert_minutes_in_human_readable_format(minutes: float) -> str:
    """Convert a number of minutes in a human-readable format.

    :param minutes: The number of minutes to convert.
    :return: The converted minutes in a human-readable format.
    """
    if minutes == 0:
        return '未设置'
    if minutes < 0:
        raise ValueError("分钟数不能为负数。")
    days, remaining_minutes = divmod(int(minutes), 1440)
    hours, minutes = divmod(int(remaining_minutes), 60)

    parts = []
    if days:
        days_display = f"{days} 天"
        parts.append(days_display)

    if hours:
        hours_display = f"{hours} 小时"
        parts.append(hours_display)

    if minutes:
        minutes_display = f"{minutes} 分钟"
        parts.append(minutes_display)

    if len(parts) == 1:
        return parts[0]
    elif len(parts) == 2:
        return f"{parts[0]} {parts[1]}"
    elif len(parts) == 3:
        return f"{parts[0]} {parts[1]} {parts[2]}"


def convert_str_to_date(date_str: str) -> datetime.date:
    """Convert a date string to a datetime date object.

    :param date_str: The date string.
                     Supported formats include `%Y-%m-%d` (like "2023-12-31") and `%Y/%m/%d` (like "2023/12/31").
    :return: The converted `datetime.date`'s object.
    """
    date_formats = ['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d']

    for fmt in date_formats:
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass

    raise ValueError(f"Invalid date format for '{date_str}'. Supported formats are YYYY-MM-DD and YYYY/MM/DD.")


def convert_str_to_time(time_str: str) -> datetime.time:
    """Convert a string representation of time to a Python `time` object.

    The function tries both 12-hour and 24-hour formats.

    :param time_str: A string representation of time.
    :return: A Python `time` object.
    """
    formats = ["%I:%M %p", "%p %I:%M", "%H:%M:%S", "%H:%M"]

    for fmt in formats:
        try:
            return datetime.datetime.strptime(normalize_period_text(time_str), fmt).time()
        except ValueError:
            pass

    raise ValueError(
        f"Invalid time format for '{time_str}'. Expected either a 12-hour (e.g., '10:00 AM') or 24-hour (e.g., "
        f"'13:00:00') format.")


def get_ar_end_time(start_time, duration) -> datetime.time:
    """Get the end time of an appointment request based on the start time and the duration.

    :param start_time: The start time of the appointment request.
    :param duration: The duration in minutes or as timedelta of the appointment request.
    :return: The end time of the appointment request.
    """
    # Check types
    if not isinstance(start_time, (datetime.time, str)):
        raise TypeError("start_time must be a datetime.time object or a string in 'HH:MM:SS' format.")

    if not isinstance(duration, (datetime.timedelta, int, float)):
        raise TypeError("duration must be either a datetime.timedelta or a numeric type representing minutes.")

    if isinstance(duration, (int, float)) and duration < 0:
        raise ValueError("duration cannot be negative.")

    # Convert the time object to a datetime object
    if isinstance(start_time, str):
        start_time = convert_str_to_time(start_time)

    dt_start_time = datetime.datetime.combine(datetime.datetime.today(), start_time)

    # Convert duration to minutes if it's a timedelta
    if isinstance(duration, datetime.timedelta):
        duration_minutes = duration.total_seconds() / 60
    else:
        duration_minutes = int(duration)

    # Add the duration
    dt_end_time = dt_start_time + datetime.timedelta(minutes=duration_minutes)

    # If end time goes past midnight, wrap it around
    if dt_end_time.day > dt_start_time.day:
        dt_end_time = dt_end_time - datetime.timedelta(days=1)

    return dt_end_time.time()


def get_timestamp() -> str:
    """Get the current timestamp as a string without the decimal part.

    :return: The current timestamp (e.g. "1612345678")
    """
    timestamp = str(timezone.now().timestamp())
    return timestamp.replace('.', '')


def get_current_year() -> int:
    """Get the current year as an integer.

    :return: The current year
    """
    return timezone.localdate().year


def get_weekday_num(weekday: str) -> int:
    """Get the number of the weekday.

    :param weekday: The weekday (e.g. "Monday", "Tuesday", etc.)
    :return: The number of the weekday (0 for Sunday, 1 for Monday, etc.)
    """
    weekdays = {
        'monday': 1,
        'tuesday': 2,
        'wednesday': 3,
        'thursday': 4,
        'friday': 5,
        'saturday': 6,
        'sunday': 0
    }
    return weekdays.get(weekday.lower(), -1)


def time_difference(time1, time2):
    # If inputs are datetime.time objects, convert them to datetime.datetime objects for the same day
    if isinstance(time1, datetime.time) and isinstance(time2, datetime.time):
        today = datetime.datetime.today()
        datetime1 = datetime.datetime.combine(today, time1)
        datetime2 = datetime.datetime.combine(today, time2)
    elif isinstance(time1, datetime.datetime) and isinstance(time2, datetime.datetime):
        datetime1 = time1
        datetime2 = time2
    else:
        raise ValueError("Both inputs should be of the same type, either datetime.time or datetime.datetime")

    # Check if datetime2 is earlier than datetime1
    if datetime2 < datetime1:
        raise ValueError("The second time provided (time2) should not be earlier than the first time (time1).")

    # Find the difference
    delta = datetime2 - datetime1

    return delta


DATE_FORMATS = {
    'ar': "D، j F Y",                        # "خ، 14 أغسطس 2025" (Arabic: RTL with Arabic comma)
    'bg': "D, j F Y",                        # "чт, 14 август 2025" (Bulgarian: comma after weekday)
    'bn': "D, j F Y",                        # "বৃহ, 14 আগস্ট 2025" (Bengali: comma after weekday)
    'cs': "D j. F Y",                        # "čt 14. srpna 2025" (Czech: period after day)
    'da': "D j. F Y",                        # "tor 14. august 2025" (Danish: period after day)
    'de': "D, j. F Y",                       # "Do, 14. August 2025" (German: period after day)
    'el': "D, j F Y",                        # "Πέμ, 14 Αυγούστου 2025" (Greek: comma after weekday)
    'en': "D, F j, Y",                       # "Thu, August 14, 2025" (English: commas)
    'es': r"D, j \d\e F \d\e Y",               # "jue, 14 de agosto de 2025" (Spanish: with "de")
    'et': "D, j. F Y",                       # "N, 14. august 2025" (Estonian: period after day)
    'fa': "D، j F Y",                        # "پ، 14 اوت 2025" (Persian: RTL with Persian comma)
    'fi': "D j. Fta Y",                      # "to 14. elokuuta 2025" (Finnish: partitive case for month)
    'fr': "D j F Y",                         # "jeu 14 août 2025" (French: no comma, day before month)
    'he': "D، j בF Y",                       # "ה، 14 באוגוסט 2025" (Hebrew: RTL format)
    'hi': "D, j F Y",                        # "गुरु, 14 अगस्त 2025" (Hindi: comma after weekday)
    'hr': "D, j. F Y.",                      # "čet, 14. kolovoza 2025." (Croatian: periods)
    'hu': "Y. F j., D",                      # "2025. augusztus 14., csütörtök" (Hungarian: year first)
    'id': "D, j F Y",                        # "Kam, 14 Agustus 2025" (Indonesian: comma after weekday)
    'it': "D j F Y",                         # "gio 14 agosto 2025" (Italian: no comma, day before month)
    'ja': "Y年Fj日(D)",                       # "2025年八月14日(木)" (Japanese: weekday in parentheses)
    'ko': "Y년 F j일 D",                      # "2025년 8월 14일 목요일" (Korean: spaces between elements)
    'lt': "Y m. F j d., D",                  # "2025 m. rugpjūčio 14 d., ketvirtadienis" (Lithuanian: unique format)
    'lv': r"D, Y. \gada j. F",               # "ceturtd, 2025. gada 14. augusts" (Latvian: unique format)
    'ms': "D, j F Y",                        # "Kha, 14 Ogos 2025" (Malay: comma after weekday)
    'nl': "D j F Y",                         # "do 14 augustus 2025" (Dutch: no comma, day before month)
    'no': "D j. F Y",                        # "tor 14. august 2025" (Norwegian: period after day)
    'pl': "D, j F Y",                        # "czw, 14 sierpnia 2025" (Polish: comma after weekday)
    'pt': r"D, j \de F \de Y",               # "qui, 14 de agosto de 2025" (Portuguese: with "de")
    'ro': "D, j F Y",                        # "joi, 14 august 2025" (Romanian: comma after weekday)
    'ru': "D, j F Y",                        # "чт, 14 август 2025" (Russian: comma after weekday)
    'sk': "D j. F Y",                        # "št 14. augusta 2025" (Slovak: period after day)
    'sl': "D, j. F Y",                       # "čet, 14. avgusta 2025" (Slovenian: period after day)
    'sr': "D, j. F Y.",                      # "чет, 14. августа 2025." (Serbian: periods)
    'sv': "D j F Y",                         # "tors 14 augusti 2025" (Swedish: no comma, day before month)
    'th': r"D\ที่ j F Y",                     # "พฤหัสที่ 14 สิงหาคม 2025" (Thai: with Thai characters)
    'tr': "j F Y D",                         # "14 Ağustos 2025 Perşembe" (Turkish: day-month-year weekday)
    'uk': "D, j F Y",                        # "чт, 14 серпня 2025" (Ukrainian: comma after weekday)
    'vi': r"D, \ngày j \tháng n \năm Y",     # "Th 5, ngày 14 tháng 8 năm 2025" (Vietnamese: with words; corrected to use n for numeric month)
    'zh': "Y年Fj日 D",                        # "2025年八月14日 星期四" (Chinese: year-month-day format)
}
