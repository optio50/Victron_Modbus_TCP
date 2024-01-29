#!/usr/bin/python3

import paho.mqtt.publish as mqttpublish
import time

# GX Device I.P Address
ip = 'localhost'

#===================================

# VRM Portal ID from GX device. 
# Menu -->> Settings -->> "VRM Online Portal -->> VRM Portal ID"
VRMid = "xxxxxxxxxxx"

#===================================
mqttpublish.single("R/"+VRMid+"/system/0/Serial", hostname=ip, port=1883)
# "Keep-Alive" MQTT request
while True:
    mqttpublish.single("R/"+VRMid+"/system/0/Serial", hostname=ip, port=1883)
    #print("Keep Alive Sent")
    time.sleep(30) # send keep-alive every 30 seconds
