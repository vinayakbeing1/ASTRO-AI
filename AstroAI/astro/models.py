from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid
from django.contrib.auth import get_user_model

User = get_user_model()


class UserProfile(models.Model):
    """Stores astrology-related user metadata linked to Django's User."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    date_of_birth = models.DateField(null=True, blank=True)
    time_of_birth = models.TimeField(null=True, blank=True)
    location_name = models.CharField(max_length=255, blank=True)

    # Optional: store raw latitude/longitude/timezone if needed later
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    timezone = models.FloatField(
        null=True,
        blank=True,
        help_text="Offset from UTC in hours, e.g. 5.5 for IST",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        # Use a safe representation regardless of custom user model fields
        username = getattr(self.user, "get_username", None)
        if callable(username):
            uname = username()
        else:
            uname = getattr(self.user, "username", str(self.user))
        return f"Profile({uname})"

    def get_birthdata(self) -> dict:
        """Return structured birthdata for astrology calculations."""
        return {
            "name": self.user.get_full_name(),
            "DOB": {
                "year": self.date_of_birth.year,
                "month": self.date_of_birth.month,
                "day": self.date_of_birth.day,
            },
            "TOB": {
                "hour": self.time_of_birth.hour,
                "min": self.time_of_birth.minute,
                "sec": self.time_of_birth.second,
            },
            "POB": {
                "name": self.location_name,
                "lat": self.latitude,
                "lon": self.longitude,
                "timezone": self.timezone,
            },
        }


class TimelineAntardashas(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="timeline_antardashas",
    )
    antardashas = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class Remedies(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="remedies",
    )
    diagnosis = models.JSONField()
    plan = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


@receiver(post_save, sender=UserProfile)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Ensure a profile exists for each user and keep it saved."""

    if created and not instance.user.is_superuser:
        # Import here to avoid circular dependency
        from astro.services.astrology import get_planet_positions

        birthdata = instance.get_birthdata()
        charts = get_planet_positions(birthdata)

        # ProfileCharts.objects.update_or_create(
        #     user=instance.user,
        #     defaults={
        #         "shadbala": charts.pop("shadbala"),
        #         "ashtaka_varga": charts.pop("ashtaka_varga")["ashtakavarga"][
        #             "sarvashtakavarga"
        #         ],
        #         "vimsottari_dhasa": charts.pop("vimsottari_dhasa"),
        #         "charts": charts,
        #     },
        # )
        # from astro.services.graphs.profile_graph import run_profile_graph

        # result = run_profile_graph(instance.user, today_only=False)

        # if result:
        #     HomePage.objects.update_or_create(
        #         user=instance.user,
        #         defaults={
        #             "today_for_you": result.get("today_for_you", ""),
        #             "career_money": result["sections"].get("career_money", ""),
        #             "relationships_love": result["sections"].get(
        #                 "relationships_love", ""
        #             ),
        #             "health_energy": result["sections"].get("health_energy", ""),
        #             "spiritual": result["sections"].get("spiritual", ""),
        #         },
        #     )

        from astro.services.graphs.timeline_graph import run_timeline_graph
        from astro.services.graphs.remedies_graph import run_remedies_graph

        # result = run_timeline_graph(user=instance.user)
        # print(result)

        # TimelineAntardashas.objects.update_or_create(
        #     user=instance.user,
        #     defaults={
        #         "antardashas": result["timeline"]["antardashas"],
        #     },
        # )

        timeline_result = run_remedies_graph(user=instance.user)

        Remedies.objects.update_or_create(
            user=instance.user,
            defaults={
                "diagnosis": timeline_result.get("diagnosis", {}),
                "plan": timeline_result.get("plan", {}),
            },
        )


class ProfileCharts(models.Model):
    """Stores astrology charts data linked to Django's User."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="charts",
    )
    shadbala = models.JSONField(null=True, blank=True)
    ashtaka_varga = models.JSONField(null=True, blank=True)
    vimsottari_dhasa = models.JSONField(null=True, blank=True)
    charts = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        # Use a safe representation regardless of custom user model fields
        username = getattr(self.user, "get_username", None)
        if callable(username):
            uname = username()
        else:
            uname = getattr(self.user, "username", str(self.user))
        return f"Charts({uname})"


class AstroClient(models.Model):
    name = models.CharField(max_length=100, blank=True)
    dob = models.DateField()
    birth_time = models.TimeField()
    birthplace = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    timezone = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or f"Client {self.id}"


class HomePage(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="homepage",
    )
    today_for_you = models.TextField()
    career_money = models.JSONField()
    relationships_love = models.JSONField()
    health_energy = models.JSONField()
    spiritual = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PromptTemplate(models.Model):
    """Stores prompt templates for LLM interactions."""

    name = models.CharField(max_length=100, unique=True)
    system_message = models.TextField()
    user_message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class LLMLog(models.Model):
    """Stores logs of LLM interactions for auditing and debugging."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="llm_logs",
        null=True,
        blank=True,
    )
    run_id = models.UUIDField(unique=True)
    prompt = models.JSONField()
    response = models.TextField()
    chain_type = models.CharField(max_length=100)
    duration = models.FloatField(help_text="Duration in seconds")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        user_str = self.user.get_username() if self.user else "Anonymous"
        return f"LLMLog({user_str}, {self.created_at})"


class ChatSession(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="chat_session"
    )
    # Stored as UUID in the DB and guaranteed unique
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"ChatSession(user={self.user.id}, session_id={self.session_id})"
