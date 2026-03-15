from django.test import TestCase
from django.urls import reverse

from accounts.models import Department, User


class LoginViewTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="ICT", code="ICT")
        self.user = User.objects.create_user(
            email="admin@example.com",
            password="password123",
            first_name="Admin",
            last_name="User",
            role="ADMIN",
            department=self.department,
        )

    def test_login_view_authenticates_and_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("login"),
            data={
                "username": self.user.email,
                "password": "password123",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_logout_view_clears_session_and_redirects_to_login(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)


class UserManagementViewTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="ICT", code="ICT")
        self.operations_department = Department.objects.create(name="Operations", code="OPS")
        self.admin_user = User.objects.create_user(
            email="manager@example.com",
            password="password123",
            first_name="Manager",
            last_name="Admin",
            role="ADMIN",
            department=self.department,
        )
        self.technician_user = User.objects.create_user(
            email="technician@example.com",
            password="password123",
            first_name="Tech",
            last_name="User",
            role="TECHNICIAN",
            department=self.operations_department,
        )

    def test_admin_can_open_user_list(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("accounts:user_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User Management")
        self.assertContains(response, self.admin_user.email)

    def test_non_admin_cannot_open_user_management(self):
        self.client.force_login(self.technician_user)

        response = self.client.get(reverse("accounts:user_list"))

        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_update_and_delete_user(self):
        self.client.force_login(self.admin_user)

        create_response = self.client.post(
            reverse("accounts:user_create"),
            data={
                "email": "new.user@example.com",
                "first_name": "New",
                "last_name": "User",
                "phone_number": "0712345678",
                "role": "MANAGEMENT",
                "department": self.operations_department.pk,
                "is_active": "on",
                "password1": "strongpass123",
                "password2": "strongpass123",
            },
        )

        self.assertEqual(create_response.status_code, 302)
        managed_user = User.objects.get(email="new.user@example.com")
        self.assertEqual(managed_user.department, self.operations_department)
        self.assertTrue(managed_user.check_password("strongpass123"))

        update_response = self.client.post(
            reverse("accounts:user_update", args=[managed_user.pk]),
            data={
                "email": "new.user@example.com",
                "first_name": "Updated",
                "last_name": "User",
                "phone_number": "0799999999",
                "role": "TECHNICIAN",
                "department": self.department.pk,
                "is_active": "on",
                "new_password1": "",
                "new_password2": "",
            },
        )

        self.assertEqual(update_response.status_code, 302)
        managed_user.refresh_from_db()
        self.assertEqual(managed_user.first_name, "Updated")
        self.assertEqual(managed_user.role, "TECHNICIAN")
        self.assertEqual(managed_user.department, self.department)

        delete_response = self.client.post(reverse("accounts:user_delete", args=[managed_user.pk]))

        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=managed_user.pk).exists())

    def test_admin_cannot_delete_current_account(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse("accounts:user_delete", args=[self.admin_user.pk]))

        self.assertRedirects(response, reverse("accounts:user_detail", args=[self.admin_user.pk]))
        self.assertTrue(User.objects.filter(pk=self.admin_user.pk).exists())


class DepartmentManagementViewTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="ICT", code="ICT")
        self.admin_user = User.objects.create_user(
            email="department-admin@example.com",
            password="password123",
            first_name="Department",
            last_name="Admin",
            role="ADMIN",
            department=self.department,
        )
        self.technician_user = User.objects.create_user(
            email="department-tech@example.com",
            password="password123",
            first_name="Department",
            last_name="Tech",
            role="TECHNICIAN",
            department=self.department,
        )

    def test_admin_can_open_department_list(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("accounts:department_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Departments")
        self.assertContains(response, self.department.code)

    def test_non_admin_cannot_open_department_management(self):
        self.client.force_login(self.technician_user)

        response = self.client.get(reverse("accounts:department_list"))

        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_update_and_delete_department(self):
        self.client.force_login(self.admin_user)

        create_response = self.client.post(
            reverse("accounts:department_create"),
            data={
                "name": "Finance",
                "code": "FIN",
                "description": "Finance and accounting department",
            },
        )

        self.assertEqual(create_response.status_code, 302)
        department = Department.objects.get(code="FIN")
        self.assertEqual(department.name, "Finance")

        update_response = self.client.post(
            reverse("accounts:department_update", args=[department.pk]),
            data={
                "name": "Finance Office",
                "code": "FIN",
                "description": "Updated department description",
            },
        )

        self.assertEqual(update_response.status_code, 302)
        department.refresh_from_db()
        self.assertEqual(department.name, "Finance Office")

        delete_response = self.client.post(reverse("accounts:department_delete", args=[department.pk]))

        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(Department.objects.filter(pk=department.pk).exists())
