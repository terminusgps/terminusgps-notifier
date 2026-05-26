from django.test import TestCase

from terminusgps_notifier import models, tasks


class ResetMessagesCountTestCase(TestCase):
    fixtures = [
        "terminusgps_notifier/tests/test_user.json",
        "terminusgps_notifier/tests/test_profile.json",
    ]

    def test_reset_messages_count(self):
        """Fails if the test profile's :py:attr:`messages_count` wasn't reset after calling the function."""
        profile = models.Profile.objects.get(pk=1)
        profile.messages_count = 420
        profile.save(update_fields=["messages_count"])
        self.assertEqual(profile.messages_count, 420)
        tasks.reset_messages_count(profile.pk)
        profile.refresh_from_db()
        self.assertEqual(profile.messages_count, 0)
