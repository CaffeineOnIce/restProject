#!/bin/bash
export HOME=/home/dietpi

# Remove a leftover share from a previous run, if any
SHARE_TOKEN=$(zrok2 list shares | grep "restapi5" | awk '{print $2}')
if [ -n "$SHARE_TOKEN" ]; then
    zrok2 delete share "$SHARE_TOKEN"
fi

# Keep the reserved name; create it only if it doesn't exist (409 = already exists, fine)
zrok2 create name -n public restapi5 2>/dev/null || true

exec zrok2 share public localhost:52471 -n public:restapi5 --headless
