"""Small isolated checks of pure generation and validation logic (unit level)."""

from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from links.forms import LinkForm
from links.services import CodeGenerator, LinkService


class CodeGeneratorUnitTests(SimpleTestCase):
    def test_eight_characters_from_allowed_alphabet(self):
        with patch("links.services.secrets.choice", return_value="a") as choice:
            code = CodeGenerator().generate()
        self.assertEqual(code, "aaaaaaaa")
        self.assertEqual(choice.call_count, 8)
        self.assertIn("a", CodeGenerator.alphabet)
        self.assertNotIn("/", CodeGenerator.alphabet)


class LinkValidationUnitTests(SimpleTestCase):
    def test_form_accepts_http_and_https_only(self):
        for url in ("https://example.org/a?q=1", "http://example.org"):
            with self.subTest(url=url):
                self.assertTrue(LinkForm({"original_url": url}).is_valid())
        for url in ("ftp://example.org", "file:///etc/passwd", "javascript:alert(1)", "broken"):
            with self.subTest(url=url):
                self.assertFalse(LinkForm({"original_url": url}).is_valid())

    def test_service_rejects_too_long_url_before_database_call(self):
        with self.assertRaises(ValidationError):
            LinkService().create(None, "https://example.org/" + "x" * 2048)
