from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, SocialAccount, Subscription

admin.site.register(User, UserAdmin)
admin.site.register(SocialAccount)
admin.site.register(Subscription)
