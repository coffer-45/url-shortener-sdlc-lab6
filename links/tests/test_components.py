"""Component boundaries: HTTP views -> forms/services -> ORM and status codes."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from links.models import ShortLink
from links.services import LinkService


class ComponentInteractionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="component", password="Test-pass-673!")

    def test_view_passes_validated_url_and_owner_to_service(self):
        self.client.force_login(self.user)
        with patch("links.views.LinkService.create") as create:
            response = self.client.post(reverse("link_create"), {
                "original_url": "https://example.org/path",
            })
        self.assertRedirects(response, reverse("link_list"))
        create.assert_called_once_with(self.user, "https://example.org/path")

    def test_invalid_form_never_calls_service(self):
        self.client.force_login(self.user)
        with patch("links.views.LinkService.create") as create:
            response = self.client.post(reverse("link_create"), {"original_url": "ftp://example.org"})
        self.assertEqual(response.status_code, 200)
        create.assert_not_called()

    def test_public_route_connects_service_and_orm_counter(self):
        link = LinkService().create(self.user, "https://example.org/page")
        self.assertEqual(self.client.get(reverse("follow_link", args=[link.code]))["Location"],
                         link.original_url)
        link.refresh_from_db()
        self.assertEqual(link.click_count, 1)
        self.assertEqual(self.client.get(reverse("follow_link", args=["absent"])).status_code, 404)

    def test_auth_and_owner_filter_across_list_and_delete(self):
        other = get_user_model().objects.create_user(username="other", password="Test-pass-673!")
        link = LinkService().create(other, "https://example.org/secret")
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(reverse("link_list")), link.original_url)
        self.assertEqual(self.client.post(reverse("link_delete", args=[link.pk])).status_code, 404)
        self.assertTrue(ShortLink.objects.filter(pk=link.pk).exists())

    def test_service_does_not_hide_unrelated_database_error(self):
        with patch("links.services.ShortLink.objects.create", side_effect=IntegrityError("other constraint")):
            with self.assertRaisesRegex(IntegrityError, "other constraint"):
                LinkService().create(self.user, "https://example.org/page")
