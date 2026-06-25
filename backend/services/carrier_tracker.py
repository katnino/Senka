"""
Carrier Strike Group OSINT Tracker
===================================
Tiered confidence system:
  Tier 1 — Live AIS hit (MMSI watchlist match) — rare but highest accuracy
  Tier 2 — NAVAREA/HYDROLANT notice from NGA MSI — medium accuracy
  Tier 3 — GDELT news inference — fallback (existing behavior)

Confidence radius grows with time since last fix at carrier max speed (~55 km/h).
"""

import json
import logging
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from services.network_utils import fetch_with_curl

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------
# MMSI Watchlist — all 11 US carriers
# Verify these against MarineTraffic/VesselFinder before deploying.
# US Navy uses MID 338; exact MMSIs below are from public AIS records.
# -----------------------------------------------------------------
CARRIER_MMSI: Dict[int, str] = {
    303981000: "CVN-68",
    338234668: "CVN-69",
    338705714: "CVN-69",
    338234670: "CVN-70",
    338234671: "CVN-71",
    338234672: "CVN-72",
    338234673: "CVN-73",
    338234674: "CVN-74",
    338234675: "CVN-75",
    338234676: "CVN-76",
    338234677: "CVN-77",
    338234678: "CVN-78",
}

# Confidence base radii (km) per source tier
_TIER_BASE_RADIUS = {
    "AIS": 10,
    "NAVAREA": 150,
    "GDELT": 500,
    "Static": 800,
}

# Max carrier speed for confidence decay: ~30 knots = 55.6 km/h
_CARRIER_MAX_SPEED_KMH = 56.0

# -----------------------------------------------------------------
# Carrier registry — unchanged from original
# -----------------------------------------------------------------
CARRIER_REGISTRY: Dict[str, dict] = {
    "CVN-68": {
        "name": "USS Nimitz (CVN-68)",
        "wiki": "https://en.wikipedia.org/wiki/USS_Nimitz",
        "homeport": "Bremerton, WA",
        "homeport_lat": 47.56,
        "homeport_lng": -122.63,
        "fallback_lat": 21.35,
        "fallback_lng": -157.95,
        "fallback_heading": 270,
        "fallback_desc": "Pacific Fleet / Pearl Harbor",
    },
    "CVN-69": {
        "name": "USS Dwight D. Eisenhower (CVN-69)",
        "wiki": "https://en.wikipedia.org/wiki/USS_Dwight_D._Eisenhower",
        "homeport": "Norfolk, VA",
        "homeport_lat": 36.95,
        "homeport_lng": -76.33,
        "fallback_lat": 18.0,
        "fallback_lng": 39.5,
        "fallback_heading": 120,
        "fallback_desc": "Red Sea / CENTCOM AOR",
    },
    "CVN-78": {
        "name": "USS Gerald R. Ford (CVN-78)",
        "wiki": "https://en.wikipedia.org/wiki/USS_Gerald_R._Ford",
        "homeport": "Norfolk, VA",
        "homeport_lat": 36.95,
        "homeport_lng": -76.33,
        "fallback_lat": 34.0,
        "fallback_lng": 25.0,
        "fallback_heading": 90,
        "fallback_desc": "Eastern Mediterranean deterrence",
    },
    "CVN-70": {
        "name": "USS Carl Vinson (CVN-70)",
        "wiki": "https://en.wikipedia.org/wiki/USS_Carl_Vinson",
        "homeport": "San Diego, CA",
        "homeport_lat": 32.68,
        "homeport_lng": -117.15,
        "fallback_lat": 15.0,
        "fallback_lng": 115.0,
        "fallback_heading": 45,
        "fallback_desc": "South China Sea patrol",
    },
    "CVN-71": {
        "name": "USS Theodore Roosevelt (CVN-71)",
        "wiki": "https://en.wikipedia.org/wiki/USS_Theodore_Roosevelt_(CVN-71)",
        "homeport": "San Diego, CA",
        "homeport_lat": 32.68,
        "homeport_lng": -117.15,
        "fallback_lat": 22.0,
        "fallback_lng": 122.0,
        "fallback_heading": 300,
        "fallback_desc": "Philippine Sea / Taiwan Strait",
    },
    "CVN-72": {
        "name": "USS Abraham Lincoln (CVN-72)",
        "wiki": "https://en.wikipedia.org/wiki/USS_Abraham_Lincoln_(CVN-72)",
        "homeport": "San Diego, CA",
        "homeport_lat": 32.68,
        "homeport_lng": -117.15,
        "fallback_lat": 21.0,
        "fallback_lng": -158.0,
        "fallback_heading": 270,
        "fallback_desc": "Pacific deployment",
    },
    "CVN-73": {
        "name": "USS George Washington (CVN-73)",
        "wiki": "https://en.wikipedia.org/wiki/USS_George_Washington_(CVN-73)",
        "homeport": "Yokosuka, Japan",
        "homeport_lat": 35.28,
        "homeport_lng": 139.67,
        "fallback_lat": 35.0,
        "fallback_lng": 139.0,
        "fallback_heading": 0,
        "fallback_desc": "Yokosuka, Japan (Forward deployed)",
    },
    "CVN-74": {
        "name": "USS John C. Stennis (CVN-74)",
        "wiki": "https://en.wikipedia.org/wiki/USS_John_C._Stennis",
        "homeport": "Norfolk, VA",
        "homeport_lat": 36.95,
        "homeport_lng": -76.33,
        "fallback_lat": 36.95,
        "fallback_lng": -76.33,
        "fallback_heading": 0,
        "fallback_desc": "RCOH / Norfolk (maintenance)",
    },
    "CVN-75": {
        "name": "USS Harry S. Truman (CVN-75)",
        "wiki": "https://en.wikipedia.org/wiki/USS_Harry_S._Truman",
        "homeport": "Norfolk, VA",
        "homeport_lat": 36.95,
        "homeport_lng": -76.33,
        "fallback_lat": 36.0,
        "fallback_lng": 15.0,
        "fallback_heading": 90,
        "fallback_desc": "Mediterranean deployment",
    },
    "CVN-76": {
        "name": "USS Ronald Reagan (CVN-76)",
        "wiki": "https://en.wikipedia.org/wiki/USS_Ronald_Reagan",
        "homeport": "Bremerton, WA",
        "homeport_lat": 47.56,
        "homeport_lng": -122.63,
        "fallback_lat": 47.56,
        "fallback_lng": -122.63,
        "fallback_heading": 0,
        "fallback_desc": "Bremerton, WA (Homeport)",
    },
    "CVN-77": {
        "name": "USS George H.W. Bush (CVN-77)",
        "wiki": "https://en.wikipedia.org/wiki/USS_George_H.W._Bush",
        "homeport": "Norfolk, VA",
        "homeport_lat": 36.95,
        "homeport_lng": -76.33,
        "fallback_lat": 36.95,
        "fallback_lng": -76.33,
        "fallback_heading": 0,
        "fallback_desc": "Norfolk, VA (Homeport)",
    },
}

# -----------------------------------------------------------------
# Region → approximate center coordinates
# Used to map textual geographic descriptions to lat/lng
# -----------------------------------------------------------------
REGION_COORDS: Dict[str, tuple] = {
    # Oceans & Seas
    "eastern mediterranean": (34.0, 25.0),
    "mediterranean": (36.0, 15.0),
    "western mediterranean": (37.0, 2.0),
    "red sea": (18.0, 39.5),
    "arabian sea": (16.0, 64.0),
    "persian gulf": (26.5, 51.5),
    "gulf of oman": (24.5, 58.5),
    "north arabian sea": (20.0, 64.0),
    "south china sea": (15.0, 115.0),
    "east china sea": (28.0, 125.0),
    "philippine sea": (20.0, 130.0),
    "sea of japan": (40.0, 135.0),
    "taiwan strait": (24.0, 119.5),
    "western pacific": (20.0, 140.0),
    "pacific": (20.0, -150.0),
    "indian ocean": (-5.0, 70.0),
    "north atlantic": (40.0, -40.0),
    "atlantic": (30.0, -50.0),
    "gulf of aden": (12.5, 45.0),
    "horn of africa": (10.0, 50.0),
    "strait of hormuz": (26.5, 56.3),
    "bab el-mandeb": (12.6, 43.3),
    "suez canal": (30.5, 32.3),
    "baltic sea": (57.0, 18.0),
    "north sea": (56.0, 3.0),
    "black sea": (43.0, 34.0),
    "south atlantic": (-20.0, -20.0),
    "coral sea": (-18.0, 155.0),
    "gulf of mexico": (25.0, -90.0),
    "caribbean": (15.0, -75.0),
    # Specific bases / ports
    "norfolk": (36.95, -76.33),
    "san diego": (32.68, -117.15),
    "yokosuka": (35.28, 139.67),
    "pearl harbor": (21.35, -157.95),
    "guam": (13.45, 144.79),
    "bahrain": (26.23, 50.55),
    "rota": (36.62, -6.35),
    "naples": (40.85, 14.27),
    "bremerton": (47.56, -122.63),
    "puget sound": (47.56, -122.63),
    "newport news": (36.98, -76.43),
    # Areas of operation
    "centcom": (25.0, 55.0),
    "indopacom": (20.0, 130.0),
    "eucom": (48.0, 15.0),
    "southcom": (10.0, -80.0),
    "5th fleet": (25.0, 55.0),
    "6th fleet": (36.0, 15.0),
    "7th fleet": (25.0, 130.0),
    "3rd fleet": (30.0, -130.0),
    "2nd fleet": (35.0, -60.0),
}

# -----------------------------------------------------------------
# Cache file for persisting positions between restarts
# -----------------------------------------------------------------
CACHE_FILE = Path(__file__).parent.parent / "carrier_cache.json"

_carrier_positions: Dict[str, dict] = {}
_positions_lock = threading.Lock()
_last_update: Optional[datetime] = None


def _load_cache() -> Dict[str, dict]:
    """Load cached carrier positions from disk."""
    try:
        if CACHE_FILE.exists():
            data = json.loads(CACHE_FILE.read_text())
            logger.info(f"Carrier cache loaded: {len(data)} carriers from {CACHE_FILE}")
            return data
    except Exception as e:
        logger.warning(f"Failed to load carrier cache: {e}")
    return {}


def _save_cache(positions: Dict[str, dict]):
    """Persist carrier positions to disk."""
    try:
        CACHE_FILE.write_text(json.dumps(positions, indent=2))
        logger.info(f"Carrier cache saved: {len(positions)} carriers")
    except Exception as e:
        logger.warning(f"Failed to save carrier cache: {e}")


def _match_region(text: str) -> Optional[tuple]:
    """Match a text string against known regions, return (lat, lng) or None."""
    text_lower = text.lower()
    for region, coords in sorted(REGION_COORDS.items(), key=lambda x: -len(x[0])):
        if region in text_lower:
            return coords
    return None


def _match_carrier(text: str) -> Optional[str]:
    """Match a text string against known carrier names/hull numbers."""
    text_lower = text.lower()
    for hull, info in CARRIER_REGISTRY.items():
        hull_check = hull.lower().replace("-", "")
        name_parts = info["name"].lower()
        # Match hull number (e.g., "CVN-78", "CVN78")
        if hull.lower() in text_lower or hull_check in text_lower.replace("-", ""):
            return hull
        # Match ship name (e.g., "Ford", "Eisenhower", "Vinson")
        ship_name = name_parts.split("(")[0].strip()
        last_name = ship_name.split()[-1] if ship_name else ""
        if last_name and len(last_name) > 3 and last_name in text_lower:
            return hull
    return None


# -----------------------------------------------------------------
# NEW: Tier 1 — AIS MMSI watchlist check
# -----------------------------------------------------------------
def _check_ais_hits() -> Dict[str, dict]:
    """
    Check the live AIS stream for any carrier MMSI hits.
    Returns hull → position dict for any carriers currently visible on AIS.
    This is rare — carriers suppress AIS most of the time — but when it
    fires it's the most accurate data we can get without classified access.
    """
    try:
        from services.ais_stream import get_vessels_by_mmsi_list

        hits = get_vessels_by_mmsi_list(list(CARRIER_MMSI.keys()))
    except Exception as e:
        logger.debug(f"AIS carrier check failed: {e}")
        return {}

    results = {}
    now = datetime.now(timezone.utc).isoformat()
    for mmsi, vessel in hits.items():
        hull = CARRIER_MMSI.get(mmsi)
        if not hull:
            continue
        lat = vessel.get("lat")
        lng = vessel.get("lng")
        if not lat or not lng:
            continue
        results[hull] = {
            "lat": lat,
            "lng": lng,
            "heading": vessel.get("heading", 0),
            "desc": f"Live AIS — MMSI {mmsi}",
            "source": "AIS",
            "source_tier": 1,
            "position_timestamp": now,
            "updated": now,
        }
        logger.info(
            f"CARRIER AIS HIT: {CARRIER_REGISTRY[hull]['name']} at {lat:.3f},{lng:.3f}"
        )
    return results


# -----------------------------------------------------------------
# NEW: Tier 2 — NAVAREA / HYDROLANT notice parsing from NGA MSI
# -----------------------------------------------------------------
def _fetch_navarea_notices() -> Dict[str, dict]:
    """
    Fetch active NAVAREA and HYDROLANT notices from NGA MSI.
    Look for carrier hull numbers or ship names in notice text.
    Returns hull → position dict for any matches found.
    """
    results = {}
    endpoints = [
        "https://msi.nga.mil/api/publications/query?type=HYDROLANT&status=active&output=json",
        "https://msi.nga.mil/api/publications/query?type=NAVAREA&status=active&output=json",
    ]
    now = datetime.now(timezone.utc).isoformat()

    for url in endpoints:
        try:
            raw = fetch_with_curl(url, timeout=10)
            if not raw or raw.status_code != 200:
                continue
            data = raw.json()

            # NGA MSI returns a list under various keys depending on type
            notices = (
                data
                if isinstance(data, list)
                else data.get("publications", data.get("broadcast", []))
            )

            for notice in notices:
                text = " ".join(
                    [
                        str(notice.get("text", "")),
                        str(notice.get("subregion", "")),
                        str(notice.get("navArea", "")),
                    ]
                ).upper()

                hull = _match_carrier(text)
                if not hull or hull in results:
                    continue

                coords = _match_region(text.lower())
                if not coords:
                    continue

                results[hull] = {
                    "lat": coords[0],
                    "lng": coords[1],
                    "heading": 0,
                    "desc": f"NAVAREA/HYDROLANT notice — {text[:80]}",
                    "source": "NAVAREA",
                    "source_tier": 2,
                    "position_timestamp": now,
                    "updated": now,
                }
                logger.info(
                    f"Carrier NAVAREA match: {CARRIER_REGISTRY[hull]['name']} → {coords}"
                )

        except Exception as e:
            logger.debug(f"NAVAREA fetch failed ({url}): {e}")

    return results


# -----------------------------------------------------------------
# Existing Tier 3 — GDELT (unchanged logic, just tagged)
# -----------------------------------------------------------------
def _fetch_gdelt_carrier_news() -> List[dict]:
    """Search GDELT for recent carrier movement news."""
    results = []
    search_terms = [
        "aircraft+carrier+deployed",
        "carrier+strike+group+navy",
        "USS+Nimitz+carrier",
        "USS+Ford+carrier",
        "USS+Eisenhower+carrier",
        "USS+Vinson+carrier",
        "USS+Roosevelt+carrier+navy",
        "USS+Lincoln+carrier",
        "USS+Truman+carrier",
        "USS+Reagan+carrier",
        "USS+Washington+carrier+navy",
        "USS+Bush+carrier",
        "USS+Stennis+carrier",
    ]

    for term in search_terms:
        try:
            url = f"https://api.gdeltproject.org/api/v2/doc/doc?query={term}&mode=artlist&maxrecords=5&format=json&timespan=14d"
            raw = fetch_with_curl(url, timeout=8)
            if not raw:
                continue
            data = raw.json()
            articles = data.get("articles", [])
            for art in articles:
                title = art.get("title", "")
                url = art.get("url", "")
                results.append({"title": title, "url": url})
        except Exception as e:
            logger.debug(f"GDELT search failed for '{term}': {e}")
            continue

    logger.info(f"Carrier OSINT: found {len(results)} GDELT articles")
    return results


def _parse_carrier_positions_from_news(articles: List[dict]) -> Dict[str, dict]:
    """Parse carrier positions from news article titles and descriptions."""
    updates: Dict[str, dict] = {}
    now = datetime.now(timezone.utc).isoformat()

    for article in articles:
        title = article.get("title", "")

        # Try to match a carrier from the title
        hull = _match_carrier(title)
        if not hull:
            continue

        # Try to match a region from the title
        coords = _match_region(title)
        if not coords:
            continue

        # Only update if we haven't seen this carrier yet (first match wins — most recent)
        if hull not in updates:
            updates[hull] = {
                "lat": coords[0],
                "lng": coords[1],
                "desc": title[:100],
                "source": "GDELT",
                "source_tier": 3,
                "position_timestamp": now,
                "updated": now,
            }
            logger.info(f"Carrier GDELT: {CARRIER_REGISTRY[hull]['name']} → {coords}")

    return updates


# -----------------------------------------------------------------
# Main update — tiered, highest confidence wins
# -----------------------------------------------------------------
def update_carrier_positions():
    """Main update function — called on startup and every 12h."""
    global _last_update

    logger.info("Carrier tracker: updating positions (tiered OSINT)...")

    # Base layer: static fallbacks (tier 4)
    positions: Dict[str, dict] = {}
    now = datetime.now(timezone.utc).isoformat()
    for hull, info in CARRIER_REGISTRY.items():
        positions[hull] = {
            "name": info["name"],
            "lat": info["fallback_lat"],
            "lng": info["fallback_lng"],
            "heading": info["fallback_heading"],
            "desc": info["fallback_desc"],
            "wiki": info["wiki"],
            "source": "Static",
            "source_tier": 4,
            "position_timestamp": now,
            "updated": now,
        }

    # Load cache — restore any previously confirmed higher-tier positions
    cached = _load_cache()
    for hull, cached_pos in cached.items():
        if hull in positions:
            cached_tier = cached_pos.get("source_tier", 4)
            if cached_tier < 4:  # Only restore if it was a real OSINT source
                positions[hull].update(cached_pos)

    # Tier 3: GDELT
    try:
        articles = _fetch_gdelt_carrier_news()
        gdelt_pos = _parse_carrier_positions_from_news(articles)
        for hull, pos in gdelt_pos.items():
            if hull in positions and pos["source_tier"] < positions[hull].get(
                "source_tier", 4
            ):
                positions[hull].update(pos)
    except Exception as e:
        logger.warning(f"GDELT carrier fetch failed: {e}")

    # Tier 2: NAVAREA (overwrites GDELT if found)
    try:
        navarea_pos = _fetch_navarea_notices()
        for hull, pos in navarea_pos.items():
            if hull in positions and pos["source_tier"] < positions[hull].get(
                "source_tier", 4
            ):
                positions[hull].update(pos)
    except Exception as e:
        logger.warning(f"NAVAREA fetch failed: {e}")

    # Tier 1: Live AIS (overwrites everything)
    try:
        ais_pos = _check_ais_hits()
        for hull, pos in ais_pos.items():
            if hull in positions:
                positions[hull].update(pos)
    except Exception as e:
        logger.warning(f"AIS carrier check failed: {e}")

    # Ensure name/wiki survive the updates
    for hull, info in CARRIER_REGISTRY.items():
        if hull in positions:
            positions[hull].setdefault("name", info["name"])
            positions[hull].setdefault("wiki", info["wiki"])

    with _positions_lock:
        _carrier_positions.clear()
        _carrier_positions.update(positions)
        _last_update = datetime.now(timezone.utc)

    _save_cache(positions)

    # Log tier distribution
    tier_counts = {}
    for p in positions.values():
        t = p.get("source", "unknown")
        tier_counts[t] = tier_counts.get(t, 0) + 1
    logger.info(f"Carrier tracker: {len(positions)} carriers. Tiers: {tier_counts}")


# -----------------------------------------------------------------
# Confidence radius computation
# -----------------------------------------------------------------
def _compute_confidence_radius(pos: dict) -> float:
    """
    Compute current confidence radius in km based on source tier and elapsed time.
    Radius grows at carrier max speed (~56 km/h) since the last confirmed fix.
    """
    tier = pos.get("source_tier", 4)
    source = pos.get("source", "Static")
    base_radius = _TIER_BASE_RADIUS.get(source, _TIER_BASE_RADIUS["Static"])

    timestamp_str = pos.get("position_timestamp")
    if not timestamp_str:
        return float(base_radius)

    try:
        fix_time = datetime.fromisoformat(timestamp_str)
        if fix_time.tzinfo is None:
            fix_time = fix_time.replace(tzinfo=timezone.utc)
        elapsed_hours = (datetime.now(timezone.utc) - fix_time).total_seconds() / 3600.0
        radius = base_radius + (elapsed_hours * _CARRIER_MAX_SPEED_KMH)
        return round(radius, 1)
    except Exception:
        return float(base_radius)


def get_carrier_positions() -> List[dict]:
    """Return current carrier positions with confidence metadata."""
    with _positions_lock:
        result = []
        for hull, pos in _carrier_positions.items():
            info = CARRIER_REGISTRY.get(hull, {})
            result.append(
                {
                    "name": pos.get("name", info.get("name", hull)),
                    "type": "carrier",
                    "lat": pos["lat"],
                    "lng": pos["lng"],
                    "heading": pos.get("heading", 0),
                    "sog": 0,
                    "cog": 0,
                    "country": "United States",
                    "desc": pos.get("desc", ""),
                    "wiki": pos.get("wiki", info.get("wiki", "")),
                    "estimated": pos.get("source_tier", 4) > 1,
                    "source": pos.get("source", "Static"),
                    "source_tier": pos.get("source_tier", 4),
                    "confidence_radius_km": _compute_confidence_radius(pos),
                    "position_timestamp": pos.get("position_timestamp", ""),
                    "last_osint_update": pos.get("updated", ""),
                }
            )
        return result


# -----------------------------------------------------------------
# Scheduler — unchanged
# -----------------------------------------------------------------
_scheduler_thread: Optional[threading.Thread] = None
_scheduler_stop = threading.Event()


def _scheduler_loop():
    try:
        update_carrier_positions()
    except Exception as e:
        logger.error(f"Carrier tracker initial update failed: {e}")

    while not _scheduler_stop.is_set():
        now = datetime.now(timezone.utc)
        hour = now.hour
        if hour < 12:
            next_hour = 12
        else:
            next_hour = 24

        next_run = now.replace(hour=next_hour % 24, minute=0, second=0, microsecond=0)
        if next_hour == 24:
            next_run = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        wait_seconds = (next_run - now).total_seconds()
        logger.info(f"Carrier tracker: next update in {wait_seconds / 3600:.1f}h")

        if _scheduler_stop.wait(timeout=wait_seconds):
            break

        try:
            update_carrier_positions()
        except Exception as e:
            logger.error(f"Carrier tracker scheduled update failed: {e}")


def start_carrier_tracker():
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop, daemon=True, name="carrier-tracker"
    )
    _scheduler_thread.start()
    logger.info("Carrier tracker started")


def stop_carrier_tracker():
    _scheduler_stop.set()
    if _scheduler_thread:
        _scheduler_thread.join(timeout=5)
    logger.info("Carrier tracker stopped")
