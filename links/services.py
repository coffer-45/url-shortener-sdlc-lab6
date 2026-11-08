"""Business operations are kept outside HTTP views for independent testing."""

import secrets
import string

from django.core.validators import URLValidator
from django.db import IntegrityError, transaction
from django.db.models import F

from .models import ShortLink


class CodeGenerator:
    alphabet = string.ascii_letters + string.digits

    def generate(self):
        return "".join(secrets.choice(self.alphabet) for _ in range(8))


class LinkService:
    max_attempts = 5

    def __init__(self, generator=None):
        self.generator = generator or CodeGenerator()

    def create(self, owner, url):
        # Django's URLValidator already rejects inputs longer than 2048 characters.
        URLValidator(schemes=["http", "https"])(url)
        for _ in range(self.max_attempts):
            code = self.generator.generate()
            try:
                with transaction.atomic():
                    return ShortLink.objects.create(owner=owner, original_url=url, code=code)
            except IntegrityError:
                if not ShortLink.objects.filter(code=code).exists():
                    raise
        raise RuntimeError("Не вдалося створити унікальний короткий код")

    def list_for(self, owner):
        return ShortLink.objects.filter(owner=owner)

    def delete_for(self, owner, pk):
        count, _ = ShortLink.objects.filter(owner=owner, pk=pk).delete()
        return bool(count)


class RedirectService:
    def resolve_and_count(self, code):
        link = ShortLink.objects.get(code=code)
        ShortLink.objects.filter(pk=link.pk).update(click_count=F("click_count") + 1)
        return link.original_url
