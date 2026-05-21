from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'
    verbose_name = 'Inventory'

    def ready(self):
        from django.conf import settings
        if not hasattr(settings, 'INVENTORY_CLIENT_MODEL'):
            settings.INVENTORY_CLIENT_MODEL = 'inventory.Client'

        from django.db.models.signals import post_migrate
        post_migrate.connect(_seed_default_label_format, sender=self)


def _seed_default_label_format(sender, **kwargs):
    """Create the standard Dymo/thermal label format if none exist yet."""
    try:
        from .models import LabelFormat
        if not LabelFormat.objects.exists():
            LabelFormat.objects.create(
                name='Standard — 3.5in × 1.1in',
                width='3.5in',
                height='1.1in',
                is_default=True,
                notes='Dymo 30252 / common thermal label size.',
            )
    except Exception:
        pass  # table may not exist yet during initial migrate
