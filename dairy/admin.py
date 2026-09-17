
from django.contrib import admin

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
    Wallet,
    WalletTransaction,
)


class DeliveryOrderItemInline(admin.TabularInline):
    model = DeliveryOrderItem
    extra = 0


@admin.register(DeliveryOrder)
class DeliveryOrderAdmin(admin.ModelAdmin):
    list_display = ("user", "delivery_date", "status", "is_locked", "is_skipped", "wallet_debited")
    list_filter = ("status", "is_locked", "is_skipped", "delivery_date")
    search_fields = ("user__email", "user__name")
    inlines = [DeliveryOrderItemInline]


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "transaction_type", "status", "reason", "created_at")
    list_filter = ("transaction_type", "status", "created_at")
    search_fields = ("user__email", "reference", "reason")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "quantity", "frequency", "status", "is_active", "delivery_time")
    list_filter = ("frequency", "status", "is_active")
    search_fields = ("user__email", "product__name")


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("ticket_id", "user", "issue_type", "status", "created_at")
    list_filter = ("issue_type", "status", "created_at")
    search_fields = ("ticket_id", "user__email", "message")


admin.site.register(Product)
admin.site.register(UserAccount)
admin.site.register(Address)
admin.site.register(Wallet)
admin.site.register(VacationPause)
admin.site.register(Referral)
admin.site.register(Notification)
