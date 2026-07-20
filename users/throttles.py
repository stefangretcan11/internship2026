from rest_framework.throttling import AnonRateThrottle,UserRateThrottle

class PasswordResetThrottle(AnonRateThrottle):
    scope = 'password_reset'

    def allow_request(self, request, view):
        # only activate this throttle if the user is hitting the reset_password endpoint
        if request.path and 'reset_password' not in request.path:
            return True  # let other requests pass without throttling

        return super().allow_request(request, view)

class IssueCreationThrottle(UserRateThrottle):
    scope = 'issue_creation'
