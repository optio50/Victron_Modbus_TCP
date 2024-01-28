#!/usr/bin/env python3

# This file is for a Raspi and a single Victron SmartSolar Charger.
# It uses MQTT for "all" of the values (Victron FlashMQ). Should have a beta or VERY recent Venus firmware.

import os
import random
import json
import re
import sys
import time
import socket
from datetime import datetime
from datetime import timedelta
from threading import Thread
from time import gmtime, strftime
from itertools import cycle # Flash the LED's

from PyQt5 import QtGui, uic, QtCore, QtWidgets, QtWebEngineWidgets
from PyQt5.QtWebEngineWidgets import *
from PyQt5.QtWebEngineWidgets import QWebEngineSettings as QWebSettings
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QColor, QPalette
#from PyQt5.QtWebKit import QWebSettings

# PGlive (Charts)
import pyqtgraph as pg
from pyqtgraph import mkPen
from pglive.kwargs import Axis, Crosshair, LeadingLine
from pglive.sources.data_connector import DataConnector
from pglive.sources.live_axis import LiveAxis
from pglive.sources.live_axis_range import LiveAxisRange
from pglive.sources.live_categorized_bar_plot import LiveCategorizedBarPlot
from pglive.sources.live_plot import LiveLinePlot, LiveVBarPlot
from pglive.sources.live_plot_widget import LivePlotWidget

# MQTT
import paho.mqtt.client as mqtt
import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as mqttpublish

try:
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-logging"
    os.putenv("QT_LOGGING_RULES", "*.debug=false;qt.qpa.*=False")
except Exception as e:
    print(f"An error occurred: {str(e)}") # Prevents QT mouse click button bug   qt.qpa.xcb: QXcbConnection: XCB error: 3 (BadWindow)
#                                                               https://bugreports.qt.io/browse/QTBUG-56893
'''
This script "ONLY" uses MQTT for the variables. Enable on the GX device
A keepalive request should be hosted on the venus device instead of in this script.
https://github.com/optio50/Victron_Modbus_TCP    forever.py & keep-alive.py
'''
#===================================
''' GX Device I.P Address '''
ip = '192.168.20.167'
#===================================
'''
VRM Portal ID from GX device.
This ID is needed even with no internet access as its the name of your venus device.
Menu -->> Settings -->> "VRM Online Portal -->> VRM Portal ID" '''
#===================================
VRMid = "zzzzzzzzzzzzz"
#===================================
''' Weather URL example https://wttr.in/dallas+texas ,use something such as manchester+england or nsw+australia or dallas+texas or a zip code'''
weather_url = "https://wttr.in/nsw+australia"
#weather_url = "https://www.worldweatheronline.com/v2/weather.aspx?q=90210"
#weather_url = "https://www.weather-us.com/en/california-usa/beverly-hills-long-term-weather-forecast?f,in,in,mi"
#weather_url = "https://www.30dayweather.com/en/d/united-states/california/90210-beverly-hills/"
#weather_url = "https://www.forecast.co.uk/united-states/dallas.html"
#weather_url = "https://www.bing.com/search?q=10+day+forecast+in+dallas+texas"
#weather_url = "https://www.msn.com/en-us/weather/forecast/in-Dallas,TX"
#weather_url = "https://www.timeanddate.com/weather/@z-us-90210/ext"
#weather_url = "https://forecast7.com/en/30d27n97d74/austin/?unit=us"
#weather_url = "https://forecast.weather.gov/MapClick.php?CityName=Beverly+Hills&state=CA&site=LOX&lat=34.0995&lon=-118.414"
'''
==========================================================
                 Change the Variables Below               
==========================================================
==========================================================
'''
#===================================
# BMV and Inverter Installed? Y or N
BMV_Installed = "y"
Inverter_Installed = "n"
#===================================

# Victron Smart Solar Charger (Required)
MQTT_SolarCharger_ID = 288 # Victron Smart MPPT

if BMV_Installed.lower() == "y":
    MQTT_BMV_ID = 289 # Victron Smart Shunt or BMV (Optional)
else:
    MQTT_BMV_ID = None

# Phoenix Inverter installed? Y or N

if Inverter_Installed.lower() == "y":
    MQTT_Inverter_ID = 290 # Victron Phoenix Inverter (Optional)
else:
    MQTT_Inverter_ID = None

#===================================
# Describe The Solar PAnel Array
Array1 = "Portable 100W Soft Panel"
#===================================
# Temperature Sensor Needed
# Alarm LED for Battery Temperature Range Deg F
Batt_Lo = 35 # Low Temperature °F
Batt_Hi = 80 # High Temperature °F
'''
==========================================================
                Change the Variables Above                
==========================================================
==========================================================
'''

#For the while loop after the keep alive publish. (mqtt_list)
SolarName           = None
Installed_Version   = None
SolarChargeLimit    = None
SolarError          = None
BatteryVolts        = None
BatteryAmps         = None

flag_connected      = 0
#===================================
# Datetime object containing date and time for App Start
nowStart = datetime.now()
# Fri 21 Jan 2022     09:06:57 PM
dt_stringStart = nowStart.strftime("%a %d %b %Y     %r")
#===================================
big_tab = "\t"*15 # used in the status bar because it compresses text
#===================================
# This will blink the Alarm LED's on and off
blinkred_Battery_Temp       = cycle(["rgb(255, 0, 0)",   "rgb(28, 28, 0)"]) # Red
blinkred_Inverter_Temp      = cycle(["rgb(255, 0, 0)",   "rgb(28, 28, 0)"]) # Red
blinkred_Inverter_Overload  = cycle(["rgb(255, 0, 0)",   "rgb(28, 28, 0)"]) # Red
blinkgreen_MQTT             = cycle(["rgb(0,154 ,23  )",   "rgb(28, 28, 0)"]) # Blinking Green LED for MQTT connection
#===================================
InverterStateDict = {0:   "OFF",
                     1:   "Searching",
                     2:   "Fault",
                     9:   "Inverting"}
#===================================
InverterModeDict =  {2:   "ON",
                     4:   "OFF",
                     5:   "Low Power/ECO"}
#===================================
SolarStateDict = {0:   "OFF",
                  2:   "Fault",
                  3:   "Bulk",
                  4:   "Absorption",
                  5:   "Float",
                  6:   "Storage",
                  7:   "Equalize",
                  11:  "Other Hub-1",
                  245: "Wake-Up",
                  252: "EXT Control"}
#===================================
SolarErrorDict = {0:"No Error",
                    1:"Error 1: Battery temperature too high",
                    2:"Error 2: Battery voltage too high",
                    3:"Error 3: Battery temperature sensor miswired (+)",
                    4:"Error 4: Battery temperature sensor miswired (-)",
                    5:"Error 5: Remote temperature sensor failure (connection lost)",
                    6:"Error 6: Battery voltage sense miswired (+)",
                    7:"Error 7: Battery voltage sense miswired (-)",
                    8:"Error 8: Battery voltage sense disconnected",
                    11:"Error 11: Battery high ripple voltage",
                    14:"Error 14: Battery low temperature",
                    17:"Error 17: Controller overheated despite reduced output current",
                    18:"Error 18: Controller over-current",
                    20:"Error 20: Maximum Bulk-time exceeded",
                    21:"Error 21: Current sensor issue",
                    22:"Error 22: Internal temperature sensor failure",
                    23:"Error 23: Internal temperature sensor failure",
                    24:"Error 24: Fan failure",
                    26:"Error 26: Terminal overheated",
                    27:"Error 27: Charger short circuit",
                    28:"Error 28: Power stage issue",
                    29:"Error 29: Over-Charge protection",
                    33:"Error 33: PV Input over-voltage",
                    34:"Error 34: PV Input over-current",
                    35:"Error 35: PV Input over-power",
                    38:"Error 38: PV Input is internally shorted in order to protect the battery from over-charging",
                    39:"Error 39: PV Input is internally shorted in order to protect the battery from over-charging",
                    40:"Error 40: PV Input failed to shutdown",
                    41:"Error 41: Inverter shutdown (PV isolation)",
                    42:"Error 42: Inverter shutdown (PV isolation)",
                    43:"Error 43: Inverter shutdown (Ground Fault)",
                    50:"Error 50: Inverter overload, Inverter peak current",
                    51:"Error 51: Inverter temperature too high",
                    52:"Error 52: Inverter overload, Inverter peak current",
                    53:"Error 53: Inverter output voltage",
                    54:"Error 54: Inverter output voltage",
                    55:"Error 55: Inverter self test failed",
                    56:"Error 56: Inverter self test failed",
                    57:"Error 57: Inverter ac voltage on output",
                    58:"Error 58: Inverter self test failed",
                    67:"Error 67: BMS Connection lost",
                    68:"Error 68: Network misconfigured",
                    69:"Error 69: Network misconfigured",
                    70:"Error 70: Network misconfigured",
                    71:"Error 71: Network misconfigured",
                    80:"Error 80: PV Input is internally shorted in order to protect the battery from over-charging",
                    81:"Error 81: PV Input is internally shorted in order to protect the battery from over-charging",
                    82:"Error 82: PV Input is internally shorted in order to protect the battery from over-charging",
                    83:"Error 83: PV Input is internally shorted in order to protect the battery from over-charging",
                    84:"Error 84: PV Input is internally shorted in order to protect the battery from over-charging",
                    85:"Error 85: PV Input is internally shorted in order to protect the battery from over-charging",
                    86:"Error 86: PV Input is internally shorted in order to protect the battery from over-charging",
                    87:"Error 87: PV Input is internally shorted in order to protect the battery from over-charging",
                    114:"Error 114: CPU temperature too high",
                    116:"Error 116: Calibration data lost",
                    117:"Error 117: Incompatible firmware",
                    119:"Error 119: Settings data lost",
                    121:"Error 121: Tester fail",
                    200:"Error 200: Internal DC voltage error",
                    201:"Error 201: Internal DC voltage error",
                    202:"Error 202: Internal GFCI sensor error",
                    203:"Error 203: Internal supply voltage error",
                    205:"Error 205: Internal supply voltage error",
                    212:"Error 212: Internal supply voltage error",
                    215:"Error 215: Internal supply voltage error"
                  }
#===================================
# Begin MQTT Section
# All the topics you want to subscripbe to
def on_connect(client, userdata, flags, rc):
    global flag_connected
    flag_connected = 1
    print(f"\033[38;5;130mConnected to Broker {ip} with result code {str(rc)}\033[0m")

    
    Solar_Charger_Topics = [("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/ProductName",0),
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
                            ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/ErrorCode",0),
                            ("N/"+VRMid+"/platform/0/Firmware/Installed/Version",0),
                            ("N/"+VRMid+"/platform/0/Firmware/Online/AvailableVersion",0)
                            ]

    BMV_Topics = [("N/"+VRMid+"/battery/"+str(MQTT_BMV_ID)+"/Dc/0/Voltage",0),
                  ("N/"+VRMid+"/battery/"+str(MQTT_BMV_ID)+"/Dc/0/Power",0),
                  ("N/"+VRMid+"/battery/"+str(MQTT_BMV_ID)+"/Dc/0/Current",0),
                  ("N/"+VRMid+"/battery/"+str(MQTT_BMV_ID)+"/Soc",0),
                  ("N/"+VRMid+"/battery/"+str(MQTT_BMV_ID)+"/TimeToGo",0)
                  ]
              
    Inverter_Topics =[("N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/ProductName",0),
                      ("N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Mode",0),
                      ("N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/State",0),
                      ("N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Alarms/HighTemperature",0),
                      ("N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Alarms/Overload",0),
                      ("N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Ac/Out/L1/V",0),
                      ("N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Ac/Out/L1/S",0),
                      ("N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Ac/Out/L1/I",0)
                      ]

    topics = Solar_Charger_Topics
    if BMV_Installed.lower() == "y":
        topics.extend(BMV_Topics)
    if Inverter_Installed.lower() == "y":
        topics.extend(Inverter_Topics)

    client.subscribe(topics)
    print("\033[38;5;127mReceiving MQTT Broker Messages\033[0m")


def on_disconnect(client, userdata,rc):
    # This should survive a Venus Reboot and reconnect so previous chart data will not be lost
    global flag_connected
    flag_connected = 0
    RC = {5: "Connection Refused",
          6: "Connection Not Found",
          7: "Connection Lost"
         }

    if rc != 0:
        Disconnect = datetime.now()
        Disconnect_dt_string = Disconnect.strftime("%a %d %b %Y     %r")
        print(f"\033[38;5;196mUnexpected Disconnect \033[0m{Disconnect_dt_string}")
        print(f"Disconnect Code {rc} {RC[rc]}" )
        print(f"\033[38;5;196mTrying to Reconnect....\033[0m")

        if rc in range(5, 8):
            try:
                #time.sleep(10)
                client.reconnect()
            except ConnectionRefusedError:
                print(f"Connection Refused Error...Retrying")
                #time.sleep(60)
                #client.reconnect()
            except TimeoutError:
                print(f"Connection Timeout Error...Retrying")
                #time.sleep(60)
                #client.reconnect()
        else:
            try:
                #time.sleep(10)
                client.reconnect()
            except ConnectionRefusedError:
                print(f"Connection Refused Error...Retrying")
                #time.sleep(60)
                #client.reconnect()
            except TimeoutError:
                print(f"Connection Timeout Error...Retrying")
                #time.sleep(60)
                #client.reconnect()
    else:
        client.loop_stop()
        print(f"\033[38;5;148mStopping MQTT Loop")
        print(f"Disconnect Result Code {str(rc)}\033[0m\n")

#===================================
# Read the topics as they come in and assign them to variables
def on_message(client, userdata, msg):
    global SolarName, SolarState, SolarStateIndex ,InverterName, \
    AC_Out_Amps, AC_Out_Watts, AC_Out_Volts, InverterHighTemp, InverterOverload, InverterState, InverterMode, \
    Installed_Version, Available_Version, SolarChargeLimit, SolarChargerMode, SolarYield, SolarYieldYest, \
    SolarError, MaxSolarWattsYest, MaxSolarWatts, SolarChargerAmps, SolarVolts, SolarWatts, BatteryTemp, \
    BatteryTTG, BatterySOC, BatteryAmps, BatteryWatts, BatteryVolts, BatteryConsumed

#===================================
    # Uncomment to watch all messages come in via terminal output.
    #NEW_message = json.loads(msg.payload)['value']
    #NEW_message = NEW_message['value']
    #print(f"{str(NEW_message): <60} {msg.topic}")
#===================================
    try:

    # Inverter
        if msg.topic == "N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/ProductName":
            InverterName = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Mode":
            InverterMode = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/State":
            InverterState = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Alarms/HighTemperature":
            InverterHighTemp = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Alarms/Overload":
            InverterOverload = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Ac/Out/L1/V":
            AC_Out_Volts = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Ac/Out/L1/S":
            AC_Out_Watts = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Ac/Out/L1/I":
            AC_Out_Amps = json.loads(msg.payload)["value"]
    #===================================
    #Firmware
        elif msg.topic == "N/"+VRMid+"/platform/0/Firmware/Installed/Version":
            Installed_Version = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/platform/0/Firmware/Online/AvailableVersion":
            Available_Version = json.loads(msg.payload)["value"]
    #===================================
    # Solar Charger
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/ProductName":
            SolarName = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Settings/ChargeCurrentLimit":
            SolarChargeLimit = json.loads(msg.payload)["value"]
            SolarChargeLimit  = int(f"{SolarChargeLimit:.0f}")
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/History/Daily/0/Yield":
            SolarYield = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/History/Daily/1/Yield":
            SolarYieldYest = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Yield/Power":
            SolarWatts = json.loads(msg.payload)["value"]
            SolarWatts = int(SolarWatts)
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
    #===================================
    # System
        elif msg.topic == "N/"+VRMid+"/system/0/Dc/Battery/ConsumedAmphours":
            BatteryConsumed = json.loads(msg.payload)["value"]
    #===================================
    # Smart Shunt
        if BMV_Installed.lower() == "y":
            if msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BMV_ID)+"/Dc/0/Voltage":
                BatteryVolts = json.loads(msg.payload)["value"]
            elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BMV_ID)+"/Dc/0/Power":
                BatteryWatts = json.loads(msg.payload)["value"]
            elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BMV_ID)+"/Dc/0/Current":
                BatteryAmps = json.loads(msg.payload)["value"]
            elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BMV_ID)+"/Soc":
                BatterySOC = json.loads(msg.payload)["value"]
            elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BMV_ID)+"/TimeToGo":
                BatteryTTG = json.loads(msg.payload)["value"]
        else:
            if msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Dc/0/Voltage":
                BatteryVolts = json.loads(msg.payload)["value"]
            elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Dc/0/Current":
                BatteryAmps = json.loads(msg.payload)["value"]
            if BatteryVolts is not None and BatteryAmps is not None:
                BatteryWatts =  BatteryVolts * BatteryAmps


    except NameError:
        print(f"\033[38;5;196mNameError Decoding JSON on Line {sys.exc_info()[-1].tb_lineno}....Retrying\033[0m")
    except ValueError:
        print(f"\033[38;5;196mValueError Decoding JSON on Line {sys.exc_info()[-1].tb_lineno}....Retrying\033[0m")
    except TypeError:
        print(f"\033[38;5;196mTypeError Decoding JSON on Line {sys.exc_info()[-1].tb_lineno}....Retrying\033[0m")
#===================================
# Create a mqtt client instance
client = mqtt.Client()

# Assign callback functions
client.on_connect    = on_connect
client.on_message    = on_message
client.on_disconnect = on_disconnect

# Connect to the broker
print(f"\n\033[38;5;28mTrying to Connect To Broker {ip}\033[0m")
client.connect(ip, 1883, 60)

# Start the loop
start = time.monotonic_ns()
client.loop_start()
# The Venus FlashMQ will refresh ALL values on a keep alive request
mqttpublish.single("R/"+VRMid+"/keepalive", hostname=ip) # One time publish to speed up 1st round mqtt read
# The normal keep alive loop should be run on the venus device


mqtt_list = [None]
timerstart = time.time()
while None in mqtt_list: # Wait for each list item to have a value other than None. Repopulate list on each loop.
# Not every mqtt variable needs to be verified as once these have been checked all mqtt variables should be populated.
    timerexpired = time.time()
    mqtt_list = [SolarName, Installed_Version, SolarChargeLimit, SolarError, BatteryAmps, BatteryVolts]
    time.sleep(.01)
    if timerexpired >= timerstart + 15: # maybe set this to the keep alive time on the GX device
                                        # because all values would have been sent at that point
        print(f"\033[48;5;197mSome or all MQTT values not Received\033[0m")
        # If we cant get the values in mqtt_list something went wrong
        sys.exit()

finish=time.monotonic_ns()
duration = finish -  start
print('\033[38;5;26m'f"Received MQTT messages in {duration//1000000}ms"'\033[0m')
print(f"\033[38;5;28mLoading User Interface\033[0m {dt_stringStart}\n")
SolarState_Old        = SolarState
SolarError_Old        = SolarError
Available_Version_Old = Available_Version
if Inverter_Installed.lower() == "y":
    InverterMode_Old  = InverterMode

# End MQTT Section
#===========================================================================================

class Window(QMainWindow):

    def __init__(self, parent=None):
        super().__init__()
        # Load the ui file
        uic.loadUi("PyQT5-Single-Charger.ui", self)
        # Set Window Icon
        self.setWindowIcon(QtGui.QIcon('Solar-icon.ico'))
        self.textBrowser.append(f"<b><span style=\" color: orangered;\">{dt_stringStart} ---- | ---- App Started</span></b>")
        
        
        if Inverter_Installed.lower() == "n":
            self.Inverter_Label.setHidden(True)
            self.Inverter_frame.setHidden(True)
        
        if BMV_Installed.lower() == "n":
            self.Shunt_Label.setHidden(True)
            self.Batt_SOC_progressBar.setHidden(True)
            self.Batt_SOC_label.setHidden(True)
            self.Battery_Temp_Value.setHidden(True)
            self.Battery_Temp_label.setHidden(True)
            self.Battery_Temp_Alarm_LED.setHidden(True)
            self.BatteryTTG_label.setHidden(True)
            self.BatteryTTG_Value.setHidden(True)
            self.Battery_State_Value.setHidden(True)
            self.Battery_State_label.setHidden(True)
            self.tabWidget.setTabVisible(2,False)
        
        
        # supress the js messages from the webview
        # https://stackoverflow.com/questions/54875167/remove-logs-from-pyqt5-browser-on-console
        class WebEnginePage(QtWebEngineWidgets.QWebEnginePage):
            def javaScriptConsoleMessage(self, level, msg, line, sourceID):
                pass

        def FirmWare_Check():
            mqttpublish.single("W/"+VRMid+"/platform/0/Firmware/Online/Check",
                               payload=json.dumps({"value": 1}), hostname=ip, port=1883)
            time.sleep(.2)
            mqttpublish.single("R/"+VRMid+"/keepalive", hostname=ip, port=1883)
            time.sleep(.2)
            if Installed_Version != Available_Version:
                global dt_string
                if Available_Version is not None:
                    self.textBrowser.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- Checking for new Firmware. ---- Available Version {Available_Version}</span></b>")
                #Available_Version_Old = Available_Version
                else:
                    self.textBrowser.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- Checking for new Firmware. ---- No New Version Available</span></b>")


            # Solar Charger Control
        def Charger1_On():
            # 1 = On 4 = Off
            mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Mode",
                                   payload=json.dumps({"value": 1}), hostname=ip, port=1883)
            global dt_string
            self.textBrowser.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- Solar Charger Mode Changed to On</span></b>")


        def Charger1_Off():
            # 1 = On 4 = Off
            mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Mode",
                                       payload=json.dumps({"value": 4}), hostname=ip, port=1883)
            global dt_string
            self.textBrowser.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- Solar Charger Mode Changed to OFF</span></b>")

        #===========================================================================================
        # Inverter Control

        def Inverter_On():
            #client.write_registers(address=3126, values=2, unit=Inverter_ID) # Turn On
            mqttpublish.single("W/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Mode",
                                        payload=json.dumps({"value": 2}), hostname=ip, port=1883)
            


        def Inverter_Off():
            #client.write_registers(address=3126, values=4, unit=Inverter_ID) # Turn Off
            mqttpublish.single("W/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Mode",
                                        payload=json.dumps({"value": 4}), hostname=ip, port=1883)


        def Inverter_Eco():
            #client.write_registers(address=3126, values=5, unit=Inverter_ID) # Eco
            mqttpublish.single("W/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Mode",
                                        payload=json.dumps({"value": 5}), hostname=ip, port=1883)


        # Add comboBox items to change stacked widget pages
        self.comboBox.addItem("Weather")
        self.comboBox.addItem("Events")
        self.comboBox.activated[int].connect(self.stackedWidget.setCurrentIndex)
        self.comboBox.setCurrentIndex(1)
        self.stackedWidget.setCurrentIndex(1)
        # See if we have WAN access for weather info
        def is_connected():
            try:
                # try to connect to a host that should be up all the time
                socketInstance = socket.create_connection(("bing.com", 80))
                return True
            except Exception:
                self.stackedWidget.setCurrentIndex(1)
                self.comboBox.setCurrentIndex(1)
                now = datetime.now()
                dt_string = now.strftime("%a %d %b %Y     %r")
                self.textBrowser.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- No WAN Access For Weather Forecast</span></b>")
                return False
            socketInstance.close()

        # Check to see if we have WAN access for weather info
        global internet
        internet = is_connected()
        # Create a new profile
        self.profile = QWebEngineProfile()
        # Disable caching
        self.profile.setHttpCacheType(QWebEngineProfile.MemoryHttpCache)
        self.profile.setHttpCacheMaximumSize(0)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)


        # Load Web Browser if connected
        if internet: # If true load weather_url
            self.browser = QtWebEngineWidgets.QWebEngineView()
            self.page = WebEnginePage(self.profile,self.browser)
            self.browser.setPage(self.page)
            self.browser.setUrl(QUrl(weather_url))
            self.webLayout.addWidget(self.browser)
            # see def closeEvent for additional code for closing




        def Reboot():
            Rebootbutton = QMessageBox.question(self, "Reboot GX Device?", "Reboot The GX Device?", QMessageBox.Yes | QMessageBox.Abort)
            if Rebootbutton == QMessageBox.Yes:
                global dt_string
                mqttpublish.single("W/"+VRMid+"/platform/0/Device/Reboot",
                                    payload=json.dumps({"value": 1}), hostname=ip, port=1883)
                self.textBrowser.append(f"<b><span style=\" color: orangered;\">{dt_string} ---- | ---- Rebooting GX Device</span></b>")
                print("Rebooting GX Device")


        def BG_Change():
            color = QColorDialog.getColor(initial=QtGui.QColor('#2e3436')) # also sets the default color in the dialog
            if color.isValid():
                self.centralwidget.setStyleSheet(f"background-color: {color.name()}")
                self.Solar_Name_lineEdit.setStyleSheet(f"background-color: {color.name()}")
                global dt_string
                self.tabWidget.setStyleSheet(f"background-color: {color.name()}")
                self.textBrowser.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- Color Changed to {color.name()}</span></b>")

        def Charger1_Limit():
            Limit = SolarChargeLimit #mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Settings/ChargeCurrentLimit") # Get the existing value
            answer, ok = QInputDialog.getInt(self, 'Enter Charger Limit', 'Enter Charger Limit', int(f"{Limit:.0f}")) # Prefill the inpout with existing value
            if ok:
                mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Settings/ChargeCurrentLimit",
                                   payload=json.dumps({"value": answer}), hostname=ip, port=1883)
                self.textBrowser.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- Charger Limit Changed to {answer} Amps</span></b>")

#============================================================================================

# Pushbuttons
        self.InverterEco_PushButton.clicked.connect(Inverter_Eco)
        self.InverterOn_PushButton.clicked.connect(Inverter_On)
        self.InverterOff_PushButton.clicked.connect(Inverter_Off)
        self.FirmWareCheck_PushButton.clicked.connect(FirmWare_Check)
        self.Reboot_PushButton.clicked.connect(Reboot)


#===========================================================================================
        # make QTimer to show clock time
        self.qTimer = QTimer()

        # set interval to 1 s
        self.qTimer.setInterval(1000) # 1000 ms = 1 s

        # connect timeout signal to signal handler
        self.qTimer.timeout.connect(self.showTime)

        # start timer
        self.qTimer.start()
#===========================================================================================
        # make 2nd QTimer to set refresh rate on the UI
        self.qTimer2 = QTimer()

        # set interval to 1 s
        self.qTimer2.setInterval(1000) # 1000 ms = 1 s

        # connect timeout signal to signal handler
        self.qTimer2.timeout.connect(self.update_ui)

        # start timer
        self.qTimer2.start()

#===========================================================================================
        # Battery Temp Alarm LED Blink once per second (500 ms = 1 second cycle time)

        def BatteryTempBlinkTimer():
            self.Battery_Temp_Alarm_LED.setStyleSheet(f"color: {next(blinkred_Battery_Temp)}")

        # make QTimer
        self.qTimerBatteryTemp = QTimer()

        # set interval
        self.qTimerBatteryTemp.setInterval(500) # 500 ms = 1 second cycle time

        # connect timeout signal to signal handler
        self.qTimerBatteryTemp.timeout.connect(BatteryTempBlinkTimer)
#===============================================

# Inverter Temp Alarm LED Blink once per second (500 ms = 1 second cycle time)

        def InverterTempBlinkTimer():
            self.Inverter_HighTemperature_LED.setStyleSheet(f"color: {next(blinkred_Inverter_Temp)}")

        # make QTimer
        self.qTimerInverterTemp = QTimer()

        # set interval
        self.qTimerInverterTemp.setInterval(500) # 500 ms = 1 second cycle time

        # connect timeout signal to signal handler
        self.qTimerInverterTemp.timeout.connect(InverterTempBlinkTimer)
#===============================================
# Inverter Temp Alarm LED Blink once per second (500 ms = 1 second cycle time)

        def InverterOverloadBlinkTimer():
            self.Inverter_Overload_LED.setStyleSheet(f"color: {next(blinkred_Inverter_Overload)}")

        # make QTimer
        self.qTimerInverterOverload = QTimer()

        # set interval
        self.qTimerInverterOverload.setInterval(500) # 500 ms = 1 second cycle time

        # connect timeout signal to signal handler
        self.qTimerInverterOverload.timeout.connect(InverterOverloadBlinkTimer)

#===============================================
# MQTT Messages LED

        def MQTTLED_Timer():
            self.MQTT_LED.setStyleSheet(f"color: {next(blinkgreen_MQTT)}")

        # make QTimer
        self.qTimerMQTT = QTimer()

        # set interval
        self.qTimerMQTT.setInterval(100) # 500 ms = 1 second cycle time

        # connect timeout signal to signal handler
        self.qTimerMQTT.timeout.connect(MQTTLED_Timer)


# Begin Charts
#===========================================================================================

        # Define crosshair parameters
        kwargs = {Crosshair.ENABLED: True,
        Crosshair.LINE_PEN: pg.mkPen(color="purple"),
        Crosshair.TEXT_KWARGS: {"color": "white"}, }
        pg.setConfigOption('leftButtonPan', True) # False = drawing a zooming box. Only needed once.
        # Because this left button is now false, panning is done by dragging the chart up down left right

#===========================================================================================
# Chart Solar Watts 24 Hrs
        # Chart Total Solar Watts & Solar Volts
        Solar_Watts_plot = LiveLinePlot(pen='blue', name = "Watts", fillLevel=0, brush=(0, 0, 108,200))
        Solar_Volts_plot = LiveLinePlot(pen='red', name = "Volts")

        self.Solar_Watts_connector = DataConnector(Solar_Watts_plot, max_points=86400, update_rate=2) # 75600
        self.Solar_Volts_connector = DataConnector(Solar_Volts_plot, max_points=86400, update_rate=2)

        watts_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.DATETIME})

        self.Solar_graph_Widget = LivePlotWidget(title="PV Watts & Volts, 24 Hours",
                                      axisItems={'bottom': watts_bottom_axis},
                                      x_range_controller=LiveAxisRange(roll_on_tick=300, offset_left=.5), **kwargs)

        self.Solar_graph_Widget.x_range_controller.crop_left_offset_to_data = True

        self.Solar_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        self.Solar_graph_Widget.setLabel('bottom')
        self.Solar_graph_Widget.setLabel('left', 'Volts')

        self.Solar_graph_Widget.addLegend() # If plot is named, auto add name to legend

        self.Solar_graph_Widget.addItem(Solar_Watts_plot)
        self.Solar_graph_Widget.addItem(Solar_Volts_plot)

        self.Chart_Watts_Layout.addWidget(self.Solar_graph_Widget)


#===========================================================================================

# Chart Battery 24 Hrs
        Battery_Volts_plot       = LiveLinePlot(pen= "red",       name = "Volts", brush=(102,0,0,100))
        Battery_Watts_plot       = LiveLinePlot(pen= "blue",      name = "Watts", brush=(88,55,88))
        Battery_Amps_plot        = LiveLinePlot(pen= "orangered", name = "Amps",  brush=(55,44,213,100))
        Battery_Temperature_plot = LiveLinePlot(pen= "green",     name = "°F",  brush=(0,80,0,100))

        # Data connectors for each plot with dequeue of max_points points
        self.Battery_Volts_connector        = DataConnector(Battery_Volts_plot,       max_points=86400, update_rate=2)
        self.Battery_Watts_connector        = DataConnector(Battery_Watts_plot,       max_points=86400, update_rate=2)
        self.Battery_Amps_connector         = DataConnector(Battery_Amps_plot,        max_points=86400, update_rate=2)
        self.Battery_Temperature_connector  = DataConnector(Battery_Temperature_plot, max_points=86400, update_rate=2)

        #Battery_Volts_plot.set_leading_line(LeadingLine.HORIZONTAL, pen=mkPen("red"), text_axis=LeadingLine.AXIS_Y)

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        Battery_Volts_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.DATETIME})
        #volts_left_axis = LiveAxis('left', showValues=True)

        # Create plot itself
        self.Battery_graph_Widget = LivePlotWidget(title="Battery Volts, Watts, Amps 24 Hrs",
        axisItems={'bottom': Battery_Volts_bottom_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=600, offset_left=.5), **kwargs)

        self.Battery_graph_Widget.x_range_controller.crop_left_offset_to_data = True

        # Show grid
        self.Battery_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        # Set labels
        self.Battery_graph_Widget.setLabel('bottom')
        self.Battery_graph_Widget.setLabel('left')
        self.Battery_graph_Widget.setLabel('right')

        # Add Floating Legend
        self.Battery_graph_Widget.addLegend() # If plot is named, auto add name to legend

        # Add Line
        self.Battery_graph_Widget.addItem(Battery_Volts_plot)
        self.Battery_graph_Widget.addItem(Battery_Watts_plot)
        self.Battery_graph_Widget.addItem(Battery_Amps_plot)
        self.Battery_graph_Widget.addItem(Battery_Temperature_plot)

        # Add chart to Layout in Qt Designer
        self.Chart_Battery_Layout.addWidget(self.Battery_graph_Widget)

#===========================================================================================

# Chart Battery SOC
        # For sub 1 Hz rate
        # Make a measurement every x seconds (1 / x)
        if BMV_Installed.lower() == "y":
            soc_plot = LiveLinePlot(pen="magenta")
    
            soc_plot.set_leading_line(LeadingLine.HORIZONTAL, pen=mkPen("red"), text_axis=LeadingLine.AXIS_Y)
    
            # Data connectors for each plot with dequeue of max_points points
            self.soc_connector = DataConnector(soc_plot, max_points=15120, update_rate=.2) # 5 Second Update
    
            # Setup bottom axis with TIME tick format
            # use Axis.DATETIME to show date
            soc_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.DATETIME})
    
            # Create plot itself
            self.Battery_SOC_graph_Widget = LivePlotWidget(title="Battery SOC, 24 Hours",
            axisItems={'bottom': soc_bottom_axis},
            x_range_controller=LiveAxisRange(roll_on_tick=75, offset_left=.5), **kwargs)
    
            self.Battery_SOC_graph_Widget.x_range_controller.crop_left_offset_to_data = True
    
            # Show grid
            self.Battery_SOC_graph_Widget.showGrid(x=True, y=True, alpha=0.3)
    
            # Set Display Limits
            #self.Battery_SOC_graph_Widget.setLimits(yMin=0, yMax=100)
    
            # Set labels
            self.Battery_SOC_graph_Widget.setLabel('bottom')
            self.Battery_SOC_graph_Widget.setLabel('left', 'Percent')
    
            # Add Line
            self.Battery_SOC_graph_Widget.addItem(soc_plot)
    
            # Add chart to Layout in Qt Designer
            self.Chart_Battery_SOC_Layout.addWidget(self.Battery_SOC_graph_Widget)

#===========================================================================================
# Chart Charger State
        # For sub 1 Hz rate
        # Make a measurement every x seconds (1 / x)
        global categories
        categories = ["OFF", "Fault", "Bulk", "Absorption", "Float", "Storage", "Equalize",
                      "Other Hub-1", "Wake Up", "EXT Control"]

        state_plot = LiveCategorizedBarPlot(categories,
                               category_color={"OFF": "saddlebrown", "Fault": "red", "Bulk": "darkblue",
                               "Absorption": "green", "Float": "yellow", "Storage": "orangered",
                               "Equalize": "magenta", "Other Hub-1": "pink", "Wake Up": "cyan",
                               "EXT Control": "purple"})

        # Data connectors for each plot with dequeue of max_points points
        self.state_connector = DataConnector(state_plot, max_points=15120, update_rate=.2) # 5 Second Update

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date

        state_left_axis = LiveAxis("left", **{Axis.TICK_FORMAT: Axis.CATEGORY, Axis.CATEGORIES: state_plot.categories})
        state_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.DATETIME})


        # Create plot itself
        self.Charger_State_graph_Widget = LivePlotWidget(title="Charger State 24 Hrs",
        axisItems={'bottom': state_bottom_axis, 'left': state_left_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=75, offset_left=.5), **kwargs)

        self.Charger_State_graph_Widget.x_range_controller.crop_left_offset_to_data = True


        # Show grid
        self.Charger_State_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        # Set labels
        self.Charger_State_graph_Widget.setLabel('bottom')
        #self.Charger_State_graph_Widget.setLabel('left', 'Amps')

        # Add Line
        self.Charger_State_graph_Widget.addItem(state_plot)

        # Add chart to Layout in Qt Designer
        self.Chart_Charger_State_Layout.addWidget(self.Charger_State_graph_Widget)

# End Charts
#===========================================================================================


        self.actionCharger_1_Off.triggered.connect(Charger1_Off)
        self.actionCharger_1_On.triggered.connect(Charger1_On)
        self.actionSet_Current_Limit_1.triggered.connect(Charger1_Limit)

        # Full Screen & Normanl
        self.actionNormal_Screen.triggered.connect(self.showNormal)
        self.actionFull_Screen.triggered.connect(self.showFullScreen)
        self.actionChange_Background_Color.triggered.connect(BG_Change)
        # Chart Updates
        Thread(target=self.update_charts).start()
#===========================================================================================

    def showTime(self):
        # Datetime object containing current date and time
        now = datetime.now()

        # Fri 21 Jan 2022     09:06:57 PM
        global dt_string
        dt_string = now.strftime("%a %d %b %Y     %r")
        self.statusBar.showMessage(f"{dt_string}")

    def closeEvent(self, event: QtGui.QCloseEvent):
        global running
        running = False
        print(f"\n\033[0m==========================================")
        print(f"\033[38;5;148mExiting App\033[0m")
        client.disconnect()
        global internet
        if internet:
            self.page.deleteLater()
            self.browser.close()


    def update_charts(self):
        while running:
            # All the below sleep calls "combined" should not exceed 1 second in total (update rate in hz)
            # The individual small sleep times help the bigger the dequeue gets
            timestamp = time.time()
            start = time.monotonic_ns()

            try:
                self.Solar_Watts_connector.cb_append_data_point(int(SolarWatts), timestamp)
                self.Solar_Volts_connector.cb_append_data_point(float(SolarVolts), timestamp)
                if BMV_Installed.lower() == "y":
                    self.soc_connector.cb_append_data_point(float(BatterySOC), timestamp)
                time.sleep(.2)

                self.Battery_Volts_connector.cb_append_data_point(float(BatteryVolts), timestamp)
                self.Battery_Watts_connector.cb_append_data_point(int(BatteryWatts), timestamp)
                self.Battery_Amps_connector.cb_append_data_point(float(BatteryAmps), timestamp)
                #self.Battery_Temperature_connector.cb_append_data_point(float(BatteryTemp), timestamp)
                time.sleep(.2)

                global SolarState
                SolarStateIndex  = list(SolarStateDict.keys()).index(SolarState)

                self.state_connector.cb_append_data_point([categories[SolarStateIndex]], timestamp)
                time.sleep(.2)

            except AttributeError:
                print(f"\033[38;5;27mAttributeError in Update Charts, on Line {sys.exc_info()[-1].tb_lineno} Retrying......\033[0m")
                continue
            except NameError:
                print(f"\033[38;5;27mNameError in Update Charts, on Line {sys.exc_info()[-1].tb_lineno} Retrying......\033[0m")
                continue
            except TypeError:
                print(f"\033[38;5;27mTypeError in Update Charts, on Line {sys.exc_info()[-1].tb_lineno} Retrying......\033[0m")
                continue
            time.sleep(.4)
            #finish=time.monotonic_ns()
            #duration = finish -  start
            #print('\033[38;5;65m'f"Duration is {duration//1000000}ms")


    def update_ui(self):
        global SolarStateIndex

        now = datetime.now()
        dt_string = now.strftime("%a %d %b %Y     %r")

        try:

            global SolarState_Old, InverterMode_Old, SolarError_Old

            if SolarState != SolarState_Old:
                self.textBrowser.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- Solar Charger Changed to   {SolarStateDict[SolarState]}</span></b>")
                SolarState_Old = SolarState

            if SolarError != SolarError_Old:
                self.textBrowser.append(f"<b><span style=\" color: red;\">{dt_string} ---- | ---- Solar Error   {SolarErrorDict[SolarError]}</span></b>")
                SolarError_Old = SolarError
            if Inverter_Installed.lower() == "y":
                if InverterMode != InverterMode_Old:
                    self.textBrowser.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- Inverter Mode Changed to   {InverterModeDict[InverterMode]}</span></b>")
                    InverterMode_Old = InverterMode

            if BMV_Installed.lower() == "y":
                #BatteryCAPRemain = BatteryCAPInst - abs(BatteryConsumed)
                if BatteryWatts == 0:
                    BatteryState = 'Idle'
                elif BatteryWatts < 0:
                    BatteryState = 'Discharging'
                elif BatteryWatts > 0:
                    BatteryState = 'Charging'

                if BatteryTTG == None:
                    New_BatteryTTG = "*"
                else:
                # BatteryTTG has a value of seconds. We dont want to change its "type" to "datetime"
                # because we dont want to pass a "datetime" to timedelta on the second+ update because it change's.
                # Make a new variable to hold the timedelta
                    New_BatteryTTG = BatteryTTG
                    New_BatteryTTG = f"{New_BatteryTTG:.0f}"
                    New_BatteryTTG = timedelta(seconds = int(New_BatteryTTG))

                self.Batt_SOC_progressBar.setRange(0, 100)
                #BatterySOC = 32
                self.Batt_SOC_progressBar.setValue(int(BatterySOC))
                self.Batt_SOC_progressBar.setFormat("%.1f %%" % BatterySOC)
                #self.Batt_SOC_progressBar.setValue(round(BatterySOC))
    
                if BatterySOC >= 66:
                    self.Batt_SOC_progressBar.setStyleSheet("QProgressBar#Batt_SOC_progressBar{selection-background-color:"
                                                            "rgb(0, 153, 0);color: rgb(0, 0, 0)}"); # Green
                elif BatterySOC < 66 and BatterySOC > 33:
                    self.Batt_SOC_progressBar.setStyleSheet("QProgressBar#Batt_SOC_progressBar{selection-background-color:"
                                                            "rgb(255, 255, 0);color: rgb(0, 0, 0)}"); # Yellow
                elif BatterySOC <= 33:
                    self.Batt_SOC_progressBar.setStyleSheet("QProgressBar#Batt_SOC_progressBar{selection-background-color:"
                                                            "rgb(200, 0, 0);}"); # Red
#===========================================================================================

# Battery Temp LED Alarm
        # if you want to test this change the Batt_Lo or Batt_Hi variable at the top of the script
            '''if BatteryTemp > Batt_Lo and BatteryTemp < Batt_Hi: # Off
                if self.qTimerBatteryTemp.isActive():
                    # Blue Bold Text
                    self.qTimerBatteryTemp.stop()
                    self.textBrowser.append(f"<b><span style=\" color: blue;\">{dt_string} ---- | ---- Battery Temperature returned to Normal  {BatteryTemp: .1f} °F</span></b>")
                self.Battery_Temp_Alarm_LED.setStyleSheet("color: rgb(28, 28, 28)") # dark

            elif BatteryTemp > Batt_Hi or BatteryTemp < Batt_Lo: # Blink
                if not self.qTimerBatteryTemp.isActive():
                    self.qTimerBatteryTemp.start()
                    self.textBrowser.append(f"<b><span style=\" color: red;\">{dt_string} ---- | ---- Battery Temperature Out Of Range  {BatteryTemp: .1f} °F</span></b>")
            '''
#===========================================================================================

# Inveter High Temp LED Alarm
            if Inverter_Installed.lower() == "y":
                if InverterHighTemp == 0: # Off
                    if self.qTimerInverterTemp.isActive():
                        self.textBrowser.append(f"<b><span style=\" color: blue;\">{dt_string} ---- | ---- Inverter High Temperature Returned to Normal</span></b>")
                        self.qTimerInverterTemp.stop()
                    self.Inverter_HighTemperature_LED.setStyleSheet("color: rgb(28, 28, 28)") # dark
    
                elif InverterHighTemp == 1: # Blink
                    if not self.qTimerInverterTemp.isActive():
                        self.textBrowser.append(f"<b><span style=\" color: red;\">{dt_string} ---- | ---- Inverter High Temperature Alarm.</span></b>")
                        self.qTimerInverterTemp.start()
    #====================================================================
    # Inveter Overload LED Alarm
                if InverterOverload == 0: # Off
                    if self.qTimerInverterOverload.isActive():
                        self.textBrowser.append(f"<b><span style=\" color: blue;\">{dt_string} ---- | ---- Inverter Overload Returned to Normal</span></b>")
                        self.qTimerInverterOverload.stop()
                    self.Inverter_Overload_LED.setStyleSheet("color: rgb(28, 28, 28)") # dark
    
                elif InverterOverload == 1: # Blink
                    if not self.qTimerInverterOverload.isActive():
                        self.textBrowser.append(f"<b><span style=\" color: red;\">{dt_string} ---- | ---- Inverter Overload Alarm.</span></b>")
                        self.qTimerInverterOverload.start()
#====================================================================
# MQTT LED
            global flag_connected
            if flag_connected == 1:
                if not self.qTimerMQTT.isActive():
                    self.qTimerMQTT.start()
                    self.textBrowser.append(f"<b><span style=\" color: green;\">{dt_string} ---- | ---- MQTT Broker Connected and Receiving Messages</span></b>")

            else:
                if self.qTimerMQTT.isActive():
                    self.qTimerMQTT.stop()
                    self.MQTT_LED.setStyleSheet("color: rgb(255, 0, 0)") # Red
                    self.textBrowser.append(f"<b><span style=\" color: red;\">{dt_string} ---- | ---- MQTT Broker Disconnected, Trying to Reconnect</span></b>")


#===========================================================================================
# Populate Screen with Variable Values
#===========================================================================================
# Solar Charger
            self.Firmware_Installed_Value.setText(Installed_Version)
            # Solar Charger Section
            self.Total_Watts_label.setText(str(SolarWatts))
            self.Solar_Name_lineEdit.setText(f"{SolarName} - {Array1}")
            self.PV_Watts_LCD.display(SolarWatts)
            self.Output_Amps_LCD.display(SolarChargerAmps)
            self.Output_Amps_Limit_label.setText(f"{SolarChargeLimit:.0f} A")
            self.PV_Volts_LCD.display(SolarVolts)
            SolarAmps = SolarWatts / SolarVolts
            self.PV_Amps_LCD.display(SolarAmps)
            self.Max_PV_Watts_Today_LCD.display(MaxSolarWatts)
            self.Max_PV_Watts_Yesterday_LCD.display(MaxSolarWattsYest)
            self.Yield_Today_LCD.display(f"{SolarYield:.3f}")
            self.Yield_Yesterday_LCD.display(f"{float(SolarYieldYest):.3f}")
            self.Solar_Charger_State_lineEdit.setText(str(SolarStateDict[SolarState]))
            self.Solar_Charger_Mode_lineEdit.setText(str(SolarChargerMode))
            if SolarChargerMode == "OFF":
                self.Solar_Charger_Mode_lineEdit.setStyleSheet(f"background-color: red")
            elif SolarChargerMode == "ON":
                self.Solar_Charger_Mode_lineEdit.setStyleSheet(f"background-color: green")
                
            if SolarError > 0:
                self.Solar_Charger_Error_Value.setText(SolarErrorDict[SolarError])
                self.Solar_Charger_Error_Value.setStyleSheet("QLabel#Solar_Charger_Error_Value{font-weight: bold; color: red; background-color: black;}");
            else:
                self.Solar_Charger_Error_Value.setText(SolarErrorDict[SolarError])
                self.Solar_Charger_Error_Value.setStyleSheet("QLabel#Solar_Charger_Error_Value{color: rgb(0, 255, 0);}");
#===========================================================================================
# Inverter Section
            if Inverter_Installed.lower() == "y":
                self.Inverter_label.setText(InverterName)
                self.Inverter_Output_Voltage_LCD.display(f"{AC_Out_Volts:.1f}")
                self.Inverter_Output_Current_LCD.display(AC_Out_Amps)
                self.Inverter_Output_Power_LCD.display(AC_Out_Watts)
                self.Inverter_State_Value.setText(InverterStateDict[InverterState])
                self.Inverter_Mode_Value.setText(InverterModeDict[InverterMode])



#===========================================================================================
# Battery BMV Section

            if BMV_Installed.lower() == "y":
                #self.Installed_CAP_Value.setText(f"{BatteryCAPInst:.2f}AH")
                #self.Remaining_CAP_Value.setText(f"{BatteryConsumed:.1f}AH")
                #self.Battery_Temp_Value.setText(f"{BatteryTemp:.2f} °F")
                #self.Batt_SOC_progressBar.setToolTip(f"Battery has {BatteryCAPRemain:.1f} AH Left") # Hover mouse on progressbar to get better resolution
                self.BatteryTTG_Value.setText(str(New_BatteryTTG))
                self.Battery_State_Value.setText(BatteryState)

            
            self.Battery_Volts_LCD.display(f"{BatteryVolts:.2f}")
            self.Battery_Amps_LCD.display(f"{BatteryAmps:.2f}")
            self.Battery_Watts_LCD.display(f"{BatteryWatts:.0f}")
            self.Firmware_Available_Value.setText(f"{Available_Version}")

                

        except AttributeError:
                print(f"\033[38;5;27mAttributeError in Update UI, on Line {sys.exc_info()[-1].tb_lineno} Retrying......\033[0m")

        except NameError:
                print(f"\033[38;5;27mNameError in Update UI, on Line {sys.exc_info()[-1].tb_lineno} Retrying......\033[0m")

        except TypeError:
                print(f"\033[38;5;27mTypeError in Update UI, on Line {sys.exc_info()[-1].tb_lineno} Retrying......\033[0m ")

#===========================================================================================


running = True
app = QApplication(sys.argv)
win = Window()
win.show()
sys.exit(app.exec_())
