from django.contrib.auth.models import BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """
    Custom user manager for the User model.
    """

    def email_validator(self, email):
        """
        Validates the given email.
        """
        try:
            validate_email(email)
        except ValidationError:
            raise ValueError(_("Please enter a valid email address"))

    def create_user(
        self,
        email,
        first_name,
        last_name,
        password,
        **extra_fields,
    ):
        """
        Creates and saves a User with the given email and password.
        """
        if email:
            email = self.normalize_email(email)
            self.email_validator(email)
        else:
            raise ValueError(_("An email address is required"))
        if not first_name:
            raise ValueError(_("First name is required"))
        if not last_name:
            raise ValueError(_("Last name is required"))

        user = self.model(
            email=email,
            first_name=first_name,
            last_name=last_name,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email,
        first_name,
        last_name,
        password,
        **extra_fields,
    ):
        """
        Creates and saves a superuser with the given email and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_verified", True)

        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser must have is_staff=True.")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_superuser=True.")

        user = self.create_user(
            email, first_name, last_name, password, **extra_fields
        )
        return user