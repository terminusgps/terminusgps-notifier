from django.contrib.auth import get_user_model
from django.test import TestCase

from terminusgps_notifier import models


class ProfileTestCase(TestCase):
    fixtures = [
        "terminusgps_notifier/tests/test_user.json",
        "terminusgps_notifier/tests/test_profile.json",
    ]

    def setUp(self):
        self.profile = models.Profile.objects.get(pk=1)

    def test___str__(self):
        """Fails if :py:func:`__str__` doesn't return the username of the user associated with the profile."""
        user = get_user_model().objects.get(pk=1)
        self.assertEqual(user.username, self.profile.__str__())
