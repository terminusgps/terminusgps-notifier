from django.core.management.base import BaseCommand, CommandError

from terminusgps_notifier.models import Profile


class Command(BaseCommand):
    help = "Resets profile(s) messages count to 0."

    def add_arguments(self, parser):
        parser.add_argument("profile_ids", nargs="+", type=int)

    def handle(self, *args, **options):
        for profile_id in options["profile_ids"]:
            try:
                profile = Profile.objects.get(pk=profile_id)
            except Profile.DoesNotExist:
                raise CommandError(f"Profile '{profile_id}' does not exist")
            else:
                profile.messages_count = 0
                profile.save(update_fields=["messages_count"])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully reset profile #{profile_id} messages count to 0"
                    )
                )
