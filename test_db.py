import os
import django
from pprint import pprint

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "srdc.settings")
django.setup()

from django.conf import settings
print("DATABASES:")
pprint(settings.DATABASES)
