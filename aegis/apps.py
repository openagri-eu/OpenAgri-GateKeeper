# aegis/apps.py

from django.apps import AppConfig


class AegisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'aegis'
    verbose_name = 'Aegis'

    def ready(self):
        import aegis.signals
        from django.contrib import admin

        from aegis.models import BlacklistedAccess, BlacklistedRefresh, CustomPermissions, RequestLog

        try:
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
        except Exception:
            OutstandingToken = None

        for model in (CustomPermissions, BlacklistedAccess, BlacklistedRefresh, RequestLog, OutstandingToken):
            if model is None:
                continue
            try:
                admin.site.unregister(model)
            except admin.sites.NotRegistered:
                pass
