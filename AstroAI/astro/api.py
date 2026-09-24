"""
AstroAI REST API

This module provides the Django Ninja API endpoints for the AstroAI
including user authentication, profile management, and astrology data access.
"""

from datetime import date


from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import update_last_login
from django.db import transaction
from ninja import NinjaAPI

from utils.select_dasha import find_current_and_next

from .models import HomePage, UserProfile, TimelineAntardashas, Remedies
from .schemas import (
    AuthOut,
    HomePageSchema,
    LoginIn,
    ProfileOut,
    RegisterIn,
    TimelineSchema,
    RemediesSchema,
)
from .security import auth, issue_jwt

User = get_user_model()

api = NinjaAPI(title="AstroAI API", version="1.0.0")


@api.post("/auth/register", response={201: AuthOut, 400: dict})
@transaction.atomic
def register(request, payload: RegisterIn):
    if not payload.email or not payload.password:
        return 400, {"error": "email and password are required"}
    if User.objects.filter(email__iexact=payload.email).exists():
        return 400, {"error": "email already registered"}

    user = User.objects.create_user(
        username=payload.email,  # if default user requires username
        email=payload.email,
        password=payload.password,
    )
    # Ensure profile exists then update
    UserProfile.objects.get_or_create(
        user=user,
        defaults={
            "date_of_birth": payload.date_of_birth,
            "time_of_birth": payload.time_of_birth,
            "location_name": payload.location_name,
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "timezone": payload.timezone,
        },
    )

    token = issue_jwt(user)
    return 201, AuthOut(token=token, user_id=user.id, email=user.email)


@api.post("/auth/login", response={200: AuthOut, 401: dict})
def login(request, payload: LoginIn):
    # authenticate defaults to username; try email as username
    user = authenticate(
        request,
        username=payload.email,
        password=payload.password,
    )
    if not user and hasattr(User, "USERNAME_FIELD") and User.USERNAME_FIELD == "email":
        user = authenticate(
            request,
            email=payload.email,
            password=payload.password,
        )
    if not user:
        return 401, {"error": "invalid credentials"}

    update_last_login(None, user)
    token = issue_jwt(user)
    return AuthOut(token=token, user_id=user.id, email=user.email)


@api.get("/auth/me", auth=auth, response={200: ProfileOut})
def me(request):
    user = request.auth
    profile = getattr(user, "profile", None)
    return ProfileOut(
        id=user.id,
        email=user.email,
        date_of_birth=getattr(profile, "date_of_birth", None),
        time_of_birth=getattr(profile, "time_of_birth", None),
        location_name=getattr(profile, "location_name", None),
        latitude=getattr(profile, "latitude", None),
        longitude=getattr(profile, "longitude", None),
        timezone=getattr(profile, "timezone", None),
    )


@api.get("/home", auth=auth, response={200: HomePageSchema})
def home(request):
    user = request.auth
    vimsottari_dhasa = user.charts.vimsottari_dhasa
    mahadasha = find_current_and_next(vimsottari_dhasa, date.today(), level="mahadasha")
    antardasha = find_current_and_next(
        vimsottari_dhasa, date.today(), level="antardasha"
    )

    return {
        "mahadasha": mahadasha,
        "antardasha": antardasha,
        "personalized": HomePage.objects.filter(user=user).first(),
    }


@api.get("/timeline", auth=auth, response={200: TimelineSchema})
def timeline(request):
    user = request.auth
    timeline = TimelineAntardashas.objects.filter(user=user).first()

    return {
        "timeline": timeline.antardashas,
    }


@api.get("/remedies", auth=auth, response={200: RemediesSchema})
def remedies(request):
    user = request.auth
    remedies = Remedies.objects.filter(user=user).first()

    return {
        "diagnosis": remedies.diagnosis,
        "plan": remedies.plan,
    }
