"""Exercise the complete browser workflow across auth, views, services and ORM."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from links.models import ShortLink


class IntegratedWorkflowTests(TestCase):
    def test_register_create_follow_count_and_delete(self):
        browser = Client(enforce_csrf_checks=True)
        register = browser.get(reverse("register"))
        token = register.cookies["csrftoken"].value
        response = browser.post(reverse("register"), {
            "username": "integrated", "password1": "Example-pass-928!",
            "password2": "Example-pass-928!", "csrfmiddlewaretoken": token,
        })
        self.assertRedirects(response, reverse("link_list"))
        user = get_user_model().objects.get(username="integrated")
        self.assertTrue(user.check_password("Example-pass-928!"))

        create = browser.get(reverse("link_create"))
        token = create.cookies["csrftoken"].value
        response = browser.post(reverse("link_create"), {
            "original_url": "https://example.com/path", "csrfmiddlewaretoken": token,
        })
        self.assertRedirects(response, reverse("link_list"))
        link = ShortLink.objects.get(owner=user)
        self.assertContains(browser.get(reverse("link_list")), reverse("follow_link", args=[link.code]))

        visitor = Client()
        response = visitor.get(reverse("follow_link", args=[link.code]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://example.com/path")
        link.refresh_from_db()
        self.assertEqual(link.click_count, 1)
        self.assertContains(browser.get(reverse("link_list")), "переходів: 1")

        other = get_user_model().objects.create_user(username="stranger", password="Safe-pass-729!")
        intruder = Client(enforce_csrf_checks=True)
        intruder.force_login(other)
        token = intruder.get(reverse("link_create")).cookies["csrftoken"].value
        self.assertNotContains(intruder.get(reverse("link_list")), link.code)
        self.assertEqual(intruder.post(reverse("link_delete", args=[link.pk]), {
            "csrfmiddlewaretoken": token,
        }).status_code, 404)
        self.assertTrue(ShortLink.objects.filter(pk=link.pk).exists())

        token = browser.get(reverse("link_list")).cookies["csrftoken"].value
        self.assertEqual(browser.post(reverse("link_delete", args=[link.pk]), {
            "csrfmiddlewaretoken": token,
        }).status_code, 302)
        self.assertEqual(visitor.get(reverse("follow_link", args=[link.code])).status_code, 404)

    def test_admin_access_is_staff_only(self):
        user = get_user_model().objects.create_user(username="ordinary", password="Safe-pass-729!")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)
        admin = get_user_model().objects.create_superuser(
            username="admin", email="admin@example.com", password="Safe-pass-729!"
        )
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_http_https_validation_and_empty_result(self):
        user = get_user_model().objects.create_user(username="owner", password="Safe-pass-729!")
        self.client.force_login(user)
        for url in ("ftp://example.com/file", "javascript:alert(1)", "not a url"):
            response = self.client.post(reverse("link_create"), {"original_url": url})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
        self.assertEqual(ShortLink.objects.count(), 0)
