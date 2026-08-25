# Where these should be placed?

1. `script.py`, `requirements.txt`, `.env`, `collect_gas.py`, `collect_temphum.py`, `config.py`, `fetch_gas.py`, `fetch_temphum.py`-> Raspberry Pi (in /Tunnel/)
2. `esp32-bridge.service` -> Raspberry Pi (move to /etc/systemd/system/)
   - Change path names in the code if necessary
3. `zrok-tunnel.service` -> Raspberry Pi (move to /etc/systemd/system/)
   - Change path names in the code if necessary
6. `zrok-reset-run.sh` -> Raspberry Pi (move to /usr/local/bin/)

# Setup

1. Run:
```bash
sudo chmod +x /usr/local/bin/zrok-reset-run.sh
```
2. Install zrok2
   - Do not share right now
   - Do not install zrok agent
3. Create zrok2 account
4. Enable zrok2 environment
5. For custom domain name:
```bash
zrok2 create name <name>
```
6. Public share:
```bash
zrok2 share public localhost:<port> -n public:<name>
```
7. Run:
```bash
sudo systemctl enable esp32-bridge.service
sudo systemctl start esp32-bridge.service
sudo systemctl enable zrok-tunnel.service
sudo systemctl start zrok-tunnel.service
```

- Name used is `restapi`
- Port used is `52471`
- Domain using zrok -> `restapi.shares.zrok.io`
- Domain is reserved using zrok, so, others cannot use this domain unless we remove this from us ourselves.


# CLI

## Fetch
```bash
curl -sL restapi.shares.zrok.io/temphum | jq .
```
- `/temphum` for temp and humidity  
- `/gas` for gas  

Outputs in JSON.

## Collect
### Start Task
```bash
curl -X POST https://restapi.shares.zrok.io/ctemphum \
     -H "Content-Type: application/json" \
     -d '{"duration": 30, "interval": 5}' | jq .
```
- `/ctemphum` for temp and humidity  
- `/cgas` for gas

- Outputs **task-id**

### Check if task has finished
```bash
curl https://restapi.shares.zrok.io/task/<task-id> | jq .                   
```
Outputs in JSON.


# Supabase
## Temp/Humidity Table
```sql
CREATE TABLE temphum (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  status TEXT DEFAULT 'pending',
  temp FLOAT,
  hum FLOAT,
  error_msg TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

-- RLS: Allow anon read/write for demo (restrict in prod)
ALTER TABLE temphum ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_access" ON temphum FOR ALL USING (true) WITH CHECK (true);
```

## Gas Table
```sql
CREATE TABLE gasval (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  status TEXT DEFAULT 'pending',
  gas FLOAT,
  error_msg TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

-- RLS: Allow anon read/write for demo (restrict in prod)
ALTER TABLE gasval ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_access" ON gasval FOR ALL USING (true) WITH CHECK (true);
```

## Additional Column Insertions
```sql
ALTER TABLE temphum 
ADD COLUMN IF NOT EXISTS is_collection BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS session_id TEXT,
ADD COLUMN IF NOT EXISTS sample_index INTEGER;

ALTER TABLE gasval 
ADD COLUMN IF NOT EXISTS is_collection BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS session_id TEXT,
ADD COLUMN IF NOT EXISTS sample_index INTEGER;

CREATE INDEX IF NOT EXISTS idx_temphum_collection ON temphum(session_id, sample_index);
CREATE INDEX IF NOT EXISTS idx_gasval_collection ON gasval(session_id, sample_index); 
```

## .env File
```
SUPABASE_URL=<url>
SUPABASE_KEY=<publishable key>
```