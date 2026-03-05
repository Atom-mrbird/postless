from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, SocialAccount, Subscription

class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'platform', 'account_name', 'account_id', 'created_at')
    list_filter = ('platform', 'created_at')
    search_fields = ('user__username', 'account_name', 'account_id')

admin.site.register(User, UserAdmin)
admin.site.register(SocialAccount, SocialAccountAdmin)
admin.site.register(Subscription)
