#!/usr/bin/python3

import paho.mqtt.publish as mqttpublish
from time import sleep

# GX Device I.P Address
ip = '192.168.20.156'

#===================================

# VRM Portal ID from GX device. 
# Menu -->> Settings -->> "VRM Online Portal -->> VRM Portal ID"
VRMid = "XXXXXXXXXXX"

#===================================
mqttpublish.single("R/"+VRMid+"/system/0/Serial", hostname=ip, port=1883)

# "Keep-Alive" MQTT request
while True:
    mqttpublish.single("R/"+VRMid+"/system/0/Serial", hostname=ip, port=1883)
    print("Keep Alive Sent")
    sleep(10)
