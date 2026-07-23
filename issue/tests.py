from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from users.models import CustomUser
from issue.models import Issue, Alert, Comment, IssueFollower
from zone.models import Zone


class IssueAPITests(APITestCase):
    def setUp(self):
        # 1. Create Test Users
        self.citizen = CustomUser.objects.create_user(
            email="citizen@example.com",
            password="password123",
            role=CustomUser.Role.CITIZEN,
            status=CustomUser.Status.ACTIVE  # <-- Add this!
        )
        self.other_citizen = CustomUser.objects.create_user(
            email="other@example.com",
            password="password123",
            role=CustomUser.Role.CITIZEN,
            status=CustomUser.Status.ACTIVE  # <-- Add this!
        )
        self.validator = CustomUser.objects.create_user(
            email="validator@example.com",
            password="password123",
            role=CustomUser.Role.VALIDATOR,
            status=CustomUser.Status.ACTIVE  # <-- Add this!
        )
        self.agent = CustomUser.objects.create_user(
            email="agent@example.com",
            password="password123",
            role=CustomUser.Role.AGENT,
            status=CustomUser.Status.ACTIVE  # <-- Add this!
        )
        self.admin = CustomUser.objects.create_user(
            email="admin@example.com",
            password="password123",
            role=CustomUser.Role.ADMIN,
            status=CustomUser.Status.ACTIVE  # <-- Add this!
        )

        # 2. Create Test Zone
        self.zone = Zone.objects.create(name="Downtown", neighborhood="Center")
        self.zone.agents.add(self.agent)

        # 3. Create Test Issues
        self.issue = Issue.objects.create(
            title="Pothole",
            description="Big pothole on Main St",
            gps_lat=45.0,
            gps_long=25.0,
            owner=self.citizen,
            status=Issue.Status.NEW,
            validation_status=Issue.ValidationStatus.PENDING
        )

    def test_issue_create(self):
        """Test creating a new issue as a citizen."""
        self.client.force_authenticate(user=self.citizen)

        # Based on TownGuardian/urls.py, the route is /api/issues/
        url = "/api/issues/"

        data = {
            "title": "Broken Streetlight",
            "description": "Light is out",
            "gps_lat": 44.0,
            "gps_long": 26.0,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Issue.objects.count(), 2)
        # Verify defaults from perform_create
        self.assertEqual(Issue.objects.get(title="Broken Streetlight").status, Issue.Status.NEW)

    def test_my_issues_list(self):
        """Test that a user only sees their own issues in /user/"""
        self.client.force_authenticate(user=self.citizen)
        url = "/api/issues/user/"

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Citizen created 1 issue in setUp
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "Pothole")

    def test_nearby_issues(self):
        """Test nearby issues filters by distance and validation status"""
        self.issue.validation_status = Issue.ValidationStatus.VALIDATED
        self.issue.save()

        self.client.force_authenticate(user=self.citizen)
        url = "/api/issues/nearby/?gps_lat=45.0&gps_long=25.0&radius=500"

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_report_issue(self):
        """Test that an issue can be reported only once by a user"""
        self.client.force_authenticate(user=self.other_citizen)
        url = f"/api/issues/{self.issue.id}/report/"

        # First report should succeed
        response1 = self.client.post(url)
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        # Second report from same user should fail
        response2 = self.client.post(url)
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_follow_issue(self):
        """Test that users cannot follow their own issue"""
        self.issue.validation_status = Issue.ValidationStatus.VALIDATED
        self.issue.save()

        self.client.force_authenticate(user=self.citizen)
        url = f"/api/issues/{self.issue.id}/follow/"

        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["message"], "You already receive notifications for your own issue.")

    def test_validate_issue(self):
        """Test validation and auto-assignment logic"""
        self.client.force_authenticate(user=self.validator)
        url = f"/api/issues/{self.issue.id}/validated/"

        # IssueValidationSerializer expects zone_id
        data = {"zone_id": str(self.zone.id)}
        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.validation_status, Issue.ValidationStatus.VALIDATED)
        # Check if auto-assignment worked
        self.assertEqual(self.issue.assigned, self.agent)

    def test_reject_issue_requires_message(self):
        """Test that rejecting an issue requires a reason (message)"""
        self.client.force_authenticate(user=self.validator)
        url = f"/api/issues/{self.issue.id}/rejected/"

        data = {"message": ""}  # Empty message
        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["message"], "A rejection reason is required.")

    def test_assign_issue_manually(self):
        """Test manually assigning an issue"""
        self.client.force_authenticate(user=self.admin)
        url = f"/api/issues/{self.issue.id}/assign/"

        # IssueAssignSerializer expects agent_id
        data = {"agent_id": str(self.agent.id)}
        response = self.client.patch(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.assigned, self.agent)

    def test_comment_on_issue(self):
        """Test that users cannot comment on issues they don't have access to"""
        # Make the issue rejected so other citizens can't see it
        self.issue.validation_status = Issue.ValidationStatus.REJECTED_DUPLICATE
        self.issue.save()

        self.client.force_authenticate(user=self.other_citizen)
        url = f"/api/issues/{self.issue.id}/comments/"

        data = {"description": "This is a comment"}
        response = self.client.post(url, data)

        # Should be forbidden because can_view_issue() returns False
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
