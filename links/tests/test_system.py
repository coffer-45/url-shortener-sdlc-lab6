"""User-facing browser scenario through real Django middleware and database."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from links.models import ShortLink


class SystemScenarioTests(TestCase):
    def test_home_and_registration_navigation_for_guest_and_user(self):
        self.assertRedirects(self.client.get(reverse("home")), reverse("login"))
        user = get_user_model().objects.create_user(username="member", password="Test-pass-673!")
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse("home")), reverse("link_list"))
        self.assertRedirects(self.client.get(reverse("register")), reverse("link_list"))
        self.assertEqual(str(ShortLink.objects.create(
            owner=user, code="member1", original_url="https://example.org/"
        )), "member1")

    def test_login_create_redirect_delete_logout_and_guest_access(self):
        get_user_model().objects.create_user(username="visitor", password="Test-pass-673!")
        browser = Client(enforce_csrf_checks=True)
        token = browser.get(reverse("login")).cookies["csrftoken"].value
        self.assertRedirects(browser.post(reverse("login"), {
            "username": "visitor", "password": "Test-pass-673!", "csrfmiddlewaretoken": token,
        }), reverse("link_list"))

        token = browser.get(reverse("link_create")).cookies["csrftoken"].value
        self.assertRedirects(browser.post(reverse("link_create"), {
            "original_url": "http://example.org/destination", "csrfmiddlewaretoken": token,
        }), reverse("link_list"))
        link = ShortLink.objects.get()
        self.assertContains(browser.get(reverse("link_list")), link.code)
        public = Client()
        for visits in (1, 2):
            response = public.get(reverse("follow_link", args=[link.code]))
            self.assertEqual((response.status_code, response["Location"]),
                             (302, "http://example.org/destination"))
            link.refresh_from_db()
            self.assertEqual(link.click_count, visits)

        token = browser.get(reverse("link_list")).cookies["csrftoken"].value
        self.assertRedirects(browser.post(reverse("link_delete", args=[link.pk]), {
            "csrfmiddlewaretoken": token,
        }), reverse("link_list"))
        self.assertEqual(public.get(reverse("follow_link", args=[link.code])).status_code, 404)
        self.assertRedirects(browser.post(reverse("logout"), {
            "csrfmiddlewaretoken": token,
        }), reverse("login"))
        self.assertRedirects(browser.get(reverse("link_list")),
                             f"{reverse('login')}?next={reverse('link_list')}")
