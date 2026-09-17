from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=200)
    variant = models.CharField(max_length=100)
    price = models.IntegerField()
    category = models.CharField(max_length=100)
    image = models.CharField(max_length=300)
    inStock = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class UserAccountManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        email = self.normalize_email(email)
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email, password, **extra_fields)


class UserAccount(AbstractBaseUser, PermissionsMixin):
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    profile_image = models.ImageField(upload_to="profiles/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name", "phone"]

    objects = UserAccountManager()

    def __str__(self):
        return self.email

    @property
    def mobile_number(self):
        return self.phone


class Address(models.Model):
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name="addresses")
    house_flat = models.CharField(max_length=200)
    area = models.CharField(max_length=200)
    landmark = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    pincode = models.CharField(max_length=20)
    delivery_instruction = models.TextField(blank=True)
    leave_at_door = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.house_flat}, {self.area}"


class Wallet(models.Model):
    user = models.OneToOneField(UserAccount, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} wallet"


class WalletTransaction(models.Model):
    CREDIT = "credit"
    DEBIT = "debit"
    TYPES = [(CREDIT, "Credit"), (DEBIT, "Debit")]

    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name="wallet_transactions")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TYPES)
    status = models.CharField(max_length=30, default="success")
    reason = models.CharField(max_length=120)
    reference = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Subscription(models.Model):
    FREQUENCIES = [
        ("daily", "Daily"),
        ("alternate_day", "Alternate day"),
        ("weekdays", "Weekdays"),
        ("custom", "Custom"),
    ]
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name="subscriptions")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    frequency = models.CharField(max_length=30, choices=FREQUENCIES, default="daily")
    delivery_time = models.CharField(max_length=20, default="7:00 AM")
    status = models.CharField(max_length=30, default="active")
    is_active = models.BooleanField(default=True)
    paused_until = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.product.name}"


class DeliveryOrder(models.Model):
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name="delivery_orders")
    delivery_date = models.DateField()
    status = models.CharField(max_length=30, default="ordered")
    is_locked = models.BooleanField(default=False)
    is_skipped = models.BooleanField(default=False)
    delivery_time = models.CharField(max_length=20, default="7:00 AM")
    wallet_debited = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "delivery_date")
        ordering = ["delivery_date"]


class DeliveryOrderItem(models.Model):
    order = models.ForeignKey(DeliveryOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, blank=True, null=True)
    quantity = models.PositiveIntegerField(default=1)
    is_extra = models.BooleanField(default=False)
    status = models.CharField(max_length=30, default="ordered")


class VacationPause(models.Model):
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name="vacations")
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SupportTicket(models.Model):
    ISSUE_TYPES = [
        ("missing_item", "Missing item"),
        ("late_delivery", "Late delivery"),
        ("payment_issue", "Payment issue"),
        ("quality_issue", "Quality issue"),
        ("other", "Other"),
    ]
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name="support_tickets")
    issue_type = models.CharField(max_length=40, choices=ISSUE_TYPES)
    message = models.TextField()
    status = models.CharField(max_length=30, default="open")
    ticket_id = models.CharField(max_length=30, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Referral(models.Model):
    user = models.OneToOneField(UserAccount, on_delete=models.CASCADE, related_name="referral")
    code = models.CharField(max_length=20, unique=True)
    reward_amount = models.DecimalField(max_digits=8, decimal_places=2, default=50)
    created_at = models.DateTimeField(auto_now_add=True)


class Notification(models.Model):
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=120)
    message = models.CharField(max_length=300)
    level = models.CharField(max_length=20, default="info")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
