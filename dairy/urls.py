from django.urls import path
from . import views

urlpatterns = [
    path("products/", views.products),
    path("signup/", views.signup),
    path("login/", views.login),
]

profile_urlpatterns = [
    path("", views.profile_detail),
    path("update/", views.update_profile),
    path("photo/", views.upload_profile_photo),
    path("addresses/", views.address_list),
    path("addresses/add/", views.add_address),
    path("addresses/<int:address_id>/update/", views.update_address),
    path("addresses/<int:address_id>/delete/", views.delete_address),
    path("addresses/<int:address_id>/default/", views.set_default_address),
]

dashboard_urlpatterns = [
    path("", views.dashboard),
    path("wallet/recharge/", views.recharge_wallet),
    path("wallet/transactions/", views.wallet_transactions),
    path("deliveries/<str:delivery_date>/", views.delivery_detail),
    path("deliveries/<str:delivery_date>/skip/", views.skip_delivery),
    path("deliveries/<str:delivery_date>/resume/", views.resume_delivery),
    path("deliveries/<str:delivery_date>/extra/", views.add_extra_item),
    path("delivery-items/<int:item_id>/quantity/", views.modify_delivery_item),
    path("subscriptions/create/", views.create_subscription),
    path("subscriptions/<int:subscription_id>/edit/", views.edit_subscription),
    path("subscriptions/<int:subscription_id>/pause/", views.pause_subscription),
    path("subscriptions/<int:subscription_id>/resume/", views.resume_subscription_view),
    path("vacation/", views.vacation_mode),
    path("support/", views.submit_support_ticket),
    path("referral/", views.referral_detail),
]
