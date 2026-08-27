# Where these should be placed?

1. `script.py` -> Raspberry Pi (in /Poll)
2. `main.py` -> Render
3. `rest-poll.service` -> Raspberry Pi (move to /etc/systemd/system)
   - Change path names in the code if necessary
4. `.env` -> Render AND Raspberry Pi (in /Poll)
5. `requirements.txt` -> Render AND Raspberry Pi (in /Poll)

# Steps
1. Upload the `main.py` to Github using a new/old repository
2. Select the `main.py` in Render using the Github repository and continue
3. Start Command: 
```bash
gunicorn main:app
```
4. Configure other parameters and deploy
5. Run:
```bash
sudo systemctl enable rest-poll.service
sudo systemctl start rest-poll.service
```

## Calling
```bash
curl -s -X POST https://restproject-h1uq.onrender.com/gas | jq
```
- `/temphum` for temp and humidity  
- `/gas` for gas  

Outputs in JSON.