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

    def test_non_get_request_returns_405(self):
        """Fails if a non-GET request returns anything other than code 405."""
        response = self.client.post(self.path)
        self.assertEqual(response.status_code, 405)
        response = self.client.put(self.path)
        self.assertEqual(response.status_code, 405)
        response = self.client.patch(self.path)
        self.assertEqual(response.status_code, 405)
        response = self.client.delete(self.path)
        self.assertEqual(response.status_code, 405)
        response = self.client.head(self.path)
        self.assertEqual(response.status_code, 405)
        response = self.client.options(self.path)
        self.assertEqual(response.status_code, 405)
        response = self.client.trace(self.path)
        self.assertEqual(response.status_code, 405)

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

    def test_htmx_request_renders_partial(self):
        """Fails if an htmx request doesn't render a partial template."""
        headers = {"HX-Request": True}
        response = self.client.get("/dashboard/", headers=headers)
        self.assertTrue(response.template_name.endswith("#main"))
        headers = {"HX-Request": True, "HX-Boosted": True}
        response = self.client.get("/dashboard/", headers=headers)
        self.assertFalse(response.template_name.endswith("#main"))
        headers = {}
        response = self.client.get("/dashboard/", headers=headers)
        self.assertFalse(response.template_name.endswith("#main"))

    def test_profile_added_to_context(self):
        """Fails if the user's profile wasn't added to the view context."""
        response = self.client.get("/dashboard/")
        self.assertIn("profile", response.context_data)

    def test_redirect_uri_added_to_context(self):
        """Fails if the redirect uri for Wialon token generation wasn't added to the view context."""
        response = self.client.get("/dashboard/")
        self.assertIn("redirect_uri", response.context_data)


class DetailSubscriptionViewTestCase(TestCase):
    fixtures = [
        "terminusgps_notifier/tests/test_user.json",
        "terminusgps_notifier/tests/test_profile.json",
    ]

    def setUp(self):
        self.path = "/detail-subscriptions/"
        self.user = get_user_model().objects.get(pk=1)
        self.profile = models.Profile.objects.get(pk=1)
        self.client = Client()
        self.client.login(**{"username": "testuser", "password": "trolldad"})

    def test_non_get_request_returns_405(self):
        """Fails if a non-POST request returns anything other than code 405."""
        response = self.client.post(self.path)
        self.assertEqual(response.status_code, 405)
        response = self.client.put(self.path)
        self.assertEqual(response.status_code, 405)
        response = self.client.patch(self.path)
        self.assertEqual(response.status_code, 405)
        response = self.client.delete(self.path)
        self.assertEqual(response.status_code, 405)
        response = self.client.head(self.path)
        self.assertEqual(response.status_code, 405)
        response = self.client.options(self.path)
        self.assertEqual(response.status_code, 405)
        response = self.client.trace(self.path)
        self.assertEqual(response.status_code, 405)


class CancelSubscriptionViewTestCase(TestCase):
    fixtures = [
        "terminusgps_notifier/tests/test_user.json",
        "terminusgps_notifier/tests/test_profile.json",
    ]

    def setUp(self):
        self.path = "/cancel-subscriptions/"
        self.user = get_user_model().objects.get(pk=1)
        self.profile = models.Profile.objects.get(pk=1)
        self.client = Client()
        self.client.login(**{"username": "testuser", "password": "trolldad"})

    def test_non_post_request_returns_405(self):
        """Fails if a non-POST request returns anything other than code 405."""
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 405)
        response = self.client.put(self.path)
        self.assertEqual(response.status_code, 405)
        response = self.client.patch(self.path)
        self.assertEqual(response.status_code, 405)
        response = self.client.delete(self.path)
        self.assertEqual(response.status_code, 405)
        response = self.client.head(self.path)
        self.assertEqual(response.status_code, 405)
        response = self.client.options(self.path)
        self.assertEqual(response.status_code, 405)
        response = self.client.trace(self.path)
        self.assertEqual(response.status_code, 405)

    @patch("terminusgps_notifier.views.get_stripe_client")
    def test_post_cancels_subscription_in_stripe(self, mock_get_stripe_client):
        """Fails if the Stripe API wasn't called on POST."""
        mock_stripe = MagicMock()
        mock_get_stripe_client.return_value = mock_stripe
        response = self.client.post(self.path, follow=True)
        self.assertEqual(response.status_code, 200)
        mock_get_stripe_client.assert_called_once()
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.subscription_id)
