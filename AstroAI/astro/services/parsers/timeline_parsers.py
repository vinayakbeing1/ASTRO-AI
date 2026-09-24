from pydantic import BaseModel
from django.conf import settings
from typing import Any, Dict, List, Optional, Literal


class DomainBaselineLite(BaseModel):
    domain: Literal["career", "love", "health", "finance"]
    primary_houses: List[int]
    grade: Literal["Strong", "Mixed", "Weak"]
    varga_used: List[str] = []
    varga_grade: Optional[Literal["Strong", "Mixed", "Weak"]] = None
    varga_confirmation: Literal["Supportive", "Neutral", "Contradictory"] = "Neutral"
    notes: List[str] = []
    risks: List[str] = []


class TLBaselineBundle(BaseModel):
    domains: List[DomainBaselineLite]


class ADInfo(BaseModel):
    lord: str
    start: str
    end: str


class PDInfo(BaseModel):
    lord: str
    start: str
    end: str


class PDCardText(BaseModel):
    career: str
    love: str
    health: str
    finance: str


class ADTimelineItem(BaseModel):
    antardasha: ADInfo
    note: str
    pratyantardashas: List[Dict[str, Any]]


class TimelinePayload(BaseModel):
    current_antardasha: ADInfo
    current_ad_note: str
    antardashas: List[ADTimelineItem]


class ADNote(BaseModel):
    note: str
