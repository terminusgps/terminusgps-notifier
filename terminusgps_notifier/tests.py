import logging

from django.test import TestCase
from django.test.client import Client

logging.disable(logging.WARNING)

# TODO: Add Wialon integration tests
# TODO: Add terminusgps_payments integration tests


class HealthCheckViewTestCase(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_health_check(self) -> None:
        """Fails if the health check endpoint doesn't return status code 200."""
        response = self.client.get("/v3/health/")
        self.assertEqual(response.status_code, 200)


class DispatchNotificationViewTestCase(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_http_post(self) -> None:
        """Fails if an http POST to the notification dispatch view returns status code 200."""
        data = {"unit_id": "12345678", "message": "test"}
        response = self.client.post("/v3/notify/sms/", data=data)
        self.assertNotEqual(response.status_code, 200)

    def test_invalid_method(self) -> None:
        """Fails if a request with an invalid method returns status code 200."""
        response = self.client.get("/v3/notify/not_a_method/")
        self.assertNotEqual(response.status_code, 200)

    def test_non_digit_unit_id(self) -> None:
        """Fails if a request with a non-digit unit id returns status code 200."""
        data = {"unit_id": "", "message": "test"}
        response = self.client.get("/v3/notify/sms/", data=data)
        self.assertNotEqual(response.status_code, 200)

    def test_message_too_long(self) -> None:
        """Fails if a request with a message longer than 2048 characters returns status code 200."""
        data = {"unit_id": "12345678", "message": "test" * 513}
        response = self.client.get("/v3/notify/sms/", data=data)
        self.assertNotEqual(response.status_code, 200)
