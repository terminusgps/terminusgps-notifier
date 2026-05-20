from unittest.mock import MagicMock, patch

from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from terminusgps_notifier import models


class HealthCheckViewTestCase(TestCase):
    def test_get_returns_200(self):
        """Fails if a GET request to the health check endpoint returns anything other than code 200."""
        client = Client()
        response = client.get("/v3/health/")
        self.assertEqual(response.status_code, 200)


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
