from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import (
    Address,
    DeliveryOrder,
    DeliveryOrderItem,
    Notification,
    Product,
    Referral,
    Subscription,
    SupportTicket,
    VacationPause,
    Wallet,
    WalletTransaction,
)
from .serializers import (
    AddressSerializer,
    DashboardProductSerializer,
    DeliveryOrderSerializer,
    LoginSerializer,
    NotificationSerializer,
    ProfileUpdateSerializer,
    ReferralSerializer,
    SignupSerializer,
    SubscriptionSerializer,
    SupportTicketSerializer,
    UserProfileSerializer,
    VacationPauseSerializer,
    WalletTransactionSerializer,
    build_auth_payload,
)


CATALOG = [
    {"name": "Full Cream Milk", "variant": "500ml", "price": 35, "image": "full-cream-milk-500.jpg", "category": "milk"},
    {"name": "Full Cream Milk", "variant": "1L", "price": 65, "image": "full-cream-milk-1L.jpg", "category": "milk"},
    {"name": "Toned Milk", "variant": "500ml", "price": 30, "image": "toned-milk-500.jpg", "category": "milk"},
    {"name": "White Butter", "variant": "100g", "price": 55, "image": "white-butter-100.jpg", "category": "butter"},
    {"name": "Salted Butter", "variant": "100g", "price": 50, "image": "salted-butter-100.jpg", "category": "butter"},
    {"name": "Pure Ghee", "variant": "200ml", "price": 160, "image": "pure-ghee-200.jpg", "category": "butter"},
    {"name": "Cheese Slice", "variant": "200g", "price": 120, "image": "cheese-slice.jpg", "category": "cheese"},
    {"name": "Cheese Spread", "variant": "200g", "price": 130, "image": "cheese-spread.jpg", "category": "cheese"},
    {"name": "Fresh Curd", "variant": "400g", "price": 45, "image": "fresh-curd-400.jpg", "category": "curd"},
    {"name": "Paneer", "variant": "200g", "price": 95, "image": "paneer-200.jpg", "category": "curd"},
    {"name": "Sweet Lassi", "variant": "200ml", "price": 35, "image": "sweet-lassi.jpg", "category": "traditional"},
    {"name": "Masala Chaas", "variant": "200ml", "price": 30, "image": "masala-chaas.jpg", "category": "traditional"},
    {"name": "Shrikhand", "variant": "250g", "price": 90, "image": "shrikhand.jpg", "category": "traditional"},
]


def ensure_catalog():
    for item in CATALOG:
        Product.objects.get_or_create(
            name=item["name"],
            variant=item["variant"],
            defaults={**item, "inStock": True},
        )


def products(request):
    ensure_catalog()
    data = DashboardProductSerializer(Product.objects.filter(inStock=True).order_by("id"), many=True).data
    return JsonResponse(data, safe=False)


def cutoff_datetime(for_date=None):
    base = for_date or timezone.localdate()
    return timezone.make_aware(datetime.combine(base, time(hour=21)))


def is_tomorrow_locked():
    return timezone.now() >= cutoff_datetime()


def ensure_user_state(user):
    ensure_catalog()
    Wallet.objects.get_or_create(user=user)
    Referral.objects.get_or_create(user=user, defaults={"code": f"SR{user.id}{uuid4().hex[:5].upper()}"})
    milk = Product.objects.filter(category="milk").order_by("price").first()
    curd = Product.objects.filter(name__icontains="Curd").first()
    if milk and not user.subscriptions.exists():
        Subscription.objects.create(user=user, product=milk, quantity=1, frequency="daily")
        if curd:
            Subscription.objects.create(user=user, product=curd, quantity=1, frequency="weekdays")
    for offset in range(14):
        build_delivery_order(user, timezone.localdate() + timedelta(days=offset))


def subscription_runs_on(subscription, delivery_date):
    if not subscription.is_active or subscription.status != "active":
        return False
    if subscription.paused_until and delivery_date <= subscription.paused_until:
        return False
    if subscription.frequency == "weekdays" and delivery_date.weekday() > 4:
        return False
    if subscription.frequency == "alternate_day":
        return (delivery_date - subscription.created_at.date()).days % 2 == 0
    return True


def build_delivery_order(user, delivery_date):
    vacation = user.vacations.filter(is_active=True, start_date__lte=delivery_date, end_date__gte=delivery_date).exists()
    order, _ = DeliveryOrder.objects.get_or_create(
        user=user,
        delivery_date=delivery_date,
        defaults={"status": "skipped" if vacation else "ordered", "is_skipped": vacation},
    )
    if delivery_date == timezone.localdate() + timedelta(days=1):
        order.is_locked = is_tomorrow_locked()
    if vacation:
        order.status = "skipped"
        order.is_skipped = True
        order.save()
        return order
    if order.items.exists():
        return order
    for subscription in user.subscriptions.select_related("product"):
        if subscription_runs_on(subscription, delivery_date):
            DeliveryOrderItem.objects.create(
                order=order,
                product=subscription.product,
                subscription=subscription,
                quantity=subscription.quantity,
            )
    if not order.items.exists():
        order.status = "skipped"
        order.is_skipped = True
        order.save()
    return order


def notify(user, title, message, level="info"):
    return Notification.objects.create(user=user, title=title, message=message, level=level)


def serialize_dashboard(request):
    user = request.user
    ensure_user_state(user)
    today = timezone.localdate()
    orders = [build_delivery_order(user, today + timedelta(days=i)) for i in range(14)]
    wallet = user.wallet
    default_address = user.addresses.filter(is_default=True).first()
    active_vacation = user.vacations.filter(is_active=True, end_date__gte=today).order_by("start_date").first()
    next_delivery = next((order for order in orders if not order.is_skipped and order.items.exists()), None)
    return {
        "profile": UserProfileSerializer(user, context={"request": request}).data,
        "wallet": {"balance": wallet.balance, "low_balance": wallet.balance < Decimal("150.00")},
        "cutoff": {"time": "21:00:00", "tomorrow_locked": is_tomorrow_locked(), "message": "Tomorrow order locked" if is_tomorrow_locked() else ""},
        "default_address": AddressSerializer(default_address).data if default_address else None,
        "products": DashboardProductSerializer(Product.objects.filter(inStock=True).order_by("id"), many=True).data,
        "subscriptions": SubscriptionSerializer(user.subscriptions.select_related("product").order_by("-is_active", "id"), many=True).data,
        "calendar": DeliveryOrderSerializer(orders, many=True).data,
        "selected_delivery": DeliveryOrderSerializer(orders[0]).data,
        "tomorrow_delivery": DeliveryOrderSerializer(orders[1]).data,
        "next_delivery": DeliveryOrderSerializer(next_delivery).data if next_delivery else None,
        "vacation": VacationPauseSerializer(active_vacation).data if active_vacation else None,
        "referral": ReferralSerializer(user.referral).data,
        "notifications": NotificationSerializer(user.notifications.all()[:8], many=True).data,
    }


@api_view(["POST"])
@permission_classes([AllowAny])
def signup(request):
    serializer = SignupSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    user = serializer.save()
    return Response(
        {"message": "Signup successful", **build_auth_payload(user, request)},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data, context={"request": request})
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    return Response(
        {"message": "Login success", **build_auth_payload(serializer.validated_data["user"], request)}
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def profile_detail(request):
    return Response(UserProfileSerializer(request.user, context={"request": request}).data)


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def update_profile(request):
    serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    user = serializer.save()
    return Response(UserProfileSerializer(user, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_profile_photo(request):
    user = request.user

    image = request.FILES.get("profile_image")
    if not image:
        return Response({"error": "Profile image required"}, status=status.HTTP_400_BAD_REQUEST)

    user.profile_image = image
    user.save()
    return Response(UserProfileSerializer(user, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def address_list(request):
    addresses = request.user.addresses.order_by("-is_default", "-updated_at")
    return Response(AddressSerializer(addresses, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_address(request):
    user = request.user
    serializer = AddressSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    address = serializer.save(user=user)
    if address.is_default or not user.addresses.exclude(id=address.id).exists():
        user.addresses.exclude(id=address.id).update(is_default=False)
        address.is_default = True
        address.save()
    return Response(AddressSerializer(address).data, status=status.HTTP_201_CREATED)


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_address(request, address_id):
    user = request.user
    try:
        address = user.addresses.get(id=address_id)
    except Address.DoesNotExist:
        return Response({"error": "Address not found"}, status=status.HTTP_404_NOT_FOUND)
    serializer = AddressSerializer(address, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    address = serializer.save()
    if address.is_default:
        user.addresses.exclude(id=address.id).update(is_default=False)
    return Response(AddressSerializer(address).data)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_address(request, address_id):
    user = request.user
    try:
        address = user.addresses.get(id=address_id)
    except Address.DoesNotExist:
        return Response({"error": "Address not found"}, status=status.HTTP_404_NOT_FOUND)
    was_default = address.is_default
    address.delete()
    if was_default:
        next_address = user.addresses.order_by("-updated_at").first()
        if next_address:
            next_address.is_default = True
            next_address.save()
    return Response({"message": "Address deleted"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_default_address(request, address_id):
    user = request.user
    try:
        address = user.addresses.get(id=address_id)
    except Address.DoesNotExist:
        return Response({"error": "Address not found"}, status=status.HTTP_404_NOT_FOUND)
    user.addresses.exclude(id=address.id).update(is_default=False)
    address.is_default = True
    address.save()
    return Response(AddressSerializer(address).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard(request):
    return Response(serialize_dashboard(request))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def wallet_transactions(request):
    return Response(WalletTransactionSerializer(request.user.wallet_transactions.all()[:30], many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def recharge_wallet(request):
    amount = Decimal(str(request.data.get("amount", "0")))
    if amount not in [Decimal("100"), Decimal("200"), Decimal("500")]:
        return Response({"error": "Choose a valid recharge amount."}, status=status.HTTP_400_BAD_REQUEST)
    with transaction.atomic():
        wallet, _ = Wallet.objects.select_for_update().get_or_create(user=request.user)
        wallet.balance += amount
        wallet.save()
        tx = WalletTransaction.objects.create(
            user=request.user,
            amount=amount,
            transaction_type=WalletTransaction.CREDIT,
            reason="Wallet recharge",
            reference=f"PAY-{uuid4().hex[:10].upper()}",
        )
        notify(request.user, "Wallet recharged", f"Rs {amount} added to your SR Wallet.", "success")
    return Response({"wallet": {"balance": wallet.balance}, "transaction": WalletTransactionSerializer(tx).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def delivery_detail(request, delivery_date):
    order = build_delivery_order(request.user, date.fromisoformat(delivery_date))
    return Response(DeliveryOrderSerializer(order).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def modify_delivery_item(request, item_id):
    quantity = int(request.data.get("quantity", 0))
    if quantity < 0:
        return Response({"error": "Quantity cannot be negative."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        item = DeliveryOrderItem.objects.select_related("order").get(id=item_id, order__user=request.user)
    except DeliveryOrderItem.DoesNotExist:
        return Response({"error": "Delivery item not found."}, status=status.HTTP_404_NOT_FOUND)
    if item.order.is_locked:
        return Response({"error": "Tomorrow order locked."}, status=status.HTTP_400_BAD_REQUEST)
    if quantity == 0:
        item.delete()
    else:
        item.quantity = quantity
        item.status = "modified"
        item.save()
    item.order.status = "modified"
    item.order.save()
    notify(request.user, "Delivery updated", "Your delivery quantity was updated.", "success")
    return Response(DeliveryOrderSerializer(item.order).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def skip_delivery(request, delivery_date):
    order = build_delivery_order(request.user, date.fromisoformat(delivery_date))
    if order.is_locked:
        return Response({"error": "Tomorrow order locked."}, status=status.HTTP_400_BAD_REQUEST)
    order.is_skipped = True
    order.status = "skipped"
    order.save()
    order.items.update(status="skipped")
    notify(request.user, "Delivery skipped", f"Delivery skipped for {delivery_date}.", "warning")
    return Response(DeliveryOrderSerializer(order).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resume_delivery(request, delivery_date):
    order = build_delivery_order(request.user, date.fromisoformat(delivery_date))
    order.is_skipped = False
    order.status = "ordered"
    order.items.update(status="ordered")
    order.save()
    notify(request.user, "Delivery resumed", f"Delivery resumed for {delivery_date}.", "success")
    return Response(DeliveryOrderSerializer(order).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_extra_item(request, delivery_date):
    if is_tomorrow_locked() and date.fromisoformat(delivery_date) == timezone.localdate() + timedelta(days=1):
        return Response({"error": "Tomorrow order locked."}, status=status.HTTP_400_BAD_REQUEST)
    product_id = request.data.get("product_id")
    quantity = int(request.data.get("quantity", 1))
    if quantity < 1:
        return Response({"error": "Quantity must be at least 1."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        product = Product.objects.get(id=product_id, inStock=True)
    except Product.DoesNotExist:
        return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)
    order = build_delivery_order(request.user, date.fromisoformat(delivery_date))
    order.is_skipped = False
    order.status = "modified"
    order.save()
    item, created = DeliveryOrderItem.objects.get_or_create(order=order, product=product, is_extra=True, defaults={"quantity": quantity})
    if not created:
        item.quantity += quantity
        item.save()
    notify(request.user, "Extra item added", f"{product.name} added to your delivery.", "success")
    return Response(DeliveryOrderSerializer(order).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_subscription(request):
    serializer = SubscriptionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    subscription = serializer.save(user=request.user, status="active", is_active=True)
    notify(request.user, "Subscription created", f"{subscription.product.name} added to your daily plan.", "success")
    return Response(SubscriptionSerializer(subscription).data, status=status.HTTP_201_CREATED)


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def edit_subscription(request, subscription_id):
    try:
        subscription = request.user.subscriptions.get(id=subscription_id)
    except Subscription.DoesNotExist:
        return Response({"error": "Subscription not found."}, status=status.HTTP_404_NOT_FOUND)
    serializer = SubscriptionSerializer(subscription, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    subscription = serializer.save()
    notify(request.user, "Subscription updated", f"{subscription.product.name} plan updated.", "success")
    return Response(SubscriptionSerializer(subscription).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def pause_subscription(request, subscription_id):
    try:
        subscription = request.user.subscriptions.get(id=subscription_id)
    except Subscription.DoesNotExist:
        return Response({"error": "Subscription not found."}, status=status.HTTP_404_NOT_FOUND)
    until = request.data.get("paused_until")
    subscription.status = "paused"
    subscription.is_active = False
    subscription.paused_until = date.fromisoformat(until) if until else timezone.localdate() + timedelta(days=1)
    subscription.save()
    return Response(SubscriptionSerializer(subscription).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resume_subscription_view(request, subscription_id):
    try:
        subscription = request.user.subscriptions.get(id=subscription_id)
    except Subscription.DoesNotExist:
        return Response({"error": "Subscription not found."}, status=status.HTTP_404_NOT_FOUND)
    subscription.status = "active"
    subscription.is_active = True
    subscription.paused_until = None
    subscription.save()
    return Response(SubscriptionSerializer(subscription).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def vacation_mode(request):
    start_date = request.data.get("start_date")
    end_date = request.data.get("end_date")
    enabled = bool(request.data.get("enabled", True))
    request.user.vacations.filter(is_active=True).update(is_active=False)
    vacation = None
    if enabled:
        if not start_date or not end_date:
            return Response({"error": "Start and end dates are required."}, status=status.HTTP_400_BAD_REQUEST)
        vacation = VacationPause.objects.create(user=request.user, start_date=start_date, end_date=end_date, is_active=True)
        notify(request.user, "Vacation mode enabled", "Deliveries will be skipped for your selected dates.", "success")
    else:
        notify(request.user, "Vacation mode disabled", "Your regular deliveries are active.", "info")
    return Response({"vacation": VacationPauseSerializer(vacation).data if vacation else None})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_support_ticket(request):
    serializer = SupportTicketSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    ticket = serializer.save(user=request.user, ticket_id=f"SR-{uuid4().hex[:8].upper()}")
    notify(request.user, "Support ticket created", f"Ticket {ticket.ticket_id} is open.", "success")
    return Response(SupportTicketSerializer(ticket).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def referral_detail(request):
    ensure_user_state(request.user)
    return Response(ReferralSerializer(request.user.referral).data)
