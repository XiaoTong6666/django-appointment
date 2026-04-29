# models.py
# Path: appointment/models.py

"""
Author: Adams Pierre David
Since: 1.0.0
"""
import colorsys
import datetime
import random
import string
import uuid

from babel.numbers import get_currency_symbol
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MinLengthValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _, ngettext
from phonenumber_field.modelfields import PhoneNumberField

from appointment.utils.date_time import convert_minutes_in_human_readable_format, get_timestamp, get_weekday_num, \
    time_difference
from appointment.utils.view_helpers import generate_random_id, get_locale

PAYMENT_TYPES = (
    ('full', '全额支付'),
    ('down', '支付定金'),
)

DAYS_OF_WEEK = (
    (0, '星期日'),
    (1, '星期一'),
    (2, '星期二'),
    (3, '星期三'),
    (4, '星期四'),
    (5, '星期五'),
    (6, '星期六'),
)


def generate_rgb_color():
    hue = random.random()  # Random hue between 0 and 1
    saturation = 0.9  # High saturation to ensure a vivid color
    value = 0.9  # High value to ensure a bright color

    r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)

    # Convert to 0-255 RGB values
    r = int(r * 255)
    g = int(g * 255)
    b = int(b * 255)

    return f'rgb({r}, {g}, {b})'


class Service(models.Model):
    """
    Represents a service provided by the appointment system.

    Author: Adams Pierre David
    Version: 1.1.0
    Since: 1.0.0
    """
    name = models.CharField(max_length=100, blank=False, verbose_name='名称')
    description = models.TextField(blank=True, null=True, verbose_name='描述')
    duration = models.DurationField(
        validators=[MinValueValidator(datetime.timedelta(seconds=1))],
        verbose_name='时长'
    )
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='价格'
    )
    down_payment = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='定金'
    )
    image = models.ImageField(upload_to='services/', blank=True, null=True, verbose_name='图像', )
    currency = models.CharField(
        max_length=3,
        default='USD',
        validators=[MaxLengthValidator(3), MinLengthValidator(3)],
        verbose_name='币种'
    )
    background_color = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        default=generate_rgb_color,
        verbose_name='背景颜色'
    )
    reschedule_limit = models.PositiveIntegerField(
        default=0,
        help_text='该服务允许改约的最大次数。',
        verbose_name='改约次数上限'
    )
    allow_rescheduling = models.BooleanField(
        default=False,
        help_text='是否允许该服务的预约进行改约。',
        verbose_name='允许改约'
    )
    use_service_duration_as_slot = models.BooleanField(
        default=True,
        verbose_name='使用服务时长作为时间段',
        help_text=(
            '启用后，系统检查可预约时间时会使用该服务的实际时长，避免服务时长超过默认时间段时发生重叠。'
            '仅当系统配置中的“默认使用服务时长”关闭时，此设置才会生效。'
        )
    )

    # meta data
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '服务'
        verbose_name_plural = '服务'
        ordering = ['name']  # alphabetical by default
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['price']),
        ]

    def __str__(self):
        return self.name

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": str(self.price)  # Convert Decimal to string for JSON serialization
        }

    def get_duration_parts(self):
        total_seconds = int(self.duration.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return days, hours, minutes, seconds

    def get_duration(self):
        days, hours, minutes, seconds = self.get_duration_parts()
        parts = []

        if days:
            parts.append(f"{days} 天")

        if hours:
            parts.append(f"{hours} 小时")

        if minutes:
            parts.append(f"{minutes} 分钟")

        if seconds:
            parts.append(f"{seconds} 秒")

        return ' '.join(parts)

    def get_price(self):
        # Check if the decimal part is 0
        if self.price % 1 == 0:
            return int(self.price)  # Return as an integer
        else:
            return self.price  # Return the original float value

    def get_currency_icon(self):
        return get_currency_symbol(self.currency, locale=get_locale())

    def get_price_text(self):
        if self.price == 0:
            return '免费'
        else:
            return f"{self.get_price()}{self.get_currency_icon()}"

    def get_down_payment(self):
        if self.down_payment % 1 == 0:
            return int(self.down_payment)  # Return as an integer
        else:
            return self.down_payment  # Return the original float value

    def get_down_payment_text(self):
        if self.down_payment == 0:
            return f"Free"
        return f"{self.get_down_payment()}{self.get_currency_icon()}"

    def get_image_url(self):
        if not self.image:
            return ""
        return self.image.url

    def is_a_paid_service(self):
        return self.price > 0

    def accepts_down_payment(self):
        return self.down_payment > 0


class StaffMember(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='用户')
    services_offered = models.ManyToManyField(
        Service,
        verbose_name='提供的服务',
        help_text='该店员可以提供的服务。'
    )
    slot_duration = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='时间段间隔',
        help_text='预约时间段的最小间隔，单位为分钟，建议填写 30。'
    )
    lead_time = models.TimeField(
        null=True, blank=True,
        verbose_name='开始营业时间',
        help_text='该店员开始工作的时间。'
    )
    finish_time = models.TimeField(
        null=True, blank=True,
        verbose_name='结束营业时间',
        help_text='该店员结束工作的时间。'
    )
    appointment_buffer_time = models.FloatField(
        blank=True, null=True,
        verbose_name='预约缓冲时间',
        help_text='从当前时间到当天第一个可预约时间段之间的缓冲时间，单位为分钟，不影响明天及之后的预约。'
    )
    slot_gap_time = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='预约间隔时间',
        help_text='两个预约之间需要预留的休息时间，单位为分钟。该设置会覆盖全局系统配置。'
    )
    work_on_saturday = models.BooleanField(
        default=False,
        verbose_name='星期六工作',
        help_text='该店员是否在星期六工作。'
    )
    work_on_sunday = models.BooleanField(
        default=False,
        verbose_name='星期日工作',
        help_text='该店员是否在星期日工作。'
    )

    # meta data
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '店员'
        verbose_name_plural = '店员'
        ordering = ['user__first_name', 'user__last_name']

    def __str__(self):
        return f"{self.get_staff_member_name()}"

    def get_slot_duration(self):
        config = Config.objects.first()
        return self.slot_duration or (config.slot_duration if config else 0)

    def get_slot_duration_text(self):
        slot_duration = self.get_slot_duration()
        return convert_minutes_in_human_readable_format(slot_duration)

    def get_lead_time(self):
        config = Config.objects.first()
        return self.lead_time or (config.lead_time if config else None)

    def get_finish_time(self):
        config = Config.objects.first()
        return self.finish_time or (config.finish_time if config else None)

    def works_on_both_weekends_day(self):
        return self.work_on_saturday and self.work_on_sunday

    def get_staff_member_name(self):
        from appointment.utils.db_helpers import username_in_user_model
        # Try get_full_name method first
        full_name = getattr(self.user, 'get_full_name', lambda: '')()
        if full_name and full_name.strip():
            return full_name.strip()

        # Try first_name + last_name
        first = getattr(self.user, 'first_name', '')
        last = getattr(self.user, 'last_name', '')
        combined = f"{first} {last}".strip()
        if combined:
            return combined

        # Try username only if it exists in the user model
        if username_in_user_model():
            username = getattr(self.user, 'username', '')
            if username and username.strip():
                return username.strip()

        # Try email
        email = getattr(self.user, 'email', '')
        if email and email.strip():
            return email.strip()

        # Fallback
        return f"店员 {self.id}"

    def get_staff_member_first_name(self):
        return self.user.first_name

    def get_non_working_days(self):
        non_working_days = []

        if not self.work_on_saturday:
            non_working_days.append(6)  # Saturday
        if not self.work_on_sunday:
            non_working_days.append(0)  # Sunday
        return non_working_days

    def get_weekend_days_worked_text(self):
        if self.work_on_saturday and self.work_on_sunday:
            return '星期六和星期日'
        elif self.work_on_saturday:
            return '星期六'
        elif self.work_on_sunday:
            return '星期日'
        else:
            return '无'

    def get_services_offered(self):
        return self.services_offered.all()

    def get_service_offered_text(self):
        return ', '.join([service.name for service in self.services_offered.all()])

    def get_service_is_offered(self, service_id):
        return self.services_offered.filter(id=service_id).exists()

    def get_appointment_buffer_time(self):
        config = Config.objects.first()
        return self.appointment_buffer_time or (config.appointment_buffer_time if config else 0)

    def get_appointment_buffer_time_text(self):
        # convert buffer time (which is in minutes) in day hours minutes if necessary
        return convert_minutes_in_human_readable_format(self.get_appointment_buffer_time())

    def get_days_off(self):
        return DayOff.objects.filter(staff_member=self)

    def get_working_hours(self):
        return self.workinghours_set.all()

    def update_upon_working_hours_deletion(self, day_of_week: int):
        if day_of_week == 6:
            self.work_on_saturday = False
        elif day_of_week == 0:
            self.work_on_sunday = False
        self.save()

    def is_working_day(self, day: int):
        return day not in self.get_non_working_days()


class AppointmentRequest(models.Model):
    """
    Represents an appointment request made by a client.

    Author: Adams Pierre David
    Since: 1.0.0
    """
    date = models.DateField(verbose_name='日期', help_text='预约请求的日期。')
    start_time = models.TimeField(
        verbose_name='开始时间',
        help_text='预约请求的开始时间。'
    )
    end_time = models.TimeField(
        verbose_name='结束时间',
        help_text='预约请求的结束时间。'
    )
    service = models.ForeignKey(Service, on_delete=models.CASCADE, verbose_name='服务')
    staff_member = models.ForeignKey(StaffMember, on_delete=models.SET_NULL, null=True, verbose_name='店员')
    payment_type = models.CharField(
        max_length=4,
        choices=PAYMENT_TYPES,
        default='full',
        verbose_name='支付类型'
    )
    id_request = models.CharField(max_length=100, blank=True, null=True, verbose_name='请求编号')
    reschedule_attempts = models.PositiveIntegerField(
        default=0,
        verbose_name='改约次数',
        help_text='该预约已经改约的次数。'
    )

    # meta data
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '预约请求'
        verbose_name_plural = '预约请求'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['date', 'start_time']),
            models.Index(fields=['staff_member', 'date']),
        ]

    def __str__(self):
        return f"{self.date} - {self.start_time} to {self.end_time} - {self.service.name}"

    def clean(self):
        if self.start_time is not None and self.end_time is not None:
            if self.start_time > self.end_time:
                raise ValidationError('开始时间必须早于结束时间')
            if self.start_time == self.end_time:
                raise ValidationError('开始时间和结束时间不能相同')

        # Ensure the date is not in the past:
        if self.date and self.date < timezone.localdate():
            raise ValidationError('日期不能早于今天')

    def save(self, *args, **kwargs):
        # if no id_request is provided, generate one
        if self.id_request is None:
            self.id_request = f"{get_timestamp()}{self.service.id}{generate_random_id()}"
        # start time should not be equal to end time
        if self.start_time == self.end_time:
            raise ValidationError('开始时间和结束时间不能相同')
        # date should not be in the past
        if self.date < timezone.localdate():
            raise ValidationError('日期不能早于今天')
        # duration should not exceed the service duration
        if time_difference(self.start_time, self.end_time) > self.service.duration:
            raise ValidationError('预约时长不能超过服务时长')
        return super().save(*args, **kwargs)

    def get_service_name(self):
        return self.service.name

    def get_service_price(self):
        return self.service.get_price()

    def get_service_down_payment(self):
        return self.service.get_down_payment()

    def get_service_image(self):
        return self.service.image

    def get_service_image_url(self):
        return self.service.get_image_url()

    def get_service_description(self):
        return self.service.description

    def get_id_request(self):
        return self.id_request

    def is_a_paid_service(self):
        return self.service.is_a_paid_service()

    def accepts_down_payment(self):
        return self.service.accepts_down_payment()

    def can_be_rescheduled(self):
        return self.reschedule_attempts < self.service.reschedule_limit

    def increment_reschedule_attempts(self):
        self.reschedule_attempts += 1
        self.save(update_fields=['reschedule_attempts'])

    def get_reschedule_history(self):
        return self.reschedule_histories.all().order_by('-created_at')


class AppointmentRescheduleHistory(models.Model):
    appointment_request = models.ForeignKey(
        'AppointmentRequest',
        on_delete=models.CASCADE, related_name='reschedule_histories',
        verbose_name='预约请求',
        help_text='客户提交的预约请求。'
    )
    date = models.DateField(
        verbose_name='日期',
        help_text='改约前的预约日期。'
    )
    start_time = models.TimeField(
        verbose_name='开始时间',
        help_text='改约前的预约开始时间。'
    )
    end_time = models.TimeField(
        verbose_name='结束时间',
        help_text='改约前的预约结束时间。'
    )
    staff_member = models.ForeignKey(
        StaffMember, on_delete=models.SET_NULL, null=True,
        verbose_name='店员',
        help_text='改约前负责该预约的店员。'
    )
    reason_for_rescheduling = models.TextField(
        blank=True, null=True,
        verbose_name='改约原因',
        help_text='本次改约的原因。'
    )
    reschedule_status = models.CharField(
        max_length=10,
        choices=[('pending', '待确认'), ('confirmed', '已确认')],
        default='pending',
        verbose_name='改约状态',
        help_text='本次改约操作的当前状态。'
    )
    id_request = models.CharField(max_length=100, blank=True, null=True, verbose_name='请求编号',)

    # meta data
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间',
        help_text='该改约记录创建的日期和时间。'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间',
        help_text='该改约记录最后更新或确认的日期和时间。'
    )

    class Meta:
        verbose_name = '改约记录'
        verbose_name_plural = '改约记录'
        ordering = ['-created_at']

    def __str__(self):
        return f"Reschedule history for {self.appointment_request} from {self.date}"

    def save(self, *args, **kwargs):
        # if no id_request is provided, generate one
        if self.id_request is None:
            self.id_request = f"{get_timestamp()}{generate_random_id()}"
        # date should not be in the past
        if self.date < timezone.localdate():
            raise ValidationError('日期不能早于今天')
        try:
            datetime.datetime.strptime(str(self.date), '%Y-%m-%d')
        except ValueError:
            raise ValidationError('日期格式无效')
        return super().save(*args, **kwargs)

    def still_valid(self):
        # if more than 5 minutes have passed, it is no longer valid
        now = timezone.now()  # This is offset-aware to match self.created_at
        delta = now - self.created_at
        return delta.total_seconds() < 300


class Appointment(models.Model):
    """
    Represents an appointment made by a client. It is created when the client confirms the appointment request.

    Author: Adams Pierre David
    Version: 1.1.0
    Since: 1.0.0
    """
    class Status(models.TextChoices):
        BOOKED = 'booked', '已预约'
        ENTERED = 'entered', '已入场'
        FINISHED = 'finished', '已离场'
        CANCELLED = 'cancelled', '已取消'

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='客户',
        help_text='提交该预约请求的用户。'
    )
    appointment_request = models.OneToOneField(
        AppointmentRequest,
        on_delete=models.CASCADE,
        verbose_name='预约请求',
        help_text='客户提交的预约请求。'
    )
    phone = PhoneNumberField(blank=True, verbose_name='电话号码')
    address = models.CharField(
        max_length=255,
        blank=True, null=True,
        default="",
        verbose_name='地址',
        help_text='可填写城市、区域或简要地址，不必过于详细。'
    )
    want_reminder = models.BooleanField(
        default=False,
        verbose_name='需要提醒',
        help_text='客户是否希望收到预约提醒。'
    )
    additional_info = models.TextField(
        blank=True, null=True,
        verbose_name='附加信息',
        help_text='客户希望补充说明的其他信息。'
    )
    paid = models.BooleanField(
        default=False,
        verbose_name='已支付',
        help_text='该预约是否已经付款。'
    )
    amount_to_pay = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True, null=True,
        verbose_name='应付金额',
        help_text='该预约需要支付的金额。若为 0，表示免费或已经支付。'
    )
    id_request = models.CharField(max_length=100, blank=True, null=True, verbose_name='请求编号')
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.BOOKED,
        verbose_name='状态',
        help_text='该预约当前的入场生命周期状态。'
    )
    entered_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='入场时间',
        help_text='客户被允许入场的时间。'
    )
    left_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='离场时间',
        help_text='客户离场并释放名额的时间。'
    )

    # meta datas
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '预约'
        verbose_name_plural = '预约'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['status']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount_to_pay__gte=0),
                name='positive_amount_to_pay'
            )
        ]

    def __str__(self):
        return f"{self.client} - " \
               f"{self.appointment_request.start_time.strftime('%Y-%m-%d %H:%M')} to " \
               f"{self.appointment_request.end_time.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        if not hasattr(self, 'appointment_request'):
            raise ValidationError('预约请求不能为空')

        if self.id_request is None:
            self.id_request = f"{get_timestamp()}{self.appointment_request.id}{generate_random_id()}"
        if self.amount_to_pay is None or self.amount_to_pay == 0:
            payment_type = self.appointment_request.payment_type
            if payment_type == 'full':
                self.amount_to_pay = self.appointment_request.get_service_price()
            elif payment_type == 'down':
                self.amount_to_pay = self.appointment_request.get_service_down_payment()
            else:
                self.amount_to_pay = 0
        return super().save(*args, **kwargs)

    def get_client_name(self):
        if hasattr(self.client, 'get_full_name') and callable(getattr(self.client, 'get_full_name')):
            name = self.client.get_full_name()
        else:
            name = self.client.first_name
        return name

    def get_date(self):
        return self.appointment_request.date

    def get_start_time(self):
        return datetime.datetime.combine(self.get_date(), self.appointment_request.start_time)

    def get_end_time(self):
        return datetime.datetime.combine(self.get_date(), self.appointment_request.end_time)

    def get_service(self):
        return self.appointment_request.service

    def get_service_name(self):
        return self.appointment_request.get_service_name()

    def get_service_duration(self):
        return self.appointment_request.service.get_duration()

    def get_staff_member_name(self):
        if not self.appointment_request.staff_member:
            return ""
        return self.appointment_request.staff_member.get_staff_member_name()

    def get_staff_member(self):
        return self.appointment_request.staff_member

    def mark_entered(self, when=None):
        self.status = self.Status.ENTERED
        self.entered_at = when or timezone.now()
        self.left_at = None
        self.save(update_fields=['status', 'entered_at', 'left_at', 'updated_at'])

    def mark_finished(self, when=None):
        self.status = self.Status.FINISHED
        self.left_at = when or timezone.now()
        self.save(update_fields=['status', 'left_at', 'updated_at'])

    def get_service_price(self):
        return self.appointment_request.get_service_price()

    def get_service_down_payment(self):
        return self.appointment_request.get_service_down_payment()

    def get_service_img(self):
        return self.appointment_request.get_service_image()

    def get_service_img_url(self):
        return self.appointment_request.get_service_image_url()

    def get_service_description(self):
        return self.appointment_request.get_service_description()

    def get_appointment_date(self):
        return self.appointment_request.date

    def is_paid(self):
        if self.get_service_price() == 0 or (self.amount_to_pay is not None and self.amount_to_pay == 0):
            return True
        return self.paid

    def service_is_paid(self):
        return self.get_service_price() != 0

    def is_paid_text(self):
        return '是' if self.is_paid() else '否'

    def get_appointment_amount_to_pay(self):
        # Check if the decimal part is 0
        if self.amount_to_pay % 1 == 0:
            return int(self.amount_to_pay)  # Return as an integer
        else:
            return self.amount_to_pay  # Return the original float value

    def get_appointment_amount_to_pay_text(self):
        if self.amount_to_pay == 0 and self.get_service_price() == 0:
            return '免费'
        return f"{self.get_appointment_amount_to_pay()}{self.get_service().get_currency_icon()}"

    def get_appointment_currency(self):
        return self.appointment_request.service.currency

    def wants_reminder_text(self):
        return '是' if self.want_reminder else '否'

    def get_appointment_id_request(self):
        return self.id_request

    def set_appointment_paid_status(self, status: bool):
        self.paid = status
        self.save()

    def get_absolute_url(self, request=None):
        url = reverse('appointment:display_appointment', args=[str(self.id)])
        return request.build_absolute_uri(url) if request else url

    def get_background_color(self):
        return self.appointment_request.service.background_color

    @staticmethod
    def is_valid_date(appt_date, start_time, staff_member, current_appointment_id, weekday: str):
        weekday_num = get_weekday_num(weekday)
        sm_name = staff_member.get_staff_member_name()

        # Check if the staff member works on the given day
        try:
            working_hours = WorkingHours.objects.get(staff_member=staff_member, day_of_week=weekday_num)
        except WorkingHours.DoesNotExist:
            message = f"{sm_name} 当天不工作。"
            return False, message

        # Check if the start time falls within the staff member's working hours
        if not (working_hours.start_time <= start_time.time() <= working_hours.end_time):
            message = f"预约开始时间不在 {sm_name} 的营业时间内。"
            return False, message

        max_capacity = CapacityState.objects.filter(pk=1).values_list('max_capacity', flat=True).first()
        if max_capacity is None:
            max_capacity = int(getattr(settings, 'APPOINTMENT_MAX_CAPACITY', 50))

        overlapping_count = Appointment.objects.filter(
            appointment_request__date=appt_date,
            appointment_request__start_time__lte=start_time.time(),
            appointment_request__end_time__gte=start_time.time(),
            status__in=(Appointment.Status.BOOKED, Appointment.Status.ENTERED),
        ).exclude(id=current_appointment_id).count()
        if overlapping_count >= max_capacity:
            message = f"该时间段预约人数已达到最大容量 {max_capacity} 人。"
            return False, message

        # Check if the staff member has a day off on the appointment's date
        days_off = DayOff.objects.filter(staff_member=staff_member, start_date__lte=appt_date, end_date__gte=appt_date)
        if days_off.exists():
            message = f"{sm_name} 在该日期休息。"
            return False, message

        return True, ""

    def is_owner(self, staff_user_id):
        return self.appointment_request.staff_member.user.id == staff_user_id

    def to_dict(self):
        return {
            "id": self.id,
            "client_name": self.get_client_name(),
            "client_email": self.client.email,
            "start_time": self.appointment_request.start_time.strftime('%Y-%m-%d %H:%M'),
            "end_time": self.appointment_request.end_time.strftime('%Y-%m-%d %H:%M'),
            "service_name": self.appointment_request.service.name,
            "address": self.address,
            "want_reminder": self.want_reminder,
            "additional_info": self.additional_info,
            "paid": self.paid,
            "amount_to_pay": self.amount_to_pay,
            "id_request": self.id_request,
        }


class Config(models.Model):
    """
    Represents configuration settings for the appointment system. There can only be one Config object in the database.
    If you want to change the settings, you must edit the existing Config object.

    Author: Adams Pierre David
    Version: 1.1.0
    Since: 1.1.0
    """
    slot_duration = models.PositiveIntegerField(
        null=True,
        verbose_name='时间段间隔',
        help_text='预约时间段的最小间隔，单位为分钟，建议填写 30。',
    )
    lead_time = models.TimeField(
        null=True,
        verbose_name='开始营业时间',
        help_text='门店开始营业的时间。',
    )
    finish_time = models.TimeField(
        null=True,
        verbose_name='结束营业时间',
        help_text='门店结束营业的时间。',
    )
    appointment_buffer_time = models.FloatField(
        null=True,
        verbose_name='预约缓冲时间',
        help_text='从当前时间到当天第一个可预约时间段之间的缓冲时间，不影响明天及之后的预约。',
    )
    website_name = models.CharField(
        max_length=255,
        default="",
        verbose_name='网站名称',
        help_text='当前预约网站显示的名称。',
    )
    app_offered_by_label = models.CharField(
        max_length=255,
        default='服务人员',
        verbose_name='服务人员标签',
        help_text='预约页面中用于展示服务人员的标签文字。'
    )
    default_reschedule_limit = models.PositiveIntegerField(
        default=3,
        verbose_name='默认改约次数上限',
        help_text='所有服务默认允许改约的最大次数。'
    )
    allow_staff_change_on_reschedule = models.BooleanField(
        default=True,
        verbose_name='改约时允许更换店员',
        help_text='客户改约时是否允许更换负责该预约的店员。'
    )
    default_to_service_duration = models.BooleanField(
        default=True,
        verbose_name='默认使用服务时长',
        help_text=(
            '启用后，所有服务在检查可预约时间时都会自动使用各自的服务时长，避免长服务发生时间重叠。'
            '关闭后，将使用每个服务自己的“使用服务时长作为时间段”设置。'
        )
    )
    slot_gap_time = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='预约间隔时间',
        help_text='两个预约之间需要预留的休息时间，单位为分钟。除非店员单独配置，否则该设置应用于所有店员。'
    )

    # meta data
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '系统配置'
        verbose_name_plural = '系统配置'
        ordering = ['-created_at']

    def clean(self):
        if Config.objects.exists() and not self.pk:
            raise ValidationError('只能创建一个系统配置')
        if self.lead_time is not None and self.finish_time is not None:
            if self.lead_time >= self.finish_time:
                raise ValidationError('开始营业时间必须早于结束营业时间')
        if self.appointment_buffer_time is not None and self.appointment_buffer_time < 0:
            raise ValidationError('预约缓冲时间不能为负数')
        if self.slot_duration is not None and self.slot_duration <= 0:
            raise ValidationError('时间段间隔必须大于 0')

    def save(self, *args, **kwargs):
        self.clean()
        self.pk = 1
        super(Config, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_instance(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Config {self.pk}: slot_duration={self.slot_duration}, lead_time={self.lead_time}, " \
               f"finish_time={self.finish_time}"


class CapacityState(models.Model):
    """Singleton fallback counter used when Redis is unavailable."""

    current_count = models.PositiveIntegerField(default=0, verbose_name='当前在场人数')
    max_capacity = models.PositiveIntegerField(default=50, verbose_name='最大容量')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '容量状态'
        verbose_name_plural = '容量状态'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_instance(cls, max_capacity=50):
        return cls.objects.get_or_create(pk=1, defaults={'max_capacity': max_capacity})[0]


class PaymentInfo(models.Model):
    """
    Represents payment information for an appointment.

    Author: Adams Pierre David
    Version: 1.1.0
    Since: 1.0.0
    """
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, verbose_name='预约')

    # meta data
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '支付信息'
        verbose_name_plural = '支付信息'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.appointment.get_service_name()} - {self.appointment.get_service_price()}"

    def __repr__(self):
        return f"{self.appointment.get_service_name()} - {self.appointment.get_service_price()}"

    def get_id_request(self):
        return self.appointment.get_appointment_id_request()

    def get_amount_to_pay(self):
        return self.appointment.get_appointment_amount_to_pay()

    def get_currency(self):
        return self.appointment.get_appointment_currency()

    def get_name(self):
        return self.appointment.get_service_name()

    def get_img_url(self):
        return self.appointment.get_service_img_url()

    def set_paid_status(self, status: bool):
        self.appointment.set_appointment_paid_status(status)

    def get_user_name(self):
        return self.appointment.client.first_name

    def get_user_email(self):
        return self.appointment.client.email


class EmailVerificationCode(models.Model):
    """
    Represents an email verification code for a user when the email already exists in the database.

    Author: Adams Pierre David
    Version: 1.1.0
    Since: 1.1.0
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='用户')
    code = models.CharField(
        max_length=6,
        verbose_name='验证码',
        help_text='发送到用户邮箱的验证码。'
    )

    # meta data
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '邮箱验证码'
        verbose_name_plural = '邮箱验证码'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code}"

    @classmethod
    def generate_code(cls, user):
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        verification_code = cls(user=user, code=code)
        verification_code.save()
        return code

    def check_code(self, code):
        return self.code == code


class PasswordResetToken(models.Model):
    """
    Represents a password reset token for users.

    Author: Adams Pierre David
    Version: 3.x.x
    Since: 3.x.x
    """

    class TokenStatus(models.TextChoices):
        ACTIVE = 'active', '有效'
        VERIFIED = 'verified', '已验证'
        INVALIDATED = 'invalidated', '已失效'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens',
        verbose_name='用户',
    )
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name='令牌')
    expires_at = models.DateTimeField(verbose_name='过期时间')
    status = models.CharField(
        max_length=11,
        choices=TokenStatus.choices,
        default=TokenStatus.ACTIVE,
        verbose_name='状态',
    )

    # meta data
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '密码重置令牌'
        verbose_name_plural = '密码重置令牌'
        ordering = ['-created_at']

    def __str__(self):
        return f"Password reset token for {self.user} [{self.token} status: {self.status} expires at {self.expires_at}]"

    @property
    def is_expired(self):
        """Checks if the token has expired."""
        return timezone.now() >= self.expires_at

    @property
    def is_verified(self):
        """Checks if the token has been verified."""
        return self.status == self.TokenStatus.VERIFIED

    @property
    def is_active(self):
        """Checks if the token is still active."""
        return self.status == self.TokenStatus.ACTIVE

    @property
    def is_invalidated(self):
        """Checks if the token has been invalidated."""
        return self.status == self.TokenStatus.INVALIDATED

    @classmethod
    def create_token(cls, user, expiration_minutes=60):
        """
        Generates a new token for the user with a specified expiration time.
        Before creating a new token, invalidate all previous active tokens by marking them as invalidated.
        """
        cls.objects.filter(user=user, expires_at__gte=timezone.now(), status=cls.TokenStatus.ACTIVE).update(
            status=cls.TokenStatus.INVALIDATED)
        expires_at = timezone.now() + timezone.timedelta(minutes=expiration_minutes)
        token = cls.objects.create(user=user, expires_at=expires_at, status=cls.TokenStatus.ACTIVE)
        return token

    def mark_as_verified(self):
        """
        Marks the token as verified.
        """
        self.status = self.TokenStatus.VERIFIED
        self.save(update_fields=['status'])

    @classmethod
    def verify_token(cls, user, token):
        """
        Verifies if the provided token is valid and belongs to the given user.
        Additionally, checks if the token has not been marked as verified.
        """
        try:
            return cls.objects.get(user=user, token=token, expires_at__gte=timezone.now(),
                                   status=cls.TokenStatus.ACTIVE)
        except cls.DoesNotExist:
            return None


class DayOff(models.Model):
    staff_member = models.ForeignKey(StaffMember, on_delete=models.CASCADE, verbose_name='店员')
    start_date = models.DateField(verbose_name='开始日期')
    end_date = models.DateField(verbose_name='结束日期')
    description = models.CharField(max_length=255, blank=True, null=True, verbose_name='描述')

    # meta data
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '休息日'
        verbose_name_plural = '休息日'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.start_date} 到 {self.end_date} - {self.description if self.description else '休息日'}"

    def clean(self):
        if self.start_date is not None and self.end_date is not None:
            if self.start_date > self.end_date:
                raise ValidationError('开始日期必须早于结束日期')

    def is_owner(self, user_id):
        return self.staff_member.user.id == user_id


class WorkingHours(models.Model):
    staff_member = models.ForeignKey(StaffMember, on_delete=models.CASCADE, verbose_name='店员')
    day_of_week = models.PositiveIntegerField(choices=DAYS_OF_WEEK, verbose_name='星期')
    start_time = models.TimeField(verbose_name='开始时间')
    end_time = models.TimeField(verbose_name='结束时间')

    # meta data
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '营业时间'
        verbose_name_plural = '营业时间'
        ordering = ['day_of_week', 'start_time']
        unique_together = ['staff_member', 'day_of_week']
        constraints = [
            models.CheckConstraint(
                check=models.Q(start_time__lt=models.F('end_time')),
                name='start_time_before_end_time'
            )
        ]

    def __str__(self):
        return f"{self.get_day_of_week_display()} - {self.start_time} 到 {self.end_time}"

    def save(self, *args, **kwargs):
        # Call the original save method
        super(WorkingHours, self).save(*args, **kwargs)

        # Update staff member's weekend working status
        if self.day_of_week == '6' or self.day_of_week == 6:  # Saturday
            self.staff_member.work_on_saturday = True
        elif self.day_of_week == '0' or self.day_of_week == 0:  # Sunday
            self.staff_member.work_on_sunday = True
        self.staff_member.save()

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError('开始时间必须早于结束时间')

    def get_start_time(self):
        return self.start_time

    def get_end_time(self):
        return self.end_time

    def get_day_of_week_str(self):
        # return the name of the day instead of the integer
        return self.get_day_of_week_display()

    def is_owner(self, user_id):
        return self.staff_member.user.id == user_id
