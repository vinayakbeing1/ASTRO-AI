# astro/services/home_with_baseline_antardasha.py
from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from django.conf import settings

# -------------------------------------------------------
# LLM
# -------------------------------------------------------
llm = ChatOpenAI(model=settings.OPENAI_MODEL, temperature=0.2)

# -------------------------------------------------------
# Domain constants (primary houses + divisional maps)
# -------------------------------------------------------


class DomainBaselineLite(BaseModel):
    domain: Literal["career_money", "relationships_love", "health_energy", "spiritual"]
    primary_houses: List[int]
    grade: Literal["Strong", "Mixed", "Weak"]
    varga_used: List[str]
    varga_grade: Optional[Literal["Strong", "Mixed", "Weak"]] = None
    varga_confirmation: Literal["Supportive", "Neutral", "Contradictory"] = "Neutral"
    notes: List[str]
    risks: List[str]


class BaselineBundleLite(BaseModel):
    overall_baseline: Literal["Strong", "Mixed", "Weak"]
    domains: List[DomainBaselineLite]


class CareerMoneySection(BaseModel):
    summary: str
    opportunities: List[str]
    risks: List[str]
    future_preview: List[str]  # anchored to NEXT Antardasha


class RelationshipsLoveSection(BaseModel):
    summary: str
    themes_guidance: List[str]
    caution: List[str]
    future_preview: List[str]


class HealthEnergySection(BaseModel):
    summary: str
    specific_health_caution: List[str]
    recommended_lifestyle: List[str]
    future_preview: List[str]


class SpiritualSection(BaseModel):
    summary: str
    simple_practice: str
    lucky_day: str
    lucky_color: str
    lifestyle_tip: str
    optional_remedies: List[str]


class SectionsBundle(BaseModel):
    career_money: CareerMoneySection
    relationships_love: RelationshipsLoveSection
    health_energy: HealthEnergySection
    spiritual: SpiritualSection


class HomeMiniPayload(BaseModel):
    today_for_you: str
    sections: SectionsBundle


class TodayLine(BaseModel):
    line: str = Field(description="<= 10 words")
