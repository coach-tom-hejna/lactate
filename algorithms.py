"""
LT1 & LT2 threshold detection algorithms.
Python port of the JavaScript frontend algorithms.
"""
import math
from typing import Optional, List, Dict, Any


def calculate_thresholds(
    steps: List[Dict[str, Any]],
    lt1_method: str = "baseline1",
    lt2_method: str = "dmax",
) -> Dict[str, Any]:
    """Main entry point — returns {lt1, lt2, lt1Method, lt2Method}."""
    if len(steps) < 3:
        return {"lt1": None, "lt2": None, "lt1Method": lt1_method, "lt2Method": lt2_method}

    pts = sorted(steps, key=lambda x: float(x["intensity"]))

    lt2 = compute_lt2_moddmax(pts) if lt2_method == "moddmax" else compute_lt2_dmax(pts)
    lt1 = compute_lt1_loglog(pts) if lt1_method == "loglog" else compute_lt1_baseline1(pts)

    # Physiological sanity check: LT1 must be strictly below LT2
    if lt1 and lt2 and lt1["intensity"] >= lt2["intensity"]:
        lt1 = None

    return {"lt1": lt1, "lt2": lt2, "lt1Method": lt1_method, "lt2Method": lt2_method}


# ── LT1: Baseline + 1 mmol/L (interpolated crossing) ──────────────────────────

def compute_lt1_baseline1(pts: List[Dict]) -> Optional[Dict]:
    min_lac = min(p["lactate"] for p in pts)
    threshold = min_lac + 1.0

    for i in range(1, len(pts)):
        prev, curr = pts[i - 1], pts[i]
        if prev["lactate"] <= threshold <= curr["lactate"]:
            t = (threshold - prev["lactate"]) / (curr["lactate"] - prev["lactate"])
            intensity = prev["intensity"] + t * (curr["intensity"] - prev["intensity"])
            hr = None
            if prev.get("hr") and curr.get("hr"):
                hr = round(prev["hr"] + t * (curr["hr"] - prev["hr"]))
            return {"intensity": round(intensity, 3), "lactate": round(threshold, 3),
                    "hr": hr, "isInterpolated": True}
    return None


# ── LT1: Log-log piecewise breakpoint ─────────────────────────────────────────

def compute_lt1_loglog(pts: List[Dict]) -> Optional[Dict]:
    valid = [p for p in pts if p["intensity"] > 0 and p["lactate"] > 0]
    if len(valid) < 4:
        return None

    log_pts = [{"x": math.log(p["intensity"]), "y": math.log(p["lactate"]), "orig": p}
               for p in valid]

    min_rss, best_i = float("inf"), None
    for i in range(1, len(log_pts) - 1):
        rss = _linear_rss(log_pts[: i + 1]) + _linear_rss(log_pts[i:])
        if rss < min_rss:
            min_rss, best_i = rss, i

    if best_i is None:
        return None
    p = log_pts[best_i]["orig"]
    return {"intensity": p["intensity"], "lactate": p["lactate"],
            "hr": p.get("hr"), "isInterpolated": False}


def _linear_rss(pts: List[Dict]) -> float:
    n = len(pts)
    if n < 2:
        return 0.0
    sx  = sum(p["x"] for p in pts)
    sy  = sum(p["y"] for p in pts)
    sxy = sum(p["x"] * p["y"] for p in pts)
    sx2 = sum(p["x"] ** 2 for p in pts)
    d   = n * sx2 - sx * sx
    if abs(d) < 1e-12:
        mean_y = sy / n
        return sum((p["y"] - mean_y) ** 2 for p in pts)
    a = (n * sxy - sx * sy) / d
    b = (sy - a * sx) / n
    return sum((p["y"] - (a * p["x"] + b)) ** 2 for p in pts)


# ── LT2: Standard DMAX ─────────────────────────────────────────────────────────

def compute_lt2_dmax(pts: List[Dict]) -> Optional[Dict]:
    idx = _dmax_index(pts, 0, len(pts) - 1)
    if idx is None:
        return None
    p = pts[idx]
    return {"intensity": p["intensity"], "lactate": p["lactate"],
            "hr": p.get("hr"), "isInterpolated": False}


# ── LT2: Modified DMAX (starts from first lactate rise) ───────────────────────

def compute_lt2_moddmax(pts: List[Dict]) -> Optional[Dict]:
    if len(pts) < 3:
        return None

    min_lac = min(p["lactate"] for p in pts)
    rise_threshold = min_lac + 0.5

    start_idx = 0
    for i in range(len(pts) - 2):
        if pts[i]["lactate"] < rise_threshold:
            start_idx = i
        else:
            break

    if len(pts) - start_idx < 3:
        return compute_lt2_dmax(pts)

    idx = _dmax_index(pts, start_idx, len(pts) - 1)
    if idx is None:
        return compute_lt2_dmax(pts)
    p = pts[idx]
    return {"intensity": p["intensity"], "lactate": p["lactate"],
            "hr": p.get("hr"), "isInterpolated": False}


# ── DMAX core ─────────────────────────────────────────────────────────────────

def _dmax_index(pts: List[Dict], from_i: int, to_i: int) -> Optional[int]:
    if to_i - from_i < 2:
        return None

    first, last = pts[from_i], pts[to_i]
    a = last["lactate"]   - first["lactate"]
    b = first["intensity"] - last["intensity"]
    c = (first["lactate"] - last["lactate"]) * first["intensity"] \
      + (last["intensity"] - first["intensity"]) * first["lactate"]
    denom = math.sqrt(a * a + b * b)
    if denom == 0:
        return None

    max_dist, max_idx = float("-inf"), None
    for i in range(from_i + 1, to_i):
        dist = (a * pts[i]["intensity"] + b * pts[i]["lactate"] + c) / denom
        if dist > max_dist:
            max_dist, max_idx = dist, i

    return max_idx if max_dist > 0.05 else None


# ── Pace ↔ speed helpers ──────────────────────────────────────────────────────

def pace_to_kmh(pace_str: str) -> float:
    """'5:30' → 10.909 km/h"""
    s = str(pace_str).strip()
    if ":" in s:
        parts = s.split(":")
        minutes = float(parts[0])
        seconds = float(parts[1]) if len(parts) > 1 else 0.0
        total_min = minutes + seconds / 60.0
        return 60.0 / total_min if total_min > 0 else 0.0
    return float(s)


def kmh_to_pace(kmh: float) -> str:
    """10.909 → '5:30'"""
    if kmh <= 0:
        return "–"
    total_min = 60.0 / kmh
    m = int(total_min)
    s = round((total_min - m) * 60)
    return f"{m}:{s:02d}"
