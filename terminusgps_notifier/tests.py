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
    def setUp(self) -> None:
        self.client = Client()

    def test_post(self) -> None:
        """Fails if a POST request doesn't respond with 405."""
        response = self.client.post("/v3/notify/sms/", data={})
        self.assertEqual(response.status_code, 405)

    def test_get_invalid_method(self) -> None:
        """Fails if a request with an invalid method doesn't respond with 404."""
        response = self.client.get("/v3/notify/not_a_method/")
        self.assertEqual(response.status_code, 404)
