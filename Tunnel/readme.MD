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

- Outputs task-id

### Check for data
```bash
curl https://restapi.shares.zrok.io/task/<task-id> | jq .                   
```
Outputs in JSON.
