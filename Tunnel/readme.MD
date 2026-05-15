# Where these should be placed?

1. `script.py` -> Raspberry Pi (in /Tunnel)
2. `esp32-bridge.service` -> Raspberry Pi (move to /etc/systemd/system)
   - Change path names in the code if necessary
3. `zrok-tunnel.service` -> Raspberry Pi (move to /etc/systemd/system)
   - Change path names in the code if necessary
4. `.env` -> Raspberry Pi (in /Tunnel)
5. `requirements.txt` -> Raspberry Pi (in /Tunnel)
6. `zrok-reset-run.sh` -> Raspberry Pi (move to /usr/local/bin)

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

# Steps

## Calling
```bash
curl -sL restapi.shares.zrok.io/temphum | jq
```
- `/temphum` for temp and humidity  
- `/gas` for gas  

Outputs in JSON.