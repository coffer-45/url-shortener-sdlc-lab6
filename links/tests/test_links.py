from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from links.forms import LinkForm
from links.models import ShortLink
from links.services import LinkService


class LinkServiceTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="first", password="safe-password-123")
        self.other = get_user_model().objects.create_user(username="second", password="safe-password-123")

    def test_create_stores_owner_and_unique_code(self):
        first = LinkService().create(self.owner, "https://example.com/first")
        second = LinkService().create(self.owner, "https://example.com/second")
        self.assertNotEqual(first.code, second.code)
        self.assertEqual(first.owner, self.owner)
        self.assertEqual(first.click_count, 0)

    def test_collision_retries_using_unique_database_constraint(self):
        ShortLink.objects.create(owner=self.other, original_url="https://example.com/", code="duplicate")
        generator = Mock()
        generator.generate.side_effect = ["duplicate", "freshcode"]
        link = LinkService(generator).create(self.owner, "https://example.com/new")
        self.assertEqual(link.code, "freshcode")
        self.assertEqual(generator.generate.call_count, 2)

    def test_repeated_collisions_fail_with_a_limit(self):
        ShortLink.objects.create(owner=self.other, original_url="https://example.com/", code="duplicate")
        generator = Mock()
        generator.generate.return_value = "duplicate"
        with self.assertRaises(RuntimeError):
            LinkService(generator).create(self.owner, "https://example.com/new")
        self.assertEqual(generator.generate.call_count, LinkService.max_attempts)

    def test_list_and_delete_only_own_links(self):
        own = LinkService().create(self.owner, "https://example.com/own")
        foreign = LinkService().create(self.other, "https://example.com/other")
        self.assertEqual(list(LinkService().list_for(self.owner)), [own])
        self.assertFalse(LinkService().delete_for(self.owner, foreign.pk))
        self.assertTrue(ShortLink.objects.filter(pk=foreign.pk).exists())
        self.assertTrue(LinkService().delete_for(self.owner, own.pk))

    def test_service_rejects_non_http_scheme(self):
        with self.assertRaises(ValidationError):
            LinkService().create(self.owner, "ftp://example.com/file")


class LinkViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="first", password="safe-password-123")
        self.other = get_user_model().objects.create_user(username="second", password="safe-password-123")

    def test_guests_must_log_in_to_manage_links(self):
        for url in (reverse("link_list"), reverse("link_create")):
            response = self.client.get(url)
            self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_register_creates_user_with_hashed_password(self):
        response = self.client.post(reverse("register"), {
            "username": "newuser", "password1": "Complex-pass-928!", "password2": "Complex-pass-928!",
        })
        self.assertRedirects(response, reverse("link_list"))
        user = get_user_model().objects.get(username="newuser")
        self.assertNotEqual(user.password, "Complex-pass-928!")
        self.assertTrue(user.check_password("Complex-pass-928!"))

    def test_login_and_logout(self):
        self.assertRedirects(self.client.post(reverse("login"), {
            "username": "first", "password": "safe-password-123",
        }), reverse("link_list"))
        self.assertRedirects(self.client.post(reverse("logout")), reverse("login"))
        self.assertRedirects(self.client.get(reverse("link_list")),
                             f"{reverse('login')}?next={reverse('link_list')}")

    def test_create_valid_link_and_show_short_url(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("link_create"), {"original_url": "https://example.com/path"})
        self.assertRedirects(response, reverse("link_list"))
        link = ShortLink.objects.get(owner=self.owner)
        self.assertContains(self.client.get(reverse("link_list")), reverse("follow_link", args=[link.code]))

    def test_invalid_scheme_does_not_create_link(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("link_create"), {"original_url": "ftp://example.com/file"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(ShortLink.objects.exists())

    def test_others_links_are_hidden_and_cannot_be_deleted(self):
        link = LinkService().create(self.other, "https://example.com/foreign")
        self.client.force_login(self.owner)
        self.assertNotContains(self.client.get(reverse("link_list")), link.original_url)
        self.assertEqual(self.client.post(reverse("link_delete", args=[link.pk])).status_code, 404)
        self.assertTrue(ShortLink.objects.filter(pk=link.pk).exists())

    def test_delete_requires_post(self):
        link = LinkService().create(self.owner, "https://example.com/own")
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("link_delete", args=[link.pk])).status_code, 405)
        self.assertRedirects(self.client.post(reverse("link_delete", args=[link.pk])), reverse("link_list"))
        self.assertFalse(ShortLink.objects.filter(pk=link.pk).exists())

    def test_public_redirect_and_counter(self):
        link = LinkService().create(self.owner, "https://example.com/destination")
        url = reverse("follow_link", args=[link.code])
        for expected_count in (1, 2):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response["Location"], link.original_url)
            link.refresh_from_db()
            self.assertEqual(link.click_count, expected_count)

    def test_unknown_short_code_is_404(self):
        self.assertEqual(self.client.get(reverse("follow_link", args=["unknown"])).status_code, 404)

    def test_csrf_is_required_for_mutations(self):
        link = LinkService().create(self.owner, "https://example.com/own")
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse("link_delete", args=[link.pk])).status_code, 403)
        self.assertTrue(ShortLink.objects.filter(pk=link.pk).exists())


class LinkFormTests(TestCase):
    def test_only_http_and_https(self):
        for url in ("http://example.com", "https://example.com/path"):
            self.assertTrue(LinkForm({"original_url": url}).is_valid())
        for url in ("ftp://example.com", "javascript:alert(1)", "not a url"):
            self.assertFalse(LinkForm({"original_url": url}).is_valid())
