from django.test import TestCase
from django.test.client import Client
from django.test.utils import override_settings


class CheckHealthViewTestCase(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_check_health(self) -> None:
        response = self.client.get("")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"I'm alive")


class DispatchNotificationViewTestCase(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_invalid_method(self) -> None:
        response = self.client.get("/v3/notify/not_a_method/")
        self.assertEqual(response.status_code, 406)

    def test_non_digit_unit_id(self) -> None:
        data = {"unit_id": "", "message": "Test Message"}
        response = self.client.get("/v3/notify/sms/", data=data)
        self.assertEqual(response.status_code, 406)

    def test_message_too_long(self) -> None:
        data = {"unit_id": "12345678", "message": "a" * 2049}
        response = self.client.get("/v3/notify/sms/", data=data)
        self.assertEqual(response.status_code, 406)

    @override_settings(DEBUG=True)
    def test_send_sms_notification(self) -> None:
        data = {"unit_id": "28121664", "message": "Test Message"}
        response = self.client.get("/v3/notify/sms/", data=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.content,
            b"Sent 'Test Message' to: ['+17133049421'] via sms",
        )

    @override_settings(DEBUG=True)
    def test_send_voice_notification(self) -> None:
        data = {"unit_id": "28121664", "message": "Test Message"}
        response = self.client.get("/v3/notify/call/", data=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.content,
            b"Sent 'Test Message' to: ['+17133049421'] via call",
        )
