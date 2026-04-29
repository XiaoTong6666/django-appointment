from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse

from appointment.models import Appointment, CapacityState
from appointment.tests.base.base_test import BaseTest
from appointment.utils.capacity import enter_appointment, get_capacity_status, leave_appointment


@override_settings(APPOINTMENT_MAX_CAPACITY=1)
class CapacityApiTest(BaseTest):
    def setUp(self):
        CapacityState.objects.all().delete()

    @patch('appointment.utils.capacity._get_redis_client', return_value=None)
    def test_enter_and_leave_appointment_updates_capacity(self, _redis):
        appointment = self.create_appt_for_sm1()

        enter_result = enter_appointment(appointment.id)
        appointment.refresh_from_db()

        self.assertTrue(enter_result.success)
        self.assertEqual(appointment.status, Appointment.Status.ENTERED)
        self.assertEqual(get_capacity_status()['current'], 1)

        leave_result = leave_appointment(appointment.id)
        appointment.refresh_from_db()

        self.assertTrue(leave_result.success)
        self.assertEqual(appointment.status, Appointment.Status.FINISHED)
        self.assertEqual(get_capacity_status()['current'], 0)

    @patch('appointment.utils.capacity._get_redis_client', return_value=None)
    def test_capacity_limit_blocks_second_entry(self, _redis):
        first = self.create_appt_for_sm1()
        second_request = self.create_appt_request_for_sm2()
        second = self.create_appt_for_sm2(second_request)

        self.assertTrue(enter_appointment(first.id).success)
        second_result = enter_appointment(second.id)
        second.refresh_from_db()

        self.assertFalse(second_result.success)
        self.assertEqual(second.status, Appointment.Status.BOOKED)
        self.assertEqual(get_capacity_status()['current'], 1)

    @patch('appointment.utils.capacity._get_redis_client', return_value=None)
    def test_staff_can_use_enter_leave_api(self, _redis):
        self.need_staff_login()
        appointment = self.create_appt_for_sm1()

        enter_response = self.client.post(
            reverse('appointment:enter_api'),
            data={'appointment_id': appointment.id},
        )
        self.assertEqual(enter_response.status_code, 200)
        self.assertTrue(enter_response.json()['success'])

        leave_response = self.client.post(
            reverse('appointment:leave_api'),
            data={'appointment_id': appointment.id},
        )
        self.assertEqual(leave_response.status_code, 200)
        self.assertTrue(leave_response.json()['success'])

    def test_status_api_is_public(self):
        response = self.client.get(reverse('appointment:capacity_status_api'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('current', response.json())
        self.assertIn('max', response.json())
