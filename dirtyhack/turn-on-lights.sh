#!/bin/bash

#username=$(/usr/bin/whoami)
#pid=$(ps -u $username e | grep -m 1 DBUS_SESSION_BUS_ADDRESS | awk '{print $1}')
#dbus=$(grep -z DBUS_SESSION_BUS_ADDRESS /proc/$pid/environ | sed 's/DBUS_SESSION_BUS_ADDRESS=//')
#export DBUS_SESSION_BUS_ADDRESS=$dbus

export DISPLAY=:0

temp=6500
d=`date`
echo $d 1st $temp color on >> /home/cds/tmp/heliolamp.log
/home/cds/dev/yeelight-shell-scripts/yeelight.sh 0 '"method":"set_power","params":["on"]'
/home/cds/dev/yeelight-shell-scripts/yeelight.sh 0 '"method":"set_ct_abx","params":['$temp',"smooth",200]'
/home/cds/bin/razer_client.php fcc68d

sleep 15m

temp=6100
d=`date`
echo $d 1st $temp color on >> /home/cds/tmp/heliolamp.log
/home/cds/dev/yeelight-shell-scripts/yeelight.sh 0 '"method":"set_power","params":["on"]'
/home/cds/dev/yeelight-shell-scripts/yeelight.sh 0 '"method":"set_ct_abx","params":['$temp',"smooth",200]'
/home/cds/bin/razer_client.php ffa463

sleep 15m

temp=5700
d=`date`
echo $d 1st $temp color on >> /home/cds/tmp/heliolamp.log
/home/cds/dev/yeelight-shell-scripts/yeelight.sh 0 '"method":"set_power","params":["on"]'
/home/cds/dev/yeelight-shell-scripts/yeelight.sh 0 '"method":"set_ct_abx","params":['$temp',"smooth",200]'
/home/cds/bin/razer_client.php fa9248

sleep 15m

temp=5300
d=`date`
echo $d 1st $temp color on >> /home/cds/tmp/heliolamp.log
/home/cds/dev/yeelight-shell-scripts/yeelight.sh 0 '"method":"set_power","params":["on"]'
/home/cds/dev/yeelight-shell-scripts/yeelight.sh 0 '"method":"set_ct_abx","params":['$temp',"smooth",200]'
/home/cds/bin/razer_client.php ff8b38

sleep 15m

temp=4900
d=`date`
echo $d 1st $temp color on >> /home/cds/tmp/heliolamp.log
/home/cds/dev/yeelight-shell-scripts/yeelight.sh 0 '"method":"set_power","params":["on"]'
/home/cds/dev/yeelight-shell-scripts/yeelight.sh 0 '"method":"set_ct_abx","params":['$temp',"smooth",200]'
/home/cds/bin/razer_client.php fc791c

sleep 15m

temp=4500
d=`date`
echo $d 1st $temp color on >> /home/cds/tmp/heliolamp.log
/home/cds/dev/yeelight-shell-scripts/yeelight.sh 0 '"method":"set_power","params":["on"]'
/home/cds/dev/yeelight-shell-scripts/yeelight.sh 0 '"method":"set_ct_abx","params":['$temp',"smooth",200]'
/home/cds/bin/razer_client.php b85212

sleep 15m

temp=4100
d=`date`
echo $d 1st $temp color on >> /home/cds/tmp/heliolamp.log
/home/cds/dev/yeelight-shell-scripts/yeelight.sh 0 '"method":"set_power","params":["on"]'
/home/cds/dev/yeelight-shell-scripts/yeelight.sh 0 '"method":"set_ct_abx","params":['$temp',"smooth",200]'
/home/cds/bin/razer_client.php a34410

sleep 15m

temp=3700
d=`date`
echo $d 1st $temp color on >> /home/cds/tmp/heliolamp.log
/home/cds/dev/yeelight-shell-scripts/yeelight.sh 0 '"method":"set_power","params":["on"]'
/home/cds/dev/yeelight-shell-scripts/yeelight.sh 0 '"method":"set_ct_abx","params":['$temp',"smooth",200]'
/home/cds/bin/razer_client.php 8c320e

sleep 15m

temp=3300
d=`date`
echo $d 1st $temp color on >> /home/cds/tmp/heliolamp.log
/home/cds/dev/yeelight-shell-scripts/yeelight.sh 0 '"method":"set_power","params":["on"]'
/home/cds/dev/yeelight-shell-scripts/yeelight.sh 0 '"method":"set_ct_abx","params":['$temp',"smooth",200]'
#/home/cds/bin/razer_client.php 8c320e

echo '{"success":"true"}'
