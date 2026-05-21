from django.conf import settings

DEFAULTS = {
    # Template to extend in any views rendered by this package
    'BASE_TEMPLATE': 'base.html',
    # Set False to hide the Client field on all Item admin views
    'ENABLE_CLIENT': True,
    # Auto-generate asset tags on Item save when asset_tag is blank
    'ASSET_TAG_AUTO': True,
    # Prefix for auto-generated asset tags, e.g. 'ASSET' → 'ASSET-00001'
    'ASSET_TAG_PREFIX': 'ASSET',
    # Zero-pad width for the numeric portion of auto-generated tags
    'ASSET_TAG_PADDING': 5,
}


def inventory_setting(name):
    user_settings = getattr(settings, 'INVENTORY', {})
    return user_settings.get(name, DEFAULTS[name])
