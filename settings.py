from os import path
from django.conf import settings

settings.INSTALLED_APPS += (
    'apps.upload_personal',
)

settings.TEMPLATE_DIRS += (
    path.join(path.dirname(__file__), 'templates'),
)

try:
    RESTRICT_TO_DEFAULTS = settings.RESTRICT_TO_DEFAULTS
    DEFAULT_PERSONAL_COLLECTION = settings.DEFAULT_PERSONAL_COLLECTION
    DEFAULT_PERSONAL_STORAGE = settings.DEFAULT_PERSONAL_STORAGE
except AttributeError:
    RESTRICT_TO_DEFAULTS = False
    DEFAULT_PERSONAL_COLLECTION = False
    DEFAULT_PERSONAL_STORAGE = False

#AUTO_PERSONAL_COLLECTION = False

