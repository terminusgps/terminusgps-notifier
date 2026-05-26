import logging

from django.db import transaction
from django.tasks import task

from terminusgps_notifier import models

logger = logging.getLogger(__name__)


@task(takes_context=True)
@transaction.atomic
def reset_messages_count(context, profile_pk):
    logger.debug(f"Resetting profile #{profile_pk} messages count...")
    logger.debug(f"Attempt: #{context.attempt}")
    logger.debug(f"Task result id: #{context.task_result.id}")
    try:
        profile = models.Profile.objects.get(pk=profile_pk)
        profile.messages_count = 0
        profile.save(update_fields=["messages_count"])
    except models.Profile.DoesNotExist:
        logger.error(f"Failed to retrieve profile #{profile_pk}.")
        logger.error(f"Profile #{profile_pk} messages count weren't reset.")
