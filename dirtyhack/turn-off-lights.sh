#!/bin/bash

export DISPLAY=:0

/home/cds/dev/yeelight-shell-scripts/yeelight.sh 0 '"method":"set_power","params":["off"]'
/usr/local/bin/razer-cli -a -c ffffff -b 0
