from django.test import TestCase

from terminusgps_notifier import models


class ProfileTestCase(TestCase):
    fixtures = ["terminusgps_notifier/tests/test_profile.json"]

    def setUp(self):
        self.profile = models.Profile.objects.get(pk=1)
