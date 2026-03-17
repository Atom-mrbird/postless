import os
import django

os.environ["DJANGO_SETTINGS_MODULE"] = "postless.settings"  # ← replace with your actual settings module
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()