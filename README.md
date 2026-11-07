# Hevy Sync & MCP Server

An automated synchronization daemon and [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for [Hevy](https://hevy.com). It enables AI agents (like **Google Antigravity**, **Claude Desktop**, or **Cursor**) on your laptop to analyze your workout history, evaluate RPE and progressive overload, and programmatically create or alter training routines directly in your Hevy account.

---

## Architecture

```
 ┌────────────────────────────────────────────────────────┐
 │                   Homelab / Server                     │
 │                                                        │
 │  ┌──────────────────────┐    ┌──────────────────────┐  │
 │  │ systemd Timer (4hr)  │    │   MCP Server (8000)  │  │
 │  │      sync_job.py     │    │    (mcp_server.py)   │  │
 │  └──────────┬───────────┘    └──────────▲───────────┘  │
 │             │                           │ (Streamable  │
 │             ▼                           │    HTTP)     │
 │   latest_workouts_summary.md            │              │
 │   latest_hevy_summary.json              │              │
 │   routines_backup.json                  │              │
 │   gym_equipment.json                    │              │
 └─────────────┬───────────────────────────┼──────────────┘
               │                           │ (Tailscale / LAN)
               ▼                           ▼
 ┌────────────────────────────────────────────────────────┐
 │                    Laptop (Client)                     │
 │                                                        │
 │    AI Agent (Antigravity / Claude Desktop / Cursor)    │
 │     - Reads workout sets, reps, weights, RPE, & notes  │
 │     - Inspects gym equipment inventory & machine quirks│
 │     - Searches exercise templates                      │
 │     - Pushes updated routines via Hevy API             │
 └────────────────────────────────────────────────────────┘
```

---

## Features

- **Two-Way Integration:** Not only reads workout logs, but also pushes updated routines back to your Hevy app via `PUT /v1/routines/{id}`.
- **Gym Equipment Context (`gym_equipment.json`):** Feeds your available machines, cable pulley ratios (e.g. 2:1), pin/seat adjustments, and unavailable equipment so the AI never suggests machines your gym doesn't have.
- **9 MCP Tools + 1 Resource:** Full tool suite exposed over standard MCP Streamable HTTP.
- **Automated Background Sync:** Systemd timer pulls fresh workouts and routines every 4 hours, generating human-readable Markdown summaries.
- **Privacy & Secret Protection:** `.gitignore` blocks `.env`, workout history logs, and personal routines from being pushed to version control.

---

## Quickstart: Setup from Scratch on Homelab

### 1. Prerequisites
- Linux machine (Ubuntu, Debian, etc.)
- Python 3.10+
- [Hevy Pro](https://hevy.com) subscription (required for developer API access)
- Network connectivity between homelab and laptop (e.g. [Tailscale](https://tailscale.com) or local LAN)

### 2. Clone and Setup Environment
```bash
git clone https://github.com/<your-username>/hevy-sync.git
cd hevy-sync

# Create virtual environment and install dependencies
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 3. Configure API Key
Get your API key from [hevy.com/settings?developer](https://hevy.com/settings?developer).

```bash
cp .env.example .env
nano .env
```
Set your key:
```env
HEVY_API_KEY=your_hevy_api_key_here
BASE_URL=https://api.hevyapp.com/v1
```

### 4. Run an Initial Sync
Verify your API credentials and generate the initial cache and workout summary:
```bash
.venv/bin/python sync_job.py
```
This generates `latest_workouts_summary.md`, `latest_hevy_summary.json`, `routines_backup.json`, and caches the exercise library in `exercise_templates.json`.

---

## Setting Up Background Services (systemd)

To keep the MCP server and background sync running continuously (even after logging out of SSH), enable user lingering:

```bash
loginctl enable-linger $USER
mkdir -p ~/.config/systemd/user
```

### Service 1: MCP Server (Streamable HTTP on Port 8000)

Create `~/.config/systemd/user/hevy-mcp.service`:
```ini
[Unit]
Description=Hevy MCP Server (Streamable HTTP)
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/art/homelab/hevy-sync
ExecStart=/home/art/homelab/hevy-sync/.venv/bin/python /home/art/homelab/hevy-sync/mcp_server.py --transport streamable-http --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```
*(Update `/home/art/homelab/hevy-sync` with your actual repository path).*

Enable and start:
```bash
systemctl --user daemon-reload
systemctl --user enable --now hevy-mcp.service
```

Verify it is running:
```bash
systemctl --user status hevy-mcp.service
```

---

### Service 2: Periodic Sync Timer (Every 4 Hours)

Create `~/.config/systemd/user/hevy-sync.service`:
```ini
[Unit]
Description=Hevy Workout and Routine Sync
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/home/art/homelab/hevy-sync
ExecStart=/home/art/homelab/hevy-sync/.venv/bin/python /home/art/homelab/hevy-sync/sync_job.py
StandardOutput=journal
StandardError=journal
```

Create `~/.config/systemd/user/hevy-sync.timer`:
```ini
[Unit]
Description=Run Hevy Sync every 4 hours

[Timer]
OnCalendar=*-*-* 03,07,11,15,19,23:15:00
RandomizedDelaySec=300
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
systemctl --user daemon-reload
systemctl --user enable --now hevy-sync.timer
```

Verify scheduled times:
```bash
systemctl --user list-timers hevy-sync.timer
```

---

## Connecting Your Laptop (Antigravity / MCP Client)

Antigravity and other modern MCP clients connect to the homelab over **Streamable HTTP**.

### 1. Configure `mcp_config.json` on Your Laptop

Locate or create `mcp_config.json` on your laptop:

- **Windows:** `C:\Users\<YourUsername>\.gemini\config\mcp_config.json`
- **macOS / Linux:** `~/.gemini/config/mcp_config.json`

Add the following configuration:

```json
{
  "mcpServers": {
    "hevy": {
      "url": "http://<HOMELAB_TAILSCALE_OR_LAN_IP>:8000/mcp"
    }
  }
}
```

> **Tip:** If using Tailscale, use your homelab's Tailscale IP (e.g. `http://100.76.29.0:8000/mcp`). If on the same local Wi-Fi, you can use your local LAN IP (e.g. `http://192.168.0.3:8000/mcp`).

### 2. Restart Antigravity
> [!IMPORTANT]
> Antigravity loads `mcp_config.json` on startup. **Fully restart the Antigravity desktop app** on your laptop after editing the file.

### 3. Verify in Chat
Start a new conversation in Antigravity and ask:
> *"What tools do you have for Hevy or my gym equipment?"*

The agent will list the 9 Hevy tools and read your gym equipment profile.

---

## Gym Equipment Profile (`gym_equipment.json`)

To ensure the AI never suggests exercises for machines you don't have, edit `gym_equipment.json` to reflect your gym:

- **`available_machines`**: Machines with specific notes (pin settings, seat notch, pulley ratio).
- **`free_weights_and_bars`**: Available barbells, trap bars, dumbbells, and benches.
- **`cable_attachments`**: Handles, ropes, wide bars.
- **`unavailable_or_lacking`**: Explicit list of missing machines (e.g. *"Hack Squat"*, *"Pendulum Squat"*).

You can edit this file directly or tell your AI agent:
> *"Add a Belt Squat machine to my gym inventory with notes: plate loaded."*  
The agent will call `update_gym_equipment` to update the file automatically.

---

## Available MCP Tools Reference

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `get_recent_workouts` | `limit` (int, default 5), `summarized` (bool, default True) | Fetches recent workout sessions with weights, reps, RPE, and set notes. |
| `get_routines` | *(none)* | Returns all routine templates with their IDs, titles, and exercise lists. |
| `get_routine_detail` | `routine_id` (str) | Fetches the full JSON configuration of a routine (sets, exercises, notes). |
| `search_exercises` | `query` (str), `limit` (int, default 10) | Searches the ~500 Hevy exercise templates by name, muscle, or equipment to find template IDs. |
| `update_routine` | `routine_id` (str), `routine_data` (str/json) | Replaces an existing routine with updated exercises, sets, weights, or notes in Hevy. |
| `create_routine` | `routine_data` (str/json) | Creates a brand new routine template in Hevy. |
| `get_gym_equipment` | *(none)* | Retrieves available machines, cable ratios, and unavailable machine limitations. |
| `update_gym_equipment` | `action`, `name`, `target_muscles`, `notes`, `...` | Adds, modifies, or removes equipment in the gym inventory. |
| `sync_local_cache` | *(none)* | Forces an immediate local refresh of JSON and Markdown summaries. |

---

## Example Prompts to Use with Your Agent

- **Progressive Overload Check:**
  > *"Analyze my last 3 Push sessions. How did my Smith machine incline bench press progress? Should I increase weight or reps for next time?"*
- **Routine Alteration:**
  > *"Inspect my 'Legs A' routine. Replace Bulgarian Split Squats with a machine exercise that targets the quads, checking my available gym equipment first. Then update the routine in Hevy."*
- **Deload / Volume Adjustment:**
  > *"I felt fatigued during my last two Pull sessions (check the notes and RPE). Adjust my 'Pull A' routine to drop 1 set per exercise for a deload week."*
- **Equipment Update:**
  > *"We no longer have the Pec Deck at my gym. Mark it as unavailable and update my routines that use it."*

---

## Service Management Commands

```bash
# Check status of the MCP server
systemctl --user status hevy-mcp.service

# View MCP server live logs
journalctl --user -u hevy-mcp.service -f

# Check status of the background sync timer
systemctl --user list-timers hevy-sync.timer

# View sync history logs
journalctl --user -u hevy-sync.service -n 50

# Manually trigger a background sync immediately
systemctl --user start hevy-sync.service
```
