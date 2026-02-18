import logging

from django.test import TestCase
from django.test.client import Client

logging.disable(logging.ERROR)


class HealthCheckViewTestCase(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_get(self) -> None:
        """Fails if the health check endpoint doesn't return status code 200."""
        response = self.client.get("/v3/health/")
        self.assertEqual(response.status_code, 200)


class DispatchNotificationViewTestCase(TestCase):
    fixtures = [
        "terminusgps_notifier/tests/test_customer.json",
        "terminusgps_notifier/tests/test_subscription.json",
    ]

    def setUp(self) -> None:
        self.client = Client()
        self.data = {
            "unit_id": "12345678",
            "user_id": "1",
            "msg_time_int": "0",
            "unit_name": "Test Unit",
            "location": "Test Location",
            "message": "Test Message",
            "dry_run": True,
        }

    def test_post(self) -> None:
        """Fails if a POST request doesn't respond with 405."""
        data = self.data.copy()
        response = self.client.post("/v3/notify/sms/", data=data)
        self.assertEqual(response.status_code, 405)

    def test_get_invalid_method(self) -> None:
        """Fails if a request with an invalid method doesn't respond with 400."""
        response = self.client.get("/v3/notify/not_a_method/")
        self.assertEqual(response.status_code, 400)

    def test_get_non_digit_unit_id(self) -> None:
        """Fails if a request with a non-digit unit id parameter doesn't respond with 400."""
        data = self.data.copy()
        data["unit_id"] = ""
        response = self.client.get("/v3/notify/sms/", data=data)
        self.assertEqual(response.status_code, 400)

    def test_get_message_too_long(self) -> None:
        """Fails if a request with a lengthy message doesn't respond with 400."""
        data = self.data.copy()
        data["message"] = "test" * 513
        response = self.client.get("/v3/notify/sms/", data=data)
        self.assertEqual(response.status_code, 400)
