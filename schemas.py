"""Pydantic request/response schemas with camelCase aliases for the frontend."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, field_validator
from pydantic.alias_generators import to_camel


# ── Shared camelCase config ───────────────────────────────────────────────────

class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,   # also accept snake_case on input
        from_attributes=True,
    )


# ── Step ─────────────────────────────────────────────────────────────────────

class StepIn(BaseModel):
    """One step of a lactate test (accepts str intensity for running pace)."""
    intensity: Union[float, str]   # km/h, W, or pace string "5:30"
    lactate:   float
    hr:        Optional[int] = None

    @field_validator("intensity", mode="before")
    @classmethod
    def coerce_intensity(cls, v):
        # Accept numeric strings like "200"
        try:
            return float(v)
        except (ValueError, TypeError):
            return v  # keep as string — backend converts pace later


class StepOut(BaseModel):
    intensity: float
    lactate:   float
    hr:        Optional[int] = None


# ── Test create (web form) ────────────────────────────────────────────────────

class TestCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name:         str
    athlete_name: Optional[str] = None
    date:         Optional[str] = None
    sport:        str = "cycling"
    notes:        Optional[str] = ""
    steps:        List[StepIn]
    lt1_method:   Optional[str] = "baseline1"
    lt2_method:   Optional[str] = "dmax"


class TestUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name:         Optional[str]       = None
    athlete_name: Optional[str]       = None
    date:         Optional[str]       = None
    sport:        Optional[str]       = None
    notes:        Optional[str]       = None
    steps:        Optional[List[StepIn]] = None
    lt1_method:   Optional[str]       = None
    lt2_method:   Optional[str]       = None


# ── Dex agent submit ──────────────────────────────────────────────────────────

class DexSubmit(BaseModel):
    """Flexible schema for the Dex agent. Accepts both snake_case and camelCase."""
    model_config = ConfigDict(populate_by_name=True)

    name:         str
    athlete_name: Optional[str] = None
    date:         Optional[str] = None
    sport:        str = "cycling"          # running | cycling | rowing | skiing
    notes:        Optional[str] = ""
    steps:        List[StepIn]
    lt1_method:   Optional[str] = "baseline1"
    lt2_method:   Optional[str] = "dmax"


# ── Test response ─────────────────────────────────────────────────────────────

class TestResponse(CamelModel):
    id:           str
    name:         str
    athlete_name: Optional[str]            = None
    date:         Optional[str]            = None
    sport:        str
    notes:        Optional[str]            = None
    steps:        List[Dict[str, Any]]
    results:      Optional[Dict[str, Any]] = None
    source:       str                      = "web"
    created_at:   datetime
    updated_at:   datetime


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status:  str = "ok"
    version: str = "1.0"
