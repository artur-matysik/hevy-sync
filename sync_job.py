#!/usr/bin/env python3
"""
Automated background sync script for Hevy.
Can be triggered via cron or systemd timer on the homelab.
"""

import os
import sys
import json
from datetime import datetime
import hevy_client

def generate_markdown_summary(summaries, routines):
    lines = [
        f"# Hevy Sync Summary",
        f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "",
        "## Recent Workouts",
        ""
    ]
    for w in summaries[:5]:
        start = w.get("start_time", "N/A")
        lines.append(f"### {w.get('title', 'Workout')} ({start})")
        if w.get("description"):
            lines.append(f"> {w.get('description')}")
        lines.append("")
        for ex in w.get("exercises", []):
            sets_repr = []
            for s in ex.get("sets", []):
                weight = f"{s.get('weight_kg')}kg" if s.get("weight_kg") is not None else ""
                reps = f"{s.get('reps')} reps" if s.get("reps") is not None else ""
                rpe = f"@RPE {s.get('rpe')}" if s.get("rpe") is not None else ""
                part = " x ".join(filter(None, [weight, reps]))
                if rpe:
                    part += f" {rpe}"
                if part:
                    sets_repr.append(part)
            sets_str = ", ".join(sets_repr) if sets_repr else "Completed"
            note_str = f" *({ex.get('notes')})*" if ex.get("notes") else ""
            lines.append(f"- **{ex.get('title')}**: {sets_str}{note_str}")
        lines.append("")

    lines.append("## Current Routines")
    lines.append("")
    for r in routines.get("routines", []):
        exercise_names = [e.get("title") for e in r.get("exercises", [])]
        lines.append(f"- **{r.get('title')}** (ID: `{r.get('id')}`): {', '.join(exercise_names)}")

    # Add available gym machines section
    gym = hevy_client.get_gym_equipment()
    lines.append("")
    lines.append("## Available Gym Equipment & Machine Quirks")
    lines.append("")
    for m in gym.get("available_machines", []):
        notes_str = f" — *{m.get('notes')}*" if m.get("notes") else ""
        lines.append(f"- **{m.get('name')}** ({', '.join(m.get('target_muscles', []))}){notes_str}")

    if gym.get("unavailable_or_lacking"):
        lines.append("")
        lines.append("### Unavailable / Lacking Equipment")
        for un in gym.get("unavailable_or_lacking", []):
            lines.append(f"- ❌ {un}")

    return "\n".join(lines)


def main():
    print(f"[{datetime.now().isoformat()}] Starting Hevy background sync...")
    try:
        res = hevy_client.sync_all_to_local_cache()
        print(f"[+] Synced {res['workouts_saved']} workouts and {res['routines_saved']} routines.")

        # Also generate a markdown summary for quick viewing
        with open(res["summary_file"], "r") as f:
            summaries = json.load(f)
        with open(res["routines_file"], "r") as f:
            routines = json.load(f)

        md_content = generate_markdown_summary(summaries, routines)
        md_file = os.path.join(os.path.dirname(__file__), "latest_workouts_summary.md")
        with open(md_file, "w") as f:
            f.write(md_content)
        print(f"[+] Markdown summary written to {md_file}")

    except Exception as e:
        print(f"[-] Sync failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
