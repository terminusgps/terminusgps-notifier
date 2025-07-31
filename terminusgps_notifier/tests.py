import logging
import uuid

from django.test import TestCase
from django.test.client import Client
from django.test.utils import override_settings
from terminusgps.wialon import utils as wialon_utils
from terminusgps.wialon.items import WialonResource, WialonUnit
from terminusgps.wialon.session import WialonSession

logging.disable(logging.WARNING)


class HealthCheckViewTestCase(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_health_check(self) -> None:
        """Fails if the health check endpoint doesn't return status code 200."""
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)


class DispatchNotificationViewTestCase(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_http_post(self) -> None:
        """Fails if an http POST to the notification dispatch view returns status code 200."""
        data = {"unit_id": "12345678", "message": "test"}
        response = self.client.post("/notify/sms/", data=data)
        self.assertNotEqual(response.status_code, 200)

    def test_invalid_method(self) -> None:
        """Fails if a request with an invalid method returns status code 200."""
        response = self.client.get("/notify/not_a_method/")
        self.assertNotEqual(response.status_code, 200)

    def test_non_digit_unit_id(self) -> None:
        """Fails if a request with a non-digit unit id returns status code 200."""
        data = {"unit_id": "", "message": "test"}
        response = self.client.get("/notify/sms/", data=data)
        self.assertNotEqual(response.status_code, 200)

    def test_message_too_long(self) -> None:
        """Fails if a request with a message longer than 2048 characters returns status code 200."""
        data = {"unit_id": "12345678", "message": "test" * 513}
        response = self.client.get("/notify/sms/", data=data)
        self.assertNotEqual(response.status_code, 200)

    @override_settings(DEBUG=True)
    def test_wialon_unit_with_to_number(self) -> None:
        """Fails if a notification wasn't sent to the phone numbers in the Wialon unit's ``to_number`` custom field."""
        with WialonSession() as test_session:
            test_unit = WialonUnit(
                id=None,
                creator_id=test_session.uid,
                name=f"test_unit_{str(uuid.uuid4())[:24].strip('-')}",
                hw_type_id=wialon_utils.get_hw_types(test_session)[0]["id"],
                session=test_session,
            )
            test_unit.update_cfield("to_number", "+17135555555,+12815555555")

            data = {"unit_id": test_unit.id, "message": "test"}
            response = self.client.get("/notify/sms/", data=data)

            test_unit.delete()
            self.assertEqual(response.status_code, 200)

    @override_settings(DEBUG=True)
    def test_wialon_unit_with_driver(self) -> None:
        """Fails if a notification wasn't sent to the Wialon unit's attached driver."""
        with WialonSession() as test_session:
            test_unit = WialonUnit(
                id=None,
                creator_id=test_session.uid,
                name=f"test_unit_{str(uuid.uuid4())[:24].strip('-')}",
                hw_type_id=wialon_utils.get_hw_types(test_session)[0]["id"],
                session=test_session,
            )
            test_resource = WialonResource(
                id=None,
                creator_id=test_session.uid,
                name=f"test_resource_{str(uuid.uuid4())[:24].strip('-')}",
                skip_creator_check=True,
                session=test_session,
            )
            driver_id = test_resource.create_driver(
                name="Test Driver", phone="+17135555555"
            )
            test_resource.bind_unit_driver(test_unit.id, driver_id)

            data = {"unit_id": test_unit.id, "message": "test"}
            response = self.client.get("/notify/sms/", data=data)

            test_unit.delete()
            test_resource.delete()
            self.assertEqual(response.status_code, 200)

    @override_settings(DEBUG=True)
    def test_wialon_unit_without_phone_numbers(self) -> None:
        """Fails if a Wialon unit without phone numbers assigned to it doesn't return status code 406."""
        with WialonSession() as test_session:
            test_unit = WialonUnit(
                id=None,
                creator_id=test_session.uid,
                name=f"test_unit_{str(uuid.uuid4())[:24].strip('-')}",
                hw_type_id=wialon_utils.get_hw_types(test_session)[0]["id"],
                session=test_session,
            )

            data = {"unit_id": test_unit.id, "message": "test"}
            response = self.client.get("/notify/sms/", data=data)

            test_unit.delete()
            self.assertEqual(response.status_code, 406)
