"""
LT1 & LT2 — FastAPI backend (stateless, no database)
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from algorithms import calculate_thresholds, pace_to_kmh
from auth import verify_token
from schemas import DexSubmit, HealthResponse, TestCreate, TestResponse

app = FastAPI(title="LT1 & LT2 API", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse("static/index.html")


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
async def health():
    return HealthResponse()


@app.post("/api/tests", response_model=TestResponse, status_code=201, tags=["tests"])
async def create_test(payload: TestCreate, _: str = Depends(verify_token)):
    steps = _normalise(payload.steps, payload.sport)
    results = calculate_thresholds(steps, payload.lt1_method or "baseline1", payload.lt2_method or "dmax")
    return _build_response(payload, steps, results, source="web")


@app.post("/api/dex/submit", response_model=TestResponse, status_code=201, tags=["dex"])
async def dex_submit(payload: DexSubmit, _: str = Depends(verify_token)):
    steps = _normalise(payload.steps, payload.sport)
    results = calculate_thresholds(steps, payload.lt1_method or "baseline1", payload.lt2_method or "dmax")
    return _build_response(payload, steps, results, source="dex")


def _build_response(payload, steps, results, source):
    now = datetime.now(timezone.utc)
    return TestResponse(
        id=uuid.uuid4().hex[:12],
        name=payload.name,
        athlete_name=payload.athlete_name,
        date=payload.date,
        sport=payload.sport,
        notes=payload.notes or "",
        steps=steps,
        results=results,
        source=source,
        created_at=now,
        updated_at=now,
    )


def _normalise(steps, sport: str) -> List[dict]:
    result = []
    for s in steps:
        intensity = s.intensity
        if sport == "running" and isinstance(intensity, str):
            intensity = pace_to_kmh(intensity)
        result.append({"intensity": float(intensity), "lactate": float(s.lactate), "hr": int(s.hr) if s.hr else None})
    return result
