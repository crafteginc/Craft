from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.maneger import UserManager

AUTH_PROVIDERS = {'email': 'email', 'google': 'google', 'github': 'github', 'linkedin': 'linkedin'}


class User(AbstractBaseUser, PermissionsMixin):
    id = models.BigAutoField(primary_key=True, editable=False)
    email = models.EmailField(max_length=255, verbose_name=_("Email Address"), unique=True)
    first_name = models.CharField(max_length=100, verbose_name=_("First Name"))
    last_name = models.CharField(max_length=100, verbose_name=_("Last Name"))
    PhoneNO = models.CharField(max_length=14, verbose_name=_("Phone number"))
    Balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    is_customer = models.BooleanField(default=False)
    is_supplier = models.BooleanField(default=False)
    is_delivery = models.BooleanField(default=False)
    last_password_reset_request = models.DateTimeField(null=True, blank=True)
    auth_provider = models.CharField(max_length=50, blank=False, null=False, default=AUTH_PROVIDERS.get('email'))

    REQUIRED_FIELDS = ["first_name", "last_name", "password"]
    objects = UserManager()
    USERNAME_FIELD = "email"

    @property
    def get_full_name(self):
        return f"{self.first_name.title()} {self.last_name.title()}"

    def tokens(self):
        refresh = RefreshToken.for_user(self)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token)
        }

    def __str__(self):
        return self.email

    def clean(self):
        super().clean()
        if User.objects.filter(email__iexact=self.email).exclude(pk=self.pk).exists():
            raise ValidationError("This email is already in use.")

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        if not self.pk or not self.password:
            if not self.pk:
                self.pk = None
            self.password = make_password(self.password)

        super().save(*args, **kwargs)


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    CustomerPhoto = models.ImageField(upload_to='customer_photos/%y/%m/%d', blank=True, null=True)
    CreditCardNO = models.CharField(max_length=20, blank=True, null=True)
    CreditCardType = models.CharField(max_length=50, blank=True, null=True)
    CreditCardMonth = models.CharField(max_length=2, blank=True, null=True)
    CreditCardYear = models.CharField(max_length=4, blank=True, null=True)
    CreditCVV = models.CharField(max_length=3)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"


class Supplier(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    SupplierPhoto = models.ImageField(upload_to='supplier_photos/%y/%m/%d', blank=True, null=True)
    SupplierCover = models.ImageField(upload_to='supplier_covers/%y/%m/%d', blank=True, null=True)
    CategoryTitle = models.CharField(max_length=50)
    CreditCardNO = models.CharField(max_length=16, blank=True, null=True)
    CreditCardType = models.CharField(max_length=20, blank=True, null=True)
    CreditCardMonth = models.IntegerField(blank=True, null=True)
    CreditCardYear = models.IntegerField(blank=True, null=True)
    CreditCVV = models.IntegerField(blank=True, null=True)
    Logo = models.ImageField(upload_to='supplier_logos/%y/%m/%d', blank=True, null=True)
    SupplierContract = models.FileField(upload_to='supplier_contracts/%y/%m/%d')
    SupplierIdentity = models.FileField(upload_to='supplier_identities/%y/%m/%d')
    FollowersNo = models.PositiveIntegerField(default=0)
    ExperienceYears = models.IntegerField(blank=True, null=True)
    Rating = models.DecimalField(max_digits=10, decimal_places=2, default=5.0,
                                 validators=(MinValueValidator(0.0), MaxValueValidator(5.0)))
    Orders = models.IntegerField(blank=True, null=True)
    accepted_supplier = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"

    def update_rating(self):
        avg_rating = self.supplier_rating.aggregate(models.Avg('rating'))['rating__avg']
        self.Rating = avg_rating if avg_rating is not None else 0
        self.save()


class Delivery(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="delivery")
    DeliveryPhoto = models.ImageField(upload_to='shipper_photos/%y/%m/%d')
    DeliveryContract = models.ImageField(upload_to='shipper_contracts/%y/%m/%d')
    DeliveryIdentity = models.ImageField(upload_to='shipper_identities/%y/%m/%d')
    VehicleModel = models.CharField(max_length=100)
    VehicleColor = models.CharField(max_length=100, blank=True, null=True)
    plateNO = models.CharField(max_length=100)
    Rating = models.DecimalField(max_digits=10, decimal_places=2, default=5.0,
                                 validators=(MinValueValidator(0.0), MaxValueValidator(5.0)))
    Orders = models.IntegerField(blank=True, null=True)
    ExperienceYears = models.IntegerField(blank=True, null=True)
    governorate = models.CharField(max_length=100, default='default_governorate')
    accepted_delivery = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"

    def update_rating(self):
        avg_rating = self.delivery_rating.aggregate(models.Avg('rating'))['rating__avg']
        self.Rating = avg_rating if avg_rating is not None else 0
        self.save()

    def save(self, *args, **kwargs):
        if not self.pk and not self.ExperienceYears:
            self.ExperienceYears = timezone.now().year - self.user.date_joined.year
        super().save(*args, **kwargs)

    def _init_(self, *args, **kwargs):
        super()._init_(*args, **kwargs)
        if not self.pk and not self.ExperienceYears:
            self.ExperienceYears = timezone.now().year - self.user.date_joined.year


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    BuildingNO = models.CharField(max_length=10, null=True)
    Street = models.CharField(max_length=100)
    City = models.CharField(max_length=100)
    State = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.user.get_full_name}"


class Follow(models.Model):
    follower_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE,
                                              default=ContentType.objects.get_for_model(Customer).id)
    follower_object_id = models.PositiveIntegerField(default=0)
    follower = GenericForeignKey('follower_content_type', 'follower_object_id')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.follower} follows {self.supplier.user.get_full_name}"

    class Meta:
        unique_together = ('follower_content_type', 'follower_object_id', 'supplier')


@receiver(post_save, sender=Follow)
def update_followers_count_on_create(sender, instance, created, **kwargs):
    if created:
        instance.supplier.FollowersNo += 1
        instance.supplier.save()


@receiver(post_delete, sender=Follow)
def update_followers_count_on_delete(sender, instance, **kwargs):
    instance.supplier.FollowersNo -= 1
    instance.supplier.save()


class OneTimePassword(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.first_name} - otp code"