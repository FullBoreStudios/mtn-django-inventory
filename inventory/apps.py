from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'
    verbose_name = 'Inventory'

    def ready(self):
        from django.conf import settings
        if not hasattr(settings, 'INVENTORY_CLIENT_MODEL'):
            settings.INVENTORY_CLIENT_MODEL = 'inventory.Client'
