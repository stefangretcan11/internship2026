from rest_framework.permissions import BasePermission, SAFE_METHODS

from users.models import CustomUser


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
        # owner can edit their own
        return view.action == 'partial_update' and request.user == obj.user


class IsCommentOwner(BasePermission):

    def has_object_permission(self, request, view):
        return request.user == view.get_object().user


class CanCreateIssue(BasePermission):
    message = "Only active citizens can report issues."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if user.role != CustomUser.Role.CITIZEN:
            self.message = "Only citizens can report issues."
            return False

        if user.status == CustomUser.Status.PENDING:
            self.message = "Your account is pending validation."
            return False

        if user.status == CustomUser.Status.REJECTED:
            self.message = "Your account has been rejected."
            return False

        return user.status == CustomUser.Status.ACTIVE


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
