"""
LT1 & LT2 — FastAPI backend
"""
from __future__ import annotations

import os
from typing import List

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

import models
from algorithms import calculate_thresholds, pace_to_kmh
from auth import verify_token
from database import Base, engine, get_db
from models import Test, new_id
from schemas import (
    DexSubmit,
    HealthResponse,
    TestCreate,
    TestResponse,
    TestUpdate,
)

# ── Bootstrap ─────────────────────────────────────────────────────────────────

# Base.metadata.create_all(bind=engine)  # ← disabled for Vercel (stateless)

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


# ── Tests CRUD ────────────────────────────────────────────────────────────────

@app.get("/api/tests", response_model=List[TestResponse], tags=["tests"])
async def list_tests(
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Return all tests, newest first."""
    return db.query(Test).order_by(Test.created_at.desc()).all()


@app.post("/api/tests", response_model=TestResponse, status_code=201, tags=["tests"])
async def create_test(
    payload: TestCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Create a new test (from the web UI)."""
    steps = _normalise_steps(payload.steps, payload.sport)
    results = calculate_thresholds(steps, payload.lt1_method or "baseline1", payload.lt2_method or "dmax")

    test = Test(
        id=new_id(),
        name=payload.name,
        athlete_name=payload.athlete_name,
        date=payload.date,
        sport=payload.sport,
        notes=payload.notes or "",
        steps=steps,
        results=results,
        source="web",
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    return test


@app.get("/api/tests/{test_id}", response_model=TestResponse, tags=["tests"])
async def get_test(
    test_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    test = _get_or_404(db, test_id)
    return test


@app.put("/api/tests/{test_id}", response_model=TestResponse, tags=["tests"])
async def update_test(
    test_id: str,
    payload: TestUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Update an existing test. Recalculates thresholds when steps or methods change."""
    test = _get_or_404(db, test_id)

    if payload.name         is not None: test.name         = payload.name
    if payload.athlete_name is not None: test.athlete_name = payload.athlete_name
    if payload.date         is not None: test.date         = payload.date
    if payload.sport        is not None: test.sport        = payload.sport
    if payload.notes        is not None: test.notes        = payload.notes

    # Re-calculate if steps or methods changed
    steps_changed   = payload.steps      is not None
    methods_changed = payload.lt1_method is not None or payload.lt2_method is not None

    if steps_changed:
        test.steps = _normalise_steps(payload.steps, test.sport)

    if steps_changed or methods_changed:
        lt1m = payload.lt1_method or (test.results or {}).get("lt1Method", "baseline1")
        lt2m = payload.lt2_method or (test.results or {}).get("lt2Method", "dmax")
        test.results = calculate_thresholds(test.steps, lt1m, lt2m)

    db.commit()
    db.refresh(test)
    return test


@app.delete("/api/tests/{test_id}", status_code=204, tags=["tests"])
async def delete_test(
    test_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    test = _get_or_404(db, test_id)
    db.delete(test)
    db.commit()


# ── Dex agent endpoint ────────────────────────────────────────────────────────

@app.post("/api/dex/submit", response_model=TestResponse, status_code=201, tags=["dex"])
async def dex_submit(
    payload: DexSubmit,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """
    Submit a lactate test from the Dex agent.

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

    test = Test(
        id=new_id(),
        name=payload.name,
        athlete_name=payload.athlete_name,
        date=payload.date,
        sport=payload.sport,
        notes=payload.notes or "",
        steps=steps,
        results=results,
        source="dex",
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    return test


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_404(db: Session, test_id: str) -> Test:
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail=f"Test '{test_id}' not found.")
    return test


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
