#!/usr/bin/env python3
"""Mushroom fruiting forecast for thelunale.com/mushroom/.

Fetches weather (Open-Meteo) and sightings (iNaturalist), scores each
species x location x day for the next week, and writes mushroom/data.json
plus a small snapshot in mushroom/history/ for later calibration.

Standard library only, so it runs unchanged on GitHub Actions.

    python3 scripts/mushroom/build.py            # fetch, score, write
    python3 scripts/mushroom/build.py --no-history
"""
import argparse
import json
import math
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "mushroom"
UA = "lunale-mushroom-forecast/0.1 (+https://thelunale.com)"

FORECAST_DAYS = 7          # today + 6
PAST_DAYS = 21             # longest rain lag (14) + a week of chart history
REGION = {"lat": 40.0, "lng": -74.8, "radius": 90}   # seasonality curves (km)
RECENT_RADIUS_KM = 40
RECENT_DAYS = 14

# ── Locations ──────────────────────────────────────────────────────────────
# habitat: 0–1 "are the right trees/ground here", per species id. Hand-tuned.
#          A species left out (or 0) is not scored or shown at that location.
# soil:    (dry, wet) soil moisture m³/m³ at 3–9 cm. The model's sandy Pinelands
#          cells peak near 0.16 even after soaking rain, loam near 0.34.
# Keep these to public areas — never put a specific tree's coordinates here.
LOCATIONS = [
    {
        "id": "holland", "name": "Holland, PA", "sub": "18966 · Tyler SP & Churchville",
        "lat": 40.19, "lng": -74.99,
        "habitat_note": "Mixed hardwood parks, planted pines, open lawns",
        "soil": (0.12, 0.32),
        "habitat": {"morel": 0.6, "chanterelle": 0.6, "king": 0.4, "leccinum": 0.4,
                    "bolete": 0.7, "suillus": 0.9, "chicken": 0.8, "hen": 0.6, "puffball": 0.9,
                    "honey": 0.8, "ringless": 0.8},
    },
    {
        "id": "pinelands", "name": "NJ Pinelands", "sub": "NJ State Forest",
        "lat": 39.76, "lng": -74.68,
        "habitat_note": "Pitch pine & oak on sandy, acidic soil that drains fast",
        "soil": (0.05, 0.15),
        "habitat": {"morel": 0.05, "chanterelle": 0.8, "king": 0.5, "leccinum": 0.9,
                    "bolete": 0.8, "suillus": 0.9, "chicken": 0.3, "hen": 0.2, "puffball": 0.5,
                    "honey": 0.6, "ringless": 0.5, "matsutake": 0.6},
    },
    {
        "id": "institute", "name": "Institute Woods", "sub": "Princeton, NJ",
        "lat": 40.327, "lng": -74.672,
        "habitat_note": "Mature oak, beech & tulip poplar on the Stony Brook floodplain",
        "soil": (0.12, 0.32),
        "habitat": {"morel": 0.7, "chanterelle": 0.5, "king": 0.5, "leccinum": 0.4,
                    "bolete": 0.8, "suillus": 0.3, "chicken": 0.8, "hen": 0.9, "puffball": 0.7,
                    "honey": 0.9, "ringless": 0.9},
    },
]

# ── Species ────────────────────────────────────────────────────────────────
# rain_in: inches in the lag window for a full trigger
# lag:     (min, max) days between rain and fruiting
# temp:    (basis, lo, hi) — ideal band for 4-day mean of daily highs, or soil temp at 6 cm
# cold:    None | "boost" (helped by nights ≤55°F) | "required"
# caution: optional safety note shown in the page's detail panel
# season_region / season_shift / season_note: for species too rare locally to
#          have their own curve — borrow a wider region's and shift it (weeks)
HONEY_CAUTION = ("Deadly galerina grows on the same wood, sometimes in the same cluster — "
                 "honeys print white, galerina rusty brown. Jack-o'-lanterns also cluster on oak. "
                 "Cook thoroughly; some people react even then.")

SPECIES = [
    {"id": "morel", "name": "Morels", "latin": "Morchella", "taxa": [56830],
     "rain_in": 0.5, "lag": (5, 14), "temp": ("soil", 50, 62), "cold": None},
    {"id": "chanterelle", "name": "Chanterelles", "latin": "Cantharellus", "taxa": [47348],
     "rain_in": 1.0, "lag": (4, 10), "temp": ("high", 70, 86), "cold": None},
    {"id": "king", "name": "King boletes", "latin": "Boletus edulis group",
     "taxa": [48701, 194218, 350217, 194181, 543052],
     "rain_in": 1.0, "lag": (4, 9), "temp": ("high", 68, 85), "cold": None},
    {"id": "leccinum", "name": "Leccinum Bolete", "latin": "Leccinum spp.", "taxa": [54203],
     "rain_in": 0.75, "lag": (3, 8), "temp": ("high", 60, 82), "cold": None},
    {"id": "bolete", "name": "Boletes (all)", "latin": "Boletaceae", "taxa": [48702],
     "rain_in": 1.0, "lag": (3, 9), "temp": ("high", 65, 85), "cold": None},
    {"id": "suillus", "name": "Slippery jacks & jills", "latin": "Suillus", "taxa": [53490],
     "rain_in": 0.75, "lag": (3, 8), "temp": ("high", 55, 75), "cold": "boost"},
    {"id": "chicken", "name": "Chicken of the woods", "latin": "Laetiporus", "taxa": [48431],
     "rain_in": 0.75, "lag": (4, 10), "temp": ("high", 60, 85), "cold": None},
    {"id": "hen", "name": "Hen of the woods", "latin": "Grifola frondosa", "taxa": [53714],
     "rain_in": 0.75, "lag": (5, 14), "temp": ("high", 55, 75), "cold": "required"},
    {"id": "puffball", "name": "Puffballs", "latin": "Lycoperdaceae", "taxa": [48445],
     "rain_in": 0.75, "lag": (2, 7), "temp": ("high", 62, 85), "cold": None},
    {"id": "honey", "name": "Honey mushrooms", "latin": "Armillaria", "taxa": [55930],
     "rain_in": 0.75, "lag": (4, 10), "temp": ("high", 50, 70), "cold": "boost",
     "caution": HONEY_CAUTION},
    {"id": "ringless", "name": "Ringless honey", "latin": "Desarmillaria caespitosa", "taxa": [1238700],
     "rain_in": 0.75, "lag": (4, 10), "temp": ("high", 65, 85), "cold": None,
     "caution": HONEY_CAUTION},
    {"id": "matsutake", "name": "Matsutake", "latin": "Tricholoma magnivelare", "taxa": [62483],
     "rain_in": 0.75, "lag": (6, 14), "temp": ("high", 50, 66), "cold": "boost",
     # Only 3 records within 200 km (all Pine Barrens, November). The Northeast
     # curve peaks Sep–Oct from New England finds; NJ runs ~4 weeks later.
     "season_region": {"lat": 41.0, "lng": -74.0, "radius": 600}, "season_shift": 4,
     "season_note": "Northeast records shifted 4 weeks later for NJ",
     "caution": ("Deadly white Amanitas (destroying angels) look similar. Check for a "
                 "sac-like cup at the base, and the matsutake's spicy cinnamon smell.")},
]


# ── HTTP ───────────────────────────────────────────────────────────────────
_last_inat = 0.0


def get_json(url, params):
    """GET with retries. iNaturalist asks for ≤1 request/second."""
    global _last_inat
    if "inaturalist" in url:
        wait = 1.1 - (time.monotonic() - _last_inat)
        if wait > 0:
            time.sleep(wait)
        _last_inat = time.monotonic()
    req = urllib.request.Request(
        f"{url}?{urllib.parse.urlencode(params, safe=',')}", headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))


# ── Fetch ──────────────────────────────────────────────────────────────────
def fetch_weather(loc):
    d = get_json("https://api.open-meteo.com/v1/forecast", {
        "latitude": loc["lat"], "longitude": loc["lng"],
        "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min,relative_humidity_2m_mean",
        "hourly": "soil_moisture_3_to_9cm,soil_temperature_6cm",
        "past_days": PAST_DAYS, "forecast_days": FORECAST_DAYS,
        "temperature_unit": "fahrenheit", "precipitation_unit": "inch",
        "timezone": "America/New_York",
    })
    daily, hourly = d["daily"], d["hourly"]

    def day_means(values):
        out = []
        for i in range(len(daily["time"])):
            xs = [v for v in values[i * 24:(i + 1) * 24] if v is not None]
            out.append(round(sum(xs) / len(xs), 3) if xs else None)
        return out

    return {
        "dates": daily["time"],
        "rain": [r or 0.0 for r in daily["precipitation_sum"]],
        "tmax": daily["temperature_2m_max"],
        "tmin": daily["temperature_2m_min"],
        "rh": daily["relative_humidity_2m_mean"],
        "sm": day_means(hourly["soil_moisture_3_to_9cm"]),
        "st": day_means(hourly["soil_temperature_6cm"]),
        "today": PAST_DAYS,
    }


def fetch_season(sp):
    """Regional week-of-year curve, smoothed, normalised to peak = 1."""
    d = get_json("https://api.inaturalist.org/v1/observations/histogram", {
        "taxon_id": ",".join(map(str, sp["taxa"])), "verifiable": "true",
        "date_field": "observed", "interval": "week_of_year",
        **sp.get("season_region", REGION),
    })
    raw = d["results"]["week_of_year"]
    weeks = [raw.get(str(w), 0) for w in range(1, 54)]
    shift = sp.get("season_shift", 0)
    weeks = weeks[-shift:] + weeks[:-shift] if shift else weeks
    total = sum(weeks)
    half = 2 if total >= 300 else 3          # sparse taxa get a wider window
    kernel = [half + 1 - abs(k) for k in range(-half, half + 1)]
    smooth = [sum(kernel[j] * weeks[(w + j - half) % 53] for j in range(len(kernel)))
              for w in range(53)]
    peak = max(smooth) or 1
    return [round(v / peak, 3) for v in smooth], total


def fetch_recent(loc, today):
    """Recent tracked sightings near a location, newest first."""
    all_taxa = sorted({t for sp in SPECIES for t in sp["taxa"]})
    d = get_json("https://api.inaturalist.org/v1/observations", {
        "taxon_id": ",".join(map(str, all_taxa)), "verifiable": "true",
        "lat": loc["lat"], "lng": loc["lng"], "radius": RECENT_RADIUS_KM,
        "d1": (today - timedelta(days=RECENT_DAYS)).isoformat(),
        "order_by": "observed_on", "order": "desc", "per_page": 200,
    })
    counts = {sp["id"]: 0 for sp in SPECIES}
    sightings = []
    for o in d["results"]:
        tx = o.get("taxon") or {}
        lineage = set(tx.get("ancestor_ids") or []) | {tx.get("id")}
        matched = [sp["id"] for sp in SPECIES if lineage & set(sp["taxa"])]
        for sid in matched:
            counts[sid] += 1
        if not matched or len(sightings) >= 24:
            continue
        photo = (o.get("photos") or [{}])[0].get("url") or ""
        km = None
        if o.get("geojson"):
            lng, lat = o["geojson"]["coordinates"]
            km = round(haversine(loc["lat"], loc["lng"], lat, lng))
        # Most specific tracked group wins the label (king before "all boletes").
        primary = next((s for s in matched if s != "bolete"), matched[0])
        sightings.append({
            "species": primary,
            "name": tx.get("preferred_common_name") or tx.get("name"),
            "latin": tx.get("name"),
            "date": o.get("observed_on"),
            "place": o.get("place_guess") or "",
            "km": km,
            "url": o.get("uri"),
            "photo": photo.replace("/square.", "/small."),
            "by": (o.get("user") or {}).get("login"),
        })
    return counts, sightings


def haversine(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2 +
         math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(a))


# ── Scoring ────────────────────────────────────────────────────────────────
def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def band(x, lo, hi, falloff=15):
    """1 inside [lo, hi], fading linearly to 0 over `falloff` degrees outside."""
    if x is None:
        return 0.5
    if x < lo:
        return clamp(1 - (lo - x) / falloff)
    if x > hi:
        return clamp(1 - (x - hi) / falloff)
    return 1.0


def score_day(sp, loc, wx, i, season, recent):
    lo_lag, hi_lag = sp["lag"]
    mid, half = (lo_lag + hi_lag) / 2, max(1, (hi_lag - lo_lag) / 2)

    # Rain trigger: weighted rain in the lag window (centre weight 1, edges 0.5).
    weighted = raw = 0.0
    for k in range(lo_lag, hi_lag + 1):
        r = wx["rain"][i - k]
        raw += r
        weighted += r * (1 - 0.5 * abs(k - mid) / half)
    rain = clamp(weighted / sp["rain_in"])

    sm = wx["sm"][i]
    dry, wet = loc["soil"]
    moisture = 0.5 if sm is None else clamp((sm - dry) / (wet - dry))

    basis, lo, hi = sp["temp"]
    if basis == "soil":
        xs = [v for v in wx["st"][i - 3:i + 1] if v is not None]
    else:
        xs = [v for v in wx["tmax"][i - 3:i + 1] if v is not None]
    t_avg = sum(xs) / len(xs) if xs else None
    temp = band(t_avg, lo, hi)

    min_low10 = min(v for v in wx["tmin"][i - 10:i + 1] if v is not None)
    if sp["cold"] == "required":
        cold = 1.0 if min_low10 <= 55 else 0.35 if min_low10 <= 60 else 0.15
    elif sp["cold"] == "boost":
        cold = 1.0 if min_low10 <= 55 else 0.75
    else:
        cold = 1.0

    min_low3 = min(v for v in wx["tmin"][i - 2:i + 1] if v is not None)
    frost = 0.3 if min_low3 <= 28 else 0.7 if min_low3 <= 32 else 1.0

    # Gentle nudge from recent regional sightings (people are finding it now).
    sightings = 0.85 + 0.3 * clamp(recent / 5)

    d = date.fromisoformat(wx["dates"][i])
    week = min(d.isocalendar().week, 53) - 1
    s_season = season[week]
    habitat = loc["habitat"][sp["id"]]
    weather = (0.6 * rain + 0.4 * moisture) * temp * cold * frost

    score = 100 * (s_season ** 0.6) * habitat * weather * sightings
    return {
        "s": round(clamp(score, 0, 100)),
        "f": {k: round(v, 2) for k, v in {
            "season": s_season, "habitat": habitat, "rain": rain, "moisture": moisture,
            "temp": temp, "cold": cold, "frost": frost, "sightings": sightings}.items()},
        "x": {"rainWin": round(raw, 2), "sm": sm, "tAvg": round(t_avg, 1) if t_avg else None,
              "minLow": round(min_low10), "week": week + 1},
    }


# ── Main ───────────────────────────────────────────────────────────────────
def build():
    now = datetime.now(TZ)
    today = now.date()

    species_out = []
    seasons = {}
    for sp in SPECIES:
        curve, total = fetch_season(sp)
        seasons[sp["id"]] = curve
        species_out.append({
            "id": sp["id"], "name": sp["name"], "latin": sp["latin"], "taxa": sp["taxa"],
            "rain_in": sp["rain_in"], "lag": list(sp["lag"]),
            "temp": list(sp["temp"]), "cold": sp["cold"],
            "caution": sp.get("caution"), "seasonNote": sp.get("season_note"),
            "season": curve, "seasonTotal": total,
        })

    locations_out = []
    for loc in LOCATIONS:
        wx = fetch_weather(loc)
        counts, sightings = fetch_recent(loc, today)
        t0 = wx["today"]
        scores = {
            sp["id"]: [score_day(sp, loc, wx, t0 + n, seasons[sp["id"]], counts[sp["id"]])
                       for n in range(FORECAST_DAYS)]
            for sp in SPECIES if loc["habitat"].get(sp["id"], 0) > 0
        }
        locations_out.append({
            **{k: loc[k] for k in ("id", "name", "sub", "lat", "lng", "habitat_note", "habitat", "soil")},
            "weather": wx, "scores": scores, "recent": counts, "sightings": sightings,
        })

    return {
        "generated": now.isoformat(timespec="minutes"),
        "today": today.isoformat(),
        "days": locations_out[0]["weather"]["dates"][PAST_DAYS:PAST_DAYS + FORECAST_DAYS],
        "recentDays": RECENT_DAYS, "recentRadiusKm": RECENT_RADIUS_KM,
        "species": species_out,
        "locations": locations_out,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-history", action="store_true")
    args = ap.parse_args()

    data = build()
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "data.json").write_text(json.dumps(data, separators=(",", ":")))

    if not args.no_history:
        snap = {
            "today": data["today"], "days": data["days"],
            "scores": {loc["id"]: {sid: [c["s"] for c in cells]
                                   for sid, cells in loc["scores"].items()}
                       for loc in data["locations"]},
            "recent": {loc["id"]: loc["recent"] for loc in data["locations"]},
        }
        hist = OUT_DIR / "history"
        hist.mkdir(exist_ok=True)
        (hist / f"{data['today']}.json").write_text(json.dumps(snap, separators=(",", ":")))

    for loc in data["locations"]:
        best = sorted(((max(c["s"] for c in cells), sid) for sid, cells in loc["scores"].items()),
                      reverse=True)[:3]
        print(f"{loc['name']:<16} " + "  ".join(f"{sid} {s}" for s, sid in best))


if __name__ == "__main__":
    main()
