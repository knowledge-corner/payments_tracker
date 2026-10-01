"""
Load the hospital directory.

    python manage.py import_hospitals --starter                      # bundled starter list
    python manage.py import_hospitals --file hospital_directory.csv  # data.gov.in download
    python manage.py import_hospitals --url "<csv download URL from data.gov.in>"
    python manage.py import_hospitals --file x.csv --districts "Pune, Mumbai, Mumbai Suburban, Thane"
"""
import io
import urllib.request

from django.core.management.base import BaseCommand, CommandError

from hospitals.directory import import_directory, load_starter


class Command(BaseCommand):
    help = "Load hospitals into the shared directory (starter list or data.gov.in file)."

    def add_arguments(self, parser):
        parser.add_argument("--starter", action="store_true", help="Load the bundled starter list.")
        parser.add_argument("--file", help="Path to a .csv/.xlsx file downloaded from data.gov.in.")
        parser.add_argument("--url", help="Direct CSV URL (e.g. data.gov.in download / API link).")
        parser.add_argument("--districts", default="Pune, Mumbai, Mumbai Suburban")
        parser.add_argument("--all-systems", action="store_true", help="Also import AYUSH (non-allopathic) facilities.")

    def handle(self, *args, **opts):
        if opts["starter"]:
            self.stdout.write(f"Starter list: {load_starter()} hospitals added.")
        source = None
        if opts["file"]:
            with open(opts["file"], "rb") as fh:
                data = fh.read()
            source = io.BytesIO(data)
            source.name = opts["file"]
        elif opts["url"]:
            request = urllib.request.Request(opts["url"], headers={"User-Agent": "payments-tracker"})
            with urllib.request.urlopen(request, timeout=120) as resp:
                source = io.BytesIO(resp.read())
            source.name = "download.csv"
        if source is None:
            if not opts["starter"]:
                raise CommandError("Use --starter, --file or --url.")
            return
        try:
            counts = import_directory(source, opts["districts"].split(","), allopathic_only=not opts["all_systems"])
        except ValueError as exc:
            raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(
            f"Directory import: {counts['created']} added, {counts['updated']} updated "
            f"({counts['matched']} rows in the chosen districts out of {counts['rows']}; "
            f"{counts['skipped_system']} non-allopathic skipped)."
        ))
