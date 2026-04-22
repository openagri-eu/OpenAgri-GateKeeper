import time

from django.core.management.base import BaseCommand

from aegis.services.fc_catalog_sync import sync_farmcalendar_catalog


class Command(BaseCommand):
    help = "Sync Farm and FarmParcels catalog from FarmCalendar into GK cache."

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval",
            type=int,
            default=5,
            help="Polling interval in seconds when --watch is enabled (default: 5).",
        )
        parser.add_argument(
            "--watch",
            action="store_true",
            help="Run continuously and sync every --interval seconds.",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=10,
            help="HTTP timeout in seconds for FC/GK calls (default: 10).",
        )

    def handle(self, *args, **options):
        interval = max(1, int(options["interval"]))
        timeout = max(1, int(options["timeout"]))
        watch = bool(options["watch"])

        def run_once():
            result = sync_farmcalendar_catalog(timeout=timeout)
            self.stdout.write(
                self.style.SUCCESS(
                    "Synced FC catalog: "
                    f"farms={result['farms']} "
                    f"parcels={result['parcels']} "
                    f"deactivated_scope_assignments={result.get('deactivated_scope_assignments', 0)}"
                )
            )

        if not watch:
            run_once()
            return

        self.stdout.write(self.style.WARNING(f"Running in watch mode. Interval={interval}s"))
        while True:
            try:
                run_once()
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"Sync failed: {exc}"))
            time.sleep(interval)
