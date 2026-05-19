import urllib.parse
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

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
        response = self.client.post(
            "/notifications/1/create/step-one/", {"units": ["1", "2", "3"]}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("step-two", response.url)

    def test_post_valid_data_added_to_session(self):
        """Fails if valid form data wasn't added to the session before redirecting the client."""
        un = ["1", "2", "3"]
        itemId = "1"

        self.client.post(
            "/notifications/1/create/step-one/", {"units": ["1", "2", "3"]}
        )
        step_one_data = self.client.session["step_one_data"]
        self.assertEqual(step_one_data["un"], un)
        self.assertEqual(step_one_data["itemId"], itemId)


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
        response = self.client.post(
            "/notifications/create/step-two/", {"t": "alarm"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("step-three", response.url)

    def test_post_valid_data_added_to_session(self):
        """Fails if valid form data wasn't added to the session before redirecting the client."""
        trg = {"t": "alarm", "p": {}}
        self.client.post("/notifications/create/step-two/", {"t": "alarm"})
        step_two_data = self.client.session["step_two_data"]
        self.assertEqual(step_two_data["trg"], trg)


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
        n = "Test Notification"
        message = "At %MSG_TIME%, %UNIT% moved."

        response = self.client.post(
            "/notifications/create/step-three/",
            data={"name": n, "message": message, "method": "sms"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("step-four", response.url)

    def test_post_valid_data_added_to_session(self):
        """Fails if valid form data wasn't added to the session before redirecting the client."""
        n = "Test Notification"
        message = "At %MSG_TIME%, %UNIT% moved."
        url = "https://api.terminusgps.com/v3/notify/sms/"
        act = [{"t": "send_messages", "p": {"url": url, "get": 0}}]
        txt = urllib.parse.urlencode(
            {
                "user_id": "1",
                "unit_id": "%UNIT_ID%",
                "message": message,
                "msg_time_int": "%MSG_TIME_INT%",
                "location": "%LOCATION%",
                "unit_name": "%UNIT%",
            },
            safe="%",
        )

        self.client.post(
            "/notifications/create/step-three/",
            data={"name": n, "message": message, "method": "sms"},
        )
        step_three_data = self.client.session["step_three_data"]
        self.assertEqual(step_three_data["n"], n)
        self.assertEqual(step_three_data["txt"], txt)
        self.assertEqual(step_three_data["act"], act)
