import logging
from unittest.mock import MagicMock, patch

from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from terminusgps.wialon.session import WialonSession

from terminusgps_notifier import forms, models, views

logging.disable(logging.CRITICAL)


class CleanPhonesTestCase(TestCase):
    def test_no_leading_plus_phone_removed_from_return_value(self):
        """Fails if a phone number without a leading plus wasn't removed from the return value."""
        input_phones = ["+15555555555", "15555555555"]
        result = views.clean_phones(input_phones)
        self.assertIn(input_phones[0], result)
        self.assertNotIn(input_phones[1], result)

    def test_none_type_phone_removed_from_return_value(self):
        """Fails if a phone provided as :py:obj:`None` wasn't removed from the return value."""
        input_phones = ["+15555555555", None]
        result = views.clean_phones(input_phones)
        self.assertIn(input_phones[0], result)
        self.assertNotIn(input_phones[1], result)

    def test_non_digit_phone_removed_from_return_value(self):
        """Fails if a phone number containing non-digit characters wasn't removed from the return value."""
        input_phones = ["+15555555555", "+1555555555a"]
        result = views.clean_phones(input_phones)
        self.assertIn(input_phones[0], result)
        self.assertNotIn(input_phones[1], result)

    def test_long_phone_removed_from_return_value(self):
        """Fails if a phone number longer than 15 characters wasn't removed from the return value."""
        input_phones = ["+15555555555", "+15555555555+15555555555"]
        result = views.clean_phones(input_phones)
        self.assertIn(input_phones[0], result)
        self.assertNotIn(input_phones[1], result)


class GetPhonesTestCase(TestCase):
    fixtures = [
        "terminusgps_notifier/tests/test_user.json",
        "terminusgps_notifier/tests/test_profile.json",
    ]

    def test_wialon_error_returns_empty_list(self):
        """Fails if the function raised :py:exec:`~terminusgps.wialon.WialonAPIError` and didn't return an empty list."""
        result = views.get_phones(token="super_secure_token", unit_id=12345678)
        self.assertEqual(result, [])


@override_settings(
    NOTIFICATION_DISPATCHERS={
        "sms": [
            "terminusgps_notifier.dispatchers.DummyNotificationDispatcher"
        ],
        "voice": [
            "terminusgps_notifier.dispatchers.DummyNotificationDispatcher"
        ],
    }
)
class GetDispatchersTestCase(TestCase):
    def test_invalid_method_raises_valueerror(self):
        """Fails if :py:exec:`ValueError` wasn't raised when provided with an invalid method."""
        form = forms.NotificationDispatchForm(
            {
                "user_id": "1",
                "unit_id": "12345678",
                "message": "Test Message",
                "msg_time_int": 0,
            }
        )
        form.is_valid()
        with self.assertRaises(ValueError):
            views.get_dispatchers(form, method="not_a_method")

    def test_expected_dispatchers_returned(self):
        """Fails if the dummy dispatcher wasn't in the return value."""
        form = forms.NotificationDispatchForm(
            {
                "user_id": "1",
                "unit_id": "12345678",
                "message": "Test Message",
                "msg_time_int": 0,
            }
        )
        form.is_valid()
        dispatchers = views.get_dispatchers(form, method="sms")
        self.assertEqual(
            type(dispatchers[0]).__name__, "DummyNotificationDispatcher"
        )
        dispatchers = views.get_dispatchers(form, method="voice")
        self.assertEqual(
            type(dispatchers[0]).__name__, "DummyNotificationDispatcher"
        )


@override_settings(
    NOTIFICATION_DISPATCHERS={
        "sms": [
            "terminusgps_notifier.dispatchers.DummyNotificationDispatcher"
        ],
        "voice": [
            "terminusgps_notifier.dispatchers.DummyNotificationDispatcher"
        ],
    }
)
class SendNotificationsTestCase(TestCase):
    def test_any_dispatcher_succeeding_returns_200(self):
        """Fails if a notification dispatcher succeeds and status code 200 wasn't returned."""
        form = forms.NotificationDispatchForm(
            {
                "user_id": "1",
                "unit_id": "12345678",
                "message": "Test Message",
                "msg_time_int": 0,
            }
        )
        self.assertTrue(form.is_valid())
        method = "sms"
        phones = ["+15555555555"]
        dispatchers = views.get_dispatchers(form, method)
        response = views.send_notifications(method, phones, dispatchers)
        self.assertEqual(response.status_code, 200)

    def test_all_dispatchers_failing_returns_500(self):
        """Fails if all notification dispatchers fail and status code 500 wasn't returned."""
        with patch(
            "terminusgps_notifier.dispatchers.DummyNotificationDispatcher.send_sms",
            side_effect=ValueError,
        ):
            form = forms.NotificationDispatchForm(
                {
                    "user_id": "1",
                    "unit_id": "12345678",
                    "message": "Test Message",
                    "msg_time_int": 0,
                }
            )
            self.assertTrue(form.is_valid())
            method = "sms"
            phones = ["+15555555555"]
            dispatchers = views.get_dispatchers(form, method)
            response = views.send_notifications(method, phones, dispatchers)
            self.assertEqual(response.status_code, 500)


class GetSubscriptionStatusTestCase(TestCase):
    fixtures = [
        "terminusgps_notifier/tests/test_user.json",
        "terminusgps_notifier/tests/test_profile.json",
    ]

    def test_staff_user_returns_active(self):
        """Fails if 'active' wasn't returned by the function with a user flagged as staff."""
        user = get_user_model().objects.get(pk=1)
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        profile = models.Profile.objects.get(pk=1)
        status = views.get_subscription_status(profile)
        self.assertEqual(status, "active")

    def test_non_staff_user_without_subscription_id_returns_none(self):
        """Fails if a non-staff user without a subscription id returns anything other than :py:obj:`None`."""
        profile = models.Profile.objects.get(pk=1)
        status = views.get_subscription_status(profile)
        self.assertIsNone(status)


class HealthCheckViewTestCase(TestCase):
    def test_get_returns_200(self):
        """Fails if a GET request to the health check endpoint returns anything other than code 200."""
        client = Client()
        response = client.get("/v3/health/")
        self.assertEqual(response.status_code, 200)


@override_settings(
    NOTIFICATION_DISPATCHERS={
        "sms": [
            "terminusgps_notifier.dispatchers.DummyNotificationDispatcher"
        ],
        "voice": [
            "terminusgps_notifier.dispatchers.DummyNotificationDispatcher"
        ],
    }
)
class NotifyTestCase(TestCase):
    fixtures = [
        "terminusgps_notifier/tests/test_user.json",
        "terminusgps_notifier/tests/test_profile.json",
    ]

    def setUp(self):
        self.client = Client()

    def test_invalid_method_returns_404(self):
        """Fails if an invalid method doesn't return status code 404."""
        response = self.client.post("/v3/notify/not_a_method/", {})
        self.assertEqual(response.status_code, 404)

    def test_invalid_form_data_returns_406(self):
        """Fails if invalid form data doesn't return status code 406."""
        data = {}
        response = self.client.post("/v3/notify/sms/", data)
        self.assertEqual(response.status_code, 406)
        data = {"user_id": "1", "unit_id": "12345678", "message": "Test"}
        response = self.client.post("/v3/notify/sms/", data)
        self.assertEqual(response.status_code, 406)
        data = {"unit_id": "12345678", "message": "Test", "msg_time_int": 0}
        response = self.client.post("/v3/notify/sms/", data)
        self.assertEqual(response.status_code, 406)

    def test_non_existent_profile_returns_404(self):
        """Fails if a user with a non-existent profile doesn't return status code 404."""
        response = self.client.post(
            "/v3/notify/sms/",
            {
                "user_id": "2",
                "unit_id": "12345678",
                "message": "Test",
                "msg_time_int": 0,
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_profile_with_inactive_subscription_returns_403(self):
        """Fails if a user with a non-active subscription doesn't return status code 403."""
        with patch(
            "terminusgps_notifier.views.get_subscription_status",
            return_value="expired",
        ):
            response = self.client.post(
                "/v3/notify/sms/",
                {
                    "user_id": "1",
                    "unit_id": "12345678",
                    "message": "Test",
                    "msg_time_int": 0,
                },
            )
            self.assertEqual(response.status_code, 403)

    def test_profile_with_staff_user_counts_as_subscribed(self):
        """Fails if a staff user is denied due to an invalid subscription."""
        user = get_user_model().objects.get(pk=1)
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        response = self.client.post(
            "/v3/notify/sms/",
            {
                "user_id": "1",
                "unit_id": "12345678",
                "message": "Test",
                "msg_time_int": 0,
            },
        )
        self.assertNotEqual(response, 406)
        user.is_staff = False
        user.save(update_fields=["is_staff"])

    def test_profile_with_maxed_out_messages_returns_403(self):
        """Fails if a profile with maxed out messages doesn't return status code 403."""
        profile = models.Profile.objects.get(pk=1)
        profile.messages_count = 500
        profile.save(update_fields=["messages_count"])
        response = self.client.post(
            "/v3/notify/sms/",
            {
                "user_id": "1",
                "unit_id": "12345678",
                "message": "Test",
                "msg_time_int": 0,
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_profile_messages_count_incremented_on_success(self):
        """Fails if a profile's messages count wasn't incremented after notification dispatch."""
        user = get_user_model().objects.get(pk=1)
        user.is_staff = True
        user.save(update_fields=["is_staff"])

        with patch(
            "terminusgps_notifier.views.get_phones",
            return_value=["+15555555555"],
        ):
            profile = models.Profile.objects.first()
            self.assertEqual(profile.messages_count, 0)
            self.client.post(
                "/v3/notify/sms/",
                {
                    "user_id": "1",
                    "unit_id": "12345678",
                    "message": "Test",
                    "msg_time_int": 0,
                },
            )
            profile.refresh_from_db()
            self.assertEqual(profile.messages_count, 1)


class DashboardViewTestCase(TestCase):
    fixtures = [
        "terminusgps_notifier/tests/test_user.json",
        "terminusgps_notifier/tests/test_profile.json",
    ]

    def setUp(self):
        self.path = "/dashboard/"
        self.user = get_user_model().objects.get(pk=1)
        self.profile = models.Profile.objects.get(pk=1)
        self.client = Client()
        self.client.login(**{"username": "testuser", "password": "trolldad"})

    @patch("terminusgps_notifier.views.get_stripe_client")
    def test_get_with_checkout_id_calls_stripe_api(
        self, mock_get_stripe_client
    ):
        """Fails if the Stripe API wasn't called on GET with a checkout id."""
        self.profile.checkout_id = "1"
        self.profile.save(update_fields=["checkout_id"])
        mock_stripe = MagicMock()
        mock_get_stripe_client.return_value = mock_stripe
        mock_stripe.v1.checkout.sessions.retrieve.return_value = MagicMock(
            customer="1", subscription="1"
        )
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        mock_get_stripe_client.assert_called_once()

    def test_profile_added_to_context(self):
        """Fails if the user's profile wasn't added to the view context."""
        response = self.client.get("/dashboard/")
        self.assertIn("profile", response.context_data)

    def test_wialon_redirect_uri_added_to_context(self):
        """Fails if the redirect uri for Wialon token generation wasn't added to the view context."""
        response = self.client.get("/dashboard/")
        self.assertIn("wialon_redirect_uri", response.context_data)


class CreateNotificationStepOneViewTestCase(TestCase):
    fixtures = [
        "terminusgps_notifier/tests/test_user.json",
        "terminusgps_notifier/tests/test_profile.json",
    ]

    def setUp(self):
        self.client = Client()
        self.client.login(**{"username": "testuser", "password": "trolldad"})

    def test_post_redirects_to_next_step(self):
        """Fails if the view doesn't redirect the client to the expected next step."""
        data = {}
        data["units"] = ["1", "2", "3"]
        data["resource"] = "1"

        with patch(
            "terminusgps_notifier.decorators.wialon_session_is_valid",
            return_value=True,
        ):
            response = self.client.post(
                "/notifications/create/step-one/", data
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual("/notifications/create/step-two/", response.url)

    def test_post_valid_data_added_to_session(self):
        """Fails if valid form data wasn't added to the session before redirecting the client."""
        data = {}
        data["units"] = ["1", "2", "3"]
        data["resource"] = "1"

        with patch(
            "terminusgps_notifier.decorators.wialon_session_is_valid",
            return_value=True,
        ):
            self.client.post("/notifications/create/step-one/", data)
            self.assertIn("step_one_data", self.client.session.keys())


class CreateNotificationStepTwoViewTestCase(TestCase):
    fixtures = [
        "terminusgps_notifier/tests/test_user.json",
        "terminusgps_notifier/tests/test_profile.json",
    ]

    def setUp(self):
        self.client = Client()
        self.client.login(**{"username": "testuser", "password": "trolldad"})

    def test_post_redirects_to_next_step(self):
        """Fails if the view doesn't redirect the client to the expected next step."""
        data = {}
        data["t"] = "alarm"

        response = self.client.post("/notifications/create/step-two/", data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual("/notifications/create/step-three/", response.url)

    def test_post_valid_data_added_to_session(self):
        """Fails if valid form data wasn't added to the session before redirecting the client."""
        data = {}
        data["t"] = "alarm"

        self.client.post("/notifications/create/step-two/", data)
        self.assertIn("step_two_data", self.client.session.keys())


class CreateNotificationStepThreeViewTestCase(TestCase):
    fixtures = [
        "terminusgps_notifier/tests/test_user.json",
        "terminusgps_notifier/tests/test_profile.json",
    ]

    def setUp(self):
        self.client = Client()
        self.client.login(**{"username": "testuser", "password": "trolldad"})

    def test_post_redirects_to_next_step(self):
        """Fails if the view doesn't redirect the client to the expected next step."""
        data = {}
        data["name"] = "Test Notification"
        data["message"] = "At %MSG_TIME%, %UNIT% had its ignition switched on."
        data["method"] = "sms"

        response = self.client.post("/notifications/create/step-three/", data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual("/notifications/create/step-four/", response.url)

    def test_post_valid_data_added_to_session(self):
        """Fails if valid form data wasn't added to the session before redirecting the client."""
        data = {}
        data["name"] = "Test Notification"
        data["message"] = "At %MSG_TIME%, %UNIT% had its ignition switched on."
        data["method"] = "sms"

        response = self.client.post("/notifications/create/step-three/", data)
        self.assertEqual(response.status_code, 302)
        self.assertIn("step_three_data", self.client.session.keys())


class CreateNotificationStepFourViewTestCase(TestCase):
    fixtures = [
        "terminusgps_notifier/tests/test_user.json",
        "terminusgps_notifier/tests/test_profile.json",
    ]

    def setUp(self):
        self.client = Client()
        self.client.login(**{"username": "testuser", "password": "trolldad"})

    def test_post_redirects_to_next_step(self):
        """Fails if the view doesn't redirect the client to the expected next step."""
        now, fmt = timezone.now(), "%Y-%m-%dT%H:%M:%S"
        data = {}
        data["tz"] = 0
        data["ta"] = now.strftime(fmt)
        data["td"] = (now + relativedelta(days=1)).strftime(fmt)
        data["fl"] = 0
        data["la"] = "en"
        data["ma"] = 0
        data["cdt"] = 0
        data["cp"] = 3600
        data["mast"] = 0
        data["mpst"] = 0
        data["mmtd"] = 0

        response = self.client.post("/notifications/create/step-four/", data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual("/notifications/create/review/", response.url)

    def test_post_valid_data_added_to_session(self):
        """Fails if valid form data wasn't added to the session before redirecting the client."""
        now, fmt = timezone.now(), "%Y-%m-%dT%H:%M:%S"
        data = {}
        data["tz"] = 0
        data["ta"] = now.strftime(fmt)
        data["td"] = (now + relativedelta(days=1)).strftime(fmt)
        data["fl"] = 0
        data["la"] = "en"
        data["ma"] = 0
        data["cdt"] = 0
        data["cp"] = 3600
        data["mast"] = 0
        data["mpst"] = 0
        data["mmtd"] = 0

        self.client.post("/notifications/create/step-four/", data)
        self.assertIn("step_four_data", self.client.session.keys())


class CreateNotificationReviewViewTestCase(TestCase):
    fixtures = [
        "terminusgps_notifier/tests/test_user.json",
        "terminusgps_notifier/tests/test_profile.json",
    ]

    def setUp(self):
        self.client = Client()
        self.client.login(**{"username": "testuser", "password": "trolldad"})
        step_one_data = {}
        step_one_data["itemId"] = "1"
        step_one_data["un"] = ["1", "2", "3"]
        step_two_data = {}
        step_two_data["trg"] = {"t": "alarm", "p": {}}
        step_three_data = {}
        step_three_data["n"] = "Test Notification"
        step_three_data["act"] = [
            {
                "t": "push_messages",
                "p": {
                    "url": "https://api.terminusgps.com/v3/notify/sms/",
                    "get": 0,
                },
            }
        ]
        step_three_data["txt"] = (
            "user_id=1&unit_id=%UNIT_ID%&msg_time_int=%MSG_TIME_INT%&message=What+up"
        )
        step_four_data = {}
        step_four_data["tz"] = 0
        step_four_data["ta"] = 0
        step_four_data["td"] = 0
        step_four_data["fl"] = 0
        step_four_data["la"] = 0
        step_four_data["ma"] = 0
        step_four_data["cdt"] = 0
        step_four_data["cp"] = 0
        step_four_data["mast"] = 0
        step_four_data["mpst"] = 0
        step_four_data["mmtd"] = 0

        session = self.client.session
        session["step_one_data"] = step_one_data.copy()
        session["step_two_data"] = step_two_data.copy()
        session["step_three_data"] = step_three_data.copy()
        session["step_four_data"] = step_four_data.copy()
        session.save()

    def test_post_valid_data_does_wialon_api_call(self):
        """Fails if a Wialon API call wasn't made with valid data."""
        with patch(
            "terminusgps_notifier.decorators.wialon_session_is_valid",
            return_value=True,
        ):
            with patch(
                "terminusgps_notifier.views.get_wialon_session",
                return_value=MagicMock(WialonSession),
            ):
                response = self.client.post("/notifications/create/review/")
                self.assertEqual(response.status_code, 302)
                has_step_one = self.client.session.has_key("step_one_data")
                has_step_two = self.client.session.has_key("step_two_data")
                has_step_three = self.client.session.has_key("step_three_data")
                has_step_four = self.client.session.has_key("step_four_data")
                self.assertFalse(has_step_one)
                self.assertFalse(has_step_two)
                self.assertFalse(has_step_three)
                self.assertFalse(has_step_four)

    def test_post_redirects_to_resource_details(self):
        """Fails if the view doesn't redirect the client to resource details."""
        with patch(
            "terminusgps_notifier.decorators.wialon_session_is_valid",
            return_value=True,
        ):
            with patch(
                "terminusgps_notifier.views.get_wialon_session",
                return_value=MagicMock(WialonSession),
            ):
                response = self.client.post("/notifications/create/review/")
                self.assertEqual(response.status_code, 302)
                self.assertEqual("/resources/1/details/", response.url)


class TriggerParametersFormViewTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.client.login(**{"username": "testuser", "password": "trolldad"})

    def test_get_without_query_parameter_returns_404(self):
        """Fails if making a GET request to the view without the `t` query parameter returns anything other than status code 404."""
        response = self.client.get("/forms/triggers/parameters/")
        self.assertEqual(response.status_code, 404)

    def test_invalid_trigger_returns_404(self):
        """Fails if making a GET request to the view without a valid `t` query parameter returns anything other than status code 404."""
        response = self.client.get(
            "/forms/triggers/parameters/", query_params={"t": "not_a_trigger"}
        )
        self.assertEqual(response.status_code, 404)

    def test_all_valid_trigger_types_return_200(self):
        """Fails if a GET request to the view with any valid trigger type returns anything other than status code 200."""
        response = self.client.get(
            "/forms/triggers/parameters/", query_params={"t": "geozone"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context_data["form"], forms.GeofenceTriggerForm
        )
