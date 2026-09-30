from django.contrib import admin

from .models import AiCache, AuditEvent, Client, Doubt, Layer, Pin, Source, SourceVersion, Team, Topic, User


def admin_permission(request):
    return request.user.is_active and request.user.is_staff and request.user.role == "ADMIN"


admin.site.has_permission = admin_permission
admin.site.site_header = "Bron administration"


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# Domain mutations go through audited services, not generic admin forms.
for model in [Team, User, Layer, Client, Topic, Source, SourceVersion, Pin, Doubt, AuditEvent, AiCache]:
    admin.site.register(model, ReadOnlyAdmin)
