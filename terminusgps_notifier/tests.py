import logging

from django.conf import settings
from django.test import TestCase
from django.test.client import Client
from terminusgps.wialon import utils as wialon_utils
from terminusgps.wialon.items import WialonUnit
from terminusgps.wialon.session import WialonSession

logging.disable(logging.WARNING)


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


class WialonIntegrationTestCase(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.test_session = WialonSession()
        self.test_session.login(token=settings.WIALON_TOKEN)

    def tearDown(self) -> None:
        self.test_session.logout()

    def test_wialon_unit_with_no_phone_numbers_returns_empty_list(
        self,
    ) -> None:
        """Fails if a test unit with no phone numbers returns anything other than an empty list when calling :py:meth:`WialonUnit.get_phone_numbers`."""
        test_unit = WialonUnit(
            id=None,
            name="Test Unit 01",
            creator_id=self.test_session.uid,
            hw_type_id=wialon_utils.get_hw_types(self.test_session)[0]["id"],
            session=self.test_session,
        )
        retrieved_phones = test_unit.get_phone_numbers()

        test_unit.delete()
        self.assertEqual(retrieved_phones, [])

    def test_retrieve_phone_number_from_custom_field(self) -> None:
        """Fails if phone numbers from the test unit's ``to_number`` custom field weren't retrieved."""
        test_unit = WialonUnit(
            id=None,
            name="Test Unit 01",
            creator_id=self.test_session.uid,
            hw_type_id=wialon_utils.get_hw_types(self.test_session)[0]["id"],
            session=self.test_session,
        )
        test_unit.update_cfield("to_number", "+15555555555")
        retrieved_phones = test_unit.get_phone_numbers()

        test_unit.delete()
        self.assertEqual(retrieved_phones, ["+15555555555"])

    # def test_retrieve_phone_number_from_attached_driver(self) -> None:
    #     """Fails if the phone number from the test unit's attached driver wasn't retrieved."""
    #     test_resource = WialonResource(
    #         id=None,
    #         creator_id=self.test_session.uid,
    #         name="test_resource_01",
    #         skip_creator_check=True,
    #         session=self.test_session,
    #     )
    #     driver_id = test_resource.create_driver(
    #         name="Test Driver", phone="+15555555555"
    #     )
    #     test_unit = WialonUnit(
    #         id=None,
    #         name="Test Unit 01",
    #         creator_id=self.test_session.uid,
    #         hw_type_id=wialon_utils.get_hw_types(self.test_session)[0]["id"],
    #         session=self.test_session,
    #     )
    #     test_resource.update_attachable_drivers(units=[test_unit.id])
    #     test_resource.bind_unit_driver(test_unit.id, driver_id)
    #     retrieved_phones = test_unit.get_phone_numbers()

    #     test_resource.delete()
    #     test_unit.delete()
    #     self.assertEqual(retrieved_phones, ["+15555555555"])
