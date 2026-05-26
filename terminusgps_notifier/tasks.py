import logging

from django.db import transaction
from django_rq import job

from terminusgps_notifier import models

logger = logging.getLogger(__name__)


@job
@transaction.atomic
def reset_messages_count(profile_pk):
    try:
        profile = models.Profile.objects.get(pk=profile_pk)
        profile.messages_count = 0
        profile.save(update_fields=["messages_count"])
    except models.Profile.DoesNotExist:
        logger.error(f"Failed to retrieve profile by id: {profile_pk}.")
        logger.error(f"Messages count for profile #{profile_pk} wasn't reset.")
