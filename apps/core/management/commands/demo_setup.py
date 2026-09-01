from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "One-shot demo preparation: seed flights + layout and generate all demo assets."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("1/5 Seeding mock AODB flights..."))
        call_command("seed_demo")
        self.stdout.write(self.style.MIGRATE_HEADING("2/5 Seeding terminal layout..."))
        call_command("seed_nav")
        self.stdout.write(self.style.MIGRATE_HEADING("3/5 Generating app icons..."))
        call_command("make_assets")
        self.stdout.write(self.style.MIGRATE_HEADING("4/5 Generating demo ticket images..."))
        call_command("make_tickets")
        self.stdout.write(self.style.MIGRATE_HEADING("5/5 Generating location QR markers..."))
        call_command("make_qr_markers")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo ready. Start with: uv run manage.py runserver"))
        self.stdout.write("  Location markers   : demo_assets/qr_markers/marker_sheet.html")
        self.stdout.write("  Demo tickets       : demo_assets/tickets/")
        self.stdout.write("  Operator panel     : http://localhost:8000/ops/  (PIN from OPS_PIN, default 1234)")
