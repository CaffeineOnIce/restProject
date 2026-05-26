#!/bin/bash
export HOME=/root

SHARE_TOKEN=$(zrok2 list shares | grep "restapi" | awk '{print $2}')

if [ ! -z "$SHARE_TOKEN" ]; then
    zrok2 delete share "$SHARE_TOKEN"
fi

zrok2 delete name -n public restapi
zrok2 create name -n public restapi
zrok2 share public localhost:52471 -n public:restapi --headless
