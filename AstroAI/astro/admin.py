from django.contrib import admin
from .models import (
    AstroClient,
    UserProfile,
    ProfileCharts,
    HomePage,
    PromptTemplate,
    LLMLog,
    TimelineAntardashas,
    Remedies,
)
from django_json_widget.widgets import JSONEditorWidget
from django.db.models import JSONField


@admin.register(AstroClient)
class AstroClientAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "dob",
        "birth_time",
        "birthplace",
        "latitude",
        "longitude",
        "timezone",
        "created_at",
    )
    search_fields = ("name", "birthplace")


class ProfileChartsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "shadbala",
        "ashtaka_varga",
        "vimsottari_dhasa",
        "updated_at",
    )
    search_fields = ("user__username",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "date_of_birth",
        "time_of_birth",
        "location_name",
        "created_at",
        "updated_at",
    )
    search_fields = ("user__username", "location_name")


@admin.register(ProfileCharts)
class ProfileChartsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "shadbala",
        "ashtaka_varga",
        "vimsottari_dhasa",
        "updated_at",
    )
    search_fields = ("user__username",)


@admin.register(HomePage)
class HomePageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "today_for_you",
        "career_money",
        "relationships_love",
        "health_energy",
        "spiritual",
        "created_at",
        "updated_at",
    )
    search_fields = ("user__username",)


@admin.register(PromptTemplate)
class PromptTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "system_message",
        "user_message",
        "created_at",
        "updated_at",
    )
    search_fields = ("name", "system_message", "user_message")


@admin.register(TimelineAntardashas)
class TimelineAntardashasAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "created_at",
    )
    search_fields = ("user__username",)
    readonly_fields = ("antardashas",)


@admin.register(LLMLog)
class LLMLogAdmin(admin.ModelAdmin):
    list_display = ("run_id", "chain_type", "user", "duration")
    search_fields = ("run_id", "user__username")
    readonly_fields = ("prompt", "response", "created_at", "duration")

    formfield_overrides = {
        JSONField: {"widget": JSONEditorWidget},
    }


@admin.register(Remedies)
class RemediesAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "diagnosis",
        "plan",
        "created_at",
    )
    search_fields = ("user__username",)
