import sys
import os
import json
import logging
import argparse
from typing import Dict, Any, List, Optional

# Configure logging to stderr so stdout remains clean for MCP stdio transport
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("hevy-mcp")

from mcp.server.mcpserver import MCPServer
import hevy_client

mcp = MCPServer("hevy-sync")


@mcp.resource("gym://equipment")
def gym_equipment_resource() -> str:
    """Resource containing available gym machines, free weights, cable stations, and equipment limitations."""
    try:
        data = hevy_client.get_gym_equipment()
        return json.dumps(data, indent=2)
    except Exception as e:
        logger.error(f"Error reading gym equipment resource: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_gym_equipment() -> str:
    """Retrieve the inventory of available gym machines, free weights, and cable attachments.

    ALWAYS consult this tool before designing or altering workout routines to ensure
    prescribed machine exercises (e.g. Smith Machine, Pec Deck, Hack Squat, Leg Press)
    actually exist in the user's gym, and to check machine-specific setup notes (e.g. pin settings, pulley ratios).

    Returns:
        JSON containing 'available_machines', 'free_weights_and_bars', 'cable_attachments',
        and 'unavailable_or_lacking' list.
    """
    try:
        data = hevy_client.get_gym_equipment()
        return json.dumps(data, indent=2)
    except Exception as e:
        logger.error(f"Error fetching gym equipment: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def update_gym_equipment(
    action: str,
    name: str,
    target_muscles: Optional[List[str]] = None,
    notes: Optional[str] = None,
    typical_exercises: Optional[List[str]] = None
) -> str:
    """Add, modify, or remove equipment in the gym inventory.

    Args:
        action: One of 'add_machine', 'remove_machine', 'add_unavailable', or 'update_notes'.
        name: Name of the machine or equipment item.
        target_muscles: List of target muscle groups (e.g. ['Chest', 'Triceps']).
        notes: Setup notes, pin holes, pulley ratios, or starting resistance.
        typical_exercises: Common exercises performed on this machine.
    """
    try:
        data = hevy_client.get_gym_equipment()
        machines = data.get("available_machines", [])
        unavailable = data.get("unavailable_or_lacking", [])

        if action == "add_machine":
            existing = next((m for m in machines if m.get("name", "").lower() == name.lower()), None)
            if existing:
                if target_muscles:
                    existing["target_muscles"] = target_muscles
                if notes:
                    existing["notes"] = notes
                if typical_exercises:
                    existing["typical_exercises"] = typical_exercises
                msg = f"Updated existing machine: {name}"
            else:
                machines.append({
                    "name": name,
                    "target_muscles": target_muscles or [],
                    "typical_exercises": typical_exercises or [],
                    "notes": notes or ""
                })
                msg = f"Added new machine: {name}"
        elif action == "remove_machine":
            machines = [m for m in machines if m.get("name", "").lower() != name.lower()]
            data["available_machines"] = machines
            msg = f"Removed machine: {name}"
        elif action == "add_unavailable":
            if name not in unavailable:
                unavailable.append(name)
            data["unavailable_or_lacking"] = unavailable
            msg = f"Marked as unavailable: {name}"
        elif action == "update_notes":
            existing = next((m for m in machines if m.get("name", "").lower() == name.lower()), None)
            if existing:
                existing["notes"] = notes or ""
                msg = f"Updated notes for: {name}"
            else:
                return json.dumps({"error": f"Machine '{name}' not found."})
        else:
            return json.dumps({"error": f"Unknown action '{action}'."})

        data["available_machines"] = machines
        hevy_client.save_gym_equipment(data)
        return json.dumps({"status": "success", "message": msg, "total_machines": len(machines)})
    except Exception as e:
        logger.error(f"Error updating gym equipment: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_recent_workouts(limit: int = 5, summarized: bool = True) -> str:
    """Fetch recent workout sessions from Hevy.

    Args:
        limit: Number of workouts to return (1-10). Defaults to 5.
        summarized: If True, returns a clean summary of exercises, sets, weights (kg), reps, and notes.
                   If False, returns raw JSON response.
    """
    try:
        limit = min(max(1, limit), 10)
        raw_data = hevy_client.get_recent_workouts(page=1, page_size=limit)
        if summarized:
            summaries = hevy_client.extract_workout_summaries(raw_data)
            return json.dumps(summaries, indent=2)
        return json.dumps(raw_data, indent=2)
    except Exception as e:
        logger.error(f"Error fetching workouts: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_routines() -> str:
    """Fetch all routine templates saved on your Hevy account.

    Returns:
        JSON list of routines containing routine ID, title, folder, and exercise overview.
    """
    try:
        data = hevy_client.get_routines(page_size=10, all_pages=True)
        return json.dumps(data, indent=2)
    except Exception as e:
        logger.error(f"Error fetching routines: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_routine_detail(routine_id: str) -> str:
    """Fetch the full configuration of a single routine template by its ID.

    Use this before modifying a routine to inspect the current exercises, target sets, reps, and notes.

    Args:
        routine_id: The UUID of the routine in Hevy.
    """
    try:
        data = hevy_client.get_routine_detail(routine_id)
        return json.dumps(data, indent=2)
    except Exception as e:
        logger.error(f"Error fetching routine {routine_id}: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def search_exercises(query: str, limit: int = 10) -> str:
    """Search available Hevy exercise templates by name, equipment, or target muscle group.

    Use this to find exercise IDs (exercise_template_id) when adding new exercises to a routine.

    Args:
        query: Search term (e.g., 'bench', 'lat pulldown', 'squat', 'biceps').
        limit: Maximum results to return (default 10).
    """
    try:
        matches = hevy_client.search_exercise_templates(query, limit=limit)
        return json.dumps(matches, indent=2)
    except Exception as e:
        logger.error(f"Error searching exercises for '{query}': {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def update_routine(routine_id: str, routine_data: str) -> str:
    """Update an existing routine template in Hevy.

    Important: Hevy replaces the routine wholesale. Ensure all exercises, notes,
    and sets are included in routine_data. It is recommended to call get_routine_detail first.

    Args:
        routine_id: The UUID of the routine to update.
        routine_data: JSON string representing the updated routine structure, containing
                     'title' (string), optional 'folder_id' (int/null), and 'exercises' (list of exercise objects).
    """
    try:
        payload = json.loads(routine_data) if isinstance(routine_data, str) else routine_data
        updated = hevy_client.update_routine(routine_id, payload)
        return json.dumps({"status": "success", "routine": updated}, indent=2)
    except Exception as e:
        logger.error(f"Error updating routine {routine_id}: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def create_routine(routine_data: str) -> str:
    """Create a brand new routine template in Hevy.

    Args:
        routine_data: JSON string containing 'title' (string), optional 'folder_id' (int/null),
                     and 'exercises' (list of exercise objects with exercise_template_id and sets).
    """
    try:
        payload = json.loads(routine_data) if isinstance(routine_data, str) else routine_data
        created = hevy_client.create_routine(payload)
        return json.dumps({"status": "success", "routine": created}, indent=2)
    except Exception as e:
        logger.error(f"Error creating routine: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def sync_local_cache() -> str:
    """Force an immediate sync of workouts and routines to local JSON cache files on the homelab."""
    try:
        res = hevy_client.sync_all_to_local_cache()
        return json.dumps(res, indent=2)
    except Exception as e:
        logger.error(f"Error syncing local cache: {e}")
        return json.dumps({"error": str(e)})


def main():
    parser = argparse.ArgumentParser(description="Hevy MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport protocol (default: stdio)"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host for SSE server (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port for SSE server (default: 8000)")
    args = parser.parse_args()

    logger.info(f"Starting Hevy MCP server using transport: {args.transport}")
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "sse":
        logger.info(f"SSE endpoint available at http://{args.host}:{args.port}/sse")
        mcp.run(transport="sse", host=args.host, port=args.port)
    elif args.transport == "streamable-http":
        mcp.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
