from django.test import TestCase
from django.test.client import Client


class DispatchNotificationViewTestCase(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_invalid_method(self) -> None:
        response = self.client.post("/notify/not_a_method/")
        self.assertEqual(response.status_code, 406)

    def test_non_digit_unit_id(self) -> None:
        data = {"unit_id": "", "message": "Test Message"}
        response = self.client.post("/notify/sms/", data=data)
        self.assertEqual(response.status_code, 406)

    def test_message_too_long(self) -> None:
        data = {"unit_id": "12345678", "message": "a" * 2049}
        response = self.client.post("/notify/sms/", data=data)
        self.assertEqual(response.status_code, 406)
