from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from typing import List, Literal
from astro.services.constants import DIVISIONAL_CHARTS
from datetime import date


class OutcomeScopeEnum(str, Enum):
    YES_NO = "yes/no"
    PROBABILITY = "probability"
    TIME_WINDOW = "time-window"


class LayerEnum(str, Enum):
    MD = "MD"
    AD = "AD"
    PD = "PD"
    SD = "SD"


class ConfidenceEnum(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class FormatEnum(str, Enum):
    YES_NO = "yes/no"
    PROBABILITY = "probability"
    TIME_WINDOW = "time-window"


class GradeEnum(str, Enum):
    STRONG = "Strong"
    MIXED = "Mixed"
    WEAK = "Weak"


class FunctionalRoleEnum(str, Enum):
    BENEFIC = "benefic"
    MALEFIC = "malefic"
    MIXED = "mixed"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class YogaStatus(str, Enum):
    PRESENT = "present"
    PARTIAL = "partial"
    CANCELED = "canceled"
    UNKNOWN = "unknown"


class TargetEnum(str, Enum):
    Lagna = "Lagna"
    Lagna_lord = "Lagna lord"
    Moon = "Moon"


class HorizonUnit(str, Enum):
    days = "days"
    months = "months"
    years = "years"


class Horizon(BaseModel):
    unit: HorizonUnit = Field(
        default=HorizonUnit.years,
        description="Time unit: 'days', 'months', or 'years'. Defaults to 'years'.",
    )
    value: int = Field(
        description="Positive integer amount for the horizon (e.g., 3, 5, ...)."
    )


RoleLiteral = Literal["house_lord", "natural_karaka", "occupant", "dispositor"]
PlanetLiteral = Literal[
    "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"
]
VargaName = Literal["D2", "D4", "D7", "D9", "D10"]
StrengthGrade = Literal["Strong", "Mixed", "Weak"]


class Stakeholder(BaseModel):
    role: RoleLiteral = Field(
        ..., description="One of: house_lord|natural_karaka|occupant|dispositor"
    )
    label: str = Field(..., min_length=1, description="Human-readable tag")
    planet: PlanetLiteral
    house: Optional[int] = Field(None, description="1–12 if applicable, else null")
    why: str = Field(..., min_length=1, description="1–2 short reasons")


class HouseMapping(BaseModel):
    primary_houses: List[int] = Field(
        ..., description="Unique ints 1–12 ordered by importance"
    )
    who_matters: List[Stakeholder] = Field(default_factory=list)


class ShadbalaMini(BaseModel):
    rupa: float = Field(description="Shadbala total in rūpas for this target.")
    pct_req: float = Field(description="Percentage of classical required value.")


class A2Flags(BaseModel):
    combust: bool = False
    retrograde: bool = False
    eclipsed: bool = False
    planetary_war: bool = False


SubjectLiteral = Literal["Lagna", "LagnaLord", "Moon"]
PlanetLiteral = Literal[
    "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"
]
DignityLiteral = Literal[
    "Exalted", "Moolatrikona", "Own", "Friendly", "Neutral", "Inimical", "Debilitated"
]
GradeLiteral = Literal["Strong", "Mixed", "Weak"]

YogaCategoryLiteral = Literal[
    "Raja", "Dhana", "Arishta", "Vipareeta", "Cancellation", "Other"
]
NetEffectLiteral = Literal["Benefic", "Malefic", "Mixed"]
ConfidenceLiteral = Literal["High", "Medium", "Low"]


class A2Assessment(BaseModel):
    subject: SubjectLiteral
    planet: Optional[PlanetLiteral] = Field(
        None, description="Planet for subject (nullable for Lagna)"
    )
    sign: Optional[str] = None
    house: Optional[int] = Field(None, description="1–12 where applicable (Lagna is 1)")
    dignity: Optional[DignityLiteral] = None
    flags: A2Flags = Field(default_factory=A2Flags)
    shadbala_pct: Optional[float] = Field(
        None, description="Percent scale if available"
    )
    aspects_in: List[str] = Field(default_factory=list)
    aspects_out: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    grade: GradeLiteral
    why: List[str] = Field(default_factory=list)


class A2Yoga(BaseModel):
    name: str
    category: YogaCategoryLiteral
    rule_brief: str
    participants: List[str] = Field(default_factory=list)
    evidence: str
    relevance_to_matter: str
    net_effect: NetEffectLiteral
    confidence: ConfidenceLiteral


class BaselineSummary(BaseModel):
    assessments: List[A2Assessment]
    yogas: List[A2Yoga] = Field(default_factory=list)
    baseline_grade: GradeLiteral
    notes: List[str] = Field(default_factory=list)


class StrengthEnum(str, Enum):
    STRONG = "Strong"
    MIXED = "Mixed"
    WEAK = "Weak"


class Flags(BaseModel):
    combust: bool = False
    retrograde: bool = False


class Lord(BaseModel):
    planet: PlanetLiteral
    sign: Optional[str] = None
    house: Optional[int] = Field(None, description="1–12")
    dignity: Optional[str] = Field(None, description="One of DignityLiteral or null")
    flags: Flags = Field(default_factory=Flags)
    aspects_in: List[str] = Field(default_factory=list)
    aspects_out: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    grade: GradeLiteral


class Occupant(BaseModel):
    planet: PlanetLiteral
    dignity: Optional[str] = Field(None, description="One of DignityLiteral or null")
    notes: List[str] = Field(default_factory=list)
    grade: GradeLiteral


class Dispositor(BaseModel):
    planet: PlanetLiteral
    sign: Optional[str] = None
    house: Optional[int] = Field(None, description="1–12")
    dignity: Optional[str] = Field(None, description="One of DignityLiteral or null")
    notes: List[str] = Field(default_factory=list)
    grade: GradeLiteral


class Ashtakavarga(BaseModel):
    sav_total_for_sign: Optional[int] = Field(
        None, description="Total SAV bindus for the sign of this house"
    )
    bav_for_lord: Optional[int] = Field(
        None, description="BAV bindus for the house lord in this sign"
    )
    comments: Optional[str] = None


class HouseEvaluation(BaseModel):
    house: int
    focus: str
    lord: Lord
    occupants: List[Occupant] = Field(default_factory=list)
    dispositor: Optional[Dispositor] = None
    ashtakavarga: Optional[Ashtakavarga] = None
    promise: List[str] = Field(default_factory=list)
    threats: List[str] = Field(default_factory=list)
    support_score: float = Field(..., ge=0.0, le=100.0)
    verdict: GradeLiteral
    why: List[str] = Field(default_factory=list)


## Removed old A3DeepDive class definition
class DeepDiveEvaluation(BaseModel):
    house_evaluation: List[HouseEvaluation] = Field(
        description="Evaluation entries for each primary house."
    )


class VargaCheck(BaseModel):
    varga: VargaName
    strength: StrengthGrade
    key_lords: List[str] = Field(
        default_factory=list,
        description="Stakeholders/karakas (labels) checked in this varga",
    )
    highlights: List[str] = Field(
        default_factory=list, description="3–6 concise supportive reasons"
    )
    contradictions: List[str] = Field(
        default_factory=list, description="0–4 concise contradictions vs D1"
    )
    notes: List[str] = Field(default_factory=list, description="0–3 optional notes")


class VargaConfirmationEnum(str, Enum):
    SUPPORTIVE = "Supportive"
    CONTRADICTORY = "Contradictory"
    NEUTRAL = "Neutral"


class DivisionalChartVerification(BaseModel):
    varga_checks: List[VargaCheck] = Field(
        description="Detailed evaluations for all stakeholders in the relevant divisional charts."
    )
    varga_confirmation: VargaConfirmationEnum = Field(
        description="Overall synthesis: whether divisional charts confirm, contradict, or are neutral compared to D1 baseline."
    )


GranularityLiteral = Literal["mahadasha", "antardasha", "pratyantardasha"]
PlanetLiteral = Literal[
    "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"
]
SlowPlanetLiteral = Literal["Jupiter", "Saturn", "Rahu", "Ketu"]
FastPlanetLiteral = Literal["Sun", "Moon", "Mercury", "Venus", "Mars"]
SlowEventLiteral = Literal["ingress", "aspect", "conjunction"]
FastEventLiteral = Literal["conjunction", "aspect", "ingress"]
StrengthLabelLiteral = Literal["Strong", "Mixed", "Weak"]


class Lords(BaseModel):
    maha: PlanetLiteral
    antara: Optional[PlanetLiteral] = None
    pratyantara: Optional[PlanetLiteral] = None


class PeriodWindow(BaseModel):
    start: date
    end: date
    granularity: GranularityLiteral
    lords: Lords
    ties: List[str] = Field(
        default_factory=list,
        description="Concise links to A1/A3/A4 (houses/karakas/dispositors)",
    )
    strength_factors: List[str] = Field(default_factory=list)
    afflictions: List[str] = Field(default_factory=list)
    score: float = Field(..., ge=0.0, le=100.0)
    reasons: List[str] = Field(default_factory=list)


class DashaAlignment(BaseModel):
    favorable_periods: List[PeriodWindow] = Field(default_factory=list)
    unfavorable_periods: List[PeriodWindow] = Field(default_factory=list)


class SlowTransit(BaseModel):
    planet: SlowPlanetLiteral
    event: SlowEventLiteral
    sign_or_house: str
    exact_dates: List[date] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class SavHint(BaseModel):
    sign: Optional[str] = None
    sav: Optional[int] = Field(
        None, description="Transit SAV for the sign, if provided"
    )
    note: Optional[str] = None

    model_config = {"extra": "forbid"}


class SymbolicSupportWindow(BaseModel):
    planet: Literal["Jupiter", "Saturn", "Rahu", "Ketu"]
    sign_or_house: str
    support_score: int = Field(ge=0, le=100)
    label: Literal["Strong", "Mixed", "Weak"]
    reasons: List[str]


class SymbolicFastTrigger(BaseModel):
    planet: Literal["Sun", "Moon", "Mercury", "Venus", "Mars"]
    event: Literal["aspect", "ingress", "conjunction"]
    target: str
    within_window: Optional[str]  # planet name or null


class TransitOverlay(BaseModel):
    symbolic_support_windows: List[SymbolicSupportWindow]
    symbolic_fast_triggers: List[SymbolicFastTrigger]


class Window(BaseModel):
    start: str = Field(
        description="Start date (ISO YYYY-MM-DD). If unknown, use 'unknown'."
    )
    end: str = Field(
        description="End date (ISO YYYY-MM-DD). If unknown, use 'unknown'."
    )
    justification: List[str] = Field(
        description="Concise reasons why this window is relevant (dasha tie, transit support, fast trigger)."
    )


class TimingWindows(BaseModel):
    windows: List[Window] = Field(
        description="List of merged/filtered timing windows when outcomes are most likely."
    )
    confidence: ConfidenceEnum = Field(
        description="Overall probability level after combining baseline grade, varga confirmations, and alignment strength."
    )


class FormatEnum(str, Enum):
    YES_NO = "yes/no"
    PROBABILITY = "probability"
    TIME_WINDOW = "time-window"


class WhenBlock(BaseModel):
    earliest: Optional[date] = Field(
        None, description="ISO date YYYY-MM-DD if available"
    )
    latest: Optional[date] = Field(None, description="ISO date YYYY-MM-DD if available")
    why: str = Field(..., description="1–2 concise sentences explaining timing")
    what_to_expect: str = Field(..., description="2–4 sentence plain-language summary")

    model_config = {"extra": "forbid"}


class SynthesisOutput(BaseModel):
    answer: str = Field(..., description="detailed answer to the client question")
    why: List[str] = Field(..., description="3–5 concise evidence-based reasons")
    risks: List[str] = Field(default_factory=list, description="0–4 concise cautions")
    confidence: ConfidenceLiteral
    when: Optional[List[WhenBlock]] = None  # OPTIONAL: include only if timing supported

    model_config = {"extra": "forbid"}


# -- Minimal output schema from the refiner --


class SimpleWindow(BaseModel):
    start: str  # ISO date
    end: str  # ISO date


class Q5RefineOut(BaseModel):
    # Keep the outcome small & actionable
    need_finer: bool = False  # whether to zoom one step finer
    windows: List[SimpleWindow] = Field(default_factory=list)  # refined windows
    next_layer: Optional[
        Literal["AD", "PD", "SD"]
    ] = None  # if need_finer=True, what next
    zoom_ranges: Optional[
        List[SimpleWindow]
    ] = None  # 1–3 ranges to inspect at next layer
    confidence: Optional[Literal["High", "Medium", "Low"]] = "Medium"
    note: Optional[str] = None  # short rationale (≤240 chars)
