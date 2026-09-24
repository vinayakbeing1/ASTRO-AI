from __future__ import annotations
from typing import Optional
from datetime import date, time
from ninja import Schema


class RegisterIn(Schema):
    email: str
    password: str
    date_of_birth: date
    time_of_birth: time
    location_name: str
    latitude: float
    longitude: float
    timezone: float


class AuthOut(Schema):
    token: str
    user_id: int
    email: str


class LoginIn(Schema):
    email: str
    password: str


class ProfileOut(Schema):
    id: int
    email: str
    date_of_birth: Optional[date] = None
    time_of_birth: Optional[time] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[float] = None


class PersonalizedSchema(Schema):
    today_for_you: str
    career_money: Optional[dict] = None
    relationships_love: Optional[dict] = None
    health_energy: Optional[dict] = None
    spiritual: Optional[dict] = None


class HomePageSchema(Schema):
    mahadasha: Optional[dict] = None
    antardasha: Optional[dict] = None
    personalized: Optional[PersonalizedSchema] = None


class TimelineSchema(Schema):
    timeline: Optional[list] = None


class RemediesSchema(Schema):
    diagnosis: Optional[dict] = None
    plan: Optional[dict] = None
