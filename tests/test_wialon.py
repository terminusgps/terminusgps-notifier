import logging
from unittest.mock import MagicMock, patch

from django.test import TestCase
from terminusgps.wialon.session import WialonSession

from terminusgps_notifier import wialon

logging.disable(logging.CRITICAL)


class CleanPhonesTestCase(TestCase):
    def test_no_leading_plus_phone_removed_from_return_value(self):
        """Fails if a phone number without a leading plus wasn't removed from the return value."""
        input_phones = ["+15555555555", "15555555555"]
        result = wialon.clean_phones(input_phones)
        self.assertIn(input_phones[0], result)
        self.assertNotIn(input_phones[1], result)

    def test_none_type_phone_removed_from_return_value(self):
        """Fails if a phone provided as :py:obj:`None` wasn't removed from the return value."""
        input_phones = ["+15555555555", None]
        result = wialon.clean_phones(input_phones)
        self.assertIn(input_phones[0], result)
        self.assertNotIn(input_phones[1], result)

    def test_non_digit_phone_removed_from_return_value(self):
        """Fails if a phone number containing non-digit characters wasn't removed from the return value."""
        input_phones = ["+15555555555", "+1555555555a"]
        result = wialon.clean_phones(input_phones)
        self.assertIn(input_phones[0], result)
        self.assertNotIn(input_phones[1], result)

    def test_long_phone_removed_from_return_value(self):
        """Fails if a phone number longer than 15 characters wasn't removed from the return value."""
        input_phones = ["+15555555555", "+15555555555+15555555555"]
        result = wialon.clean_phones(input_phones)
        self.assertIn(input_phones[0], result)
        self.assertNotIn(input_phones[1], result)


class GetPhonesFromWialonTestCase(TestCase):
    fixtures = [
        "terminusgps_notifier/tests/test_user.json",
        "terminusgps_notifier/tests/test_profile.json",
    ]

    def test_wialon_error_returns_empty_list(self):
        """Fails if the function raised :py:exec:`~terminusgps.wialon.WialonAPIError` and didn't return an empty list."""
        result = wialon.get_phones(
            token="super_secure_token", unit_id=12345678
        )
        self.assertEqual(result, [])


class GetResourcesFromWialonTestCase(TestCase):
    def test_forced_true(self):
        """Fails if `force` wasn't set to `1` before making a Wialon API call."""
        with patch(
            "terminusgps_notifier.wialon.get_session"
        ) as mock_get_session:
            mock_session = MagicMock(WialonSession)
            mock_get_session.return_value = mock_session
            wialon_sid = "wialon_sid"
            force = True
            wialon.get_resources(wialon_sid, force)
            expected_params = {
                "spec": {
                    "itemsType": "avl_resource",
                    "propName": "sys_name",
                    "propValueMask": "*",
                    "propType": "property",
                    "sortType": "sys_name",
                },
                "force": force,
                "from": 0,
                "to": 0,
                "flags": 1,
            }
            mock_session.wialon_api.core_search_items.assert_called_with(
                **expected_params
            )

    def test_forced_false(self):
        """Fails if `force` wasn't set to `1` before making a Wialon API call."""
        with patch(
            "terminusgps_notifier.wialon.get_session"
        ) as mock_get_session:
            mock_session = MagicMock(WialonSession)
            mock_get_session.return_value = mock_session
            wialon_sid = "wialon_sid"
            force = False
            wialon.get_resources(wialon_sid, force)
            expected_params = {
                "spec": {
                    "itemsType": "avl_resource",
                    "propName": "sys_name",
                    "propValueMask": "*",
                    "propType": "property",
                    "sortType": "sys_name",
                },
                "force": force,
                "from": 0,
                "to": 0,
                "flags": 1,
            }
            mock_session.wialon_api.core_search_items.assert_called_with(
                **expected_params
            )


class GetItemsFromWialonTestCase(TestCase):
    def test_items_type_avl_unit(self):
        """Fails if `items_type` wasn't set to `avl_unit` before making a Wialon API call."""
        with patch(
            "terminusgps_notifier.wialon.get_session"
        ) as mock_get_session:
            mock_session = MagicMock(WialonSession)
            mock_get_session.return_value = mock_session
            wialon_sid = "wialon_sid"
            resource_id = "12345678"
            items_type = "avl_unit"
            force = False
            wialon.get_items(wialon_sid, resource_id, items_type, force)
            expected_params = {
                "spec": {
                    "itemsType": items_type,
                    "propName": "sys_name,sys_billing_account_guid",
                    "propValueMask": f"*,{resource_id}",
                    "propType": "property,property",
                    "sortType": "sys_name",
                },
                "force": force,
                "from": 0,
                "to": 0,
                "flags": 1,
            }
            mock_session.wialon_api.core_search_items.assert_called_with(
                **expected_params
            )

    def test_items_type_avl_unit_group(self):
        """Fails if `items_type` wasn't set to `avl_unit_group` before making a Wialon API call."""
        with patch(
            "terminusgps_notifier.wialon.get_session"
        ) as mock_get_session:
            mock_session = MagicMock(WialonSession)
            mock_get_session.return_value = mock_session
            wialon_sid = "wialon_sid"
            resource_id = "12345678"
            items_type = "avl_unit_group"
            force = False
            wialon.get_items(wialon_sid, resource_id, items_type, force)
            expected_params = {
                "spec": {
                    "itemsType": items_type,
                    "propName": "sys_name,sys_billing_account_guid",
                    "propValueMask": f"*,{resource_id}",
                    "propType": "property,property",
                    "sortType": "sys_name",
                },
                "force": force,
                "from": 0,
                "to": 0,
                "flags": 1,
            }
            mock_session.wialon_api.core_search_items.assert_called_with(
                **expected_params
            )


class GetNotificationsFromWialonTestCase(TestCase):
    def test_notification_ids_not_provided(self):
        """Fails if `notification_ids` wasn't provided and `col` was present in the Wialon API parameters."""
        with patch(
            "terminusgps_notifier.wialon.get_session"
        ) as mock_get_session:
            mock_session = MagicMock(WialonSession)
            mock_get_session.return_value = mock_session
            wialon_sid = "wialon_sid"
            resource_id = "12345678"
            notification_ids = None
            wialon.get_notifications(wialon_sid, resource_id, notification_ids)
            expected_params = {"itemId": resource_id}
            mock_session.wialon_api.resource_get_notification_data.assert_called_with(
                **expected_params
            )

    def test_notification_ids_provided(self):
        """Fails if `notification_ids` was provided and `col` wasn't present in the Wialon API parameters."""
        with patch(
            "terminusgps_notifier.wialon.get_session"
        ) as mock_get_session:
            mock_session = MagicMock(WialonSession)
            mock_get_session.return_value = mock_session
            wialon_sid = "wialon_sid"
            resource_id = "12345678"
            notification_ids = ["1", "2", "3"]
            wialon.get_notifications(wialon_sid, resource_id, notification_ids)
            expected_params = {"itemId": resource_id, "col": notification_ids}
            mock_session.wialon_api.resource_get_notification_data.assert_called_with(
                **expected_params
            )
