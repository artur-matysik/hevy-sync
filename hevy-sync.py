import os
import json
import requests
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

HEVY_API_KEY = os.getenv("HEVY_API_KEY", "")
BASE_URL = os.getenv("BASE_URL", "https://api.hevyapp.com/v1")

HEADERS = {
    "api-key": HEVY_API_KEY,
    "accept": "application/json",
    "Content-Type": "application/json"
}

def get_recent_workouts(page=1, page_size=5):
    """Fetch recent workouts from Hevy."""
    url = f"{BASE_URL}/workouts"
    params = {"page": page, "pageSize": page_size}
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    return response.json()

def get_routines():
    """Fetch routine templates."""
    url = f"{BASE_URL}/routines"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()

def extract_workout_summary(workouts_data):
    """Parse workouts into a clean summary focusing on weights, reps, and notes."""
    summaries = []
    for w in workouts_data.get("workouts", []):
        summary = {
            "title": w.get("title"),
            "start_time": w.get("start_time"),
            "end_time": w.get("end_time"),
            "exercises": []
        }
        for ex in w.get("exercises", []):
            ex_summary = {
                "name": ex.get("title"),
                "notes": ex.get("notes"),
                "sets": []
            }
            for s in ex.get("sets", []):
                ex_summary["sets"].append({
                    "set_type": s.get("set_type"),
                    "weight_kg": s.get("weight_kg"),
                    "reps": s.get("reps"),
                    "rpe": s.get("rpe")
                })
            summary["exercises"].append(ex_summary)
        summaries.append(summary)
    return summaries

if __name__ == "__main__":
    try:
        print("[*] Fetching recent workouts from Hevy...")
        workouts = get_recent_workouts(page=1, page_size=3)
        summary = extract_workout_summary(workouts)
        
        output_file = "latest_hevy_summary.json"
        with open(output_file, "w") as f:
            json.dump(summary, f, indent=2)
            
        print(f"[+] Successfully fetched {len(summary)} sessions. Saved to {output_file}.")
        
    except requests.exceptions.RequestException as e:
        print(f"[-] API Error: {e}")