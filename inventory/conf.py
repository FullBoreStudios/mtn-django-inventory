from django.conf import settings

DEFAULTS = {
    # Template to extend in any views rendered by this package
    'BASE_TEMPLATE': 'base.html',
    # Set False to hide the Client field on all Item admin views
    'ENABLE_CLIENT': True,
}


def inventory_setting(name):
    user_settings = getattr(settings, 'INVENTORY', {})
    return user_settings.get(name, DEFAULTS[name])
