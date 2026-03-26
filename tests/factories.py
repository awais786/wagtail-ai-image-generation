"""
factory_boy factories for tests.

UserFactory creates an inactive (no permissions) user.
StaffUserFactory adds is_staff=True and the wagtailimages.add_image permission.
SuperuserFactory creates a superuser that passes all permission checks.
"""
import factory
from django.contrib.auth.models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    is_active = True
    password = factory.PostGenerationMethodCall("set_password", "password")


class StaffUserFactory(UserFactory):
    """User with is_staff=True and the wagtailimages.add_image permission."""

    is_staff = True

    @factory.post_generation
    def add_image_permission(obj, create, extracted, **kwargs):
        if not create:
            return
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from wagtail.images import get_image_model

        Image = get_image_model()
        ct = ContentType.objects.get_for_model(Image)
        permission = Permission.objects.get(content_type=ct, codename="add_image")
        obj.user_permissions.add(permission)
        # Clear Django's permission cache so has_perm() picks up the new grant.
        if hasattr(obj, "_perm_cache"):
            del obj._perm_cache
        if hasattr(obj, "_user_perm_cache"):
            del obj._user_perm_cache


class StaffUserNoImagePermFactory(UserFactory):
    """User who can access the Wagtail admin but has no wagtailimages.add_image permission.

    In Wagtail 6.x, admin access requires the wagtailadmin.access_admin permission
    (or superuser).  This factory grants that permission but deliberately withholds
    add_image, so our view's permission check (not Wagtail's admin gate) denies access.
    """

    is_staff = True

    @factory.post_generation
    def add_admin_access(obj, create, extracted, **kwargs):
        if not create:
            return
        from django.contrib.auth.models import Permission

        try:
            perm = Permission.objects.get(codename="access_admin")
            obj.user_permissions.add(perm)
        except Permission.DoesNotExist:
            pass  # Wagtail version without this permission — tests will skip naturally


class SuperuserFactory(UserFactory):
    """Superuser — passes all Django permission checks without explicit grants."""

    is_staff = True
    is_superuser = True
