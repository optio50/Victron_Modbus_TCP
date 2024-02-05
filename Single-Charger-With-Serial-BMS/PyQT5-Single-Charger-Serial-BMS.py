#!/usr/bin/env python3

# This file is for a Raspi and a single Victron SmartSolar Charger. Also includes a Serial UART BMS (JBD in my case).
# I have no idea if this works with the other compatiable BMS's. I only have a JBD.
# It uses MQTT for "all" of the values (Victron FlashMQ). Should have a beta or VERY recent Venus firmware.

# Venus OS Serial BMS info
# https://github.com/Louisvdw/dbus-serialbattery
# USB Serial interface https://overkillsolar.com/product/usb-module-for-bms/
# The connector included did not fit my BMS, YMMV. I cut the BMS BlueTooth cable in half and soldered the UART wire's to the connector wire's
# TimeToSOC list must match the format in /data/etc/dbus-serialbattery/config.ini on the Venus OS device
import os
#import random
import json
import re
import sys
import time
import socket
from datetime import datetime
from datetime import timedelta
from threading import Thread
from time import gmtime, strftime
from itertools import cycle # Flash the alarm LED's on and off
# for QtWebEngineWidgets do sudo apt install python3-pyqt5.qtwebengine
from PyQt5 import QtGui, uic, QtCore, QtWidgets, QtWebEngineWidgets
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView, QWebEngineProfile, QWebEngineSettings
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QColor, QPalette


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
'''
This script "ONLY" uses MQTT for the variables. Enable on the GX device.
A keepalive request should be hosted on the venus device instead of in this script.
https://github.com/optio50/Victron_Modbus_TCP   --->    forever.py & keep-alive.py

/data/etc/dbus-serialbattery/config.ini
In newer driver versions the serial BMS config.ini must contain the line
PUBLISH_CONFIG_VALUES = True
This seems to be fluid if they require it or not. Try without first



==========================================================
==========================================================
                 Change the Variables Below
==========================================================
==========================================================
'''

#===================================
''' GX Device I.P Address '''
ip = '192.168.20.167' # <------- Change This
port = 1883 # 1883 is a MQTT standard port
#===================================
# VRM Portal ID from GX device.
'''
This ID is needed even with no internet access as its the name of your venus device.
Menu -->> Settings -->> "VRM Online Portal -->> VRM Portal ID"
'''
VRMid = "xxxxxxxxxxxx" # <------- Change This
#===================================
# Weather Widget
'''
Go to https://weatherwidget.io/ to get your weather location code (url only).
You Only need the https url portion that looks like
https://forecast7.com/en/34d10n118d41/90210/?unit=us
and type in your desired text for "city name"
'''
weather_widget_url = "https://forecast7.com/en/40d71n74d01/new-york/" # <------- Change This
city_name = "Local" # <------- Change This to anything you want. -- Not required
#===================================
# Web browser url (the last tab of the Charts widget)
# Not to be confused with the weather widget url above
'''
Weather URL example https://wttr.in/dallas+texas
use something such as manchester+england or nsw+australia or dallas+texas or a zip code
'''
# Seclect one or a custom one of your choice
#weather_url = "https://wttr.in/palmer+alaska"
weather_url = "https://www.forecast.co.uk/united-states/dallas.html"

#===================================
# BMV and Inverter Optional Equipment Installed? Y or N
BMV_Installed      = "y" # <------- Change This
Inverter_Installed = "y" # Such as a Phoenix VE direct # <------- Change This
#===================================
# MQTT Instance ID's Below.
# MQTT Instance ID not to be confused with the Modbus Unit ID.
#===================================
# Louisvdw Battery Monitor driver.
# https://github.com/Louisvdw/dbus-serialbattery
MQTT_BatteryBMS_ID   = 4   # Serial BMS (Required) # <------- Change This
#===================================
# Victron Smart Solar Charger
MQTT_SolarCharger_ID = 288 # Victron Smart MPPT (Required) # <------- Change This
#===================================
if BMV_Installed.lower() == "y":
    MQTT_BMV_ID = 289 # Victron Smart Shunt or BMV (Optional) # <------- Change This
else:
    MQTT_BMV_ID = None
#===================================
if Inverter_Installed.lower() == "y":
    MQTT_Inverter_ID = 290 # The small Victron Phoenix Inverter's (Optional) # <------- Change This

else:
    MQTT_Inverter_ID = None
#===================================
# Describe The Solar Panel Array
Array1 = "Portable 100W Soft Panel" # <------- Change This
#===================================
'''
Choosing LIFEPO4 will disable BMS voltage based features such as state of charge / time to state of charge.
LIFEPO4 cannot tell SOC from a voltage and the JBD builtin shunt cannot detect small currents correctly.
A better shunt is required. Such as a Victron Smart Shunt (Required if you choose LIFEPO4).
SOC and "Time to Go" will be more accurate.
I only use the BMS values for the individual cell voltages.
Choosing "Other" will use the BMS shunt and values. Good Luck :-)
'''
# LIFEPO4 or Other Battery? Selcect one
Battery_Type = "LIFEPO4" 
#Battery_Type = "OTHER"
#===================================
# Temperature Sensor Needed (JBD BMS has one built-in)
# Alarm LED for Battery Temperature Range Deg F
Batt_Lo = 35 # Low  Temperature °F Alarm # <------- Change This
Batt_Hi = 80 # High Temperature °F Alarm # <------- Change This
'''
==========================================================
==========================================================
                Change the Variables Above
==========================================================
==========================================================
'''
# Make sure you changed the VRMid variable from xxxxxxxx
if not (any(char.isalpha() for char in VRMid) and any(char.isnumeric() for char in VRMid)):
    print(f"Something is wrong with the VRMid variable {VRMid}. It's NOT letters and numbers")
    quit()

#======================================================================
if Battery_Type == "LIFEPO4" and MQTT_BMV_ID == None:
    print(f"MQTT_BMV_ID does not exist, A Victron Smart Shunt is required for a LIFEPO4 battery")
    quit()
#===================================
#For the while loop after the keep alive publish. (mqtt_list)
Cell1V              = None
NumOfCells          = None
SolarName           = None
BMSname             = None
InverterName        = None
Installed_Version   = None
DVCCstatus          = None
flag_connected      = 0
#===================================
try:
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-logging"
    os.environ['QT_LOGGING_RULES'] = 'qt.qpa.*=false;*.debug=false'
except Exception as e:
    print(f"A logging error occurred: {str(e)}")
# Prevents QT mouse click button bug   qt.qpa.xcb: QXcbConnection: XCB error: 3 (BadWindow)
#                                               https://bugreports.qt.io/browse/QTBUG-56893
#===================================
# Datetime object containing date and time for App Start
nowStart = datetime.now()
# Fri 21 Jan 2022     09:06:57 PM
dt_stringStart = nowStart.strftime("%a %d %b %Y     %r")
#===================================
big_tab = "\t"*15 # used in the status bar because it compresses text
#===================================
# This will blink the Alarm LED's on and off
blinkred_Battery_Temp       = cycle(["rgb(255, 0, 0)",   "rgb(28, 28, 0)"]) # Red to dark
blinkred_Inverter_Temp      = cycle(["rgb(255, 0, 0)",   "rgb(28, 28, 0)"]) # Red to dark
blinkred_Inverter_Overload  = cycle(["rgb(255, 0, 0)",   "rgb(28, 28, 0)"]) # Red to dark
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

    BatteryBMS_Topics = [("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell1",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell2",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell3",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell4",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell5",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell6",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell7",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell8",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell9",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell10",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell11",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell12",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell13",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell14",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell15",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell16",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Diff",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Sum",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/System/NrOfCellsPerBattery",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/System/MinCellVoltage",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/System/MaxCellVoltage",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/System/MinVoltageCellId",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/System/MaxVoltageCellId",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/InstalledCapacity",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Dc/0/Temperature",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Info/MaxChargeCurrent",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Info/MaxDischargeCurrent",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Info/MaxChargeVoltage",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Io/AllowToCharge",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Io/AllowToDischarge",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/ProductName",0),
                      ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Info/Config/#",0)
                      ]

    BMV_Topics = [("N/"+VRMid+"/battery/"+str(MQTT_BMV_ID)+"/Dc/0/Voltage",0),
                  ("N/"+VRMid+"/battery/"+str(MQTT_BMV_ID)+"/Dc/0/Power",0),
                  ("N/"+VRMid+"/battery/"+str(MQTT_BMV_ID)+"/Dc/0/Current",0),
                  ("N/"+VRMid+"/battery/"+str(MQTT_BMV_ID)+"/Soc",0),
                  ("N/"+VRMid+"/battery/"+str(MQTT_BMV_ID)+"/TimeToGo",0)
                ]

    Inverter_Topics = [("N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/ProductName",0),
                      ("N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Mode",0),
                      ("N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/State",0),
                      ("N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Alarms/HighTemperature",0),
                      ("N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Alarms/Overload",0),
                      ("N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Ac/Out/L1/V",0),
                      ("N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Ac/Out/L1/S",0),
                      ("N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Ac/Out/L1/I",0)
                      ]

    Solar_Charger_Topics = [("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/ProductName",0),
                          ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Settings/ChargeCurrentLimit",0),
                          ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/History/Daily/0/Yield",0),
                          ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/History/Daily/1/Yield",0),
                          ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Yield/Power",0),
                          ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Pv/V",0),
                          ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Dc/0/Current",0),
                          ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/History/Daily/0/MaxPower",0),
                          ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/History/Daily/1/MaxPower",0),
                          ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/State",0),
                          ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Mode",0),
                          ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/ErrorCode",0),
                          ("N/"+VRMid+"/platform/0/Firmware/Installed/Version",0),
                          ("N/"+VRMid+"/platform/0/Firmware/Online/AvailableVersion",0),
                          ("N/"+VRMid+"/system/0/Control/Dvcc",0),
                          ("N/"+VRMid+"/system/0/Dc/Battery/ConsumedAmphours",0)
                          ]


    if Battery_Type != "LIFEPO4":
        TimeToSOC_Topics = [
                             ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/100",0),
                             ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/95",0),
                             ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/90",0),
                             ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/85",0),
                             ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/75",0),
                             ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/50",0),
                             ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/25",0),
                             ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/20",0),
                             ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/10",0),
                             ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/0",0),
                             ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Dc/0/Voltage",0),
                             ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Dc/0/Power",0),
                             ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Dc/0/Current",0),
                             ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Soc",0),
                             ("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToGo",0)
                             ]

    topics = Solar_Charger_Topics
    topics.extend(BatteryBMS_Topics)
    if BMV_Installed.lower() == "y":
        topics.extend(BMV_Topics)
    if Inverter_Installed.lower() == "y":
        topics.extend(Inverter_Topics)
    if Battery_Type != "LIFEPO4":
        topics.extend(TimeToSOC_Topics)

    client.subscribe(topics)
    print("\033[38;5;127mReceiving MQTT Broker Messages\033[0m")


def on_disconnect(client, userdata,rc):
    # This should survive a Venus Reboot and reconnect so previous chart data will not be lost
    global flag_connected
    flag_connected = 0
    RC = {1: "Out of memory",
          2: "A network protocol error occurred when communicating with the broker.",
          3: "Invalid function arguments provided.",
          4: "The client is not currently connected.",
          5: "Connection Refused",
          6: "Connection Not Found",
          7: "Connection Lost",
          8: "A TLS error occurred.",
          9: "Payload too large.",
          10: "This feature is not supported.",
          11: "Authorisation failed.",
          12: "Access denied by ACL.",
          13: "Unknown error.",
          14: "Error defined by errno.",
          15: "Message queue full.",
          16: "Connection Lost for Unknown Reason"
         }

    if rc != 0:
        Disconnect = datetime.now()
        Disconnect_dt_string = Disconnect.strftime("%a %d %b %Y     %r")
        print(f"\033[38;5;196mUnexpected Disconnect \033[0m{Disconnect_dt_string}")
        print(f"Disconnect Code {str(rc)} {RC[rc]}" )
        print(f"\033[38;5;196mTrying to Reconnect....\033[0m")

        if rc in range(1, 17):
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
            print(f"\033[38;5;196mUnexpected Disconnect reason unknown \033[0m")
            print(f"Disconnect Code {str(rc)}")
    else:
        client.loop_stop()
        print(f"\033[38;5;148mStopping MQTT Loop")
        print(f"Disconnect Result Code {str(rc)}\033[0m\n")

#===================================
# Read the topics as they come in and assign them to variables
def on_message(client, userdata, msg):
    global Cell1V, Cell2V, Cell3V, Cell4V, Cell5V, Cell6V, Cell7V, Cell8V,  Cell9V, Cell10V, Cell11V, Cell12V, \
    Cell13V, Cell14V, Cell15V, Cell16V, NumOfCells, SolarName, SolarState, SolarStateIndex ,BMSname, InverterName, \
    AC_Out_Amps, AC_Out_Watts, AC_Out_Volts, InverterHighTemp, InverterOverload, InverterState, InverterMode, \
    Installed_Version, Available_Version, SolarChargeLimit, SolarYield, SolarYieldYest, SolarError, MaxSolarWattsYest, \
    MaxSolarWatts, SolarChargerAmps, SolarVolts, SolarWatts, BatteryCAPInst, BatteryTemp, MinCellVolts, MaxCellVolts, \
    MinCellVoltsID, MaxCellVoltsID, CellVoltsDiff, CellVoltsSum, MaxChargeCurrentNOW, MaxDischargeCurrentNOW, \
    MaxChargeVoltage, AllowedToCharge, AllowedToDischarge, DVCCstatus, TimeToSOC_100, TimeToSOC_95, TimeToSOC_90, \
    TimeToSOC_85, TimeToSOC_75, TimeToSOC_50, TimeToSOC_25, TimeToSOC_20, TimeToSOC_10, TimeToSOC_0, BatteryTTG, \
    BatterySOC, BatteryAmps, BatteryWatts, BatteryVolts, BatteryConsumed, SolarChargerMode

#===================================
    # Uncomment to watch all messages come in via terminal output.
    NEW_message = json.loads(msg.payload)['value']
    print(f"{str(NEW_message): <60} {msg.topic}")
#===================================
# BatteryBMS

    try:
        if msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell1":
            Cell1V = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell2":
            Cell2V = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell3":
            Cell3V = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell4":
            Cell4V = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell5":
            Cell5V = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell6":
            Cell6V = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell7":
            Cell7V = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell8":
            Cell8V = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell9":
            Cell9V = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell10":
            Cell10V = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell11":
            Cell11V = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell12":
            Cell12V = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell13":
            Cell13V = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell14":
            Cell14V = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell15":
            Cell15V = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell16":
            Cell16V = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/System/NrOfCellsPerBattery":
            NumOfCells = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/ProductName":
            BMSname = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/InstalledCapacity":
            BatteryCAPInst = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Dc/0/Temperature":
            BatteryTemp = json.loads(msg.payload)["value"] * 1.8 + 32 # Deg F
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/System/MinCellVoltage":
            MinCellVolts = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/System/MaxCellVoltage":
            MaxCellVolts = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/System/MinVoltageCellId":
            MinCellVoltsID = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/System/MaxVoltageCellId":
            MaxCellVoltsID = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Diff":
            CellVoltsDiff = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Sum":
            CellVoltsSum = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Info/MaxChargeCurrent":
            MaxChargeCurrentNOW = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Info/MaxDischargeCurrent":
            MaxDischargeCurrentNOW = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Info/MaxChargeVoltage":
            MaxChargeVoltage = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Io/AllowToCharge":
            AllowedToCharge = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Io/AllowToDischarge":
            AllowedToDischarge = json.loads(msg.payload)["value"]
    #===================================
    # Inverter
        elif msg.topic == "N/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/ProductName":
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
        elif msg.topic == "N/"+VRMid+"/system/0/Control/Dvcc":
            DVCCstatus = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/system/0/Dc/Battery/ConsumedAmphours":
            BatteryConsumed = json.loads(msg.payload)["value"]
    #===================================
    # Smart Shunt
        if Battery_Type == "LIFEPO4":
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

    #===================================
    # BatteryBMS if Battery is Not LIFEPO4
        if Battery_Type != "LIFEPO4":
            if msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/100":
                TimeToSOC_100 = json.loads(msg.payload)["value"]
                if TimeToSOC_100 is not None:
                    TimeToSOC_100 = re.search('(?<=\[)(.*?)(?=\])', TimeToSOC_100)
                    TimeToSOC_100 = TimeToSOC_100.group()
                else:
                    TimeToSOC_100 = "**"
            elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/95":
                TimeToSOC_95 = json.loads(msg.payload)["value"]
                if TimeToSOC_95 is not None:
                    TimeToSOC_95 = re.search('(?<=\[)(.*?)(?=\])', TimeToSOC_95)
                    TimeToSOC_95 = TimeToSOC_95.group()
                else:
                    TimeToSOC_95 = "**"
            elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/90":
                TimeToSOC_90 = json.loads(msg.payload)["value"]
                if TimeToSOC_90 is not None:
                    TimeToSOC_90 = re.search('(?<=\[)(.*?)(?=\])', TimeToSOC_90)
                    TimeToSOC_90 = TimeToSOC_90.group()
                else:
                    TimeToSOC_90 = "**"
            elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/85":
                TimeToSOC_85 = json.loads(msg.payload)["value"]
                if TimeToSOC_85 is not None:
                    TimeToSOC_85 = re.search('(?<=\[)(.*?)(?=\])', TimeToSOC_85)
                    TimeToSOC_85 = TimeToSOC_85.group()
                else:
                    TimeToSOC_85 = "**"
            elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/75":
                TimeToSOC_75 = json.loads(msg.payload)["value"]
                if TimeToSOC_75 is not None:
                    TimeToSOC_75 = re.search('(?<=\[)(.*?)(?=\])', TimeToSOC_75)
                    TimeToSOC_75 = TimeToSOC_75.group()
                else:
                    TimeToSOC_75 = "**"
            elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/50":
                TimeToSOC_50 = json.loads(msg.payload)["value"]
                if TimeToSOC_50 is not None:
                    TimeToSOC_50 = re.search('(?<=\[)(.*?)(?=\])', TimeToSOC_50)
                    TimeToSOC_50 = TimeToSOC_50.group()
                else:
                    TimeToSOC_50 = "**"
            elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/25":
                TimeToSOC_25 = json.loads(msg.payload)["value"]
                if TimeToSOC_25 is not None:
                    TimeToSOC_25 = re.search('(?<=\[)(.*?)(?=\])', TimeToSOC_25)
                    TimeToSOC_25 = TimeToSOC_25.group()
                else:
                    TimeToSOC_25 = "**"
            elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/20":
                TimeToSOC_20 = json.loads(msg.payload)["value"]
                if TimeToSOC_20 is not None:
                    TimeToSOC_20 = re.search('(?<=\[)(.*?)(?=\])', TimeToSOC_20)
                    TimeToSOC_20 = TimeToSOC_20.group()
                else:
                    TimeToSOC_20 = "**"
            elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/10":
                TimeToSOC_10 = json.loads(msg.payload)["value"]
                if TimeToSOC_10 is not None:
                    TimeToSOC_10 = re.search('(?<=\[)(.*?)(?=\])', TimeToSOC_10)
                    TimeToSOC_10 = TimeToSOC_10.group()
                else:
                    TimeToSOC_10 = "**"
            elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/0":
                TimeToSOC_0 = json.loads(msg.payload)["value"]
                if TimeToSOC_0 is not None:
                    TimeToSOC_0 = re.search('(?<=\[)(.*?)(?=\])', TimeToSOC_0)
                    TimeToSOC_0 = TimeToSOC_0.group()
                else:
                    TimeToSOC_0 = "**"
            elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Dc/0/Voltage":
                BatteryVolts = json.loads(msg.payload)["value"]
            elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Dc/0/Power":
                BatteryWatts = json.loads(msg.payload)["value"]
            elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Dc/0/Current":
                BatteryAmps = json.loads(msg.payload)["value"]
            elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Soc":
                BatterySOC = json.loads(msg.payload)["value"]
            elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToGo":
                BatteryTTG = json.loads(msg.payload)["value"]
    except NameError:
        print(f"\033[38;5;196mNameError Decoding JSON on Line {sys.exc_info()[-1].tb_lineno}....Retrying\033[0m")
    except ValueError:
        print(f"\033[38;5;196mValueError Decoding JSON on Line {sys.exc_info()[-1].tb_lineno}....Retrying\033[0m")
    except TypeError:
        print(f"\033[38;5;196mTypeError Decoding JSON on Line {sys.exc_info()[-1].tb_lineno}....Retrying\033[0m")
#===================================
# Create a client instance
client = mqtt.Client()
#client._connect_timeout = 60

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
    mqtt_list = [Cell1V, NumOfCells, SolarName, BMSname, Installed_Version, DVCCstatus]
    time.sleep(.01)
    if timerexpired >= timerstart + 15: # maybe set this to the keep alive time on the GX device
                                        # because all values would have been sent at that point
        print(f"\033[48;5;197mSome or all MQTT values not Received\033[0m")
        # If we cant get the values in mqtt_list something went wrong
        quit()


finish=time.monotonic_ns()
duration = finish -  start
client.unsubscribe("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Info/Config/#")
print('\033[38;5;26m'f"Received MQTT messages in {duration//1000000}ms"'\033[0m')
print(f"\033[38;5;28mLoading User Interface\033[0m {dt_stringStart}\n")
SolarState_Old        = SolarState
SolarError_Old        = SolarError
if Inverter_Installed.lower() == "y":
    InverterMode_Old = InverterMode
Available_Version_Old = Available_Version
# End MQTT Section
#===========================================================================================



class Window(QMainWindow):

    global Config
    Config = []
    def __init__(self, parent=None):
        super().__init__()
        # Load the ui file
        uic.loadUi("PyQT5-Single-Charger-Serial-BMS.ui", self)
        # Set Window Icon
        self.setWindowIcon(QtGui.QIcon('Solar-icon.ico'))

        # supress the js messages from the webview
        # https://stackoverflow.com/questions/54875167/remove-logs-from-pyqt5-browser-on-console
        class WebEnginePage(QtWebEngineWidgets.QWebEnginePage):
            def javaScriptConsoleMessage(self, level, msg, line, sourceID):
                pass
                #print(f"Console message: {level} - {msg} [{sourceID}:{line}]")



        if Inverter_Installed.lower() == "n":
            self.Inverter_frame.setHidden(True)


        def FirmWare_Check():
            self.statusBar.showMessage("Checking for New Firmware", 5000)
            mqttpublish.single("W/"+VRMid+"/platform/0/Firmware/Online/Check",
                               payload=json.dumps({"value": 1}), hostname=ip, port=port)
            mqttpublish.single("R/"+VRMid+"/keepalive", hostname=ip)
            if Installed_Version != Available_Version:
                global dt_string
                if Available_Version is not None:
                    self.textBrowser2.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- Checking for new Firmware. ---- Available Version {Available_Version}</span></b>")
                #Available_Version_Old = Available_Version
                else:
                    self.textBrowser2.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- Checking for new Firmware.</span></b>")


            # Solar Charger Control
        def Charger1_On():
            # 1 = On 4 = Off
            mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Mode",
                                   payload=json.dumps({"value": 1}), hostname=ip, port=port)
            global dt_string
            self.textBrowser2.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- Solar Charger Mode Changed to On</span></b>")
            self.statusBar.showMessage("Solar Charger Manually Changed to ON", 5000)


        def Charger1_Off():
            # 1 = On 4 = Off
            mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Mode",
                                       payload=json.dumps({"value": 4}), hostname=ip, port=port)
            global dt_string
            self.textBrowser2.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- Solar Charger Mode Changed to OFF</span></b>")
            self.statusBar.showMessage("Solar Charger Manually Changed to OFF", 5000)

        def Mode_Label_Clicked(event):
            global dt_string
            if SolarChargerMode == "ON":
                mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Mode",
                                       payload=json.dumps({"value": 4}), hostname=ip, port=port) # Turn Off

                self.textBrowser2.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- Solar Charger Mode Manually Changed to OFF</span></b>")
                self.statusBar.showMessage("Solar Charger MODE Manually Changed to OFF", 5000)

            elif SolarChargerMode == "OFF":
                mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Mode",
                                   payload=json.dumps({"value": 1}), hostname=ip, port=port) # Turn On
                self.textBrowser2.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- Solar Charger Mode Manually Changed to ON</span></b>")
                self.statusBar.showMessage("Solar Charger MODE Manually Changed to ON", 5000)


        #===========================================================================================
        # Inverter Control

        def Inverter_On():
            #client.write_registers(address=3126, values=2, unit=Inverter_ID) # Turn On
            mqttpublish.single("W/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Mode",
                                        payload=json.dumps({"value": 2}), hostname=ip, port=port)



        def Inverter_Off():
            #client.write_registers(address=3126, values=4, unit=Inverter_ID) # Turn Off
            mqttpublish.single("W/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Mode",
                                        payload=json.dumps({"value": 4}), hostname=ip, port=port)


        def Inverter_Eco():
            #client.write_registers(address=3126, values=5, unit=Inverter_ID) # Eco
            mqttpublish.single("W/"+VRMid+"/inverter/"+str(MQTT_Inverter_ID)+"/Mode",
                                        payload=json.dumps({"value": 5}), hostname=ip, port=port)
        #===========================================================================================



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
                self.textBrowser2.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- No WAN Access For Weather Forecast</span></b>")
                return False
            socketInstance.close()

        # Check to see if we have WAN access for weather info
        global internet
        internet = is_connected()
        # Create a new profile
        self.profile = QWebEngineProfile()
        # Disable caching
        self.profile.setHttpCacheType(QWebEngineProfile.NoCache)
        #self.profile.setHttpCacheType(QWebEngineProfile.MemoryHttpCache)
        #self.profile.setHttpCacheMaximumSize(0)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)


        # Load Web Browser if connected
        if internet: # If true load weather_url
            self.Weatherbrowser = QtWebEngineWidgets.QWebEngineView()
            self.Weatherbrowserpage = WebEnginePage(self.profile,self.Weatherbrowser)
            self.Weatherbrowser.setPage(self.Weatherbrowserpage)
            self.Weatherbrowser.setUrl(QUrl(weather_url))
            self.webLayout.addWidget(self.Weatherbrowser)
            # see def closeEvent for additional settings for closing

            # Weather widget https://weatherwidget.io/
            self.WeatherWidget = QtWebEngineWidgets.QWebEngineView()
            self.WeatherWidgetpage = WebEnginePage(self.profile,self.WeatherWidget)
            self.WeatherWidget.setPage(self.WeatherWidgetpage)
            self.WeatherWidget.loadFinished.connect(self.onLoadFinished)
            self.web_settings = self.WeatherWidget.settings()
            self.web_settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, False)
            self.web_settings.setAttribute(QWebEngineSettings.ShowScrollBars, False)
            self.WeatherWidget.page().setBackgroundColor(QColor(0, 0, 0, 0))
            self.WeatherWidget.setHtml(f"""
                    <html>
                    <head>
                        <!-- Include the widget's styles -->
                        <link rel="stylesheet" type="text/css" href="https://weatherwidget.io/css/style.css">
                    </head>
                    <body style="background-color: transparent;">
                        <!-- Place the weather widget code here -->
                        <a class="weatherwidget-io"
                        href="{weather_widget_url}"
                        data-label_1="{city_name}"
                        data-label_2="Forecast"
                        data-icons="Climacons Animated"
                        data-highcolor="orangered"
                        data-lowcolor="skyblue"
                        data-suncolor="darkorange"
                        data-cloudfill="gray"
                        data-raincolor="deepskyblue"
                        data-snowcolor="white"
                        </a>

                        <script>
                        !function(d,s,id){{var js,fjs=d.getElementsByTagName(s)[0];if(!d.getElementById(id)){{js=d.createElement(s);js.id=id;js.src='https://weatherwidget.io/js/widget.min.js';fjs.parentNode.insertBefore(js,fjs);}}}}(document,'script','weatherwidget-io-js');
                        </script>
                    </body>
                    </html>
            """, QUrl(''))

            self.WeatherWidgetLayout.addWidget(self.WeatherWidget)





        if Battery_Type == "LIFEPO4":
            self.TimeToSOC_frame.setHidden(True)
        else:
            self.TimeToSOC_frame.setHidden(False)

        self.textBrowser2.append(f"<b><span style=\" color: orangered;\">{dt_stringStart} ---- | ---- App Started</span></b>")


        def Reboot():
            Rebootbutton = QMessageBox.question(self, "Reboot GX Device?", "Reboot The GX Device?", QMessageBox.Yes | QMessageBox.Abort)
            if Rebootbutton == QMessageBox.Yes:
                global dt_string
                mqttpublish.single("W/"+VRMid+"/platform/0/Device/Reboot",
                                    payload=json.dumps({"value": 1}), hostname=ip, port=port)
                self.textBrowser2.append(f"<b><span style=\" color: orangered;\">{dt_string} ---- | ---- Rebooting GX Device</span></b>")
                print("Rebooting GX Device")


        def BG_Change():
            color = QColorDialog.getColor(initial=QtGui.QColor('#2e3436')) # also sets the default color in the dialog
            if color.isValid():
                self.centralwidget.setStyleSheet(f"background-color: {color.name()}")
                self.Solar_Name_lineEdit.setStyleSheet(f"background-color: {color.name()}")
                global dt_string
                self.tabWidget.setStyleSheet(f"background-color: {color.name()}")
                self.textBrowser2.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- Color Changed to {color.name()}</span></b>")

        def Charger1_Limit():
            Limit = SolarChargeLimit #mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Settings/ChargeCurrentLimit") # Get the existing value
            answer, ok = QInputDialog.getInt(self, 'Enter Charger Limit', 'Enter Charger Limit', int(f"{Limit:.0f}")) # Prefill the inpout with existing value
            if ok:
                mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Settings/ChargeCurrentLimit",
                                   payload=json.dumps({"value": answer}), hostname=ip, port=port)
                self.statusBar.showMessage(f"Setting Charger Limit to {answer} Amps", 5000)

#============================================================================================
#============================================================================================
        # Start of secondary Connection
        # This is part of the secondary connection to provide a one time run for the Config values in the textbrowser tab
        def on_connect2(client2, userdata, flags, rc):
            #print("Secondary connection with result code "+str(rc))
            client2.subscribe("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Info/Config/#")


        def on_message2(client2, userdata, msg2):
            global Config
            TOPIC = msg2.topic
            PAYLOAD = json.loads(msg2.payload)
            PAYLOAD = PAYLOAD['value']
            PAYLOAD = f"{TOPIC: <85}{PAYLOAD}"
            # Delete the path portion in the PAYLOAD such as "N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Info/Config/
            string  = PAYLOAD
            pattern = "Config/"
            index   = string.find(pattern)
            if index != -1:
                new_string = string[index + len(pattern):]
                Config.append(new_string)


        def on_disconnect2(client2, userdata, rc):
            #print(f"\033[38;5;196mDisconnected and Stopping MQTT Secondary Connection Loop. Result code = {str(rc)}\033[0m")
            client2.loop_stop()


        client2 = mqtt.Client()
        client2.on_connect     = on_connect2
        client2.on_message     = on_message2
        client2.on_disconnect  = on_disconnect2
        client2.connect(ip, 1883, 60)
        client2.loop_start()
        mqttpublish.single("R/"+VRMid+"/keepalive", hostname=ip) # One time publish to speed up 1st round MQTT Read's
        time.sleep(.2) # this works better with a small delay
        client2.disconnect() # Disconnect because this secondary connection is only needed one time on startup
        global Config
        Config = sorted(set(Config))
        for items in Config:
            self.textBrowser.append(items)
        self.textBrowser.moveCursor(QTextCursor.Start)
        #End of secondary connection

#===========================================================================================
#============================================================================================
# Pushbuttons
        self.InverterEco_PushButton.clicked.connect(Inverter_Eco)
        self.InverterOn_PushButton.clicked.connect(Inverter_On)
        self.InverterOff_PushButton.clicked.connect(Inverter_Off)
        self.Solar_Charger_Mode_lineEdit.mouseReleaseEvent = Mode_Label_Clicked
        self.Reload_Weather_PushButton.clicked.connect(self.Reload_Weather)

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
# MQTT Messages Blinking Green LED

        def MQTTLED_Timer():
            self.MQTT_LED.setStyleSheet(f"color: {next(blinkgreen_MQTT)}")

        # make QTimer
        self.qTimerMQTT = QTimer()

        # set interval
        self.qTimerMQTT.setInterval(150) # 500 ms = 1 second cycle time

        # connect timeout signal to signal handler
        self.qTimerMQTT.timeout.connect(MQTTLED_Timer)

#===========================================================================================
        # make QTimer to show Refresh Weather Widget
        self.qTimerWeatherWidget = QTimer()

        # set interval to 30m
        self.qTimerWeatherWidget.setInterval(900000) # 1000 ms = 1 s ... 1800000 = 30 Min

        # connect timeout signal to signal handler
        self.qTimerWeatherWidget.timeout.connect(self.Reload_Weather)

        # start timer
        self.qTimerWeatherWidget.start()
        # Connect to the JavaScript console message signal

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

        Solar_Watts_plot = LiveLinePlot(pen=(0,120,250), name = "Watts",  fillLevel=0, brush=(0,0,102,200))
        #Solar_Watts_plot = LiveLinePlot(pen='blue', name = "Watts", fillLevel=0, brush=(0, 0, 108,200))
        Solar_Volts_plot = LiveLinePlot(pen='red', name = "Volts")

        self.Solar_Watts_connector = DataConnector(Solar_Watts_plot, max_points=87200, update_rate=1) # 75600
        self.Solar_Volts_connector = DataConnector(Solar_Volts_plot, max_points=87200, update_rate=1)

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
        #Dynamic Max Charge Current
        Charge_Current_plot      = LiveLinePlot(pen= "white",     name = "Max Charge Current (Dynamic)",  brush=(200,200,200,100))

        # Data connectors for each plot with dequeue of max_points points
        self.Battery_Volts_connector        = DataConnector(Battery_Volts_plot,       max_points=87200, update_rate=1)
        self.Battery_Watts_connector        = DataConnector(Battery_Watts_plot,       max_points=87200, update_rate=1)
        self.Battery_Amps_connector         = DataConnector(Battery_Amps_plot,        max_points=87200, update_rate=1)
        self.Battery_Temperature_connector  = DataConnector(Battery_Temperature_plot, max_points=87200, update_rate=1)
        #Dynamic Max Charge Current
        self.Charge_Current_connector       = DataConnector(Charge_Current_plot,      max_points=87200, update_rate=1)

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
        #Dynamic Max Charge Current
        self.Battery_graph_Widget.addItem(Charge_Current_plot)

        # Add chart to Layout in Qt Designer
        self.Chart_Battery_Layout.addWidget(self.Battery_graph_Widget)

#===========================================================================================

# Chart Battery SOC
        # For sub 1 Hz rate
        # Make a measurement every x seconds (1 / x)

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

# Chart Battery Cells

        C1_plot = LiveLinePlot(pen="orangered", name='Cell 1') # 12 VDC
        C2_plot = LiveLinePlot(pen="green",     name='Cell 2')
        C3_plot = LiveLinePlot(pen="purple",    name='Cell 3')
        C4_plot = LiveLinePlot(pen="blue",      name='Cell 4')

        # Data connectors for each plot with dequeue of max_points points
        self.C1_connector = DataConnector(C1_plot, max_points=87200, update_rate=1)
        self.C2_connector = DataConnector(C2_plot, max_points=87200, update_rate=1)
        self.C3_connector = DataConnector(C3_plot, max_points=87200, update_rate=1)
        self.C4_connector = DataConnector(C4_plot, max_points=87200, update_rate=1)

        #global NumOfCells
        if NumOfCells >= 8:
            C5_plot = LiveLinePlot(pen="cyan",    name='Cell 5') # 24 VDC
            C6_plot = LiveLinePlot(pen="red",     name='Cell 6')
            C7_plot = LiveLinePlot(pen="yellow",  name='Cell 7')
            C8_plot = LiveLinePlot(pen="pink",    name='Cell 8')
            self.C5_connector = DataConnector(C5_plot, max_points=87200, update_rate=1)
            self.C6_connector = DataConnector(C6_plot, max_points=87200, update_rate=1)
            self.C7_connector = DataConnector(C7_plot, max_points=87200, update_rate=1)
            self.C8_connector = DataConnector(C8_plot, max_points=87200, update_rate=1)

        if NumOfCells >= 16:
            C9_plot = LiveLinePlot(pen="lightcyan",     name='Cell 9') # 48 VDC
            C10_plot = LiveLinePlot(pen="antiquewhite", name='Cell 10')
            C11_plot = LiveLinePlot(pen="chartreuse",   name='Cell 11')
            C12_plot = LiveLinePlot(pen="saddlebrown",  name='Cell 12')
            C13_plot = LiveLinePlot(pen="deepskyblue",  name='Cell 13')
            C14_plot = LiveLinePlot(pen="mediumpurple", name='Cell 14')
            C15_plot = LiveLinePlot(pen="orange",       name='Cell 15')
            C16_plot = LiveLinePlot(pen="peru",         name='Cell 16')
            self.C9_connector  = DataConnector(C9_plot,  max_points=87200, update_rate=1)
            self.C10_connector = DataConnector(C10_plot, max_points=87200, update_rate=1)
            self.C11_connector = DataConnector(C11_plot, max_points=87200, update_rate=1)
            self.C12_connector = DataConnector(C12_plot, max_points=87200, update_rate=1)
            self.C13_connector = DataConnector(C13_plot, max_points=87200, update_rate=1)
            self.C14_connector = DataConnector(C14_plot, max_points=87200, update_rate=1)
            self.C15_connector = DataConnector(C15_plot, max_points=87200, update_rate=1)
            self.C16_connector = DataConnector(C16_plot, max_points=87200, update_rate=1)

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        cells_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.DATETIME})

        # Create plot itself
        self.Cells_graph_Widget = LivePlotWidget(title="Cells Voltage, 24 Hours",
        axisItems={'bottom': cells_bottom_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=600, offset_left=.5), **kwargs)

        self.Cells_graph_Widget.x_range_controller.crop_left_offset_to_data = True

        # Show grid
        self.Cells_graph_Widget.showGrid(x=True, y=True, alpha=0.3)


        # Set labels
        self.Cells_graph_Widget.setLabel('bottom')
        self.Cells_graph_Widget.setLabel('left', 'Volts')

        #self.Cells_graph_Widget.setLimits(yMin=2.5, yMax=3.8)


        # Add Legend. You can drag the Legend with the mouse
        self.Cells_graph_Widget.addLegend(offset=("0","-160")) # If plot is named, auto add name to legend



        # Add Line
        self.Cells_graph_Widget.addItem(C1_plot) #1 the addItem sequence effects the legend order
        self.Cells_graph_Widget.addItem(C2_plot) #2
        self.Cells_graph_Widget.addItem(C3_plot) #3
        self.Cells_graph_Widget.addItem(C4_plot) #4

        if NumOfCells >= 8:
            self.Cells_graph_Widget.addItem(C5_plot) #5
            self.Cells_graph_Widget.addItem(C6_plot) #6
            self.Cells_graph_Widget.addItem(C7_plot) #7
            self.Cells_graph_Widget.addItem(C8_plot) #8

        if NumOfCells >= 16:
            self.Cells_graph_Widget.addItem(C9_plot)  #9
            self.Cells_graph_Widget.addItem(C10_plot) #10
            self.Cells_graph_Widget.addItem(C11_plot) #11
            self.Cells_graph_Widget.addItem(C12_plot) #12
            self.Cells_graph_Widget.addItem(C13_plot) #13
            self.Cells_graph_Widget.addItem(C14_plot) #14
            self.Cells_graph_Widget.addItem(C15_plot) #15
            self.Cells_graph_Widget.addItem(C16_plot) #16

        # Add chart to Layout in Qt Designer
        self.Chart_Cells_Layout.addWidget(self.Cells_graph_Widget)

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
        self.actionReboot_GX_Device.triggered.connect(Reboot)
        self.actionCheck_For_New_Firmware.triggered.connect(FirmWare_Check)

        # Full Screen & Normanl
        self.actionNormal_Screen.triggered.connect(self.showNormal)
        self.actionFull_Screen.triggered.connect(self.showFullScreen)
        self.actionChange_Background_Color.triggered.connect(BG_Change)
        # Chart Updates
        Thread(target=self.update_charts).start()
#===========================================================================================

    # Reload Wether Widget
    def Reload_Weather(self):
        sender = self.sender()
        self.WeatherWidget.reload()
        # Execute JavaScript to reload the page
        #script = "location.reload(true);"
        #self.WeatherWidgetpage.runJavaScript(script)

        self.statusBar.showMessage("Weather Widget Refreshing", 5000)
        if sender is self.Reload_Weather_PushButton:
            # reset the weather widget refresh timer. No need for multiple refresh's within the timer interval.
            self.qTimerWeatherWidget.stop()
            self.qTimerWeatherWidget.start()
            self.textBrowser2.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- Weather Widget Manually Refreshed</span></b>")


    def showTime(self):
        # Datetime object containing current date and time
        now = datetime.now()
        global dt_string
        # Fri 21 Jan 2022     09:06:57 PM
        dt_string = now.strftime("%a %d %b %Y     %r")
        self.Time_Label.setText(f"{dt_string}")


    def onLoadFinished(self, ok):
        now = datetime.now()
        dt_string = now.strftime("%a %d %b %Y     %r")
        if not ok:
            self.textBrowser2.append(f"<b><span style=\" color: red;\">{dt_string} ---- | ---- Weather Widget Did NOT Auto Refresh Correctly</span></b>")


    def closeEvent(self, event: QtGui.QCloseEvent):
        global running
        running = False
        print(f"\n\033[0m==========================================")
        print(f"\033[38;5;148mExiting App\033[0m")
        client.disconnect()
        global internet
        if internet:
            self.Weatherbrowserpage.deleteLater()
            self.Weatherbrowser.close()
            self.WeatherWidgetpage.deleteLater()
            self.WeatherWidget.close()






    def update_charts(self):
        while running:
            timestamp = time.time()
            start = time.monotonic_ns()

            try:
                self.Solar_Watts_connector.cb_append_data_point(int(SolarWatts), timestamp)
                self.Solar_Volts_connector.cb_append_data_point(float(SolarVolts), timestamp)
                self.soc_connector.cb_append_data_point(float(BatterySOC), timestamp)
                time.sleep(.2)

                self.Battery_Volts_connector.cb_append_data_point(float(BatteryVolts), timestamp)
                self.Battery_Watts_connector.cb_append_data_point(int(BatteryWatts), timestamp)
                self.Battery_Amps_connector.cb_append_data_point(float(BatteryAmps), timestamp)
                self.Battery_Temperature_connector.cb_append_data_point(float(BatteryTemp), timestamp)
                #Dynamic Max Charge Current
                self.Charge_Current_connector.cb_append_data_point(float(MaxChargeCurrentNOW), timestamp)
                time.sleep(.2)

                self.C1_connector.cb_append_data_point(float(Cell1V), timestamp)
                self.C2_connector.cb_append_data_point(float(Cell2V), timestamp)
                self.C3_connector.cb_append_data_point(float(Cell3V), timestamp)
                self.C4_connector.cb_append_data_point(float(Cell4V), timestamp)
                time.sleep(.2)

                if NumOfCells >= 8: # this many cells might overload the chart and create lag. ¯\_ (ツ)_/¯
                    self.C5_connector.cb_append_data_point(float(Cell5V), timestamp)
                    self.C6_connector.cb_append_data_point(float(Cell6V), timestamp)
                    self.C7_connector.cb_append_data_point(float(Cell7V), timestamp)
                    self.C8_connector.cb_append_data_point(float(Cell8V), timestamp)
                    time.sleep(.1)

                if NumOfCells >= 16: # this many cells might overload the chart and create lag. ¯\_ (ツ)_/¯
                    self.C9_connector.cb_append_data_point(float(Cell9V), timestamp)
                    self.C10_connector.cb_append_data_point(float(Cell10V), timestamp)
                    self.C11_connector.cb_append_data_point(float(Cell11V), timestamp)
                    self.C12_connector.cb_append_data_point(float(Cell12V), timestamp)
                    self.C13_connector.cb_append_data_point(float(Cell13V), timestamp)
                    self.C14_connector.cb_append_data_point(float(Cell14V), timestamp)
                    self.C15_connector.cb_append_data_point(float(Cell15V), timestamp)
                    self.C16_connector.cb_append_data_point(float(Cell16V), timestamp)
                    time.sleep(.1)


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
            time.sleep(.2)
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
                self.textBrowser2.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- Solar Charger Changed to   {SolarStateDict[SolarState]}</span></b>")
                SolarState_Old = SolarState

            if SolarError != SolarError_Old:
                self.textBrowser2.append(f"<b><span style=\" color: red;\">{dt_string} ---- | ---- Solar Error   {SolarErrorDict[SolarError]}</span></b>")
                SolarError_Old = SolarError

            if Inverter_Installed.lower() == "y":
                if InverterMode != InverterMode_Old:
                    self.textBrowser2.append(f"<b><span style=\" color: black;\">{dt_string} ---- | ---- Inverter Mode Changed to   {InverterModeDict[InverterMode]}</span></b>")
                    InverterMode_Old = InverterMode

            BatteryCAPRemain = BatteryCAPInst - abs(BatteryConsumed)

            #SolarState = SolarStateDict[SolarState]
            #SolarError = SolarErrorDict[0]

            #global BatteryTTG
            if BatteryTTG == None:
                New_BatteryTTG = "Infinite"
            else:
            # BatteryTTG has a value of seconds. We dont want to change its "type" to "datetime"
            # because we dont want to pass a "datetime" to timedelta on the second+ update because it change's.
            # Make a new variable to hold the timedelta
                New_BatteryTTG = BatteryTTG
                New_BatteryTTG = f"{New_BatteryTTG:.0f}"
                New_BatteryTTG = timedelta(seconds = int(New_BatteryTTG))

            if BatteryAmps > SolarChargerAmps: # The charging power has to come from somewhere. If its not the MPPT its external charger
                BatteryState = 'External Charging'

            elif BatteryWatts == 0:
                BatteryState = 'Idle'

            elif BatteryWatts < 0:
                BatteryState = 'Discharging'

            elif BatteryWatts > 0:
                BatteryState = 'Charging'

    #===========================================================================================

    # Battery Box Temp LED Alarm
        # if you want to test this change the Batt_Lo or Batt_Hi variable at the top of the script
            if BatteryTemp > Batt_Lo and BatteryTemp < Batt_Hi: # Off
                if self.qTimerBatteryTemp.isActive():
                    # Blue Bold Text
                    self.qTimerBatteryTemp.stop()
                    self.textBrowser2.append(f"<b><span style=\" color: blue;\">{dt_string} ---- | ---- Battery Temperature returned to Normal  {BatteryTemp: .1f} °F</span></b>")
                self.Battery_Temp_Alarm_LED.setStyleSheet("color: rgb(28, 28, 28)") # dark

            elif BatteryTemp > Batt_Hi or BatteryTemp < Batt_Lo: # Blink Red
                if not self.qTimerBatteryTemp.isActive():
                    self.qTimerBatteryTemp.start()
                    self.textBrowser2.append(f"<b><span style=\" color: red;\">{dt_string} ---- | ---- Battery Temperature Out Of Range  {BatteryTemp: .1f} °F</span></b>")
    #===========================================================================================

    # Inveter High Temp LED Alarm
            if Inverter_Installed.lower() == "y":
                if InverterHighTemp == 0: # Off
                    if self.qTimerInverterTemp.isActive():
                        self.textBrowser2.append(f"<b><span style=\" color: blue;\">{dt_string} ---- | ---- Inverter High Temperature Returned to Normal</span></b>")
                        self.qTimerInverterTemp.stop()
                    self.Inverter_HighTemperature_LED.setStyleSheet("color: rgb(28, 28, 28)") # dark

                elif InverterHighTemp == 1: # Blink Red
                    if not self.qTimerInverterTemp.isActive():
                        self.textBrowser2.append(f"<b><span style=\" color: red;\">{dt_string} ---- | ---- Inverter High Temperature Alarm.</span></b>")
                        self.qTimerInverterTemp.start()
    #====================================================================
    # Inveter Overload LED Alarm
                if InverterOverload == 0: # Off
                    if self.qTimerInverterOverload.isActive():
                        self.textBrowser2.append(f"<b><span style=\" color: blue;\">{dt_string} ---- | ---- Inverter Overload Returned to Normal</span></b>")
                        self.qTimerInverterOverload.stop()
                    self.Inverter_Overload_LED.setStyleSheet("color: rgb(28, 28, 28)") # dark

                elif InverterOverload == 1: # Blink Red
                    if not self.qTimerInverterOverload.isActive():
                        self.textBrowser2.append(f"<b><span style=\" color: red;\">{dt_string} ---- | ---- Inverter Overload Alarm.</span></b>")
                        self.qTimerInverterOverload.start()
    #====================================================================
    # MQTT LED Blinking Green Connected, Red Disconnected
            global flag_connected
            if flag_connected == 1:
                if not self.qTimerMQTT.isActive():
                    self.qTimerMQTT.start()
                    self.textBrowser2.append(f"<b><span style=\" color: green;\">{dt_string} ---- | ---- MQTT Broker Connected and Receiving Messages</span></b>")

            else:
                if self.qTimerMQTT.isActive():
                    self.qTimerMQTT.stop()
                    self.MQTT_LED.setStyleSheet("color: rgb(255, 0, 0)") # Red
                    self.textBrowser2.append(f"<b><span style=\" color: red;\">{dt_string} ---- | ---- MQTT Broker Disconnected, Trying to Reconnect</span></b>")

    #====================================================================

            self.Cell_1_Voltage_Value.setText(f"{Cell1V:.3f} V")
            self.Cell_2_Voltage_Value.setText(f"{Cell2V:.3f} V")
            self.Cell_3_Voltage_Value.setText(f"{Cell3V:.3f} V")
            self.Cell_4_Voltage_Value.setText(f"{Cell4V:.3f} V")

    #===========================================================================================
            if NumOfCells >= 8:
                self.Cell_5_Voltage_Value.setText(f"{Cell5V:.3f} V")
                self.Cell_6_Voltage_Value.setText(f"{Cell6V:.3f} V")
                self.Cell_7_Voltage_Value.setText(f"{Cell7V:.3f} V")
                self.Cell_8_Voltage_Value.setText(f"{Cell8V:.3f} V")

    #===========================================================================================
            if NumOfCells >= 16:
                self.Cell_9_Voltage_Value.setText(f"{Cell9V:.3f} V")
                self.Cell_10_Voltage_Value.setText(f"{Cell10V:.3f} V")
                self.Cell_11_Voltage_Value.setText(f"{Cell11V:.3f} V")
                self.Cell_12_Voltage_Value.setText(f"{Cell12V:.3f} V")
                self.Cell_13_Voltage_Value.setText(f"{Cell13V:.3f} V")
                self.Cell_14_Voltage_Value.setText(f"{Cell14V:.3f} V")
                self.Cell_15_Voltage_Value.setText(f"{Cell15V:.3f} V")
                self.Cell_16_Voltage_Value.setText(f"{Cell16V:.3f} V")

    #===========================================================================================
    # Pregressbar Conditional Values
    #===========================================================================================
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
    # Populate Screen with Variable Values
    #===========================================================================================
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
    #===========================================================================================
            # Inverter Section
            #if InverterConnected == 1:
            if Inverter_Installed.lower() == "y":
                self.Inverter_label.setText(InverterName)
                self.Inverter_Output_Voltage_LCD.display(f"{AC_Out_Volts:.1f}")
                self.Inverter_Output_Current_LCD.display(AC_Out_Amps)
                self.Inverter_Output_Power_LCD.display(AC_Out_Watts)
                self.Inverter_State_Value.setText(InverterStateDict[InverterState])
                self.Inverter_Mode_Value.setText(InverterModeDict[InverterMode])

    #===========================================================================================

            # Battery BMS Section
            self.Battery_Volts_LCD.display(f"{BatteryVolts:.2f}")
            self.Battery_Amps_LCD.display(f"{BatteryAmps:.2f}")
            self.Battery_Watts_LCD.display(f"{BatteryWatts:.0f}")
            self.MinCell_Volts_LCD.display(f"{MinCellVolts:.3f}")
            self.MaxCell_Volts_LCD.display(f"{MaxCellVolts:.3f}")
            self.MinCellVoltsID_label.setText(MinCellVoltsID)
            self.MaxCellVoltsID_label.setText(MaxCellVoltsID)
            self.Cell_Volts_Diff_LCD.display(f"{CellVoltsDiff:.3f}")
            self.Installed_CAP_Value.setText(f"{BatteryCAPInst:.2f}AH")
            self.Remaining_CAP_Value.setText(f"{BatteryConsumed:.1f}AH")
            self.Battery_Temp_Value.setText(f"{BatteryTemp:.2f} °F")
            self.BMSname_label.setText(f"BMS Model -- {BMSname}")
            self.Batt_SOC_progressBar.setToolTip(f"Battery has {BatteryCAPRemain:.1f} AH Left") # Hover mouse on progressbar to get better resolution
            self.Max_Charge_Current_NOW_Value.setText(f"{MaxChargeCurrentNOW: .1f} Amps")
            self.Max_Charge_Current_NOW_label.setToolTip("Charging is limited at High SOC") # https://github.com/Louisvdw/dbus-serialbattery/wiki/Features#charge-current-control-management
            self.Max_Discharge_Current_NOW_Value.setText(f"{MaxDischargeCurrentNOW} Amps")
            self.Max_Discharge_Current_NOW_label.setToolTip("Discharging is limited at Low SOC") # https://github.com/Louisvdw/dbus-serialbattery/wiki/Features#charge-current-control-management
            self.Max_Charge_Voltage_Value.setText(f"{MaxChargeVoltage:.2f} V")
            self.Firmware_Available_Value.setText(f"{Available_Version}")

            # Battery Time To Go Section
            if Battery_Type != "LIFEPO4":
                self.TimeToSOC_100_Value.setText(TimeToSOC_100)
                self.TimeToSOC_95_Value.setText(TimeToSOC_95)
                self.TimeToSOC_90_Value.setText(TimeToSOC_90)
                self.TimeToSOC_85_Value.setText(TimeToSOC_85)
                self.TimeToSOC_75_Value.setText(TimeToSOC_75)
                self.TimeToSOC_50_Value.setText(TimeToSOC_50)
                self.TimeToSOC_25_Value.setText(TimeToSOC_25)
                self.TimeToSOC_20_Value.setText(TimeToSOC_20)
                self.TimeToSOC_10_Value.setText(TimeToSOC_10)
                self.TimeToSOC_0_Value.setText(TimeToSOC_0)
            if BMV_Installed.lower() == "y":
                self.BatteryTTG_Value.setText(str(New_BatteryTTG))
                self.Battery_State_Value.setText(BatteryState)
            else:
                self.BatteryTTG_Value.setHidden(True)
                self.BatteryTTG_label.setHidden(True)
                self.Battery_State_Value.setHidden(True)
                self.Battery_State_label.setHidden(True)
    #===========================================================================================
            # Allow to Charge and Allow to Discharge LED's Green=Yes, Red=No
            if DVCCstatus == 1:
                self.Charge_frame.setHidden(False)
                self.DVCC_Info_Value.setText("ON")
                self.DVCC_Info_Value.setStyleSheet("QLabel""{color : rgb(0, 255, 0);}"); # Green
                if float(BatteryVolts) >= 13.700 and AllowedToCharge == 0 and BatterySOC > 99:
                    self.MaxChargingVoltageReached_label.setHidden(False)
                    self.MaxChargingVoltageReached_label.setText("Max SOC & Charging Voltage Reached")

                if float(BatteryVolts) < 13.700 and AllowedToCharge == 0 and BatterySOC > 99:
                    self.MaxChargingVoltageReached_label.setHidden(False)
                    self.MaxChargingVoltageReached_label.setText("Max SOC Reached")

                if float(BatteryVolts) < 13.700 and BatterySOC < 99 or AllowedToCharge == 1:
                    self.MaxChargingVoltageReached_label.setHidden(True)

                if AllowedToCharge == 1:
                    self.Charging_Allowed_Value.setStyleSheet("QLabel#Charging_Allowed_Value{color: rgb(0, 153, 0);}"); # Green
                else:
                    self.Charging_Allowed_Value.setStyleSheet("QLabel#Charging_Allowed_Value{color: rgb(200, 0, 0);}"); # Red

                if AllowedToDischarge == 1:
                    self.Discharging_Allowed_Value.setStyleSheet("QLabel#Discharging_Allowed_Value{color: rgb(0, 153, 0);}"); # Green
                else:
                    self.Discharging_Allowed_Value.setStyleSheet("QLabel#Discharging_Allowed_Value{color: rgb(255, 0, 0);}"); # Red
            else:
                self.Charge_frame.setHidden(True)
                self.DVCC_Info_Value.setText("OFF")
                self.DVCC_Info_Value.setStyleSheet("QLabel""{color : rgb(255, 0, 0);}"); # Red
    #===========================================================================================

            if SolarError > 0:
                self.Solar_Charger_Error_Value.setText(SolarErrorDict[SolarError])
                self.Solar_Charger_Error_Value.setStyleSheet("QLabel#Solar_Charger_Error_Value{font-weight: bold; color: red; background-color: black;}");
            else:
                self.Solar_Charger_Error_Value.setText(SolarErrorDict[SolarError])
                self.Solar_Charger_Error_Value.setStyleSheet("QLabel#Solar_Charger_Error_Value{color: rgb(0, 255, 0);}");

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
