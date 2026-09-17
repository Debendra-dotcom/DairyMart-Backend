from django.contrib.auth.hashers import make_password
from django.db import migrations, models


def prepare_existing_users(apps, schema_editor):
    UserAccount = apps.get_model("dairy", "UserAccount")
    for user in UserAccount.objects.all():
        changed_fields = []

        if not user.email:
            user.email = f"legacy-{user.id}@sr-dairy.local"
            changed_fields.append("email")
        else:
            user.email = user.email.strip().lower()
            changed_fields.append("email")

        if not user.name:
            user.name = getattr(user, "phone", "") or "SR Dairy Customer"
            changed_fields.append("name")

        if not user.phone:
            user.phone = f"legacy-{user.id}"
            changed_fields.append("phone")

        if not user.password:
            user.password = make_password(None)
            changed_fields.append("password")

        user.save(update_fields=list(set(changed_fields)))


class Migration(migrations.Migration):

    dependencies = [
        ("dairy", "0007_mobile_auth"),
    ]

    operations = [
        migrations.AddField(
            model_name="useraccount",
            name="password",
            field=models.CharField(default="", max_length=128, verbose_name="password"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="useraccount",
            name="last_login",
            field=models.DateTimeField(blank=True, null=True, verbose_name="last login"),
        ),
        migrations.AddField(
            model_name="useraccount",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="useraccount",
            name="is_staff",
            field=models.BooleanField(default=False),
        ),
        migrations.RenameField(
            model_name="useraccount",
            old_name="mobile_number",
            new_name="phone",
        ),
        migrations.RunPython(prepare_existing_users, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="useraccount",
            name="email",
            field=models.EmailField(max_length=254, unique=True),
        ),
        migrations.AlterField(
            model_name="useraccount",
            name="name",
            field=models.CharField(max_length=200),
        ),
        migrations.AlterField(
            model_name="useraccount",
            name="phone",
            field=models.CharField(max_length=20),
        ),
        migrations.RemoveField(
            model_name="useraccount",
            name="is_mobile_verified",
        ),
        migrations.DeleteModel(
            name="OTPVerification",
        ),
    ]
