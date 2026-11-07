# Hevy Sync & MCP Server

Automated synchronization and Model Context Protocol (MCP) server for [Hevy](https://hevy.com), allowing AI agents (Antigravity, Claude, etc.) on your laptop to analyze workout history and alter routines programmatically.

---

## Architecture Overview

```
 ┌────────────────────────────────────────────────────────┐
 │                      Homelab                           │
 │                                                        │
 │  ┌──────────────────────┐    ┌──────────────────────┐  │
 │  │ systemd Timer (4hr)  │    │      MCP Server      │  │
 │  │      sync_job.py     │    │    (mcp_server.py)   │  │
 │  └──────────┬───────────┘    └──────────▲───────────┘  │
 │             │                           │ (stdio / SSE)│
 │             ▼                           │              │
 │   latest_workouts_summary.md            │              │
 │   latest_hevy_summary.json              │              │
 │   routines_backup.json                  │              │
 └─────────────┬───────────────────────────┼──────────────┘
               │                           │ (Encrypted SSH Bridge)
               ▼                           ▼
 ┌────────────────────────────────────────────────────────┐
 │                   Laptop (Client)                      │
 │                                                        │
 │      AI Agent (Antigravity / Claude Desktop / etc.)    │
 │       - Reads workouts & RPE progression               │
 │       - Searches exercise templates                    │
 │       - Modifies & pushes routine updates              │
 └────────────────────────────────────────────────────────┘
```

---

## Available MCP Tools

The agent running on your laptop receives 9 tools and 1 resource:

### Gym Equipment & Context
- `get_gym_equipment()`: Retrieves available machines, pulley ratios (e.g. 2:1), seat/pin settings, free weights, and unavailable machines.
- `update_gym_equipment(action, name, ...)`: Add, remove, or update machines and setup notes in the gym inventory.
- **Resource `gym://equipment`**: Exposes the full equipment inventory as an MCP resource.

### Workouts & Routines
- `get_recent_workouts(limit=5, summarized=True)`: Retrieves workout logs with weights, reps, RPE, and set notes.
- `get_routines()`: Lists all routine templates with their IDs, titles, and exercise breakdown.
- `get_routine_detail(routine_id)`: Fetches the complete JSON configuration of a routine (sets, exercises, notes).
- `search_exercises(query, limit=10)`: Searches the ~500 Hevy exercise templates by exercise title, muscle group, or equipment (returns template IDs required for routine alteration).
- `update_routine(routine_id, routine_data)`: Updates an existing routine wholesale in Hevy via `PUT /v1/routines/{id}`.
- `create_routine(routine_data)`: Creates a new routine template via `POST /v1/routines`.
- `sync_local_cache()`: Forces an immediate refresh of local JSON and Markdown cache files on the homelab.

---

## Connecting Your Laptop's Agent to the Homelab MCP

### Option A: Direct SSH Command (Recommended)

Because you already have SSH access from your laptop to the homelab, your laptop's agent can invoke the MCP server over SSH stdio without opening any inbound ports or running a permanent daemon.

Add the following to your agent configuration file:

#### For Antigravity (`~/.gemini/antigravity/mcp_settings.json` or Workspace settings):
```json
{
  "mcpServers": {
    "hevy": {
      "command": "ssh",
      "args": [
        "-T",
        "art@<HOMELAB_IP_OR_HOSTNAME>",
        "/home/art/homelab/hevy-sync/.venv/bin/python",
        "/home/art/homelab/hevy-sync/mcp_server.py"
      ]
    }
  }
}
```

#### If using Antigravity in Remote SSH mode (connected directly to this homelab):
```json
{
  "mcpServers": {
    "hevy": {
      "command": "/home/art/homelab/hevy-sync/.venv/bin/python",
      "args": ["/home/art/homelab/hevy-sync/mcp_server.py"]
    }
  }
}
```

---

### Option B: SSE Daemon over Tailscale or Local LAN

If you prefer a persistent HTTP/SSE service running on your homelab:

1. Start the server on the homelab:
   ```bash
   /home/art/homelab/hevy-sync/.venv/bin/python /home/art/homelab/hevy-sync/mcp_server.py --transport sse --host 0.0.0.0 --port 8000
   ```
2. Point your laptop agent to the SSE URL:
   ```json
   {
     "mcpServers": {
       "hevy": {
         "url": "http://<HOMELAB_IP_OR_TAILSCALE>:8000/sse"
       }
     }
   }
   ```

---

## Automated Background Sync (Systemd)

A systemd user timer is enabled on this homelab to automatically sync workouts every 4 hours with random jitter:

- **Check timer status:**
  ```bash
  systemctl --user list-timers hevy-sync.timer
  ```
- **Check sync logs:**
  ```bash
  journalctl --user -u hevy-sync.service -n 50
  ```
- **Trigger an immediate manual sync:**
  ```bash
  systemctl --user start hevy-sync.service
  ```
- **Generated files:**
  - `latest_workouts_summary.md` (clean, formatted markdown)
  - `latest_hevy_summary.json` (parsed workout logs)
  - `routines_backup.json` (routine templates backup)
  - `exercise_templates.json` (local cache of exercise library)
