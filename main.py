"""
LT1 & LT2 — FastAPI backend (stateless, no database)
"""
from __future__ import annotations

import os
from typing import List

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from algorithms import calculate_thresholds, pace_to_kmh
from auth import verify_token
from schemas import (
    DexSubmit,
    HealthResponse,
    TestCreate,
    TestResponse,
    TestUpdate,
)

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="LT1 & LT2 API",
    description="Lactate threshold analysis — REST API for web app and Dex agent.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (frontend)
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Frontend ──────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse("static/index.html")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse, tags=["system"])
async def health():
    """Public health-check endpoint (no auth required)."""
    return HealthResponse()


# ── Calculate (stateless) ─────────────────────────────────────────────────────

@app.post("/api/tests", response_model=TestResponse, status_code=201, tags=["tests"])
async def create_test(
    payload: TestCreate,
    _: str = Depends(verify_token),
):
    """Calculate thresholds and return result (stateless — not persisted)."""
    steps = _normalise_steps(payload.steps, payload.sport)
    results = calculate_thresholds(steps, payload.lt1_method or "baseline1", payload.lt2_method or "dmax")

    return TestResponse(
        id=_new_id(),
        name=payload.name,
        athlete_name=payload.athlete_name,
        date=payload.date,
        sport=payload.sport,
        notes=payload.notes or "",
        steps=steps,
        results=results,
        source="web",
        created_at=_now(),
        updated_at=_now(),
    )


@app.get("/api/tests", response_model=List[TestResponse], tags=["tests"])
async def list_tests(
    _: str = Depends(verify_token),
):
    """No database — always returns empty list."""
    return []


@app.get("/api/tests/{test_id}", response_model=TestResponse, tags=["tests"])
async def get_test(
    test_id: str,
    _: str = Depends(verify_token),
):
    """No database — always 404."""
    raise HTTPException(status_code=404, detail=f"Test '{test_id}' not found.")


@app.put("/api/tests/{test_id}", response_model=TestResponse, tags=["tests"])
async def update_test(
    test_id: str,
    payload: TestUpdate,
    _: str = Depends(verify_token),
):
    """No database — always 404."""
    raise HTTPException(status_code=404, detail=f"Test '{test_id}' not found.")


@app.delete("/api/tests/{test_id}", status_code=204, tags=["tests"])
async def delete_test(
    test_id: str,
    _: str = Depends(verify_token),
):
    """No database — always 404."""
    raise HTTPException(status_code=404, detail=f"Test '{test_id}' not found.")


# ── Dex agent endpoint ────────────────────────────────────────────────────────

@app.post("/api/dex/submit", response_model=TestResponse, status_code=201, tags=["dex"])
async def dex_submit(
    payload: DexSubmit,
    _: str = Depends(verify_token),
):
    """
    Submit a lactate test from the Dex agent.
    Calculates and returns thresholds (stateless — not persisted).

    Running pace can be sent as a string ("5:30") or as km/h (float).
    All other sports use watts (float).

    Example payload:
    ```json
    {
      "name": "Ranní test",
      "athlete_name": "Jan Novák",
      "date": "2024-04-09",
      "sport": "cycling",
      "lt1_method": "baseline1",
      "lt2_method": "dmax",
      "steps": [
        {"intensity": 150, "lactate": 1.2, "hr": 130},
        {"intensity": 175, "lactate": 1.5, "hr": 145},
        {"intensity": 200, "lactate": 1.9, "hr": 158},
        {"intensity": 225, "lactate": 2.8, "hr": 170},
        {"intensity": 250, "lactate": 4.5, "hr": 182},
        {"intensity": 275, "lactate": 7.9, "hr": 191}
      ]
    }
    ```
    """
    steps = _normalise_steps(payload.steps, payload.sport)
    results = calculate_thresholds(
        steps,
        payload.lt1_method or "baseline1",
        payload.lt2_method or "dmax",
    )

    return TestResponse(
        id=_new_id(),
        name=payload.name,
        athlete_name=payload.athlete_name,
        date=payload.date,
        sport=payload.sport,
        notes=payload.notes or "",
        steps=steps,
        results=results,
        source="dex",
        created_at=_now(),
        updated_at=_now(),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

import uuid
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _normalise_steps(steps, sport: str) -> List[dict]:
    """Convert StepIn objects to plain dicts, handling running pace strings."""
    result = []
    for s in steps:
        intensity = s.intensity
        if sport == "running" and isinstance(intensity, str):
            intensity = pace_to_kmh(intensity)
        result.append({
            "intensity": float(intensity),
            "lactate":   float(s.lactate),
            "hr":        int(s.hr) if s.hr else None,
        })
    return result
