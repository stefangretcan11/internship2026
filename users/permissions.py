from rest_framework import permissions
from rest_framework.permissions import BasePermission, SAFE_METHODS

from users.models import CustomUser


class IsActiveOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user.status == 'active'


class IsAdminOrReadOnly(BasePermission):

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user.is_authenticated

        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in {
                CustomUser.Role.ADMIN,
                CustomUser.Role.SUPERADMIN,
            }
        )


class IsActiveUser(BasePermission):

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.status == CustomUser.Status.ACTIVE
        )


class IsCitizen(BasePermission):

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.status == CustomUser.Status.ACTIVE
            and request.user.role == CustomUser.Role.CITIZEN
        )


class IsValidator(BasePermission):

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.status == CustomUser.Status.ACTIVE
            and request.user.role == CustomUser.Role.VALIDATOR
        )


class IsAgent(BasePermission):

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.status == CustomUser.Status.ACTIVE
            and request.user.role == CustomUser.Role.AGENT
        )


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.status == CustomUser.Status.ACTIVE
            and request.user.role in {
                CustomUser.Role.ADMIN,
                CustomUser.Role.SUPERADMIN,
            }
        )


class IsAgentOrAbove(BasePermission):
    ALLOWED_ROLES = {
        CustomUser.Role.AGENT,
        CustomUser.Role.VALIDATOR,
        CustomUser.Role.ADMIN,
        CustomUser.Role.SUPERADMIN,
    }

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.status == CustomUser.Status.ACTIVE
            and request.user.role in self.ALLOWED_ROLES
        )


class IsSuperAdmin(BasePermission):

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.status == CustomUser.Status.ACTIVE
            and request.user.role == CustomUser.Role.SUPERADMIN
        )


class IsAdminOrValidator(BasePermission):

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.status == CustomUser.Status.ACTIVE
            and request.user.role in {
                CustomUser.Role.ADMIN,
                CustomUser.Role.SUPERADMIN,
                CustomUser.Role.VALIDATOR,
            }
        )


# list/receive - get, any logged user
# create-post
# edit - patch, only the comment author/admin
# delete - delete only owner,admin,superadmin
class IsOwnerOrAdmin(BasePermission):
    # permission for the comments
    def has_object_permission(self, request, view, obj=None):
        # anyone can read
        if request.method in SAFE_METHODS:
            return True
        # admin can do anything
        if request.user.role in {'admin', 'superadmin'}:
            return True
        # owner can edit their own comments
        return view.action == 'partial_update' and request.user == obj.user


class IsCommentOwner(BasePermission):
    message = "You can only modify your own comment."

    def has_object_permission(self, request, view, obj):
        return obj.user_id == request.user.id


class CanCreateIssue(BasePermission):
    message = "Only active citizens can report issues."

    def has_permission(self, request, view):
        user = request.user

        if user and user.is_authenticated:
            if user.role == CustomUser.Role.AGENT:
                self.message = "Agents cannot report an issue."
            elif user.status == CustomUser.Status.PENDING:
                self.message = "Your account is pending validation."
            elif user.status == CustomUser.Status.REJECTED:
                self.message = "Your account has been rejected."
            else:
                return user.status == CustomUser.Status.ACTIVE

        # catches unauthenticated users and any conditions above that failed
        return False


class IsIssueOwnerOrAdmin(BasePermission):
    message = "You do not have permission to edit this issue."

    def has_permission(self, request, view):
        user = request.user

        return bool(
            user
            and user.is_authenticated
            and user.status == CustomUser.Status.ACTIVE
        )

    def has_object_permission(self, request, view, obj):
        user = request.user

        if user.role in {
            CustomUser.Role.ADMIN,
            CustomUser.Role.SUPERADMIN,
            CustomUser.Role.VALIDATOR,
            CustomUser.Role.AGENT,
        }:
            return True

        return (
                user.role == CustomUser.Role.CITIZEN
                and obj.owner_id == user.id
        )


class IsIssueOwner(BasePermission):
    message = "Only the citizen who created this issue can resubmit it."

    def has_permission(self, request, view):
        user = request.user

        return bool(
            user
            and user.is_authenticated
            and user.status == CustomUser.Status.ACTIVE
            and user.role == CustomUser.Role.CITIZEN
        )

    def has_object_permission(self, request, view, obj):
        return obj.owner_id == request.user.id
