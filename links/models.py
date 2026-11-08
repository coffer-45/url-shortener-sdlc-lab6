from django.conf import settings
from django.db import models


class ShortLink(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="short_links")
    original_url = models.URLField(max_length=2048)
    code = models.CharField(max_length=12, unique=True)
    click_count = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "short_links"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.code
