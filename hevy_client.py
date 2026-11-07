import os
import json
import time
from typing import Dict, Any, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

HEVY_API_KEY = os.getenv("HEVY_API_KEY", "")
BASE_URL = os.getenv("BASE_URL", "https://api.hevyapp.com/v1").rstrip("/")
CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
_EXERCISE_TEMPLATES_CACHE: Optional[List[Dict[str, Any]]] = None


def get_headers() -> Dict[str, str]:
    api_key = os.getenv("HEVY_API_KEY") or HEVY_API_KEY
    if not api_key:
        raise ValueError(
            "HEVY_API_KEY not found. Set it in .env or as an environment variable."
        )
    return {
        "api-key": api_key,
        "accept": "application/json",
        "Content-Type": "application/json",
    }


def get_gym_equipment() -> Dict[str, Any]:
    """Retrieve the gym equipment profile (available machines, cable attachments, free weights)."""
    equipment_file = os.path.join(CACHE_DIR, "gym_equipment.json")
    if os.path.exists(equipment_file):
        try:
            with open(equipment_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"gym_name": "Primary Gym", "available_machines": [], "unavailable_or_lacking": []}


def save_gym_equipment(data: Dict[str, Any]) -> None:
    """Save the updated gym equipment profile."""
    equipment_file = os.path.join(CACHE_DIR, "gym_equipment.json")
    with open(equipment_file, "w") as f:
        json.dump(data, f, indent=2)


def get_headers() -> Dict[str, str]:
    api_key = os.getenv("HEVY_API_KEY", HEVY_API_KEY)
    return {
        "api-key": api_key,
        "accept": "application/json",
        "Content-Type": "application/json",
    }


def get_recent_workouts(page: int = 1, page_size: int = 5, since: Optional[str] = None) -> Dict[str, Any]:
    """Fetch workouts directly from Hevy API. Note: Hevy limits page_size <= 10."""
    url = f"{BASE_URL}/workouts"
    page_size = min(max(1, page_size), 10)
    params: Dict[str, Any] = {"page": page, "pageSize": page_size}
    if since:
        params["since"] = since
    res = requests.get(url, headers=get_headers(), params=params, timeout=15)
    res.raise_for_status()
    return res.json()


def extract_workout_summaries(workouts_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert raw Hevy workouts data into structured summaries for agent analysis."""
    summaries = []
    workouts = workouts_data.get("workouts", []) if isinstance(workouts_data, dict) else workouts_data
    for w in workouts:
        summary = {
            "id": w.get("id"),
            "title": w.get("title"),
            "description": w.get("description"),
            "start_time": w.get("start_time"),
            "end_time": w.get("end_time"),
            "exercises": []
        }
        for ex in w.get("exercises", []):
            ex_summary = {
                "title": ex.get("title"),
                "notes": ex.get("notes"),
                "exercise_template_id": ex.get("exercise_template_id"),
                "sets": []
            }
            for s in ex.get("sets", []):
                set_info = {
                    "index": s.get("index"),
                    "type": s.get("set_type", s.get("type", "normal")),
                    "weight_kg": s.get("weight_kg"),
                    "reps": s.get("reps"),
                    "rpe": s.get("rpe"),
                    "distance_meters": s.get("distance_meters"),
                    "duration_seconds": s.get("duration_seconds")
                }
                ex_summary["sets"].append(set_info)
            summary["exercises"].append(ex_summary)
        summaries.append(summary)
    return summaries


def get_routines(page: int = 1, page_size: int = 10, all_pages: bool = True) -> Dict[str, Any]:
    """Fetch routine templates. Note: Hevy limits page_size <= 10."""
    url = f"{BASE_URL}/routines"
    page_size = min(max(1, page_size), 10)
    
    if not all_pages:
        params = {"page": page, "pageSize": page_size}
        res = requests.get(url, headers=get_headers(), params=params, timeout=15)
        res.raise_for_status()
        return res.json()

    all_routines = []
    curr_page = 1
    page_count = 1
    while curr_page <= page_count:
        params = {"page": curr_page, "pageSize": page_size}
        res = requests.get(url, headers=get_headers(), params=params, timeout=15)
        res.raise_for_status()
        data = res.json()
        page_count = data.get("page_count", 1)
        all_routines.extend(data.get("routines", []))
        curr_page += 1

    return {"routines": all_routines, "total_count": len(all_routines)}


def get_routine_detail(routine_id: str) -> Dict[str, Any]:
    """Fetch full routine details by routine ID."""
    url = f"{BASE_URL}/routines/{routine_id}"
    res = requests.get(url, headers=get_headers(), timeout=15)
    res.raise_for_status()
    return res.json().get("routine", {})


def get_routine_folders() -> List[Dict[str, Any]]:
    """Fetch folders organizing routines."""
    url = f"{BASE_URL}/routine_folders"
    res = requests.get(url, headers=get_headers(), timeout=15)
    res.raise_for_status()
    return res.json().get("routine_folders", [])


def get_all_exercise_templates(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Fetch and cache all available exercise templates (~500 templates)."""
    global _EXERCISE_TEMPLATES_CACHE
    cache_file = os.path.join(CACHE_DIR, "exercise_templates.json")

    if not force_refresh and _EXERCISE_TEMPLATES_CACHE is not None:
        return _EXERCISE_TEMPLATES_CACHE

    if not force_refresh and os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                _EXERCISE_TEMPLATES_CACHE = json.load(f)
                return _EXERCISE_TEMPLATES_CACHE
        except Exception:
            pass

    templates = []
    page = 1
    page_count = 1
    while page <= page_count:
        url = f"{BASE_URL}/exercise_templates"
        params = {"page": page, "pageSize": 100}
        res = requests.get(url, headers=get_headers(), params=params, timeout=15)
        res.raise_for_status()
        data = res.json()
        page_count = data.get("page_count", 1)
        templates.extend(data.get("exercise_templates", []))
        page += 1
        time.sleep(0.1)

    _EXERCISE_TEMPLATES_CACHE = templates
    try:
        with open(cache_file, "w") as f:
            json.dump(templates, f, indent=2)
    except Exception:
        pass

    return templates


def search_exercise_templates(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search exercise templates by name, equipment, or muscle group."""
    templates = get_all_exercise_templates()
    q = query.strip().lower()
    matches = []
    for t in templates:
        title = (t.get("title") or "").lower()
        muscle = (t.get("primary_muscle_group") or "").lower()
        equipment = (t.get("equipment") or "").lower()
        if q in title or q in muscle or q in equipment:
            matches.append({
                "id": t.get("id"),
                "title": t.get("title"),
                "primary_muscle_group": t.get("primary_muscle_group"),
                "secondary_muscle_groups": t.get("secondary_muscle_groups", []),
                "equipment": t.get("equipment"),
                "type": t.get("type"),
                "is_custom": t.get("is_custom", False)
            })
            if len(matches) >= limit:
                break
    return matches


def update_routine(routine_id: str, routine_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update an existing routine.
    Note: Hevy PUT requires the full routine object under the 'routine' key.
    """
    url = f"{BASE_URL}/routines/{routine_id}"
    payload = {"routine": routine_data} if "routine" not in routine_data else routine_data
    res = requests.put(url, headers=get_headers(), json=payload, timeout=15)
    res.raise_for_status()
    return res.json().get("routine", {})


def create_routine(routine_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new routine template in Hevy."""
    url = f"{BASE_URL}/routines"
    payload = {"routine": routine_data} if "routine" not in routine_data else routine_data
    res = requests.post(url, headers=get_headers(), json=payload, timeout=15)
    res.raise_for_status()
    return res.json().get("routine", {})


def sync_all_to_local_cache() -> Dict[str, Any]:
    """Sync latest workouts and routines to local json files for instant lookup/backups."""
    workouts_raw = get_recent_workouts(page=1, page_size=10)
    summaries = extract_workout_summaries(workouts_raw)
    routines = get_routines(page=1, page_size=10, all_pages=True)
    
    summary_path = os.path.join(CACHE_DIR, "latest_hevy_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summaries, f, indent=2)

    routines_path = os.path.join(CACHE_DIR, "routines_backup.json")
    with open(routines_path, "w") as f:
        json.dump(routines, f, indent=2)

    return {
        "status": "success",
        "workouts_saved": len(summaries),
        "routines_saved": len(routines.get("routines", [])),
        "summary_file": summary_path,
        "routines_file": routines_path
    }
