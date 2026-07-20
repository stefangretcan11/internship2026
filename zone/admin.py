from django.contrib import admin
from .models import Zone

@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "neighborhood",
        "color",
        "display_agents",
    )

    search_fields = (
        "name",
        "neighborhood",
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'agents' in form.base_fields:
            form.base_fields['agents'].label_from_instance = lambda agent_obj: f"{agent_obj.id}"
        return form

    @admin.display(description="Agents")
    def display_agents(self, obj):
        return obj.agent_ids_str
