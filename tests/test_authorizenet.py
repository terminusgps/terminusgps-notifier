from unittest.mock import patch

from django.test import TestCase, override_settings
from terminusgps.authorizenet.service import AuthorizenetError

from terminusgps_notifier import authorizenet


class GetHostedProfilePageUrlTestCase(TestCase):
    @override_settings(DEBUG=True)
    def test_debug_true(self):
        """Fails if the wrong url was returned with debug mode on."""
        url = authorizenet.get_hosted_profile_page_url()
        self.assertEqual(url, "https://test.authorize.net/customer/manage")

    @override_settings(DEBUG=False)
    def test_debug_false(self):
        """Fails if the wrong url was returned with debug mode off."""
        url = authorizenet.get_hosted_profile_page_url()
        self.assertEqual(url, "https://accept.authorize.net/customer/manage")


class SubscriptionIsActiveTestCase(TestCase):
    def test_no_id_provided_returns_false(self):
        """Fails if :py:obj:`False` wasn't returned with no id provided."""
        result = authorizenet.subscription_is_active(id=None)
        self.assertFalse(result)

    def test_active_subscription_returns_true(self):
        """Fails if :py:obj:`True` wasn't returned with an active subscription."""
        with patch(
            "terminusgps_notifier.authorizenet.get_subscription_status",
            return_value="active",
        ):
            result = authorizenet.subscription_is_active(id=1)
            self.assertTrue(result)

    def test_canceled_subscription_returns_true(self):
        """Fails if :py:obj:`True` wasn't returned with a canceled subscription."""
        with patch(
            "terminusgps_notifier.authorizenet.get_subscription_status",
            return_value="canceled",
        ):
            result = authorizenet.subscription_is_active(id=1)
            self.assertTrue(result)

    def test_terminated_subscription_returns_false(self):
        """Fails if :py:obj:`False` wasn't returned with a terminated subscription."""
        with patch(
            "terminusgps_notifier.authorizenet.get_subscription_status",
            return_value="terminated",
        ):
            result = authorizenet.subscription_is_active(id=1)
            self.assertFalse(result)

    def test_suspended_subscription_returns_false(self):
        """Fails if :py:obj:`False` wasn't returned with a suspended subscription."""
        with patch(
            "terminusgps_notifier.authorizenet.get_subscription_status",
            return_value="suspended",
        ):
            result = authorizenet.subscription_is_active(id=1)
            self.assertFalse(result)

    def test_expired_subscription_returns_false(self):
        """Fails if :py:obj:`False` wasn't returned with a expired subscription."""
        with patch(
            "terminusgps_notifier.authorizenet.get_subscription_status",
            return_value="expired",
        ):
            result = authorizenet.subscription_is_active(id=1)
            self.assertFalse(result)

    def test_authorizeneterror_reraised(self):
        """Fails if an Authorizenet error was raised but not reraised."""
        with patch(
            "terminusgps_notifier.authorizenet.get_subscription_status",
            side_effect=AuthorizenetError(message="", code="E00000"),
        ):
            with self.assertRaises(AuthorizenetError):
                authorizenet.subscription_is_active(id=1)

    def test_authorizeneterror_e00035_returns_false(self):
        """Fails if an Authorizenet error E00035 was raised and the return value was not :py:obj:`False`."""
        with patch(
            "terminusgps_notifier.authorizenet.get_subscription_status",
            side_effect=AuthorizenetError(message="", code="E00035"),
        ):
            result = authorizenet.subscription_is_active(id=1)
            self.assertFalse(result)
