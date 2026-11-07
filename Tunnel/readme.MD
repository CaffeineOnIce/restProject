# Tunnel (Architecture 1: Zrok)

Remote client → Zrok public share → Flask API on the Raspberry Pi → ESP32 (via mDNS).
Routes, methods and response format are the same as the Poll (Render) API.

# Install
```bash
sudo apt update
sudo apt install avahi-daemon avahi-utils libnss-mdns
sudo systemctl enable --now avahi-daemon
```

# Where these should be placed?

1. `script.py`, `requirements.txt`, `.env`, `collect_gas.py`, `collect_temphum.py`, `config.py`, `fetch_gas.py`, `fetch_temphum.py` -> Raspberry Pi (in `/home/dietpi/API Cloud/REST/Tunnel/`)
2. `esp32-bridge.service` -> Raspberry Pi (move to `/etc/systemd/system/`)
   - Paths contain a space (`API Cloud`), so they are quoted in `ExecStart`. Change them if your folder differs.
3. `zrok-tunnel.service` -> Raspberry Pi (move to `/etc/systemd/system/`)
4. `zrok-reset-run.sh` -> Raspberry Pi (move to `/usr/local/bin/`)
5. `UI.py` -> laptop (dashboard, runs on port `8081`)

# Setup

1. Create the virtual environment on the Pi:
```bash
cd "/home/dietpi/API Cloud/REST/Tunnel"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```
2. Make the Zrok script executable:
```bash
sudo chmod +x /usr/local/bin/zrok-reset-run.sh
```
3. Install zrok2
   - Do not share right now
   - Do not install zrok agent
4. Create a zrok2 account
5. Enable the zrok2 environment **as the `dietpi` user** (no `sudo`). The tunnel service runs as `dietpi` and uses `/home/dietpi/.zrok2`:
```bash
zrok2 enable <account-token>
zrok2 status
```
6. Run:
```bash
sudo systemctl daemon-reload
sudo systemctl enable esp32-bridge.service zrok-tunnel.service
sudo systemctl start esp32-bridge.service zrok-tunnel.service
```
- Name used is `restapi5`
- Port used is `52471`
- Domain using zrok -> `restapi5.shares.zrok.io`
- The name is reserved in the `public` namespace, so others cannot use this domain unless we remove it ourselves.
- `zrok-reset-run.sh` deletes any leftover `restapi5` share, creates the name only if it does not exist, then starts the share.

## Check
```bash
sudo systemctl status esp32-bridge.service zrok-tunnel.service
sudo journalctl -u zrok-tunnel.service -n 30 --no-pager -l
zrok2 overview
```
A healthy tunnel shows `zrok2 share public localhost:52471 -n public:restapi5 --headless` as the running process.

## Switching between architectures
The Tunnel and Poll setups share the ESP32, so run only one at a time.
```bash
# Poll -> Tunnel
sudo systemctl stop rest-poll.service
sudo systemctl start esp32-bridge.service zrok-tunnel.service

# Tunnel -> Poll
sudo systemctl stop zrok-tunnel.service esp32-bridge.service
sudo systemctl start rest-poll.service
```

## Troubleshooting
- `203/EXEC` from `esp32-bridge.service`: the `.venv` is missing or the path in the service file is wrong.
- `Could not resolve host: esp32.local` on the Pi: mDNS is not working on this network. Check `avahi-resolve -n esp32.local`, or set `ESP32_URL` in `.env` to the ESP32's IP. The Pi and the ESP32 must be on the same network.
- `401 unauthorized` from `zrok2 share`: the Zrok environment is stale. As `dietpi`, move `~/.zrok2` aside and run `zrok2 enable <account-token>` again.
- `authentication attempt failed ... netfoundry.io ... context deadline exceeded`: the network cannot reach Zrok's relay. Use a different network (e.g. a phone hotspot).
- Requests that take ~15–20 s after an idle gap: the network's IPv6 is broken and connections wait for it to time out. Disable IPv6 on the Pi (`/etc/sysctl.d/99-no-ipv6.conf`) or use another network.


# CLI

Same routes and response format as the Poll (Render) API.

## Fetch
```bash
curl -s -X POST https://restapi5.shares.zrok.io/th | jq .
```
- `/th` for temp and humidity  
- `/gas` for gas  

Outputs in JSON (`temp`/`hum` or `gas`, plus a `timing` object with per-hop timestamps in epoch ms: `t_pi_rx`, `t_esp_start`, `t_esp_end`, `t_db_done`, `t_pi_tx`). Errors return HTTP 500 with `{"error": ..., "timing": ...}`.

Local test on the Pi (bypasses Zrok):
```bash
curl -s -X POST http://localhost:52471/th | jq .
```

## Collect
### Start Task
```bash
curl -X POST https://restapi5.shares.zrok.io/cth \
     -H "Content-Type: application/json" \
     -d '{"duration": 30, "interval": 5}' | jq .
```
- `/cth` for temp and humidity  
- `/cgas` for gas
- `duration` and `interval` default to 30 s and 5 s if omitted

- Outputs **task-id** (HTTP 202)

### Check if task has finished
```bash
curl https://restapi5.shares.zrok.io/task/<task-id> | jq .
```
Outputs in JSON (HTTP 200 completed, 202 running, 500 error, 404 not found).

## Health
```bash
curl https://restapi5.shares.zrok.io/health | jq .
```


# Supabase

Both architectures use the same Supabase project and tables. The Tunnel code only writes `status`, `temp`/`hum` or `gas`, `error_msg` and `completed_at`; the other columns are used by the Poll architecture.

## Temp/Humidity Table
```sql
CREATE TABLE IF NOT EXISTS temphum (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT DEFAULT 'pending',
    temp FLOAT,
    hum FLOAT,
    error_msg TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);
```

## Gas Table
```sql
CREATE TABLE IF NOT EXISTS gasval (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT DEFAULT 'pending',
    gas FLOAT,
    error_msg TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);
```

## Collection Columns (Poll)
```sql
ALTER TABLE temphum ADD COLUMN IF NOT EXISTS duration INT;
ALTER TABLE temphum ADD COLUMN IF NOT EXISTS interval INT;
ALTER TABLE temphum ADD COLUMN IF NOT EXISTS result_data JSONB;

ALTER TABLE gasval ADD COLUMN IF NOT EXISTS duration INT;
ALTER TABLE gasval ADD COLUMN IF NOT EXISTS interval INT;
ALTER TABLE gasval ADD COLUMN IF NOT EXISTS result_data JSONB;
```

## Per-Hop Timing Columns (Poll)
Epoch milliseconds (UTC), written by the Poll gateway and returned by Render in the `timing` object. The Tunnel returns its timing directly in the HTTP response, so it does not write these.
```sql
ALTER TABLE temphum
  ADD COLUMN IF NOT EXISTS t_pi_seen   DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS t_esp_start DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS t_esp_end   DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS t_db_done   DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS t_pi_done   DOUBLE PRECISION;

ALTER TABLE gasval
  ADD COLUMN IF NOT EXISTS t_pi_seen   DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS t_esp_start DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS t_esp_end   DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS t_db_done   DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS t_pi_done   DOUBLE PRECISION;
```

## Indexes
```sql
CREATE INDEX IF NOT EXISTS idx_temphum_status ON temphum(status);
CREATE INDEX IF NOT EXISTS idx_gasval_status ON gasval(status);
CREATE INDEX IF NOT EXISTS idx_temphum_created ON temphum(created_at);
CREATE INDEX IF NOT EXISTS idx_gasval_created ON gasval(created_at);
```

## Row Level Security
Open policies for the demo (anyone with the publishable key can read/write). Restrict these in production.
```sql
ALTER TABLE temphum ENABLE ROW LEVEL SECURITY;
ALTER TABLE gasval ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable all access for all users" ON temphum FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Enable all access for all users" ON gasval FOR ALL USING (true) WITH CHECK (true);
```

## .env File
```env
SUPABASE_URL=<your_supabase_url>
SUPABASE_KEY=<your_supabase_publishable_key>
ESP32_URL=http://esp32.local
```
Use the same `SUPABASE_URL` and `SUPABASE_KEY` as the Poll `.env`. If `esp32.local` does not resolve on the Pi, use the ESP32's IP (e.g. `ESP32_URL=http://192.168.1.6`).
