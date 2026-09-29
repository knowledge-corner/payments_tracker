"""Create the first admin from DJANGO_SUPERUSER_* env vars if it does not exist yet."""
import os

from django.core.management.base import BaseCommand

from accounts.models import User


class Command(BaseCommand):
    help = "Create an admin user from DJANGO_SUPERUSER_USERNAME / _PASSWORD / _EMAIL if missing."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        if not username or not password:
            self.stdout.write("DJANGO_SUPERUSER_USERNAME/PASSWORD not set - skipping.")
            return
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"Admin '{username}' already exists.")
            return
        User.objects.create_superuser(
            username=username, password=password,
            email=os.environ.get("DJANGO_SUPERUSER_EMAIL", ""), role=User.ROLE_ADMIN,
        )
        self.stdout.write(self.style.SUCCESS(f"Admin '{username}' created."))
