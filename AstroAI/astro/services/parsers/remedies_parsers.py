from __future__ import annotations
from typing import TypedDict, Any, Dict, List, Optional, Literal, Tuple
from datetime import date
import os
from pydantic import BaseModel, Field

# =========================
# Strict minimal models
# =========================
class TargetLite(BaseModel):
    planet: str
    action: Literal["pacify", "strengthen"]
    why: List[str] = Field(default_factory=list, description="≤2 short bullets")
    priority: int = Field(ge=1, le=3, description="1=core, 2=helpful, 3=optional")
    model_config = {"extra": "forbid"}


class DiagnosisLite(BaseModel):
    targets: List[TargetLite] = Field(min_items=1, max_items=3)
    notes: List[str] = Field(default_factory=list)
    model_config = {"extra": "forbid"}


REMEDY_TYPES = (
    "mantra",
    "stotra",
    "vrata",
    "daan",
    "seva",
    "lifestyle",
    "color_day",
    "food_herb",
    "puja",
    "yantra",
    "gemstone",
)


class WindowLite(BaseModel):
    start: str
    end: str
    model_config = {"extra": "forbid"}


class RemedyLite(BaseModel):
    type: Literal[REMEDY_TYPES]
    how: str  # concise instruction (what/count/cadence)
    cadence: Optional[str] = None  # "daily", "weekly", "108× Thu"
    caution: Optional[str] = None
    model_config = {"extra": "forbid"}


class PlanLite(BaseModel):
    headline: str = Field(description="<= 12 words")
    window: WindowLite
    daily: List[RemedyLite] = Field(min_items=1, max_items=3)
    weekly: List[RemedyLite] = Field(default_factory=list, max_items=2)
    optional: List[RemedyLite] = Field(
        default_factory=list, max_items=1
    )  # puja/yantra/gemstone if safe
    rationale: List[str] = Field(min_items=2, max_items=4)
    confidence: Literal["High", "Medium", "Low"]
    model_config = {"extra": "forbid"}
