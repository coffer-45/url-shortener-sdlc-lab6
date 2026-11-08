from django.contrib import admin

from .models import ShortLink


@admin.register(ShortLink)
class ShortLinkAdmin(admin.ModelAdmin):
    list_display = ("code", "owner", "original_url", "click_count", "created_at")
    search_fields = ("code", "original_url", "owner__username")
    list_filter = ("created_at",)
    readonly_fields = ("click_count", "created_at")
