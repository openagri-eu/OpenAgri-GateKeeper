from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Authenticate against either the username field or the email field.
    This keeps Django admin and the site login consistent with GK's API login.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        identifier = username if username is not None else kwargs.get(UserModel.USERNAME_FIELD)
        if identifier is None or password is None:
            return None

        try:
            user = UserModel._default_manager.get(
                Q(username=identifier) | Q(email=identifier)
            )
        except UserModel.DoesNotExist:
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            return None

        if self.user_can_authenticate(user) and user.check_password(password):
            return user
        return None
