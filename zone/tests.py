from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import CustomUser
from zone.models import Zone


class ZoneAPITests(APITestCase):

    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            email="admin@test.com",
            password="TestPassword123!",
            role=CustomUser.Role.ADMIN,
            status=CustomUser.Status.ACTIVE,
        )

        self.citizen = CustomUser.objects.create_user(
            email="citizen@test.com",
            password="TestPassword123!",
            role=CustomUser.Role.CITIZEN,
            status=CustomUser.Status.ACTIVE,
        )

        self.agent = CustomUser.objects.create_user(
            email="agent@test.com",
            password="TestPassword123!",
            role=CustomUser.Role.AGENT,
            status=CustomUser.Status.ACTIVE,
        )

        self.zone = Zone.objects.create(
            name="Zona Centrală",
            neighborhood="Centru",
            color="#FFFFFF",
        )

        self.zone.agents.add(self.agent)

        self.zone_list_url = reverse("zone-list")

        self.zone_detail_url = reverse(
            "zone-detail",
            kwargs={"pk": self.zone.id},
        )

    # 1. GET /zone/
    def test_list_zones(self):
        self.client.force_authenticate(user=self.citizen)

        response = self.client.get(self.zone_list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["name"],
            "Zona Centrală",
        )

    # 2. POST /zone/
    def test_create_zone(self):
        self.client.force_authenticate(user=self.admin)

        payload = {
            "name": "Zona Nouă",
            "neighborhood": "Burdujeni",
            "color": "#123456",
            "agents": [str(self.agent.id)],
        }

        response = self.client.post(
            self.zone_list_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            Zone.objects.filter(
                name="Zona Nouă",
            ).exists()
        )

    # 3. GET /zone/{id}/
    def test_retrieve_zone(self):
        self.client.force_authenticate(user=self.citizen)

        response = self.client.get(
            self.zone_detail_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["id"],
            str(self.zone.id),
        )

        self.assertEqual(
            response.data["name"],
            "Zona Centrală",
        )

    # 4. PUT /zone/{id}/
    def test_update_zone(self):
        self.client.force_authenticate(user=self.admin)

        payload = {
            "name": "Zona Actualizată",
            "neighborhood": "Obcini",
            "color": "#ABCDEF",
            "agents": [str(self.agent.id)],
        }

        response = self.client.put(
            self.zone_detail_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.zone.refresh_from_db()

        self.assertEqual(
            self.zone.name,
            "Zona Actualizată",
        )
        self.assertEqual(
            self.zone.neighborhood,
            "Obcini",
        )
        self.assertEqual(
            self.zone.color,
            "#ABCDEF",
        )

    # 5. PATCH /zone/{id}/
    def test_partial_update_zone(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            self.zone_detail_url,
            {
                "color": "#000000",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.zone.refresh_from_db()

        self.assertEqual(
            self.zone.color,
            "#000000",
        )

        self.assertEqual(
            self.zone.name,
            "Zona Centrală",
        )

    # 6. DELETE /zone/{id}/
    def test_delete_zone(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.delete(
            self.zone_detail_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            Zone.objects.filter(
                id=self.zone.id,
            ).exists()
        )