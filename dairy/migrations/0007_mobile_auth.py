from django.db import migrations, models
import django.db.models.deletion


def migrate_phone_to_mobile(apps, schema_editor):
    UserAccount = apps.get_model("dairy", "UserAccount")
    for user in UserAccount.objects.all():
        if not getattr(user, "mobile_number", None):
            user.mobile_number = getattr(user, "phone", "") or f"legacy-{user.id}"
            user.save(update_fields=["mobile_number"])


def clear_old_otps(apps, schema_editor):
    OTPVerification = apps.get_model("dairy", "OTPVerification")
    OTPVerification.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("dairy", "0006_useraccount_profile_image_address"),
    ]

    operations = [
        migrations.AddField(
            model_name="useraccount",
            name="mobile_number",
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
        migrations.RunPython(migrate_phone_to_mobile, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="useraccount",
            name="password",
        ),
        migrations.RemoveField(
            model_name="useraccount",
            name="phone",
        ),
        migrations.RenameField(
            model_name="useraccount",
            old_name="is_verified",
            new_name="is_mobile_verified",
        ),
        migrations.AlterField(
            model_name="useraccount",
            name="email",
            field=models.EmailField(blank=True, max_length=254, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="useraccount",
            name="mobile_number",
            field=models.CharField(max_length=20, unique=True),
        ),
        migrations.AlterField(
            model_name="useraccount",
            name="name",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.RunPython(clear_old_otps, migrations.RunPython.noop),
        migrations.AddField(
            model_name="otpverification",
            name="mobile_number",
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
        migrations.RemoveField(
            model_name="otpverification",
            name="email",
        ),
        migrations.AddField(
            model_name="otpverification",
            name="expires_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="otpverification",
            name="last_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="otpverification",
            name="send_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="otpverification",
            name="mobile_number",
            field=models.CharField(max_length=20, unique=True),
        ),
        migrations.AlterField(
            model_name="otpverification",
            name="expires_at",
            field=models.DateTimeField(),
        ),
    ]
