from rest_framework.permissions import BasePermission, SAFE_METHODS
from users.models import CustomUser


class IsAdminOrReadOnly(BasePermission):

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user.is_authenticated

        return (
                request.user.is_authenticated
                and request.user.role in [
                    CustomUser.Role.ADMIN,
                    CustomUser.Role.SUPERADMIN,
                ]
        )


class IsActiveUser(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.status == 'active'
        )


class IsCitizen(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.status == 'active'
            and request.user.role == 'citizen'
        )


class IsValidator(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.status == 'active'
            and request.user.role == 'validator'
        )


class IsAgent(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.status == 'active'
            and request.user.role == 'agent'
        )


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.status == 'active'
            and request.user.role == 'admin'
        )


class IsAgentOrAbove(BasePermission):
    ALLOWED_ROLES = {'agent', 'validator', 'admin', 'superadmin'}

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.status == 'active'
            and request.user.role in self.ALLOWED_ROLES
        )


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role == 'superadmin'
        )


class IsAdminOrValidator(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.status == 'active'
            and request.user.role in {'admin', 'superadmin', 'validator'}
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
