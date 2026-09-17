import socket

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email as django_validate_email
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    Address,
    DeliveryOrder,
    DeliveryOrderItem,
    Notification,
    Product,
    Referral,
    Subscription,
    SupportTicket,
    UserAccount,
    VacationPause,
    WalletTransaction,
)

BLOCKED_EMAIL_DOMAINS = {
    "example.com",
    "example.in",
    "test.com",
    "invalid.com",
    "fake.com",
    "localhost",
    "mailinator.com",
    "10minutemail.com",
    "tempmail.com",
    "yopmail.com",
}


def normalize_and_validate_real_email(value):
    email = value.strip().lower()
    if not email:
        raise serializers.ValidationError("Email is required.")
    try:
        django_validate_email(email)
    except DjangoValidationError:
        raise serializers.ValidationError("Enter a valid email address.")

    local_part, domain = email.rsplit("@", 1)
    if ".." in email or local_part.startswith(".") or local_part.endswith("."):
        raise serializers.ValidationError("Enter a valid email address.")
    if domain in BLOCKED_EMAIL_DOMAINS or domain.endswith(".test") or domain.endswith(".invalid") or domain.endswith(".local"):
        raise serializers.ValidationError("Use a real email provider domain.")

    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(3)
    try:
        socket.getaddrinfo(domain, None)
    except socket.gaierror:
        raise serializers.ValidationError("Email domain does not exist.")
    finally:
        socket.setdefaulttimeout(previous_timeout)

    return email


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = UserAccount
        fields = ["name", "email", "phone", "password"]

    def validate_email(self, value):
        email = normalize_and_validate_real_email(value)
        if UserAccount.objects.filter(email=email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email

    def validate_phone(self, value):
        phone = value.strip()
        if not phone:
            raise serializers.ValidationError("Phone is required.")
        return phone

    def create(self, validated_data):
        return UserAccount.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = normalize_and_validate_real_email(attrs["email"])
        user = authenticate(
            request=self.context.get("request"),
            email=email,
            password=attrs["password"],
        )
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        attrs["user"] = user
        return attrs


class AuthTokenSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    profile = serializers.DictField()


class UserProfileSerializer(serializers.ModelSerializer):
    profile_image = serializers.SerializerMethodField()
    mobile_number = serializers.CharField(source="phone", read_only=True)
    is_mobile_verified = serializers.SerializerMethodField()
    is_verified = serializers.SerializerMethodField()

    class Meta:
        model = UserAccount
        fields = [
            "id",
            "name",
            "mobile_number",
            "phone",
            "email",
            "profile_image",
            "is_mobile_verified",
            "is_verified",
            "created_at",
        ]

    def get_profile_image(self, obj):
        if not obj.profile_image:
            return None

        request = self.context.get("request")
        url = obj.profile_image.url
        return request.build_absolute_uri(url) if request else url

    def get_is_mobile_verified(self, obj):
        return False

    def get_is_verified(self, obj):
        return False


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAccount
        fields = ["name", "phone", "profile_image"]

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Name is required.")
        return name

    def validate_phone(self, value):
        phone = value.strip()
        if not phone:
            raise serializers.ValidationError("Phone is required.")
        return phone


def build_auth_payload(user, request=None):
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "profile": UserProfileSerializer(user, context={"request": request}).data,
    }


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            "id",
            "house_flat",
            "area",
            "landmark",
            "city",
            "pincode",
            "delivery_instruction",
            "leave_at_door",
            "is_default",
            "created_at",
            "updated_at",
        ]


class DashboardProductSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "variant", "price", "category", "image", "inStock"]


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = ["id", "amount", "transaction_type", "status", "reason", "reference", "created_at"]


class SubscriptionSerializer(serializers.ModelSerializer):
    product = DashboardProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), source="product", write_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "product",
            "product_id",
            "quantity",
            "frequency",
            "delivery_time",
            "status",
            "is_active",
            "paused_until",
            "created_at",
        ]


class DeliveryOrderItemSerializer(serializers.ModelSerializer):
    product = DashboardProductSerializer(read_only=True)

    class Meta:
        model = DeliveryOrderItem
        fields = ["id", "product", "subscription", "quantity", "is_extra", "status"]


class DeliveryOrderSerializer(serializers.ModelSerializer):
    items = DeliveryOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = DeliveryOrder
        fields = [
            "id",
            "delivery_date",
            "status",
            "is_locked",
            "is_skipped",
            "delivery_time",
            "wallet_debited",
            "items",
        ]


class VacationPauseSerializer(serializers.ModelSerializer):
    class Meta:
        model = VacationPause
        fields = ["id", "start_date", "end_date", "is_active", "created_at"]


class SupportTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ["id", "ticket_id", "issue_type", "message", "status", "created_at"]
        read_only_fields = ["ticket_id", "status", "created_at"]


class ReferralSerializer(serializers.ModelSerializer):
    class Meta:
        model = Referral
        fields = ["code", "reward_amount", "created_at"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "message", "level", "is_read", "created_at"]
