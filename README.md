# Hevy Sync & MCP Server

An automated synchronization daemon and [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for [Hevy](https://hevy.com). It enables AI agents (such as **Google Antigravity**, **Claude Desktop**, or **Cursor**) to inspect workout history, evaluate RPE and progressive overload, and programmatically create or alter training routines directly in a Hevy account.

---

## Deployment Topologies

This system can be deployed in either a distributed (two-machine) or single-machine configuration:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Deployment Architecture                         │
│                                                                        │
│  [Host / Server]                                                       │
│  ┌──────────────────────┐        ┌──────────────────────────────────┐  │
│  │ systemd Timer (4hr)  │        │       MCP Server (Port 8000)     │  │
│  │     sync_job.py      │        │          (mcp_server.py)         │  │
│  └──────────┬───────────┘        └─────────────────▲────────────────┘  │
│             │                                      │                   │
│             ▼                                      │ (Streamable HTTP) │
│   latest_workouts_summary.md                       │                   │
│   latest_hevy_summary.json                         │                   │
│   routines_backup.json                             │                   │
│   gym_equipment.json                               │                   │
│                                                    │                   │
│  ──────────────────────────────────────────────────┼─────────────────  │
│  Topology A (Two Machines): Tailscale / LAN / VPN  │                   │
│  Topology B (Single Machine): localhost            │                   │
│  ──────────────────────────────────────────────────┼─────────────────  │
│                                                    │                   │
│  [Client / Agent Host]                             │                   │
│  ┌─────────────────────────────────────────────────┴────────────────┐  │
│  │ AI Agent (Antigravity / Claude Desktop / Cursor)                 │  │
│  │  - Queries workout history, sets, reps, weights, RPE, and notes  │  │
│  │  - Inspects gym equipment inventory and machine quirks           │  │
│  │  - Searches exercise templates                                   │  │
│  │  - Pushes routine modifications via Hevy API                     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

- **Topology A (Distributed / Two Machines):** The sync daemon and MCP service run on a server, NAS, or remote homelab. The AI agent runs on a separate workstation or laptop, connecting to `http://<SERVER_IP>:8000/mcp` over Tailscale, a VPN, or local network.
- **Topology B (Single Machine):** Both the MCP service and the AI agent run on the same computer, communicating over `http://localhost:8000/mcp`.

---

## Features

- **Two-Way Integration:** Reads workout history logs and pushes updated routines back to Hevy via `PUT /v1/routines/{id}`.
- **Gym Equipment Context (`gym_equipment.json`):** Supplies available machines, cable pulley ratios (e.g. 2:1), seat/pin adjustments, and unavailable equipment so the AI does not prescribe unavailable gym machines.
- **9 MCP Tools + 1 Resource:** Standard MCP Streamable HTTP interface.
- **Automated Background Sync:** Systemd timer pulls fresh workouts and routines periodically, generating Markdown and JSON summaries.
- **Privacy & Secret Protection:** Pre-configured `.gitignore` prevents `.env`, workout history logs, and personal routine dumps from being tracked in version control.

---

## Host Setup (From Scratch)

### 1. Prerequisites
- Linux (Ubuntu, Debian, Arch, Fedora) or macOS/WSL
- Python 3.10+
- [Hevy Pro](https://hevy.com) subscription (required for developer API access)

### 2. Clone and Setup Environment
```bash
git clone https://github.com/<your-username>/hevy-sync.git
cd hevy-sync

# Create a virtual environment and install dependencies
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 3. Configure API Credentials
Generate an API key at [hevy.com/settings?developer](https://hevy.com/settings?developer).

```bash
cp .env.example .env
nano .env
```
Populate the configuration:
```env
HEVY_API_KEY=your_hevy_api_key_here
BASE_URL=https://api.hevyapp.com/v1
```

### 4. Run an Initial Sync
Verify API connectivity and generate initial cache files:
```bash
.venv/bin/python sync_job.py
```
This produces `latest_workouts_summary.md`, `latest_hevy_summary.json`, `routines_backup.json`, and populates `exercise_templates.json`.

---

## Background Services (systemd)

On Linux systems, `systemd` user services keep the MCP server and sync timer running persistently.

To allow user services to run without an active login session, enable user lingering:
```bash
loginctl enable-linger $USER
mkdir -p ~/.config/systemd/user
```

### 1. MCP Server Service (Streamable HTTP on Port 8000)

Create `~/.config/systemd/user/hevy-mcp.service`:
```ini
[Unit]
Description=Hevy MCP Server (Streamable HTTP)
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/hevy-sync
ExecStart=/path/to/hevy-sync/.venv/bin/python /path/to/hevy-sync/mcp_server.py --transport streamable-http --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```
> **Note:** Replace `/path/to/hevy-sync` with the absolute path to the repository directory.

Enable and start the service:
```bash
systemctl --user daemon-reload
systemctl --user enable --now hevy-mcp.service
```

### 2. Periodic Sync Timer (Every 4 Hours)

Create `~/.config/systemd/user/hevy-sync.service`:
```ini
[Unit]
Description=Hevy Workout and Routine Sync
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/path/to/hevy-sync
ExecStart=/path/to/hevy-sync/.venv/bin/python /path/to/hevy-sync/sync_job.py
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

Enable and start the timer:
```bash
systemctl --user daemon-reload
systemctl --user enable --now hevy-sync.timer
```

---

## Connecting the AI Agent (Client Configuration)

MCP clients connect to the server via **Streamable HTTP**.

### 1. Configure `mcp_config.json`

Add the server to the client's MCP configuration file:

- **Windows:** `C:\Users\<Username>\.gemini\config\mcp_config.json` (or `%USERPROFILE%\.gemini\config\mcp_config.json`)
- **macOS / Linux:** `~/.gemini/config/mcp_config.json`

#### For Topology A (Distributed / Remote Host):
```json
{
  "mcpServers": {
    "hevy": {
      "url": "http://<SERVER_IP>:8000/mcp"
    }
  }
}
```
*(Replace `<SERVER_IP>` with the server's Tailscale, VPN, or local network IP).*

#### For Topology B (Single Machine / Local):
```json
{
  "mcpServers": {
    "hevy": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### 2. Restart the Agent Application
> [!IMPORTANT]
> Antigravity and other MCP desktop clients load `mcp_config.json` on application startup. Fully restart the application after saving the configuration file.

### 3. Verification
Open a new conversation with the agent and submit:
> *"What tools are available for Hevy or gym equipment?"*

The agent should report the 9 Hevy tools and read the gym equipment profile.

---

## Gym Equipment Profile (`gym_equipment.json`)

To ensure the AI suggests only available exercises and accounts for machine quirks, `gym_equipment.json` defines the equipment baseline:

- **`available_machines`**: Machines and specific setup notes (e.g. seat notch, pin hole, pulley ratio).
- **`free_weights_and_bars`**: Barbells, trap bars, dumbbells, and benches.
- **`cable_attachments`**: Attachment handles, ropes, and bars.
- **`unavailable_or_lacking`**: Missing equipment to avoid (e.g. *"Hack Squat"*, *"Pendulum Squat"*).

The file can be edited directly or modified conversationally through the agent:
> *"Add a Belt Squat machine to the gym equipment inventory with notes: plate loaded."*  
The agent invokes `update_gym_equipment` to persist the update.

---

## Available MCP Tools Reference

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `get_recent_workouts` | `limit` (int, default 5), `summarized` (bool, default True) | Fetches recent workout sessions with weights, reps, RPE, and set notes. |
| `get_routines` | *(none)* | Returns all routine templates with routine IDs, titles, and exercise breakdown. |
| `get_routine_detail` | `routine_id` (str) | Fetches the full JSON configuration of a routine (sets, exercises, notes). |
| `search_exercises` | `query` (str), `limit` (int, default 10) | Searches exercise templates by name, muscle, or equipment to locate template IDs. |
| `update_routine` | `routine_id` (str), `routine_data` (str/json) | Replaces an existing routine with updated exercises, sets, weights, or notes in Hevy. |
| `create_routine` | `routine_data` (str/json) | Creates a new routine template in Hevy. |
| `get_gym_equipment` | *(none)* | Retrieves available machines, cable ratios, and unavailable machine limitations. |
| `update_gym_equipment` | `action`, `name`, `target_muscles`, `notes`, `...` | Adds, modifies, or removes equipment in the gym inventory. |
| `sync_local_cache` | *(none)* | Forces an immediate local refresh of JSON and Markdown summaries. |

---

## Example Interaction Scenarios

- **Progressive Overload Assessment:**
  > *"Analyze the last 3 Push sessions. How did the Smith machine incline bench press progress? Should weight or reps be adjusted for the next session?"*
- **Routine Alteration:**
  > *"Inspect the 'Legs A' routine. Replace Bulgarian Split Squats with an available quad-focused machine exercise, referencing the gym equipment profile. Then update the routine in Hevy."*
- **Deload / Volume Adjustment:**
  > *"Based on the RPE and fatigue notes in the recent Pull sessions, adjust the 'Pull A' routine to reduce volume by 1 set per exercise for a deload week."*
- **Equipment Update:**
  > *"The Pec Deck is currently out of order. Mark it as unavailable and suggest replacements in existing routines."*

---

## Service Management Commands

```bash
# Check MCP server status
systemctl --user status hevy-mcp.service

# View MCP server live logs
journalctl --user -u hevy-mcp.service -f

# Check sync timer schedule
systemctl --user list-timers hevy-sync.timer

# View sync history logs
journalctl --user -u hevy-sync.service -n 50

# Manually trigger a sync execution
systemctl --user start hevy-sync.service
```
