import json

from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from appointment.decorators import require_staff_or_superuser
from appointment.models import Appointment
from appointment.utils.capacity import enter_appointment, get_capacity_status, leave_appointment


def _appointment_to_dict(appointment):
    request = appointment.appointment_request
    status_labels = {
        Appointment.Status.BOOKED: '已预约',
        Appointment.Status.ENTERED: '已入场',
        Appointment.Status.FINISHED: '已离场',
        Appointment.Status.CANCELLED: '已取消',
    }
    return {
        'id': appointment.id,
        'client_name': appointment.get_client_name(),
        'client_email': appointment.client.email if appointment.client else '',
        'phone': str(appointment.phone) if appointment.phone else '',
        'address': appointment.address or '',
        'additional_info': appointment.additional_info or '',
        'service': request.service.name,
        'date': request.date.isoformat(),
        'start_time': request.start_time.strftime('%H:%M'),
        'end_time': request.end_time.strftime('%H:%M'),
        'status': appointment.status,
        'status_text': status_labels.get(appointment.status, appointment.status),
        'entered_at': appointment.entered_at.isoformat() if appointment.entered_at else None,
        'left_at': appointment.left_at.isoformat() if appointment.left_at else None,
    }


def _get_appointment_id(request):
    if request.content_type and request.content_type.startswith('application/json'):
        try:
            payload = json.loads(request.body.decode() or '{}')
        except json.JSONDecodeError:
            payload = {}
        return payload.get('appointment_id')
    return request.POST.get('appointment_id')


def _ensure_staff_can_manage(request, appointment):
    if request.user.is_superuser:
        return
    staff_member = appointment.get_staff_member()
    if not staff_member or staff_member.user_id != request.user.id:
        raise PermissionDenied


@require_GET
def capacity_status_api(request):
    return JsonResponse(get_capacity_status())


@require_GET
@require_staff_or_superuser
def today_queue_api(request):
    today = timezone.localdate()
    appointments = Appointment.objects.select_related(
        'client', 'appointment_request__service', 'appointment_request__staff_member__user'
    ).filter(appointment_request__date=today).order_by('appointment_request__start_time')

    if not request.user.is_superuser:
        appointments = appointments.filter(appointment_request__staff_member__user=request.user)

    return JsonResponse({'appointments': [_appointment_to_dict(appointment) for appointment in appointments]})


@require_POST
@require_staff_or_superuser
def enter_api(request):
    appointment_id = _get_appointment_id(request)
    appointment = get_object_or_404(Appointment, pk=appointment_id)
    _ensure_staff_can_manage(request, appointment)

    result = enter_appointment(appointment.id)
    return JsonResponse({
        'success': result.success,
        'message': result.message,
        'current': result.current,
        'max': result.max_capacity,
        'appointment': _appointment_to_dict(result.appointment) if result.appointment else None,
    }, status=200 if result.success else 409)


@require_POST
@require_staff_or_superuser
def leave_api(request):
    appointment_id = _get_appointment_id(request)
    appointment = get_object_or_404(Appointment, pk=appointment_id)
    _ensure_staff_can_manage(request, appointment)

    result = leave_appointment(appointment.id)
    return JsonResponse({
        'success': result.success,
        'message': result.message,
        'current': result.current,
        'max': result.max_capacity,
        'appointment': _appointment_to_dict(result.appointment) if result.appointment else None,
    }, status=200 if result.success else 409)


def user_capacity_page(request):
    return render(request, 'capacity/user_status.html')


@require_staff_or_superuser
def staff_capacity_page(request):
    return render(request, 'capacity/staff_console.html')
