from django.test import TestCase
from django.urls import reverse

from accounts.models import Department, User


class LandingPageTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="ICT", code="ICT")
        self.user = User.objects.create_user(
            email="dashboard@example.com",
            password="password123",
            first_name="Dash",
            last_name="User",
            role="ADMIN",
            department=self.department,
        )

    def test_home_page_shows_login_for_anonymous_users(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Login")

    def test_dashboard_redirects_anonymous_users_to_login(self):
        response = self.client.get(reverse("dashboard"))

        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_dashboard_renders_for_authenticated_users(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard.html")
        self.assertContains(response, "ICT Operations Dashboard")
