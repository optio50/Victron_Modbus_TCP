#!/usr/bin/env python3

'''
 it's assumed you have a keep alive setup on the Venus device itself.
 otherwise your messages will timeout after some seconds.
 its very simple to run the keep alive on the venus device in a while loop from the /data directory rc.local file.
 see the forever.py and keep-alive.py files in https://github.com/optio50/Victron_Modbus_TCP
 use them in the rc.local. Place a line in that file like this /data/forever.py /data/keep-alive.py &
 that means forever.py will run keep-alive.py in a while loop. Only if the keep-alive.py process dies will it loop to the next iteration
 it will also produce a log file so you can see how many times it has died.
'''

import paho.mqtt.client as mqtt
import paho.mqtt.publish as mqttpublish
import time
import json

# GX Device IP Address
ip = '192.168.20.167'

# VRM Portal ID from GX device.
VRMid = "b827eba69d10"

# MQTT Instance ID
MQTT_SolarCharger_ID = 288 # Victron Smart MPPT

SolarName         = None
SolarYield        = None
SolarError        = None
SolarChargerAmps  = None

print("\033[H\033[J") # Clear screen
print('\033[?25l', end="") # Hide Blinking Cursor
clear = "\033[K\033[1K" # Eliminates screen flashing / blink during refresh
                        # It clear's to end of line and moves to begining of line then prints the new line


# Define callback functions
# On Connect, subscribe to these topics. The 0 is the QOS
def on_connect(client, userdata, flags, rc):
    topics = [("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/ProductName",0),
            ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Settings/ChargeCurrentLimit",0),
            ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/History/Daily/0/Yield",0),
            ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/History/Daily/1/Yield",0),
            ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/History/Daily/0/MaxPower",0),
            ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/History/Daily/1/MaxPower",0),
            ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Yield/Power",0),
            ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Dc/0/Voltage",0),
            ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Dc/0/Current",0),
            ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Pv/V",0),
            ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/State",0),
            ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Mode",0),
            ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/ErrorCode",0)
            ]
    client.subscribe(topics)


def on_disconnect(client, userdata,rc=0):
    client.loop_stop()
    print("Loop Stopped")
    print("Disconnected result code "+str(rc))
    if rc != 0:
        print("Unexpected disconnection. Trying to reconnect")
        client.reconnect()



def on_message(client, userdata, msg):
    # make the variables global to be accessed outside of the scope.
    global  SolarName, SolarChargeLimit, SolarYield, SolarYieldYest, SolarWatts, SolarVolts, SolarChargerAmps, \
    MaxSolarWatts, MaxSolarWattsYest, SolarState, SolarError, SolarChargerMode, start, finish

    # as the topic messages come in, match them to your variable
    if msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/ProductName":
        SolarName = json.loads(msg.payload)["value"]
    elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Settings/ChargeCurrentLimit":
        SolarChargeLimit = json.loads(msg.payload)["value"]
    elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/History/Daily/0/Yield":
        SolarYield = json.loads(msg.payload)["value"]
    elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/History/Daily/1/Yield":
        SolarYieldYest = json.loads(msg.payload)["value"]
    elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Yield/Power":
        SolarWatts = json.loads(msg.payload)["value"]
    elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Pv/V":
        SolarVolts = json.loads(msg.payload)["value"]
    elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Dc/0/Current":
        SolarChargerAmps = json.loads(msg.payload)["value"]
    elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/History/Daily/0/MaxPower":
        MaxSolarWatts = json.loads(msg.payload)["value"]
    elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/History/Daily/1/MaxPower":
        MaxSolarWattsYest = json.loads(msg.payload)["value"]
    elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/State":
        SolarState = json.loads(msg.payload)["value"]
    elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/ErrorCode":
        SolarError = json.loads(msg.payload)["value"]
    elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Mode":
        SolarChargerMode = json.loads(msg.payload)["value"]
        if SolarChargerMode == 1:
            SolarChargerMode = "ON"
        elif SolarChargerMode == 4:
            SolarChargerMode = "OFF"



# Create a mqtt client instance
client = mqtt.Client()

# Assign callback functions
client.on_connect    = on_connect    # Do something on broker connection (Subscribe)
client.on_message    = on_message    # Do something on the message that comes in (look at the message topic and assign a variable)
                                     # Messages are only sent if they change or a full publish is requested (as in a keep alive)
client.on_disconnect = on_disconnect # If disconnect is expected then exit, else try to reconnect

# Connect to the broker
client.connect(ip, 1883, 60)

# Start the non blocking loop
client.loop_start()

# send a keep alive to do a full send of all topics (refresh)
mqttpublish.single("R/"+VRMid+"/keepalive", hostname=ip) # One time publish to refresh all topics

# The variables in this list were set to None at the top of the script. Loop until they are no longer None.
mqtt_list = [None]
# You dont need to verify all your variables with this loop. After you send the keep alive and have a few they should all be good.
# On a rare chance this could actually take up to the keep alive timeout
while None in mqtt_list:
    mqtt_list = [SolarName, SolarYield, SolarChargerAmps, SolarError]
    time.sleep(.001)

# Loop Counter
counter = 1

try:
    while True: # print the variable and value on the screen
        print("\033[0;0f") # move to col 0 row 0 to start the printing at the same spot everytime
                           # instead of having the text scoll up the screen just reuse the same spot on the screen
                           # the "clear" in the following lines erases the line and reprints wih new values from the begining of the line
        print(f"\033[38;5;202m==================Loop Number {counter} ==================\033[0m")
        print(f"{clear}SolarName...........: {SolarName}")
        print(f"{clear}SolarYield..........: {SolarYield:.2f}")
        print(f"{clear}SolarWatts..........: {int(SolarWatts)}") # The int is to change it to a whole number
        print(f"{clear}SolarVolts..........: {SolarVolts:.2f}") # The :.2f changes the resolution to 2 digits to the right
        print(f"{clear}SolarChargerAmps....: {SolarChargerAmps:.2f}")
        print(f"{clear}SolarYieldYest......: {SolarYieldYest:.2f}")
        print(f"{clear}MaxSolarWatts.......: {MaxSolarWatts}")
        print(f"{clear}SolarChargeLimit....: {SolarChargeLimit}")
        print(f"{clear}MaxSolarWattsYest...: {MaxSolarWattsYest}")
        print(f"{clear}SolarState..........: {SolarState}")
        print(f"{clear}SolarError..........: {SolarError}") # You need a dict to know the error. This is only the value.
        print(f"{clear}SolarChargerMode....: {SolarChargerMode}") # Normally You would need a dict to know the state
                                                                  # but there are only two choices (on or off)
                                                                  # so we make it known with an if statement in "on_message"
        print(f"\n\n\n Ctrl✞C to Exit")
        counter += 1 # increment the loop counter by 1 every loop
        time.sleep(.5) # how fast do you want to look for a new message? (refresh rate in seconds)

except KeyboardInterrupt:
        print("\033[J") # erase the screen from the cursor position to the end of the screen
        print('\033[?25h', end="") # Restore Blinking Cursor
        print("\033[K\033[1K") # Erase the line
        print("Ctrl-C Pressed")
        client.disconnect()
