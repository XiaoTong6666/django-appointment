from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from appointment.models import Appointment, CapacityState

try:
    import redis
except ImportError:  # pragma: no cover - exercised when optional dependency is absent
    redis = None


ENTER_SCRIPT = """
local current = tonumber(redis.call("GET", KEYS[1]) or "0")
local max = tonumber(redis.call("GET", KEYS[2]) or ARGV[1])
if current < max then
    redis.call("INCR", KEYS[1])
    redis.call("SET", KEYS[2], max)
    return 1
end
return 0
"""

LEAVE_SCRIPT = """
local current = tonumber(redis.call("GET", KEYS[1]) or "0")
if current > 0 then
    redis.call("DECR", KEYS[1])
    return 1
end
return 0
"""


@dataclass
class CapacityResult:
    success: bool
    message: str
    current: int
    max_capacity: int
    appointment: Appointment | None = None


def get_max_capacity():
    default_capacity = int(getattr(settings, 'APPOINTMENT_MAX_CAPACITY', 50))
    state = CapacityState.objects.filter(pk=1).only('max_capacity').first()
    return state.max_capacity if state else default_capacity


def _redis_keys():
    prefix = getattr(settings, 'APPOINTMENT_REDIS_PREFIX', 'appointment')
    return f'{prefix}:current_count', f'{prefix}:max_count'


def _get_redis_client():
    if redis is None:
        return None
    client = redis.Redis(
        host=getattr(settings, 'APPOINTMENT_REDIS_HOST', 'redis'),
        port=getattr(settings, 'APPOINTMENT_REDIS_PORT', 6379),
        db=getattr(settings, 'APPOINTMENT_REDIS_DB', 0),
        socket_connect_timeout=0.2,
        socket_timeout=0.5,
        decode_responses=True,
    )
    client.ping()
    return client


def _entered_count_from_db():
    return Appointment.objects.filter(status=Appointment.Status.ENTERED).count()


def _sync_redis_from_db(client):
    current_key, max_key = _redis_keys()
    if client.get(current_key) is None:
        client.set(current_key, _entered_count_from_db())
    client.set(max_key, get_max_capacity())


def get_capacity_status():
    max_capacity = get_max_capacity()
    try:
        client = _get_redis_client()
        if client:
            _sync_redis_from_db(client)
            current_key, max_key = _redis_keys()
            current = int(client.get(current_key) or 0)
            max_capacity = int(client.get(max_key) or max_capacity)
            return {'current': current, 'max': max_capacity, 'available': max(max_capacity - current, 0)}
    except Exception:
        pass

    state = CapacityState.get_instance(max_capacity=max_capacity)
    db_current = _entered_count_from_db()
    if state.current_count != db_current:
        state.current_count = db_current
        state.save(update_fields=['current_count', 'updated_at'])
    return {'current': state.current_count, 'max': state.max_capacity, 'available': max(state.max_capacity - state.current_count, 0)}


def enter_appointment(appointment_id):
    try:
        client = _get_redis_client()
    except Exception:
        client = None

    if client:
        return _enter_with_redis(client, appointment_id)
    return _enter_with_database(appointment_id)


def leave_appointment(appointment_id):
    try:
        client = _get_redis_client()
    except Exception:
        client = None

    if client:
        return _leave_with_redis(client, appointment_id)
    return _leave_with_database(appointment_id)


def _enter_with_redis(client, appointment_id):
    max_capacity = get_max_capacity()
    _sync_redis_from_db(client)
    current_key, max_key = _redis_keys()

    with transaction.atomic():
        appointment = Appointment.objects.select_for_update().get(pk=appointment_id)
        if appointment.status == Appointment.Status.ENTERED:
            status = get_capacity_status()
            return CapacityResult(True, '该预约已经入场。', status['current'], status['max'], appointment)
        if appointment.status in (Appointment.Status.FINISHED, Appointment.Status.CANCELLED):
            status = get_capacity_status()
            return CapacityResult(False, '该预约当前状态不能入场。', status['current'], status['max'], appointment)

        allowed = int(client.eval(ENTER_SCRIPT, 2, current_key, max_key, max_capacity))
        if not allowed:
            status = get_capacity_status()
            return CapacityResult(False, '当前人数已满，不能入场。', status['current'], status['max'], appointment)

        try:
            appointment.mark_entered(timezone.now())
        except Exception:
            client.eval(LEAVE_SCRIPT, 2, current_key, max_key)
            raise

    status = get_capacity_status()
    return CapacityResult(True, '已同意入场。', status['current'], status['max'], appointment)


def _leave_with_redis(client, appointment_id):
    max_capacity = get_max_capacity()
    _sync_redis_from_db(client)
    current_key, max_key = _redis_keys()

    with transaction.atomic():
        appointment = Appointment.objects.select_for_update().get(pk=appointment_id)
        if appointment.status == Appointment.Status.FINISHED:
            status = get_capacity_status()
            return CapacityResult(True, '该预约已经离场。', status['current'], status['max'], appointment)
        if appointment.status != Appointment.Status.ENTERED:
            status = get_capacity_status()
            return CapacityResult(False, '该预约还未入场，不能离场。', status['current'], status['max'], appointment)

        client.eval(LEAVE_SCRIPT, 2, current_key, max_key)
        try:
            appointment.mark_finished(timezone.now())
        except Exception:
            client.eval(ENTER_SCRIPT, 2, current_key, max_key, max_capacity)
            raise

    status = get_capacity_status()
    return CapacityResult(True, '已确认离场并释放名额。', status['current'], status['max'], appointment)


def _enter_with_database(appointment_id):
    max_capacity = get_max_capacity()
    with transaction.atomic():
        state = CapacityState.objects.select_for_update().get_or_create(pk=1, defaults={'max_capacity': max_capacity})[0]
        appointment = Appointment.objects.select_for_update().get(pk=appointment_id)

        if appointment.status == Appointment.Status.ENTERED:
            return CapacityResult(True, '该预约已经入场。', state.current_count, state.max_capacity, appointment)
        if appointment.status in (Appointment.Status.FINISHED, Appointment.Status.CANCELLED):
            return CapacityResult(False, '该预约当前状态不能入场。', state.current_count, state.max_capacity, appointment)
        if state.current_count >= state.max_capacity:
            return CapacityResult(False, '当前人数已满，不能入场。', state.current_count, state.max_capacity, appointment)

        state.current_count += 1
        state.save(update_fields=['current_count', 'updated_at'])
        appointment.mark_entered(timezone.now())
        return CapacityResult(True, '已同意入场。', state.current_count, state.max_capacity, appointment)


def _leave_with_database(appointment_id):
    max_capacity = get_max_capacity()
    with transaction.atomic():
        state = CapacityState.objects.select_for_update().get_or_create(pk=1, defaults={'max_capacity': max_capacity})[0]
        appointment = Appointment.objects.select_for_update().get(pk=appointment_id)

        if appointment.status == Appointment.Status.FINISHED:
            return CapacityResult(True, '该预约已经离场。', state.current_count, state.max_capacity, appointment)
        if appointment.status != Appointment.Status.ENTERED:
            return CapacityResult(False, '该预约还未入场，不能离场。', state.current_count, state.max_capacity, appointment)

        state.current_count = max(state.current_count - 1, 0)
        state.save(update_fields=['current_count', 'updated_at'])
        appointment.mark_finished(timezone.now())
        return CapacityResult(True, '已确认离场并释放名额。', state.current_count, state.max_capacity, appointment)
