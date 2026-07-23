from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import CustomUser


class UsersAPITests(APITestCase):

    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            email="admin@test.com",
            password="TestPassword123!",
            first_name="Admin",
            last_name="User",
            personal_number="1111111111111",
            role=CustomUser.Role.ADMIN,
            status=CustomUser.Status.ACTIVE,
        )

        self.validator = CustomUser.objects.create_user(
            email="validator@test.com",
            password="TestPassword123!",
            first_name="Validator",
            last_name="User",
            personal_number="2222222222222",
            role=CustomUser.Role.VALIDATOR,
            status=CustomUser.Status.ACTIVE,
        )

        self.citizen = CustomUser.objects.create_user(
            email="citizen@test.com",
            password="TestPassword123!",
            first_name="Citizen",
            last_name="User",
            personal_number="3333333333333",
            role=CustomUser.Role.CITIZEN,
            status=CustomUser.Status.ACTIVE,
        )

        self.pending_user = CustomUser.objects.create_user(
            email="pending@test.com",
            password="TestPassword123!",
            first_name="Pending",
            last_name="User",
            personal_number="4444444444444",
            role=CustomUser.Role.CITIZEN,
            status=CustomUser.Status.PENDING,
        )

        self.user_list_url = reverse(
            "user-management-list"
        )

        self.user_detail_url = reverse(
            "user-management-detail",
            kwargs={"pk": self.citizen.id},
        )

        self.validate_user_url = reverse(
            "validate-user",
            kwargs={"user_id": self.pending_user.id},
        )

        self.me_url = reverse("me")
        self.jwt_create_url = reverse("jwt-create")

    # 1. GET /api/users/admin/users/
    def test_list_users(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            self.user_list_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            4,
        )

    # 2. POST /api/users/admin/users/
    def test_create_user(self):
        self.client.force_authenticate(user=self.admin)

        payload = {
            "email": "newagent@test.com",
            "password": "TestPassword123!",
            "first_name": "New",
            "last_name": "Agent",
            "personal_number": "5555555555555",
            "role": CustomUser.Role.AGENT,
            "status": CustomUser.Status.ACTIVE,
        }

        response = self.client.post(
            self.user_list_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            CustomUser.objects.filter(
                email="newagent@test.com"
            ).exists()
        )

    # 3. GET /api/users/admin/users/{id}/
    def test_retrieve_user(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            self.user_detail_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["id"],
            self.citizen.id,
        )

        self.assertEqual(
            response.data["email"],
            self.citizen.email,
        )

    # 4. PUT /api/users/admin/users/{id}/
    def test_update_user(self):
        self.client.force_authenticate(user=self.admin)

        payload = {
            "email": "updated@test.com",
            "first_name": "Updated",
            "last_name": "Citizen",
            "personal_number": "6666666666666",
            "role": CustomUser.Role.CITIZEN,
            "status": CustomUser.Status.ACTIVE,
        }

        response = self.client.put(
            self.user_detail_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.citizen.refresh_from_db()

        self.assertEqual(
            self.citizen.email,
            "updated@test.com",
        )

        self.assertEqual(
            self.citizen.first_name,
            "Updated",
        )

        self.assertEqual(
            self.citizen.personal_number,
            "6666666666666",
        )

    # 5. PATCH /api/users/admin/users/{id}/
    def test_partial_update_user(self):
        self.client.force_authenticate(
            user=self.validator
        )

        response = self.client.patch(
            self.user_detail_url,
            {
                "status": CustomUser.Status.REJECTED,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.citizen.refresh_from_db()

        self.assertEqual(
            self.citizen.status,
            CustomUser.Status.REJECTED,
        )

        self.assertFalse(
            self.citizen.is_active
        )

    # 6. DELETE /api/users/admin/users/{id}/
    def test_delete_user(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.delete(
            self.user_detail_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.citizen.refresh_from_db()

        self.assertEqual(
            self.citizen.status,
            CustomUser.Status.DELETED,
        )

        self.assertFalse(
            self.citizen.is_active
        )

        self.assertTrue(
            CustomUser.objects.filter(
                id=self.citizen.id
            ).exists()
        )

    # 7. PATCH /api/users/{user_id}/validate/
    def test_validate_user(self):
        self.client.force_authenticate(
            user=self.validator
        )

        response = self.client.patch(
            self.validate_user_url,
            {
                "status": CustomUser.Status.ACTIVE,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.pending_user.refresh_from_db()

        self.assertEqual(
            self.pending_user.status,
            CustomUser.Status.ACTIVE,
        )

        self.assertTrue(
            self.pending_user.is_active
        )

    # 8. GET /api/users/me/
    def test_get_current_user(self):
        self.client.force_authenticate(
            user=self.citizen
        )

        response = self.client.get(
            self.me_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["id"],
            self.citizen.id,
        )

        self.assertEqual(
            response.data["email"],
            self.citizen.email,
        )

        self.assertEqual(
            response.data["role"],
            CustomUser.Role.CITIZEN,
        )

    # 9. POST /auth/jwt/create/
    def test_create_jwt_token(self):
        payload = {
            "email": self.citizen.email,
            "password": "TestPassword123!",
        }

        response = self.client.post(
            self.jwt_create_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn(
            "access",
            response.data,
        )

        self.assertIn(
            "refresh",
            response.data,
        )