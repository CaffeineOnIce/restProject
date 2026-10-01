# Install
```bash
sudo apt update
sudo apt install avahi-daemon avahi-utils libnss-mdns
```

# Where these should be placed?

1. `script.py`, `requirements.txt`, `.env`, `collect_gas.py`, `collect_temphum.py`, `config.py`, `fetch_gas.py`, `fetch_temphum.py` -> Raspberry Pi (in `/Poll/`)
2. `main.py` -> Render (via GitHub repository)
3. `rest-poll.service` -> Raspberry Pi (move to `/etc/systemd/system/`)
   - Change path names in the code/service file if necessary.

# Setup

1. Upload the `main.py` (and optionally `requirements.txt`) to GitHub using a new or existing repository.
2. Select the GitHub repository in Render and connect it.
3. Set the Start Command to:
   ```bash
   gunicorn main:app
   ```
4. Configure environment variables (from your `.env` file) and other deployment parameters, then deploy.
5. On the Raspberry Pi, run:
   ```bash
   sudo systemctl enable rest-poll.service
   sudo systemctl start rest-poll.service
   ```

# CLI

## Fetch / Trigger
```bash
curl -s -X POST https://restproject-inbd.onrender.com/th | jq .
```
- `/th` for temp and humidity  
- `/gas` for gas  

Outputs in JSON.

# Supabase

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

ALTER TABLE temphum ADD COLUMN IF NOT EXISTS duration INT;
ALTER TABLE temphum ADD COLUMN IF NOT EXISTS interval INT;
ALTER TABLE temphum ADD COLUMN IF NOT EXISTS result_data JSONB;

CREATE TABLE IF NOT EXISTS gasval (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT DEFAULT 'pending',
    gas FLOAT,
    error_msg TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

ALTER TABLE gasval ADD COLUMN IF NOT EXISTS duration INT;
ALTER TABLE gasval ADD COLUMN IF NOT EXISTS interval INT;
ALTER TABLE gasval ADD COLUMN IF NOT EXISTS result_data JSONB;

CREATE INDEX IF NOT EXISTS idx_temphum_status ON temphum(status);
CREATE INDEX IF NOT EXISTS idx_gasval_status ON gasval(status);
CREATE INDEX IF NOT EXISTS idx_temphum_created ON temphum(created_at);
CREATE INDEX IF NOT EXISTS idx_gasval_created ON gasval(created_at);

-- Enable Row Level Security (RLS)
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
