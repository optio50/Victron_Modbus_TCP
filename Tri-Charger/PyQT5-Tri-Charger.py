#!/usr/bin/env python3

import sys
import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QObject, QTimer, QTime, QThread, pyqtSignal
from PyQt5 import uic, QtGui

from threading import Thread

from datetime import datetime
from datetime import timedelta
import time
from time import strftime
from time import gmtime
from time import sleep

from itertools import cycle # Flash the LED's
import json

# MQTT
# MQTT
import paho.mqtt.client as mqtt
import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as mqttpublish

# Modbus
from pymodbus.constants import Defaults
from pymodbus.constants import Endian
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.payload import BinaryPayloadBuilder

# Chart
import pyqtgraph as pg
from pyqtgraph import mkPen
from pglive.kwargs import Axis, Crosshair, LeadingLine
from pglive.sources.data_connector import DataConnector
from pglive.sources.live_axis import LiveAxis
from pglive.sources.live_plot import LiveLinePlot
from pglive.sources.live_axis_range import LiveAxisRange
from pglive.sources.live_plot_widget import LivePlotWidget
from pglive.sources.live_categorized_bar_plot import LiveCategorizedBarPlot

#os.putenv("QTWEBENGINE_CHROMIUM_FLAGS", "--blink-settings=darkMode=4,darkModeImagePolicy=2,--disable-logging")
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-logging"
os.putenv("QT_LOGGING_RULES","*.debug=false;qt.qpa.*=false"); # Prevents QT mouse click button bug   qt.qpa.xcb: QXcbConnection: XCB error: 3 (BadWindow)
#                                                               https://bugreports.qt.io/browse/QTBUG-56893

'''
#===================================================================
 If a keep-alive is needed it should be run on the vesus-OS device.
#===================================================================

Required Equipment:
#===================================================================
Victron Cerbo GX: (or Raspberry PI)
Victron Grid Tie Inverter: (Such as a Multiplus II)
3 VE.Direct Victron MPPT's: (Such as Smart Solar Charger MPPT 150/35)
Victron BMV: (Such as BMV-712)
#===================================================================
'''

# Datetime object containing current date and time
nowStart = datetime.now()
# Fri 21 Jan 2022     09:06:57 PM
dt_stringStart = nowStart.strftime("%a %d %b %Y     %r")

#==========================================================
'''
Alarm LED for LIFEPO4 Battery Box Temperature Range Deg F
This event will be logged in the Event Tab
'''
Batt_Temp_Lo = 35 # Low Temperature °F
Batt_Temp_Hi = 80 # High Temperature °F
#==========================================================
'''
Alarm LED for Max Battery Charging Amps Exceeded
This event will be logged in the Event Tab
'''
MaxAmps = 100
#==========================================================

# GX Device I.P Address
ip = '192.168.20.156'

#===================================
'''
 VRM Portal ID from GX device for MQTT requests.
 This ID is needed even with no internet access as its the name of your venus device.
 Menu -->> Settings -->> VRM Online Portal -->> VRM Portal ID
'''
VRMid = "d41243d31a90"
#===================================
'''
Y or N (case insensitive) to display Gerbo GX Analog Temperature inputs
Turn this off if you dont have the Temperature sensors
'''
Analog_Inputs  = 'Y'

#===================================
'''
Change the MQTT Instance ID to match the cerbo gx value.
'''
if Analog_Inputs.lower() == 'y':
    MQTT_TempSens1_ID = 24
    MQTT_TempSens2_ID = 25
    MQTT_TempSens3_ID = 26


if Analog_Inputs.lower() == 'y':
    Tempsensor1_Name = "Battery Box Temperature     °F"
    Tempsensor2_Name = "Cabin Interior Temperature °F"
    Tempsensor3_Name = "Cabin Exterior Temperature °F"

#===================================
'''
MQTT Instance ID
Device List in VRM or crossed referenced in the CCGX-Modbus-TCP-register-list.xlsx Tab #2
'''
MQTT_SolarCharger_1_ID = 279
MQTT_SolarCharger_2_ID = 280
MQTT_SolarCharger_3_ID = 288
MQTT_MultiPlus_ID      = 276
MQTT_Bmv_ID            = 277
MQTT_VEsystem_ID       = 0

#===================================
'''
Describe The Arrays
'''
Array1 = "400W Panel" # New 400W Panel
Array2 = "310W Panel" # New 310W Panel
Array3 = "365W Panel" # New 365W Panel


SolarName1          = None
SolarOn1            = None
SolarState1         = None
SolarChargeLimit1   = None
SolarVolts1         = None
SolarWatts1         = None
SolarAmps1          = None
SolarYield1         = None
VEbusStatus         = None
VEbusError          = None
ESSbatteryLifeState = None
TempSensor1         = None
TempSensor2         = None
TempSensor3         = None
# ===========================================================================================
''' used in the status bar because it compresses text '''
big_tab = "\t"*15

# Cycle colors for blinking LED's (Bright / Dark)
# There seems to be an issue when you share these, so they are seperate.
blinkred_Battery_Temp  = cycle(["rgb(255, 0, 0  )",   "rgb(28, 28, 0)"]) # Red
blinkred_Battery_Amps  = cycle(["rgb(255, 0, 0  )",   "rgb(28, 28, 0)"]) # Red
blinkred_Temp          = cycle(["rgb(255, 0, 0  )",   "rgb(28, 28, 0)"]) # Red
blinkred_LowBatt       = cycle(["rgb(255, 0, 0  )",   "rgb(28, 28, 0)"]) # Red
blinkred_OverLoad      = cycle(["rgb(255, 0, 0  )",   "rgb(28, 28, 0)"]) # Red
blinkyellow_Bulk       = cycle(["rgb(255, 255, 0)",   "rgb(28, 28, 0)"]) # Yellow
blinkyellow_Absorption = cycle(["rgb(255, 255, 0)",   "rgb(28, 28, 0)"]) # Yellow
blinkyellow_Float      = cycle(["rgb(255, 255, 0)",   "rgb(28, 28, 0)"]) # Yellow
blinkgreen_Mains       = cycle(["rgb(0,154 ,23  )",   "rgb(28, 28, 0)"]) # Green
blinkgreen_Inverter    = cycle(["rgb(0,154 ,23  )",   "rgb(28, 28, 0)"]) # Green
blinkgreen_MQTT        = cycle(["rgb(0,154 ,23  )",   "rgb(28, 28, 0)"]) # Green LED for MQTT connection
# ===========================================================================================

SolarStateDict = {0:  "OFF",
                  2:  "Fault",
                  3:  "Bulk",
                  4:  "Absorption",
                  5:  "Float",
                  6:  "Storage",
                  7:  "Equalize",
                  11: "Other Hub-1",
                  245:"Wake-Up",
                  252:"EXT Control"}
# ===========================================================================================

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
# ===========================================================================================
#   VE.Bus Status
VEbusStatusDict =  {0:  "OFF",
                    1:  "Low Power",
                    2:  "Fault",
                    3:  "Bulk Charging",
                    4:  "Absorption Charging",
                    5:  "Float Charging",
                    6:  "Storage",
                    7:  "Equalize",
                    8:  "Passthru",
                    9:  "Inverting",
                    10: "Power Assist",
                    11: "Power Supply Mode",
                    246:"Repeated Absorption",
                    247:"Equalize",
                    248:"Battery Safe",
                    249:"Test",
                    250:"Blocked",
                    251:"Test",
                    252:"External control",
                    256:"Discharging",
                    257:"Sustain",
                    258:"Recharging",
                    259:"Scheduled Charge"
                    }

# ===========================================================================================
#   VE.Bus Error
VEbusErrorDict = {
                  0: "No Error",
                  1: "Error 1: Device is switched off because one of the other "
                     "phases in the system has switched off",
                  2: "Error 2: New and old types MK2 are mixed in the system",
                  3: "Error 3: Not all- or more than- the expected devices "
                     "were found in the system",
                  4: "Error 4: No other device whatsoever detected",
                  5: "Error 5: Overvoltage on AC-out",
                  6: "Error 6: in DDC Program",
                  7: "VE.Bus BMS connected- which requires an Assistant- "
                     "but no assistant found",
                  8: "Error 8: Ground Relay Test Failed",
                  9: "VE.Bus Error 9",
                  10:"VE.Bus Error 10: System time synchronisation problem occurred",
                  11:"Error 11: Relay Test Fault - Installation error or possibly relay failure",
                  12:"Error 12: - Config mismatch with 2nd mcu",
                  13:"VE.Bus Error 13",
                  14:"Error 14: Device cannot transmit data",
                  15:"Error 15 - VE.Bus combination error",
                  16:"Error 16: Dongle missing",
                  17:"Error 17: One of the devices assumed master "
                     "status because the original master failed",
                  18:"Error 18: AC Overvoltage on the output "
                     "of a slave has occurred while already switched off",
                  19:"Error 19 - Slave does not have AC input!",
                  20:"Error 20: - Configuration mismatch",
                  21:"VE.Bus Error 21",
                  22:"Error 22: This device cannot function as slave",
                  23:"VE.Bus Error 23",
                  24:"Error 24: Switch-over system protection initiated",
                  25:"Error 25: Firmware incompatibility. The firmware of a connected device "
                     "is not sufficiently up to date.",
                  26:"Error 26: Internal error",
                  27:"VE.Bus Error 27",
                  28:"VE.Bus Error 28",
                  29:"VE.Bus Error 29",
                  30:"VE.Bus Error 30",
                  31:"VE.Bus Error 31",
                  32:"VE.Bus Error 32"
                  }
# ===========================================================================================
# ESS Battery Life State
ESSbatteryLifeStateDict = {0: "Battery Life Disabled",
                           1: "Restarting",
                           2: "Self-consumption",
                           3: "Self consumption, SoC exceeds 85%",
                           4: "Self consumption, SoC at 100%",
                           5: "Discharge disabled. SoC below BatteryLife Dynamic SoC",
                           6: "SoC has been below SoC limit for more than 24 hours. Slow Charging battery",
                           7: "Multi is in sustain mode",
                           8: "Recharge, SOC dropped 5% or more below minimum SOC",
                           9: "Keep batteries charged mode enabled",
                           10:"Self consumption, SoC at or above minimum SoC",
                           11:"Discharge Disabled (Low SoC), SoC is below minimum SoC",
                           12:"Recharge, SOC dropped 5% or more below minimum"
                           }
# ===========================================================================================
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Begin MQTT Section
# All the topics you want to subscripbe to
def on_connect(client, userdata, flags, rc):
    global flag_connected
    flag_connected = 1
    print(f"\033[38;5;130mConnected to Broker {ip} with result code {str(rc)}\033[0m")

    topics = [
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Devices/0/ProductName",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Mode",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/State",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Settings/ChargeCurrentLimit",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Pv/V",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Yield/Power",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Dc/0/Current",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/History/Daily/0/Yield",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/History/Daily/1/Yield",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/History/Daily/0/MaxPower",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/History/Daily/1/MaxPower",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/ErrorCode",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Devices/0/ProductName",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Mode",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/State",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Settings/ChargeCurrentLimit",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Pv/V",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Yield/Power",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Dc/0/Current",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/History/Daily/0/Yield",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/History/Daily/1/Yield",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/History/Daily/0/MaxPower",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/History/Daily/1/MaxPower",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/ErrorCode",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/Devices/0/ProductName",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/Mode",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/State",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/Settings/ChargeCurrentLimit",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/Pv/V",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/Yield/Power",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/Dc/0/Current",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/History/Daily/0/Yield",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/History/Daily/1/Yield",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/History/Daily/0/MaxPower",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/History/Daily/1/MaxPower",0),
              ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/ErrorCode",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Alarms/GridLost",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Dc/0/MaxChargeCurrent",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L2/V",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Mains",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Inverter",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Bulk",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Overload",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Absorption",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/LowBattery",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Float",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Temperature",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/ProductName",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L1/V",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L2/V",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L1/I",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L2/I",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L1/F",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L1/V",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L2/V",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L1/I",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L2/I",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L1/F",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/CurrentLimit",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Hub4/L1/MaxFeedInPower",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/VebusError",0),
              ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Mode",0),
              ("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Soc",0),
              ("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Dc/0/Power",0),
              ("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Dc/0/Current",0),
              ("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Dc/0/Voltage",0),
              ("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/History/ChargeCycles",0),
              ("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/ConsumedAmphours",0),
              ("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/History/LastDischarge",0),
              ("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/History/DeepestDischarge",0),
              ("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/History/AverageDischarge",0),
              ("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/History/TimeSinceLastFullCharge",0),
              ("N/"+VRMid+"/hub4/"+str(MQTT_VEsystem_ID)+"/PvPowerLimiterActive",0),
              ("N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Dc/Battery/State",0),
              ("N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Dc/Battery/TimeToGo",0),
              ("N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Ac/Grid/L1/Power",0),
              ("N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Ac/Grid/L2/Power",0),
              ("N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/SystemState/State",0),
              ("N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Ac/Consumption/L1/Power",0),
              ("N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Ac/Consumption/L2/Power",0),
              ("N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Dc/System/Power",0),
              ("N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Dc/Pv/Power",0),
              ("N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/State",0),
              ("N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/MinimumSocLimit",0),
              ("N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/SocLimit",0),
              ("N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/OvervoltageFeedIn",0),
              ("N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/AcPowerSetPoint",0),
              ("N/"+VRMid+"/platform/"+str(MQTT_VEsystem_ID)+"/Firmware/Installed/Version",0),
              ("N/"+VRMid+"/platform/"+str(MQTT_VEsystem_ID)+"/Firmware/Online/AvailableVersion",0),
              ("N/"+VRMid+"/platform/"+str(MQTT_VEsystem_ID)+"/Firmware/Backup/AvailableVersion",0),
              ("N/"+VRMid+"/temperature/"+str(MQTT_TempSens1_ID)+"/Temperature",0),
              ("N/"+VRMid+"/temperature/"+str(MQTT_TempSens2_ID)+"/Temperature",0),
              ("N/"+VRMid+"/temperature/"+str(MQTT_TempSens3_ID)+"/Temperature",0)
                ]
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


# Read the topics as they come in and assign them to variables
def on_message(client, userdata, msg):
    global SolarName1, SolarOn1, SolarState1, SolarChargeLimit1, SolarVolts1, SolarWatts1, SolarAmps1, SolarYield1, \
    SolarYieldYest1, MaxSolarWatts1, MaxSolarWattsYest1, SolarError1, SolarName2, SolarOn2, SolarState2, SolarChargeLimit2, \
    SolarVolts2, SolarWatts2, SolarAmps2, SolarYield2, SolarYieldYest2, MaxSolarWatts2, MaxSolarWattsYest2, SolarError2, \
    SolarName3, SolarOn3, SolarState3, SolarChargeLimit3, SolarVolts3, SolarWatts3, SolarAmps3, SolarYield3, SolarYieldYest3, \
    MaxSolarWatts3, MaxSolarWattsYest3, SolarError3, GridCondition, MaxChargeCurrent, GridVoltsL2, Mains, Inverter, Bulk, Overload, \
    Absorp, Lowbatt, Floatchg, Temperature, MultiName, VEbusStatus, FW_Installed, FW_Available, FW_Backup, BatteryState, BatteryTTG, \
    BatterySOC, BatteryWatts, BatteryAmps, BatteryVolts, ChargeCycles, ConsumedAH, LastDischarge, DeepestDischarge, AvgDischarge, \
    LastFullcharge, DCsystemPower, SolarWatts, FeedInLimited, GridWattsL1, GridWattsL2, ACoutWattsL1, ACoutWattsL2, ESSbatteryLifeState, \
    ESSsocLimitUser, ESSsocLimitDynamic, FeedIn, GridSetPoint, GridVoltsL1, GridVoltsL2, GridAmpsL1, GridAmpsL2, GridHZ, ACoutVoltsL1, \
    ACoutVoltsL2, ACoutAmpsL1, ACoutAmpsL2, ACoutHZ, GridAmpLimit, GridCondition, FeedInMax, VEbusError, MPswitch, TempSensor1, TempSensor2, TempSensor3


#===================================
    # Uncomment to watch all messages come in via terminal output.
    #NEW_message = json.loads(msg.payload)['value']
    #print(f"{str(NEW_message): <60} {msg.topic}")
#===================================

    try:
#Solar Charge Controller # 1
        if msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Devices/0/ProductName":
            SolarName1 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Mode":
            SolarOn1 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/State":
            SolarState1 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Settings/ChargeCurrentLimit":
            SolarChargeLimit1 = json.loads(msg.payload)["value"]
            SolarChargeLimit1 = f"{SolarChargeLimit1: .0f}"
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Pv/V":
            SolarVolts1 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Yield/Power":
            SolarWatts1 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Dc/0/Current":
            SolarAmps1 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/History/Daily/0/Yield":
            SolarYield1 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/History/Daily/1/Yield":
            SolarYieldYest1 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/History/Daily/0/MaxPower":
            MaxSolarWatts1 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/History/Daily/1/MaxPower":
            MaxSolarWattsYest1 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/ErrorCode":
            SolarError1 = json.loads(msg.payload)["value"]
#Solar Charge Controller # 2
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Devices/0/ProductName":
            SolarName2 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Mode":
            SolarOn2 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/State":
            SolarState2 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Settings/ChargeCurrentLimit":
            SolarChargeLimit2 = json.loads(msg.payload)["value"]
            SolarChargeLimit2 = f"{SolarChargeLimit2: .0f}"
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Pv/V":
            SolarVolts2 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Yield/Power":
            SolarWatts2 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Dc/0/Current":
            SolarAmps2 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/History/Daily/0/Yield":
            SolarYield2 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/History/Daily/1/Yield":
            SolarYieldYest2 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/History/Daily/0/MaxPower":
            MaxSolarWatts2 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/History/Daily/1/MaxPower":
            MaxSolarWattsYest2 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/ErrorCode":
            SolarError2 = json.loads(msg.payload)["value"]
#Solar Charge Controller # 3
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/Devices/0/ProductName":
            SolarName3 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/Mode":
            SolarOn3 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/State":
            SolarState3 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/Settings/ChargeCurrentLimit":
            SolarChargeLimit3 = json.loads(msg.payload)["value"]
            SolarChargeLimit3 = f"{SolarChargeLimit3: .0f}"
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/Pv/V":
            SolarVolts3 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/Yield/Power":
            SolarWatts3 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/Dc/0/Current":
            SolarAmps3 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/History/Daily/0/Yield":
            SolarYield3 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/History/Daily/1/Yield":
            SolarYieldYest3 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/History/Daily/0/MaxPower":
            MaxSolarWatts3 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/History/Daily/1/MaxPower":
            MaxSolarWattsYest3 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/ErrorCode":
            SolarError3 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/ProductName":
            MultiName = json.loads(msg.payload)["value"]
# Multiplus
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Alarms/GridLost":
            GridCondition = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/CurrentLimit":
            GridAmpLimit = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Dc/0/MaxChargeCurrent":
            MaxChargeCurrent = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L2/V":
            GridVoltsL2 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Mode":
            MPswitch = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/VebusError":
            VEbusError = json.loads(msg.payload)["value"]



# Multiplus LED's
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Mains":
            Mains = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Inverter":
            Inverter = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Bulk":
            Bulk = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Overload":
            Overload = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Absorption":
            Absorp = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/LowBattery":
            Lowbatt = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Float":
            Floatchg = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Temperature":
            Temperature = json.loads(msg.payload)["value"]
# Multiplus AC
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L1/V":
            GridVoltsL1 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L2/V":
            GridVoltsL2 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L1/I":
            GridAmpsL1 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L2/I":
            GridAmpsL2 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L1/F":
            GridHZ = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L1/V":
            ACoutVoltsL1 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L2/V":
            ACoutVoltsL2 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L1/I":
            ACoutAmpsL1 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L2/I":
            ACoutAmpsL2 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L1/F":
            ACoutHZ = json.loads(msg.payload)["value"]

# BMV
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Soc":
            BatterySOC = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Dc/0/Power":
            BatteryWatts = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Dc/0/Current":
            BatteryAmps = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Dc/0/Voltage":
            BatteryVolts = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/History/ChargeCycles":
            ChargeCycles = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/ConsumedAmphours":
            ConsumedAH = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/History/LastDischarge":
            LastDischarge = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/History/DeepestDischarge":
            DeepestDischarge = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/History/TimeSinceLastFullCharge":
            LastFullcharge = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/History/AverageDischarge":
            AvgDischarge = json.loads(msg.payload)["value"]
#V.E. Bus
        elif msg.topic == "N/"+VRMid+"/hub4/"+str(MQTT_VEsystem_ID)+"/PvPowerLimiterActive":
            FeedInLimited = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Dc/System/Power":
            DCsystemPower = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Dc/Pv/Power":
            SolarWatts = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Ac/Grid/L1/Power":
            GridWattsL1 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Ac/Grid/L2/Power":
            GridWattsL2 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Ac/Consumption/L1/Power":
            ACoutWattsL1 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Ac/Consumption/L2/Power":
            ACoutWattsL2 = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Dc/Battery/State":
            BatteryState = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Dc/Battery/TimeToGo":
            BatteryTTG = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/SystemState/State":
            VEbusStatus = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/State":
            ESSbatteryLifeState = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/MinimumSocLimit":
            ESSsocLimitUser = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/SocLimit":
            ESSsocLimitDynamic = json.loads(msg.payload)["value"]
            if ESSsocLimitDynamic <= ESSsocLimitUser: # The ESS value will never be below the user value in the "Remote Console"
            # https://energytalk.co.za/t/possible-to-manually-change-active-soc-limit-on-victron/294?page=2
               ESSsocLimitDynamic = ESSsocLimitUser
        elif msg.topic == "N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/OvervoltageFeedIn":
            FeedIn = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/AcPowerSetPoint":
            GridSetPoint = json.loads(msg.payload)["value"]
# GX Firmware
        elif msg.topic == "N/"+VRMid+"/platform/"+str(MQTT_VEsystem_ID)+"/Firmware/Installed/Version":
            FW_Installed = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/platform/"+str(MQTT_VEsystem_ID)+"/Firmware/Online/AvailableVersion":
            FW_Available = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/platform/"+str(MQTT_VEsystem_ID)+"/Firmware/Backup/AvailableVersion":
            FW_Backup = json.loads(msg.payload)["value"]
#Temp Sensors
        elif msg.topic == "N/"+VRMid+"/temperature/"+str(MQTT_TempSens1_ID)+"/Temperature":
            TempSensor1 = json.loads(msg.payload)["value"] * 1.8 + 32
        elif msg.topic == "N/"+VRMid+"/temperature/"+str(MQTT_TempSens2_ID)+"/Temperature":
            TempSensor2 = json.loads(msg.payload)["value"] * 1.8 + 32
        elif msg.topic == "N/"+VRMid+"/temperature/"+str(MQTT_TempSens3_ID)+"/Temperature":
            TempSensor3 = json.loads(msg.payload)["value"] * 1.8 + 32

    except (ValueError, TypeError):
        print("\033[38;5;196mDecoding JSON has failed....Still Trying to Recover\033[0m")
        pass
#===================================
# Create a client instance
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
time.sleep(.25) # time to let the keep alive publish resend all values

mqtt_list = [None]
timerstart = time.time()
while None in mqtt_list: # Wait for each list item to have a value other than None. Repopulate list on each loop.
# Not every mqtt variable needs to be verified as once these have been checked all mqtt variables should be populated.
    timerexpired = time.time()
    mqtt_list = [ESSbatteryLifeState, SolarName1, SolarOn1, SolarState1, SolarChargeLimit1, SolarVolts1, SolarWatts1, SolarAmps1, SolarYield1]
    time.sleep(.01)
    if timerexpired > timerstart + 30: # set this to the keep alive time on the GX device
                                        # because all values would have been sent at that point
        print(f"\033[48;5;197mSome or all MQTT values not Received\033[0m")
        # If we cant get the values in mqtt_list something went wrong with retreiving the MQTT values. Max time would be the keep alive time
        sys.exit()


finish=time.monotonic_ns()
duration = finish -  start
print('\033[38;5;26m'f"Received MQTT messages in {duration//1000000}ms"'\033[0m')
print(f"\033[38;5;28mLoading User Interface\033[0m {dt_stringStart}")
SolarState1_Old   = SolarState1
SolarError1_Old   = SolarError1
SolarState2_Old   = SolarState2
SolarError2_Old   = SolarError2
SolarState3_Old   = SolarState3
SolarError3_Old   = SolarError3
GridCondition_Old = GridCondition
Inverter_Old      = Inverter
Mains_Old         = Mains
Bulk_Old          = Bulk
Absorp_Old        = Absorp
Floatchg_Old      = Floatchg
ESSbatteryLifeState_Old = ESSbatteryLifeState
# End MQTT Section


if TempSensor1 == None:
    TempSensor1 = 99
if TempSensor2 == None:
    TempSensor2 = 99
if TempSensor3 == None:
    TempSensor3 = 99

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#===========================================================================================
# END Variables
#===========================================================================================



class Window(QMainWindow):

    def __init__(self, parent=None):
        super().__init__()
        # Load the ui file
        uic.loadUi("PyQT5-Tri-Charger.ui", self)
        self.setWindowIcon(QtGui.QIcon('Solar.png'))
        self.Started_label.setText(f"App Started on {dt_stringStart}")
        self.textBrowser.append(f"<b><span style=\" color: orangered;\">{dt_stringStart} ---- | ---- App Started<span style=\" color: black;\"</span></b>")


#===========================================================================================
        # Define crosshair parameters
        kwargs = {Crosshair.ENABLED: True,
        Crosshair.LINE_PEN: pg.mkPen(color="yellow", width=.5),
        Crosshair.TEXT_KWARGS: {"color": "white"}}
#===========================================================================================
#  Begin Charts
        left_axis = LiveAxis("left")

        watts_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.DATETIME})

        self.Solar_graph_Widget = LivePlotWidget(title="PV Watts, 24 Hours",
                                      axisItems={'bottom': watts_bottom_axis, 'left': left_axis},
                                      x_range_controller=LiveAxisRange(roll_on_tick=300, offset_left=.5), **kwargs)

        self.Solar_graph_Widget.x_range_controller.crop_left_offset_to_data = True

        watts_plot = LiveLinePlot(pen=(0,120,250), fillLevel=0, brush=(0,0,102,200))

        self.watts_connector = DataConnector(watts_plot, max_points=70000, update_rate=2)# max_points=70000, update_rate=2 is almost exact

        self.Chart_Watts_Layout.addWidget(self.Solar_graph_Widget)

        self.Solar_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        self.Solar_graph_Widget.addItem(watts_plot)
#===========================================================================================

# Chart Battery SOC
        soc_plot = LiveLinePlot(pen="magenta")

        # Data connectors for each plot with dequeue of max_points points
        self.soc_connector = DataConnector(soc_plot, max_points=70000, update_rate=2) # 1.5 seconds in 24 hrs

        soc_plot.set_leading_line(LeadingLine.HORIZONTAL, pen=mkPen("red"), text_axis=LeadingLine.AXIS_Y)

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        soc_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.DATETIME})

        # Create plot itself
        self.Battery_SOC_graph_Widget = LivePlotWidget(title="Battery SOC, 24 Hours",
        axisItems={'bottom': soc_bottom_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=300, offset_left=.5), **kwargs)

        self.Battery_SOC_graph_Widget.x_range_controller.crop_left_offset_to_data = True

        #self.Battery_SOC_graph_Widget = LivePlotWidget(title="Battery SOC 24 Hrs", axisItems={'bottom': soc_bottom_axis}, **kwargs)

        # Show grid
        self.Battery_SOC_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        # Set labels
        self.Battery_SOC_graph_Widget.setLabel('bottom')
        self.Battery_SOC_graph_Widget.setLabel('left', 'Percent')

        # Add Line
        self.Battery_SOC_graph_Widget.addItem(soc_plot)

        # Add chart to Layout in Qt Designer
        self.Chart_Battery_SOC_Layout.addWidget(self.Battery_SOC_graph_Widget)

#===========================================================================================
# Chart Battery Volts, Amps, Watts
        volts_plot     = LiveLinePlot(pen="red",   name='Volts')
        bat_watts_plot = LiveLinePlot(pen="blue",  name='Watts')
        amps_plot      = LiveLinePlot(pen="green", name='Amps')


        # Data connectors for each plot with dequeue of max_points points
        self.volts_connector     = DataConnector(volts_plot, max_points=70000, update_rate=2) # 1.5 seconds in 24 hrs
        self.bat_watts_connector = DataConnector(bat_watts_plot, max_points=70000, update_rate=2) # 1.5 seconds in 24 hrs
        self.amps_connector      = DataConnector(amps_plot, max_points=70000, update_rate=2) # 1.5 seconds in 24 hrs


        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        volts_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.DATETIME})

        # Create plot itself
        self.Battery_Volts_graph_Widget = LivePlotWidget(title="Battery Volts, Watts & Amps 24 Hours",
        axisItems={'bottom': volts_bottom_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=300, offset_left=.5), **kwargs)

        self.Battery_Volts_graph_Widget.x_range_controller.crop_left_offset_to_data = True


        # Show grid
        self.Battery_Volts_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        # Set labels
        self.Battery_Volts_graph_Widget.setLabel('bottom')
        self.Battery_Volts_graph_Widget.setLabel('left')
        self.Battery_Volts_graph_Widget.setLabel('right')


        # Add Floating Legend
        self.Battery_Volts_graph_Widget.addLegend() # If plot is named, auto add name to legend

        # Add Line
        self.Battery_Volts_graph_Widget.addItem(volts_plot)
        self.Battery_Volts_graph_Widget.addItem(bat_watts_plot)
        self.Battery_Volts_graph_Widget.addItem(amps_plot)


        # Add chart to Layout in Qt Designer
        self.Chart_Volts_Layout.addWidget(self.Battery_Volts_graph_Widget)
#===========================================================================================
# Chart Grid Watts, Amps
        grid_watts_L1_plot = LiveLinePlot(pen="blue", name='Watts L1',fillLevel=0, brush=(102,102,255,100))
        grid_watts_L2_plot = LiveLinePlot(pen="darkmagenta", name='Watts L2',fillLevel=0, brush=(170,120,225,50))
        grid_amps_L1_plot = LiveLinePlot(pen="green", name='Amps L1')
        grid_amps_L2_plot = LiveLinePlot(pen="red", name='Amps L2')

        # Data connectors for each plot with dequeue of max_points points
        self.grid_watts_L1_connector = DataConnector(grid_watts_L1_plot, max_points=70000, update_rate=2) # 1.5 seconds in 24 hrs
        self.grid_watts_L2_connector = DataConnector(grid_watts_L2_plot, max_points=70000, update_rate=2) # 1.5 seconds in 24 hrs
        self.grid_amps_L1_connector = DataConnector(grid_amps_L1_plot, max_points=70000, update_rate=2) # 1.5 seconds in 24 hrs
        self.grid_amps_L2_connector = DataConnector(grid_amps_L2_plot, max_points=70000, update_rate=2) # 1.5 seconds in 24 hrs

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        grid_watts_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.DATETIME})

        # Create plot itself
        self.Grid_Watts_graph_Widget = LivePlotWidget(title="Grid Watts & Amps, 24 Hours",
        axisItems={'bottom': grid_watts_bottom_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=300, offset_left=.5), **kwargs)

        self.Grid_Watts_graph_Widget.x_range_controller.crop_left_offset_to_data = True

        #self.Grid_Watts_graph_Widget = LivePlotWidget(title="Grid Watts & Amps 24 Hrs", axisItems={'bottom': grid_watts_bottom_axis}, **kwargs)

        # Show grid
        self.Grid_Watts_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        # Set labels
        self.Grid_Watts_graph_Widget.setLabel('bottom')
        self.Grid_Watts_graph_Widget.setLabel('left')


        self.Grid_Watts_graph_Widget.addLegend() # If plot is named, auto add name to legend

        # Add Line
        self.Grid_Watts_graph_Widget.addItem(grid_watts_L1_plot)
        self.Grid_Watts_graph_Widget.addItem(grid_amps_L1_plot)

        if GridVoltsL2 > 0:
            self.Grid_Watts_graph_Widget.addItem(grid_watts_L2_plot)
            self.Grid_Watts_graph_Widget.addItem(grid_amps_L2_plot)



        # Add chart to Layout in Qt Designer
        self.Chart_Grid_Watts_Layout.addWidget(self.Grid_Watts_graph_Widget)


#===========================================================================================
# Chart Cabin Temperatures. Battery Box, Cabin Interior, Cabin Exterior

        if Analog_Inputs.lower() == 'y':
            Exterior_Temp_plot = LiveLinePlot(pen="cyan", name='Cabin Exterior')
            Interior_Temp_plot = LiveLinePlot(pen="red", name='Cabin Interior')
            Box_Temp_plot = LiveLinePlot(pen="yellow", name='Battery Box')

            # Data connectors for each plot with dequeue of max_points points
            self.Exterior_Temp_connector = DataConnector(Exterior_Temp_plot, max_points=70000, update_rate=2) # 1.5 seconds in 24 hrs
            self.Interior_Temp_connector = DataConnector(Interior_Temp_plot, max_points=70000, update_rate=2) # 1.5 seconds in 24 hrs
            self.Box_Temp_connector      = DataConnector(Box_Temp_plot,      max_points=70000, update_rate=2) # 1.5 seconds in 24 hrs


            # Setup bottom axis with TIME tick format
            # use Axis.DATETIME to show date
            Box_Temp_plot_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.DATETIME})

            # Create plot itself
            self.Temperature_graph_Widget = LivePlotWidget(title="Cabin Temperatures °F, 24 Hours",
            axisItems={'bottom': Box_Temp_plot_bottom_axis},
            x_range_controller=LiveAxisRange(roll_on_tick=300, offset_left=.5), **kwargs)

            self.Temperature_graph_Widget.x_range_controller.crop_left_offset_to_data = True

            #self.Temperature_graph_Widget = LivePlotWidget(title="Cabin Temperatures °F 24 Hrs", axisItems={'bottom': Box_Temp_plot_bottom_axis}, **kwargs)

            # Show grid
            self.Temperature_graph_Widget.showGrid(x=True, y=True, alpha=0.3)


            # Set labels
            self.Temperature_graph_Widget.setLabel('bottom')
            #self.Temperature_graph_Widget.setLabel('bottom', 'Time', units='hh:mm:ss' )
            #self.Temperature_graph_Widget.getAxis('bottom').enableAutoSIPrefix(False)
            self.Temperature_graph_Widget.setLabel('left', '°F')

            # Add Floating Legend
            self.Temperature_graph_Widget.addLegend() # If plot is named, add name to legend

            # Add Line
            self.Temperature_graph_Widget.addItem(Box_Temp_plot) #1 the addItem sequence effects the legend order
            self.Temperature_graph_Widget.addItem(Exterior_Temp_plot) #2
            self.Temperature_graph_Widget.addItem(Interior_Temp_plot) #3


            # Add chart to Layout in Qt Designer
            self.Temperature_Layout.addWidget(self.Temperature_graph_Widget)
#===========================================================================================
# Chart A/C Out Watts, Amps
        #, symbol='o', symbolSize=3, symbolPen ='darkmagenta'
        ac_out_watts_L1_plot = LiveLinePlot(pen='darkmagenta', name='Watts L1')
        ac_out_watts_L2_plot = LiveLinePlot(pen='yellow', name='Watts L2')
        ac_out_amps_L1_plot  = LiveLinePlot(pen='orangered', name='Amps L1')
        ac_out_amps_L2_plot  = LiveLinePlot(pen='green', name='Amps L2')
        ac_out_freq_plot  = LiveLinePlot(pen='pink', name='Freq')

        # Data connectors for each plot with dequeue of max_points points
        self.ac_out_watts_L1_connector = DataConnector(ac_out_watts_L1_plot, max_points=70000, update_rate=2) # 1.5 seconds in 24 hrs
        self.ac_out_watts_L2_connector = DataConnector(ac_out_watts_L2_plot, max_points=70000, update_rate=2) # 1.5 seconds in 24 hrs
        self.ac_out_amps_L1_connector  = DataConnector(ac_out_amps_L1_plot,  max_points=70000, update_rate=2) # 1.5 seconds in 24 hrs
        self.ac_out_amps_L2_connector  = DataConnector(ac_out_amps_L2_plot,  max_points=70000, update_rate=2) # 1.5 seconds in 24 hrs
        self.ac_out_freq_connector  = DataConnector(ac_out_freq_plot,  max_points=70000, update_rate=2)

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        ac_out_watts_L1_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.DATETIME})


        # Create plot itself
        self.ac_out_watts_graph_Widget = LivePlotWidget(title="A/C Out Watts, Amps & Freq, 24 Hours",
        axisItems={'bottom': ac_out_watts_L1_bottom_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=300, offset_left=.5), **kwargs)

        self.ac_out_watts_graph_Widget.x_range_controller.crop_left_offset_to_data = True

        #self.ac_out_watts_graph_Widget = LivePlotWidget(title="A/C Out Watts & Amps 24 Hours", axisItems={'bottom': ac_out_watts_bottom_axis}, **kwargs)

        # Show grid
        self.ac_out_watts_graph_Widget.showGrid(x=True, y=True, alpha=0.3)


        # SetLimits
        #self.ac_out_watts_graph_Widget.setLimits(yMin=-1)

        # Set labels
        self.ac_out_watts_graph_Widget.setLabel('bottom')
        self.ac_out_watts_graph_Widget.setLabel('left')

        self.ac_out_watts_graph_Widget.addLegend() # If plot is named auto add name to legend

        # Add Line
        self.ac_out_watts_graph_Widget.addItem(ac_out_watts_L1_plot)
        self.ac_out_watts_graph_Widget.addItem(ac_out_watts_L2_plot)
        self.ac_out_watts_graph_Widget.addItem(ac_out_amps_L1_plot)
        self.ac_out_watts_graph_Widget.addItem(ac_out_amps_L2_plot)
        self.ac_out_watts_graph_Widget.addItem(ac_out_freq_plot)


        # Add chart to Layout in Qt Designer
        self.AC_Out_Watts_Layout.addWidget(self.ac_out_watts_graph_Widget)

#===========================================================================================
# Chart Solar Watts PV 1, PV 2, PV 3

        PV1watts_plot = LiveLinePlot(pen='orangered',name='PV-1',fillLevel=0, brush=(213,129,44,100))
        PV2watts_plot = LiveLinePlot(pen='cyan',name='PV-2', fillLevel=0, brush=(102,102,255,100))
        PV3watts_plot = LiveLinePlot(pen='darkgreen',name='PV-3', fillLevel=0, brush=(0,120,50,115))

        # Data connectors for each plot with dequeue of max_points points
        self.PV1watts_connector = DataConnector(PV1watts_plot, max_points=70000, update_rate=2)
        self.PV2watts_connector = DataConnector(PV2watts_plot, max_points=70000, update_rate=2)
        self.PV3watts_connector = DataConnector(PV3watts_plot, max_points=70000, update_rate=2)


        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        pv1_watts_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.DATETIME})

        # Create plot
        self.PV1_graph_Widget = LivePlotWidget(title="Charger 1, 2 & 3 Watts, 24 Hours",
        axisItems={'bottom': pv1_watts_bottom_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=300, offset_left=.5), **kwargs)

        self.PV1_graph_Widget.x_range_controller.crop_left_offset_to_data = True

        # Show grid
        self.PV1_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        # Set labels
        self.PV1_graph_Widget.setLabel('bottom')
        self.PV1_graph_Widget.setLabel('left', 'Watts')

        self.PV1_graph_Widget.addLegend() # If plot is named, auto add name to legend

        # Add Line
        self.PV1_graph_Widget.addItem(PV1watts_plot)
        self.PV1_graph_Widget.addItem(PV2watts_plot)
        self.PV1_graph_Widget.addItem(PV3watts_plot)

        # Add chart to Layout in Qt Designer
        self.PV1_Watts_Layout.addWidget(self.PV1_graph_Widget)

#===========================================================================================
# Chart Multiplus Charger State
        global MP_categories
        MP_categories = ["Float", "Absorption", "Bulk", "Inverting", "Mains", "Grid Lost"]

        MP_plot = LiveCategorizedBarPlot(MP_categories,
                               category_color={"Float": "blue", "Absorption": "orangered", "Bulk": "yellow",
                                "Inverting": "green", "Mains": "saddlebrown", "Grid Lost": "red"}, bar_height=.2)

        # Data connectors for each plot with dequeue of max_points points
        self.MP_connector = DataConnector(MP_plot, max_points=14000, update_rate=.2) #  2880 * 5 = 14400


        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date

        MP_left_axis = LiveAxis("left", **{Axis.TICK_FORMAT: Axis.CATEGORY, Axis.CATEGORIES: MP_plot.categories})
        MP_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.DATETIME})

        self.MP_State_graph_Widget = LivePlotWidget(title="Multiplus Status, 24 Hours",
        axisItems={'bottom': MP_bottom_axis,'left': MP_left_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=300, offset_left=.5), **kwargs)


        # Create plot itself
        ##self.MP_State_graph_Widget = LivePlotWidget(title="Multiplus Charger State 24 Hrs", axisItems={'bottom': MP_bottom_axis, 'left': MP_left_axis}, **kwargs)

        # Show grid
        #self.MP_State_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        # Set labels
        self.MP_State_graph_Widget.setLabel('bottom')

        # Add Line
        self.MP_State_graph_Widget.addItem(MP_plot)

        # Add chart to Layout in Qt Designer
        self.MP_Charger_Layout.addWidget(self.MP_State_graph_Widget)

#===========================================================================================
# Chart Charger #1 State
        global categories
        categories = ["OFF", "Fault", "Bulk", "Absorption", "Float", "Storage", "Equalize",
                      "Other Hub-1", "Wake-Up", "EXT Control"]

        state1_plot = LiveCategorizedBarPlot(categories,
                               category_color={"OFF": "saddlebrown", "Fault": "red", "Bulk": "yellow",
                               "Absorption": "orangered", "Float": "blue", "Storage": "green",
                               "Equalize": "purple", "Other Hub-1": "pink", "Wake-Up": "cyan",
                               "EXT Control": "deepskyblue"}, bar_height=.2)

        # Data connectors for each plot with dequeue of max_points points
        self.state1_connector = DataConnector(state1_plot, max_points=14000, update_rate=.2)

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date

        state1_left_axis = LiveAxis("left", **{Axis.TICK_FORMAT: Axis.CATEGORY, Axis.CATEGORIES: state1_plot.categories})
        state1_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.DATETIME})


        # Create plot itself
        ##self.Charger1_State_graph_Widget = LivePlotWidget(title="Charger #1 State 24 Hrs", axisItems={'bottom': state1_bottom_axis, 'left': state1_left_axis}, **kwargs)

        self.Charger1_State_graph_Widget = LivePlotWidget(title="Charger 1 Status, 24 Hours",
        axisItems={'bottom': state1_bottom_axis,'left': state1_left_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=300, offset_left=.5), **kwargs)


        # Show grid
        #self.Charger1_State_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        # Set labels
        self.Charger1_State_graph_Widget.setLabel('bottom')
        #self.Charger_State_graph_Widget.setLabel('left', 'Amps')

        # Add Line
        self.Charger1_State_graph_Widget.addItem(state1_plot)

        # Add chart to Layout in Qt Designer
        self.Charger1_State_Layout.addWidget(self.Charger1_State_graph_Widget)

#===========================================================================================
# Chart Charger #2 State

        state2_plot = LiveCategorizedBarPlot(categories,
                               category_color={"OFF": "saddlebrown", "Fault": "red", "Bulk": "yellow",
                               "Absorption": "orangered", "Float": "blue", "Storage": "green",
                               "Equalize": "purple", "Other Hub-1": "pink", "Wake-Up": "cyan",
                               "EXT Control": "deepskyblue"}, bar_height=.2)


        # Data connectors for each plot with dequeue of max_points points
        self.state2_connector = DataConnector(state2_plot, max_points=14000, update_rate=.2) # 24 hours in seconds

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date


        state2_left_axis = LiveAxis("left", **{Axis.TICK_FORMAT: Axis.CATEGORY, Axis.CATEGORIES: state2_plot.categories})
        state2_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.DATETIME})


        # Create plot itself
        ##self.Charger2_State_graph_Widget = LivePlotWidget(title="Charger #2 State 24 Hrs", axisItems={'bottom': state2_bottom_axis, 'left': state2_left_axis}, **kwargs)

        self.Charger2_State_graph_Widget = LivePlotWidget(title="Charger 2 Status, 24 Hours",
        axisItems={'bottom': state2_bottom_axis,'left': state2_left_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=300, offset_left=.5), **kwargs)

        # Show grid
        #self.Charger2_State_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        # Set labels
        self.Charger2_State_graph_Widget.setLabel('bottom')
        #self.Charger_State_graph_Widget.setLabel('left', 'Amps')

        # Add Line
        self.Charger2_State_graph_Widget.addItem(state2_plot)

        # Add chart to Layout in Qt Designer
        self.Charger2_State_Layout.addWidget(self.Charger2_State_graph_Widget)

#===========================================================================================
# Chart Charger #3 State

        state3_plot = LiveCategorizedBarPlot(categories,
                               category_color={"OFF": "saddlebrown", "Fault": "red", "Bulk": "yellow",
                               "Absorption": "orangered", "Float": "blue", "Storage": "green",
                               "Equalize": "purple", "Other Hub-1": "pink", "Wake-Up": "cyan",
                               "EXT Control": "deepskyblue"}, bar_height=.2)


        # Data connectors for each plot with dequeue of max_points points
        self.state3_connector = DataConnector(state3_plot, max_points=14000, update_rate=.2) # 24 hours in seconds

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date


        state3_left_axis = LiveAxis("left", **{Axis.TICK_FORMAT: Axis.CATEGORY, Axis.CATEGORIES: state3_plot.categories})
        state3_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.DATETIME})


        # Create plot itself
        ##self.Charger3_State_graph_Widget = LivePlotWidget(title="Charger #3 State 24 Hrs", axisItems={'bottom': state2_bottom_axis, 'left': state3_left_axis}, **kwargs)

        self.Charger3_State_graph_Widget = LivePlotWidget(title="Charger 3 Status, 24 Hours",
        axisItems={'bottom': state3_bottom_axis,'left': state3_left_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=300, offset_left=.5), **kwargs)

        # Show grid
        #self.Charger2_State_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        # Set labels
        self.Charger3_State_graph_Widget.setLabel('bottom')
        #self.Charger_State_graph_Widget.setLabel('left', 'Amps')

        # Add Line
        self.Charger3_State_graph_Widget.addItem(state3_plot)

        # Add chart to Layout in Qt Designer
        self.Charger3_State_Layout.addWidget(self.Charger3_State_graph_Widget)

#===========================================================================================
# End Charts
#===========================================================================================
        # Multiplus Control

        def Multiplus_Charger():
            # Charger Only
            mqttpublish.single("W/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Mode",
                                                        payload=json.dumps({"value": 1}),
                                                        hostname=ip, port=1883)
            self.textBrowser.append(f"<b>{dt_string} ---- | ---- MultiPlus Changed to Charger Only</b>")


        def Multiplus_Inverter():
            # Inverter Only
            mqttpublish.single("W/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Mode",
                                                        payload=json.dumps({"value": 2}),
                                                        hostname=ip, port=1883)
            self.textBrowser.append(f"<b>{dt_string} ---- | ---- MultiPlus Changed to Inverter Only</b>")


        def Multiplus_On():
            # ON
            mqttpublish.single("W/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Mode",
                                                        payload=json.dumps({"value": 3}),
                                                        hostname=ip, port=1883)
            self.textBrowser.append(f"<b>{dt_string} ---- | ---- MultiPlus Changed to On</b>")


        def Multiplus_Off():
            # Off
            mqttpublish.single("W/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Mode",
                                                        payload=json.dumps({"value": 4}),
                                                        hostname=ip, port=1883)
            self.textBrowser.append(f"<b>{dt_string} ---- | ---- MultiPlus Changed to OFF</b>")


        def ESSbatteryLifeEnabled():
            mqttpublish.single("W/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/State",
                                                        payload=json.dumps({"value": 1}),
                                                        hostname=ip, port=1883)
            self.textBrowser.append(f"<b>{dt_string} ---- | ---- BatteryLife Enabled</b>")


        def ESSbatteryLifeDisabled():
            mqttpublish.single("W/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/State",
                                                        payload=json.dumps({"value": 10}),
                                                        hostname=ip, port=1883)
            self.textBrowser.append(f"<b>{dt_string} ---- | ---- BatteryLife Disabled</b>")


        def ESSbatteriesCharged():
            # Mode 9 'Keep batteries charged' mode enabled
            mqttpublish.single("W/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/State",
                                                        payload=json.dumps({"value": 9}),
                                                        hostname=ip, port=1883)
            self.textBrowser.append(f"<b>{dt_string} ---- | ---- Keep Batteries Charged Enabled</b>")


        #===========================================================================================
        # Solar Charger Control
        def Charger1_On():
            mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Mode",
                                                    payload=json.dumps({"value": 1}),
                                                    hostname=ip, port=1883)
            self.textBrowser.append(f"<b>{dt_string} ---- | ---- Charger 1 Changed to ON</b>")


        def Charger1_Off():
            mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Mode",
                                                    payload=json.dumps({"value": 4}),
                                                    hostname=ip, port=1883)
            self.textBrowser.append(f"<b>{dt_string} ---- | ---- Charger 1 Changed to OFF</b>")


        def Charger2_On():
            mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Mode",
                                                    payload=json.dumps({"value": 1}),
                                                    hostname=ip, port=1883)
            self.textBrowser.append(f"<b>{dt_string} ---- | ---- Charger 2 Changed to ON</b>")

        def Charger2_Off():
            mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Mode",
                                                    payload=json.dumps({"value": 4}),
                                                    hostname=ip, port=1883)
            self.textBrowser.append(f"<b>{dt_string} ---- | ---- Charger 2 Changed to OFF</b>")


        def Charger3_On():
            mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/Mode",
                                                    payload=json.dumps({"value": 1}),
                                                    hostname=ip, port=1883)
            self.textBrowser.append(f"<b>{dt_string} ---- | ---- Charger 3 Changed to ON</b>")


        def Charger3_Off():
            mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/Mode",
                                                    payload=json.dumps({"value": 4}),
                                                    hostname=ip, port=1883)
            self.textBrowser.append(f"<b>{dt_string} ---- | ---- Charger 3 Changed to OFF</b>")


        def Charger1_Limit():
            answer, ok = QInputDialog.getInt(self, 'Enter Charger 1 Limit', 'Enter Charger 1 Limit', 20)
            if ok:
                mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Settings/ChargeCurrentLimit",
                                                                   payload=json.dumps({"value": answer}),
                                                                   hostname=ip, port=1883)
                self.textBrowser.append(f"<b>{dt_string} ---- | ---- Charger 1 Limit Changed to    {answer} Amps</b>")


        def Charger2_Limit():
            answer, ok = QInputDialog.getInt(self, 'Enter Charger 2 Limit', 'Enter Charger 2 Limit', 15)
            if ok:
                mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Settings/ChargeCurrentLimit",
                                                                   payload=json.dumps({"value": answer}),
                                                                   hostname=ip, port=1883)
                self.textBrowser.append(f"<b>{dt_string} ---- | ---- Charger 2 Limit Changed to    {answer} Amps</b>")


        def Charger3_Limit():
            answer, ok = QInputDialog.getInt(self, 'Enter Charger 3 Limit', 'Enter Charger 3 Limit', 30)
            if ok:
                mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_3_ID)+"/Settings/ChargeCurrentLimit",
                                                                   payload=json.dumps({"value": answer}), hostname=ip, port=1883)
                self.textBrowser.append(f"<b>{dt_string} ---- | ---- Charger 3 Limit Changed to    {answer} Amps</b>")


        def GridFeedIn():
            if FeedIn == 1:
                mqttpublish.single("W/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/OvervoltageFeedIn",
                                                                   payload=json.dumps({"value": 0}),
                                                                   hostname=ip, port=1883) # Off
                self.textBrowser.append(f"<b>{dt_string} ---- | ---- Grid Feedin Changed to OFF</b>")

            else:
                mqttpublish.single("W/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/OvervoltageFeedIn",
                                                                   payload=json.dumps({"value": 1}),
                                                                   hostname=ip, port=1883) # On
                self.textBrowser.append(f"<b>{dt_string} ---- | ---- Grid Feedin Changed to ON</b>")


        def SetGridWatts():
            answer, ok = QInputDialog.getInt(self, 'Enter Desired Grid Watts', 'Enter New Grid Watts Value',
                                            25, -1000, 1000, 5)
            if ok:
                mqttpublish.single("W/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/AcPowerSetPoint",
                                   payload=json.dumps({"value": answer}), hostname=ip, port=1883)
                self.textBrowser.append(f"<b>{dt_string} ---- | ---- Set Grid Watts Changed to    {answer} Watts</b>")


        def Clear_History():
            self.textBrowser.clear()


        def VEbusReset():
            mqttpublish.single("W/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/SystemReset",
                                                                   payload=json.dumps({"value": 1}),
                                                                   hostname=ip, port=1883) #
            self.textBrowser.append(f"<b>{dt_string} ---- | ---- Resetting V.E. Bus</b>")


        def Input_Amps_Limit():
            answer, ok = QInputDialog.getInt(self, 'Enter New AC Input Amps Limit', 'Enter New AC Input Amps Limit',
                                            25, 10, 50, 5)
            if ok:
                mqttpublish.single("W/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/CurrentLimit",
                                                            payload=json.dumps({"value": answer}),
                                                            hostname=ip, port=1883)
                self.textBrowser.append(f"<b>{dt_string} ---- | ---- Grid Input Limit Changed to    {answer} Amps</b>")

        def ESSuser():
            answer, ok = QInputDialog.getInt(self, 'Enter New ESS User Limit', 'ESS User Limit',
                                            75, 10, 100, 5)
            if ok:
                mqttpublish.single("W/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/MinimumSocLimit",
                                                            payload=json.dumps({"value": answer}),
                                                            hostname=ip, port=1883)
                self.textBrowser.append(f"<b>{dt_string} ---- | ---- ESS User Limit Changed to    {answer} Watts</b>")


        def BG_Change():
            color = QColorDialog.getColor(initial=QtGui.QColor('#2e3436')) # also sets the default color in the dialog
            if color.isValid():
                self.centralwidget.setStyleSheet(f"background-color: {color.name()}")
                #self.Solar_Name_1_lineEdit.setStyleSheet(f"background-color: {color.name()}")
                #self.Solar_Name_2_lineEdit.setStyleSheet(f"background-color: {color.name()}")
                self.tabWidget.setStyleSheet(f"background-color: {color.name()}")

        # Keep these out of the timing loop (.connect)
        self.FeedIn_pushButton.clicked.connect(GridFeedIn)
        self.Set_Grid_Watts_pushButton.clicked.connect(SetGridWatts)
        self.History_pushButton.clicked.connect(Clear_History)
        self.Reset_VEbus_pushButton.clicked.connect(VEbusReset)
        self.ACin_Amp_Limit_pushButton.clicked.connect(Input_Amps_Limit)

        self.actionOptimized_Battery_Life_Enabled.triggered.connect(ESSbatteryLifeEnabled)
        self.actionOptimized_Battery_Life_Disabled.triggered.connect(ESSbatteryLifeDisabled)
        self.actionKeep_Batteries_Charged.triggered.connect(ESSbatteriesCharged)
        self.actionChange_ESS_User_Limit.triggered.connect(ESSuser)
        self.actionCharger_Only.triggered.connect(Multiplus_Charger)
        self.actionInverter_Only.triggered.connect(Multiplus_Inverter)
        self.actionOff.triggered.connect(Multiplus_Off)
        self.actionOn.triggered.connect(Multiplus_On)

        self.actionCharger_1_Off.triggered.connect(Charger1_Off)
        self.actionCharger_1_On.triggered.connect(Charger1_On)
        self.actionCharger_2_Off.triggered.connect(Charger2_Off)
        self.actionCharger_2_On.triggered.connect(Charger2_On)
        self.actionCharger_3_Off.triggered.connect(Charger3_Off)
        self.actionCharger_3_On.triggered.connect(Charger3_On)

        self.actionSet_Current_Limit_1.triggered.connect(Charger1_Limit)
        self.actionSet_Current_Limit_2.triggered.connect(Charger2_Limit)
        self.actionSet_Current_Limit_3.triggered.connect(Charger3_Limit)

        # Full Screen & Normanl
        self.actionNormal_Screen.triggered.connect(self.showNormal)
        self.actionFull_Screen.triggered.connect(self.showFullScreen)
        self.actionChange_Background_Color.triggered.connect(BG_Change)


#===========================================================================================

# Timers
#===============================================
        # Clock
        self.qTimer = QTimer()

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
        self.qTimer2.timeout.connect(self.update)

        # start timer
        self.qTimer2.start()
#===============================================
        '''# make 3rd QTimer to set refresh rate on the Charts
        self.qTimer3 = QTimer()

        # set interval to 1 s
        self.qTimer3.setInterval(1000) # 1000 ms = 1 s

        # connect timeout signal to signal handler
        self.qTimer3.timeout.connect(self.update_charts)

        # start timer
        time.sleep(1)
        self.qTimer3.start()'''
#===============================================
        # Battery Temp Alarm LED Blink once per second (500 ms = 1 second cycle time)

        def BatteryBoxBlinkTimer():
                self.Battery_Box_Alarm_LED.setStyleSheet(f"color: {next(blinkred_Battery_Temp)}")

        # make QTimer
        self.qTimerBatteryBox = QTimer()

        # set interval
        self.qTimerBatteryBox.setInterval(500) # 500 ms = 1 second cycle time

        # connect timeout signal to signal handler
        self.qTimerBatteryBox.timeout.connect(BatteryBoxBlinkTimer)
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
#===============================================
        # Battery Amps Alarm LED Blink once per second (500 ms = 1 second cycle time)

        def BatteryAmpsBlinkTimer():
                self.Battery_Amps_Alarm_LED.setStyleSheet(f"color: {next(blinkred_Battery_Amps)}")

        # make QTimer
        self.qTimerBatteryAmps = QTimer()

        # set interval
        self.qTimerBatteryAmps.setInterval(500) # 500 ms = 1 second cycle time

        # connect timeout signal to signal handler
        self.qTimerBatteryAmps.timeout.connect(BatteryAmpsBlinkTimer)
#===============================================
        # Mains LED Blink once per second (500 ms = 1 second cycle time)

        def MainsBlinkTimer():
                self.Mains_LED.setStyleSheet(f"color: {next(blinkgreen_Mains)}")

        # make QTimer
        self.qTimerMains = QTimer()

        # set interval
        self.qTimerMains.setInterval(500) # 500 ms = 1 second cycle time

        # connect timeout signal to signal handler
        self.qTimerMains.timeout.connect(MainsBlinkTimer)

#===============================================
        # Bulk LED Blink once per second (500 ms = 1 second cycle time)

        def BulkBlinkTimer():
                self.Bulk_LED.setStyleSheet(f"color: {next(blinkyellow_Bulk)}")

        # make QTimer
        self.qTimerBulk = QTimer()

        # set interval
        self.qTimerBulk.setInterval(500) # 500 ms = 1 second cycle time

        # connect timeout signal to signal handler
        self.qTimerBulk.timeout.connect(BulkBlinkTimer)
#===============================================
        # Absorption LED Blink once per second (500 ms = 1 second cycle time)

        def AbsorpBlinkTimer():
                self.Absorption_LED.setStyleSheet(f"color: {next(blinkyellow_Absorption)}")

        # make QTimer
        self.qTimerAbsorp = QTimer()

        # set interval
        self.qTimerAbsorp.setInterval(500) # 500 ms = 1 second cycle time

        # connect timeout signal to signal handler
        self.qTimerAbsorp.timeout.connect(AbsorpBlinkTimer)
#===============================================
        # Float LED Blink once per second (500 ms = 1 second cycle time)

        def FloatBlinkTimer():
                self.Float_LED.setStyleSheet(f"color: {next(blinkyellow_Float)}")

        # make QTimer
        self.qTimerFloat = QTimer()

        # set interval
        self.qTimerFloat.setInterval(500) # 500 ms = 1 second cycle time

        # connect timeout signal to signal handler
        self.qTimerFloat.timeout.connect(FloatBlinkTimer)
#===============================================
        # Inverter LED Blink once per second (500 ms = 1 second cycle time)

        def InverterBlinkTimer():
                self.Inverting_LED.setStyleSheet(f"color: {next(blinkgreen_Inverter)}")

        # make QTimer
        self.qTimerInverter = QTimer()

        # set interval
        self.qTimerInverter.setInterval(500) # 500 ms = 1 second cycle time

        # connect timeout signal to signal handler
        self.qTimerInverter.timeout.connect(InverterBlinkTimer)
#===============================================
        # Overload LED Blink once per second (500 ms = 1 second cycle time)
        def OverloadBlinkTimer():
                self.Overload_LED.setStyleSheet(f"color: {next(blinkred_OverLoad)}")

        # make QTimer
        self.qTimerOverload = QTimer()

        # set interval
        self.qTimerOverload.setInterval(500) # 500 ms = 1 second cycle time

        # connect timeout signal to signal handler
        self.qTimerOverload.timeout.connect(OverloadBlinkTimer)
#===============================================
        # Low Battery LED Blink once per second (500 ms = 1 second cycle time)
        def LowBattBlinkTimer():
                self.Low_Battery_LED.setStyleSheet(f"color: {next(blinkred_LowBatt)}")

        # make QTimer
        self.qTimerLowBatt = QTimer()

        # set interval
        self.qTimerLowBatt.setInterval(500) # 500 ms = 1 second cycle time

        # connect timeout signal to signal handler
        self.qTimerLowBatt.timeout.connect(LowBattBlinkTimer)
#===============================================
        # Temperature LED Blink once per second (500 ms = 1 second cycle time)
        def TemperatureBlinkTimer():
                self.Temperature_LED.setStyleSheet(f"color: {next(blinkred_Temp)}")

        # make QTimer
        self.qTimerTemp = QTimer()

        # set interval
        self.qTimerTemp.setInterval(500) # 500 ms = 1 second cycle time

        # connect timeout signal to signal handler
        self.qTimerTemp.timeout.connect(TemperatureBlinkTimer)
#===========================================================================================
        """ Make sure the GX variable Qthread has completed first loop before starting chart update thread
            These variables were set as None at top of script"""
        # while VEbusStatus is None and VEbusError is None:
        #       loading time is much faster with a sleep interval, then an unrestricted loop
        #    time.sleep(.01)
        #    continue
        Thread(target=self.update_charts).start()

#===========================================================================================
    def showTime(self):
        # Datetime object containing current date and time
        nowTime = datetime.now()
        # Fri 21 Jan 2022     09:06:57 PM
        Time_string = nowTime.strftime("%a %d %b %Y     %r")
        self.Time_Label.setText(Time_string)
        self.statusBar.showMessage(f"{Time_string}{big_tab}App Started on {dt_stringStart}")
#===========================================================================================

    def closeEvent(self, event: QtGui.QCloseEvent):
        global running
        running = False
        print(f"\033[0m==========================================")
        print(f"\033[38;5;148mExiting App\033[0m")
        client.disconnect()

#===========================================================================================
    def update_charts(self):
        while running:
            timestamp = time.time()
            try:

                # Sleep time is needed in small groups vs one single value to prevent Chart Crosshair lag when appending the deque.
                # 18 plots at
                #40000 points(MAX) each takes some time to load up. Not quite sure why this works better.
                # Maybe my computer is too slow? (Intel Core i7-8550U, 8G Ram)

                # Solar
                self.watts_connector.cb_append_data_point(int(SolarWatts), timestamp)
                self.PV1watts_connector.cb_append_data_point(float(SolarWatts1), timestamp)
                self.PV2watts_connector.cb_append_data_point(float(SolarWatts2), timestamp)
                self.PV3watts_connector.cb_append_data_point(float(SolarWatts3), timestamp)
                time.sleep(.1)

                # Battery
                self.bat_watts_connector.cb_append_data_point(float(BatteryWatts), timestamp)
                self.amps_connector.cb_append_data_point(float(BatteryAmps), timestamp)
                self.volts_connector.cb_append_data_point(float(BatteryVolts), timestamp)
                self.soc_connector.cb_append_data_point(float(BatterySOC), timestamp)
                time.sleep(.1)

                # A/C In
                self.grid_amps_L1_connector.cb_append_data_point(float(GridAmpsL1), timestamp)
                self.grid_watts_L1_connector.cb_append_data_point(float(GridWattsL1), timestamp)
                if GridVoltsL2 > 0:
                    self.grid_watts_L2_connector.cb_append_data_point(float(GridWattsL2), timestamp)
                    self.grid_amps_L2_connector.cb_append_data_point(float(GridAmpsL2), timestamp)
                time.sleep(.1)

                # A/C Out
                self.ac_out_watts_L1_connector.cb_append_data_point(float(ACoutWattsL1), timestamp)
                self.ac_out_watts_L2_connector.cb_append_data_point(float(ACoutWattsL2), timestamp)
                self.ac_out_amps_L1_connector.cb_append_data_point(float(ACoutAmpsL1), timestamp)
                self.ac_out_amps_L2_connector.cb_append_data_point(float(ACoutAmpsL2), timestamp)
                self.ac_out_freq_connector.cb_append_data_point(float(ACoutHZ), timestamp)
                time.sleep(.2)

                if Analog_Inputs.lower() == 'y':
                    self.Box_Temp_connector.cb_append_data_point(float(TempSensor1), timestamp)
                    self.Interior_Temp_connector.cb_append_data_point(float(TempSensor2), timestamp)
                    self.Exterior_Temp_connector.cb_append_data_point(float(TempSensor3), timestamp)
                    time.sleep(.1)

                global SolarState1, SolarState2, SolarState3
                SolarState1Index  = list(SolarStateDict.keys()).index(SolarState1)
                SolarState2Index  = list(SolarStateDict.keys()).index(SolarState2)
                SolarState3Index  = list(SolarStateDict.keys()).index(SolarState3)
                time.sleep(.1)

                self.state1_connector.cb_append_data_point([categories[SolarState1Index]], timestamp)
                self.state2_connector.cb_append_data_point([categories[SolarState2Index]], timestamp)
                self.state3_connector.cb_append_data_point([categories[SolarState3Index]], timestamp)
                time.sleep(.1)

                if Bulk == 1 and Absorp != 1 and Floatchg != 1: #Charging LED's
                    MP_State = 2 # Bulk State
                elif Absorp == 1 and Bulk != 1 and Floatchg != 1: #Charging LED's
                    MP_State = 1 # Absorption State
                elif Floatchg == 1 and Bulk != 1 and Absorp != 1: #Charging LED's
                    MP_State = 0 # Float State

               #    Index          0            1         2          3        4         5
               # MP_categories   Float     Absorption    Bulk    Inverting   Mains   Grid Lost
                if GridCondition == 2:
                    # Inverting On & Grid Lost (2 active bars on chart). There is no charger status LED's in this state.
                    self.MP_connector.cb_append_data_point([MP_categories[3],MP_categories[5]], timestamp)

                elif MPswitch == 2:  # Multiplus Mode Inverter only
                    # Inverting On (1 active bar on chart). There is no charger status LED's in this state.
                    self.MP_connector.cb_append_data_point([MP_categories[3]], timestamp)

                elif Inverter >= 1 and Mains >= 1:
                    # Charging Status, Inverting On & Grid Connected (3 active bars on chart)
                    self.MP_connector.cb_append_data_point([MP_categories[MP_State],MP_categories[3],MP_categories[4]], timestamp)

                elif Inverter == 0 and Mains >= 1: # Inverting Off & Grid Connected
                    # Charging Status, Inverting Off & Grid Connected (2 active bars on chart)
                    self.MP_connector.cb_append_data_point([MP_categories[MP_State],MP_categories[4]], timestamp)
                time.sleep(.2)
            except AttributeError:
                print(f"\033[38;5;27mAttributeError in Update Charts, Retrying......\033[0m")
            except NameError:
                print(f"\033[38;5;27mNameError in Update Charts, Retrying......\033[0m")
            except TypeError:
                print(f"\033[38;5;27mTypeError in Update Charts, Retrying......\033[0m")


#===========================================================================================

    def update(self): # Update all the UI widgets
        global dt_string, TempSensor1
        # Datetime object containing current date and time
        now = datetime.now()
        # Fri 21 Jan 2022     09:06:57 PM
        dt_string = now.strftime("%a %d %b %Y  %r")

        PvAmps1            = SolarWatts1 / SolarVolts1
        PvAmps2            = SolarWatts2 / SolarVolts2
        PvAmps3            = SolarWatts3 / SolarVolts3
        TotalYield         = SolarYield1 + SolarYield2 + SolarYield3
        TotalYieldYest     = SolarYieldYest1 + SolarYieldYest2 + SolarYieldYest3
        MaxTotalWattsToday = MaxSolarWatts1 + MaxSolarWatts2 + MaxSolarWatts3
        MaxTotalWattsToday = f"{MaxTotalWattsToday: .0f}"
        MaxTotalWattsYest  = MaxSolarWattsYest1 + MaxSolarWattsYest2 + MaxSolarWattsYest3
        MaxTotalWattsYest  = f"{MaxTotalWattsYest: .0f}"
        BigSolarWatts      = f"{SolarWatts: .0f}"
        New_LastFullcharge = timedelta(seconds = int(LastFullcharge))


        # LED's to indicate if the Charger is switched on or off
        # Not to be confused with the charging "state" which can be off, bulk, absorp, float
        if SolarOn1 == 1:
            self.SolarMode_1_LED.setStyleSheet(f"color: green")
        elif SolarOn1 == 4:
            self.SolarMode_1_LED.setStyleSheet(f"color: red")
        if SolarOn2 == 1:
            self.SolarMode_2_LED.setStyleSheet(f"color: green")
        elif SolarOn2 == 4:
            self.SolarMode_2_LED.setStyleSheet(f"color: red")
        if SolarOn3 == 1:
            self.SolarMode_3_LED.setStyleSheet(f"color: green")
        elif SolarOn3 == 4:
            self.SolarMode_3_LED.setStyleSheet(f"color: red")


        if BatteryTTG == None :
            New_BatteryTTG = "Infinite"
        else:
        # BatteryTTG has a value of seconds. We dont want to change its "type" to "datetime"
        # because we dont want to pass a "datetime" to timedelta on the second+ update because it change's.
        # Make a new variable to hold the timedelta
            New_BatteryTTG = BatteryTTG
            New_BatteryTTG = f"{New_BatteryTTG:.0f}"
            New_BatteryTTG = timedelta(seconds = int(New_BatteryTTG))

        # Current Battery State
        if BatteryState == 0:
            New_BatteryState = "Idle"
        elif BatteryState == 1:
            New_BatteryState = "Charging"
        elif BatteryState == 2:
            New_BatteryState = "Discharging"

        # If grid watts is less than zero feedin is active and show the label "FeedIn Active"
        if GridWattsL1 < 0 and Mains >= 2:
            self.Grid_FeedIn_Active_Label.setHidden(False)
            self.Grid_Watts_LCD_L1.setStyleSheet("QLCDNumber { background: rgb(0, 128, 255); }");
            self.Grid_FeedIn_Active_Label.setText("FeedIn Active")
            self.Grid_FeedIn_Active_Label.setStyleSheet("QLabel { background: rgb(0, 128, 255); color: rgb(0, 0, 0); }")

        # If grid watts is NOT less than zero, Hide the label "FeedIn Active"
        else:
            self.Grid_FeedIn_Active_Label.setHidden(True)
            self.Grid_Watts_LCD_L1.setStyleSheet("QLCDNumber { background: rgb(85, 87, 83); }")

        # If "Feedin" is allowed and it is limited, show thw label and its limit
        if FeedIn == 1 and FeedInLimited == 1:
            self.Grid_FeedIn_Limit_Label.setHidden(False)
            self.Grid_FeedIn_Limit_Label.setText(f"Feed In Limited to {FeedInMax:.0f} W per Phase")
        else:
            self.Grid_FeedIn_Limit_Label.setHidden(True)

        # If "Feedin" is allowed. Show the label on the button
        if FeedIn == 1:
            self.FeedIn_pushButton.setText('Enabled')

        # If "Feedin" is NOT allowed. Show the label on the button
        elif FeedIn == 0:
            self.FeedIn_pushButton.setText('Disabled')

        # If grid power is in a normal state, Show label "OK"
        if GridCondition == 0:
            Condition = 'OK'
            self.Grid_Condition_lineEdit.setStyleSheet("QLineEdit { background: rgb(136, 138, 133); }");

        # If grid power is NOT in a normal state, Show label "LOST"
        elif GridCondition == 2:
            Condition = 'LOST'
            self.Grid_Condition_lineEdit.setStyleSheet("QLineEdit { background: red; }");

        # Change color of progressbar based on value
        if BatterySOC >= 66:
            self.Batt_SOC_progressBar.setStyleSheet("QProgressBar#Batt_SOC_progressBar{selection-background-color:"
                                                    "rgb(36, 232, 20);color: rgb(0, 0, 0)}"); # Green
        elif BatterySOC < 66 and BatterySOC >= 33:
            self.Batt_SOC_progressBar.setStyleSheet("QProgressBar#Batt_SOC_progressBar{selection-background-color:"
                                                    "rgb(255, 255, 0);color: rgb(0, 0, 0)}"); # Yellow
        elif BatterySOC < 33:
            self.Batt_SOC_progressBar.setStyleSheet("QProgressBar#Batt_SOC_progressBar{selection-background-color:"
                                                    "rgb(200, 0, 0);}"); # Red

        # The Big Font Watts Label
        #SolarWatts = 923
        self.Total_Watts_label.setText(str(BigSolarWatts))

        # If you have the temperature inputs enabled
        if Analog_Inputs.lower() == 'y':
            self.TempSensor1_lcdNumber.display(str(f"{TempSensor1:.1f}"))
            self.TempSensor2_lcdNumber.display(str(f"{TempSensor2:.1f}"))
            self.TempSensor3_lcdNumber.display(str(f"{TempSensor3:.1f}"))
        else:
            self.Battery_Box_Alarm_LED.setHidden(True)
            self.Temperature_frame.setHidden(True)
            self.TempSensor1_lcdNumber.setHidden(True)
            self.TempSensor2_lcdNumber.setHidden(True)
            self.TempSensor3_lcdNumber.setHidden(True)
            self.TempSensor1_label.setHidden(True)
            self.TempSensor2_label.setHidden(True)
            self.TempSensor3_label.setHidden(True)

# ===========================================================================================

# Battery Box Temp LED
        # if you want to test this change the Batt_Temp_Lo or Batt_Temp_Hi variable at the top of the script
        if Analog_Inputs.lower() == 'y':
            if TempSensor1 == 99:
                print("Analog Input Sensor 1 Disconnected or Wrong Address")
            if TempSensor2 == 99:
                print("Analog Input Sensor 2 Disconnected or Wrong Address")
            if TempSensor3 == 99:
                print("Analog Input Sensor 3 Disconnected or Wrong Address")

            if TempSensor1 > Batt_Temp_Lo and TempSensor1 < Batt_Temp_Hi: # Off
                if self.qTimerBatteryBox.isActive():
                    # Blue Bold Text
                    self.qTimerBatteryBox.stop()
                self.Battery_Box_Alarm_LED.setStyleSheet("color: rgb(28, 28, 28)") # dark

            elif TempSensor1 > Batt_Temp_Hi or TempSensor1 < Batt_Temp_Lo: # Blink
                if not self.qTimerBatteryBox.isActive():
                    self.qTimerBatteryBox.start()
# ===========================================================================================

# Battery Amps LED
        #BatteryAmps = 101
        if BatteryAmps <= MaxAmps: # Off
            if self.qTimerBatteryAmps.isActive():
                # Blue Bold Text
                self.textBrowser.append(f"<b><span style=\" color: #050a49;\">{dt_string} ---- | ---- Battery Charging Amps Returned to Normal Level.   {BatteryAmps:.1f} Amps<span style=\" color: black;\"</span></b>")
                self.qTimerBatteryAmps.stop()
            self.Battery_Amps_Alarm_LED.setStyleSheet("color: rgb(28, 28, 28)") # dark

        elif BatteryAmps > MaxAmps: # Blink
            if not self.qTimerBatteryAmps.isActive():
                # Red Bold Text
                self.textBrowser.append(f"<b><span style=\" color: #6f0f16;\">{dt_string} ---- | ---- Battery Charging Amps Exceeded.   {BatteryAmps:.1f} Amps<span style=\" color: black;\"</span></b>")
                self.qTimerBatteryAmps.start()
#====================================================================
# Mains LED
        #Mains = 3
        if Mains == 0: # Off
            if self.qTimerMains.isActive():
                self.qTimerMains.stop()
            self.Mains_LED.setStyleSheet("color: rgb(28, 28, 28)") # dark

        elif Mains == 1: # On
            if self.qTimerMains.isActive():
                self.qTimerMains.stop()
            self.Mains_LED.setStyleSheet("color: rgb(0,154,23)") # bright Green

        elif Mains >= 2: # Blink
            if not self.qTimerMains.isActive():
                self.qTimerMains.start()
#====================================================================
# Inverter LED
        #Inverter = 3
        if Inverter == 0: # Off
            if self.qTimerInverter.isActive():
                self.qTimerInverter.stop()
            self.Inverting_LED.setStyleSheet("color: rgb(28, 28, 28)") # dark
        elif Inverter == 1: # On
            if self.qTimerInverter.isActive():
                self.qTimerInverter.stop()
            self.Inverting_LED.setStyleSheet("color: rgb(0,154,23)") # bright Green
        elif Inverter >= 2: # Blink
            if not self.qTimerInverter.isActive():
                self.qTimerInverter.start()
#====================================================================
# Bulk LED
        #Bulk = 3
        if Bulk == 0: # Off
            if self.qTimerBulk.isActive():
                self.qTimerBulk.stop()
            self.Bulk_LED.setStyleSheet("color: rgb(28, 28, 28)") # dark
        elif Bulk == 1: # On
            if self.qTimerBulk.isActive():
                self.qTimerBulk.stop()
            self.Bulk_LED.setStyleSheet("color: rgb(255, 255, 0)") # yellow
        elif Bulk >= 2: # Blink
            if not self.qTimerBulk.isActive():
                self.qTimerBulk.start()
#====================================================================
# Overload LED
        if Overload == 0: # Off
            if self.qTimerOverload.isActive():
                self.qTimerOverload.stop()
            self.Overload_LED.setStyleSheet("color: rgb(28, 28, 28)"); # dark

        elif Overload == 1: # On
            if self.qTimerOverload.isActive():
                self.qTimerOverload.stop()
            self.Overload_LED.setStyleSheet("color: rgb(255, 0, 0)"); # red

        elif Overload >= 2: # Blink
            if not self.qTimerOverload.isActive():
                self.qTimerOverload.start()
#====================================================================
# Absorption LED
        #Absorp = 3
        if Absorp == 0: # Off
            if self.qTimerAbsorp.isActive():
                self.qTimerAbsorp.stop()
            self.Absorption_LED.setStyleSheet("color: rgb(28, 28, 28)"); # dark
                                                         # Orange rgb(247, 119, 7)
        elif Absorp == 1: # On
            if self.qTimerAbsorp.isActive():
                self.qTimerAbsorp.stop()
            self.Absorption_LED.setStyleSheet("color: rgb(255, 255, 0)"); # yellow

        elif Absorp >= 2: # Blink
            if not self.qTimerAbsorp.isActive():
                self.qTimerAbsorp.start()
#====================================================================
# Low Battery LED
        if Lowbatt == 0: # Off
            if self.qTimerLowBatt.isActive():
                self.qTimerLowBatt.stop()
            self.Low_Battery_LED.setStyleSheet("color: rgb(28, 28, 28)"); # dark
                                                         # Orange rgb(247, 119, 7)
        elif Lowbatt == 1: # On
            if self.qTimerLowBatt.isActive():
                self.qTimerLowBatt.stop()
            self.Low_Battery_LED.setStyleSheet("color: rgb(255, 0, 0)"); # red

        elif Lowbatt >= 2: # Blink
            if not self.qTimerLowBatt.isActive():
                self.qTimerLowBatt.start()
#====================================================================
# Float LED
        #Floatchg = 0
        if Floatchg == 0: # Off
            if self.qTimerFloat.isActive():
                self.qTimerFloat.stop()
            self.Float_LED.setStyleSheet("color: rgb(28, 28, 28)"); # dark

        elif Floatchg == 1: # On
            if self.qTimerFloat.isActive():
                self.qTimerFloat.stop()
            self.Float_LED.setStyleSheet("color: rgb(255, 255, 0)"); # Yellow
                                                         # Orange rgb(247, 119, 7)
        elif Floatchg >= 2: # Blink
            if not self.qTimerFloat.isActive():
                self.qTimerFloat.start()
#====================================================================
# Temperature LED
        if Temperature == 0: # Off
            if self.qTimerTemp.isActive():
                self.qTimerTemp.stop()
            self.Temperature_LED.setStyleSheet("color: rgb(28, 28, 28)"); # dark

        elif Temperature == 1: # On
            if self.qTimerTemp.isActive():
                self.qTimerTemp.stop()
            self.Temperature_LED.setStyleSheet("color: rgb(255, 0, 0)"); # red

        elif Temperature >= 2: # Blink
            if not self.qTimerTemp.isActive():
                self.qTimerTemp.start()
#====================================================================
    # MQTT LED Alarm
        global flag_connected
        if flag_connected == 1:
            if not self.qTimerMQTT.isActive():
                self.qTimerMQTT.start()
                self.textBrowser.append(f"<b><span style=\" color: green;\">{dt_string} ---- | ---- MQTT Broker Connected and Receiving Messages<span style=\" color: black;\"</span></b>")

        else:
            if self.qTimerMQTT.isActive():
                self.qTimerMQTT.stop()
                self.MQTT_LED.setStyleSheet("color: rgb(255, 0, 0)") # Red
                self.textBrowser.append(f"<b><span style=\" color: red;\">{dt_string} ---- | ---- MQTT Broker Disconnected, Trying to Reconnect<span style=\" color: black;\"</span></b>")
#====================================================================
#   VE.Bus Status
        if VEbusStatus == 2:
            self.System_State_Value.setText(str(VEbusStatusDict[VEbusStatus]))
            self.System_State_Value.setStyleSheet("QLabel#System_State_Value{font-weight: bold; color: red; background-color: black;}");

        else:
            self.System_State_Value.setText(str(VEbusStatusDict[VEbusStatus]))
            self.System_State_Value.setStyleSheet("QLabel#System_State_Value{font-weight: bold; color: rgb(0, 0, 0);}");
#====================================================================
#   VE.Bus Error
        if VEbusError > 0:
            self.VE_Bus_Error_Value.setText(str(VEbusErrorDict[VEbusError]))
            self.VE_Bus_Error_Value.setStyleSheet("QLabel#VE_Bus_Error_Value{font-weight: bold; color: red; background-color: black;}");

        else:
            self.VE_Bus_Error_Value.setText(str(VEbusErrorDict[VEbusError]))
            self.VE_Bus_Error_Value.setStyleSheet("QLabel#VE_Bus_Error_Value{font-weight: bold; color: rgb(0, 255, 0);}");

        # Battery Life Disabled
        if ESSbatteryLifeState >= 10:
            self.ESS_SOC_Dynamic_label.setHidden(True)
            self.ESS_SOC_Dynamic_Value.setHidden(True)
            self.ESS_SOC_User_Value.setText(str(ESSsocLimitUser))
            self.ESS_Mode_Value.setText(ESSbatteryLifeStateDict[ESSbatteryLifeState] + "           ESS Type: Optimized (BatteryLife Disabled)")

        # Battery Life Enabled
        elif ESSbatteryLifeState >= 1 and ESSbatteryLifeState <= 8:
            self.ESS_SOC_Dynamic_label.setHidden(False)
            self.ESS_SOC_Dynamic_Value.setHidden(False)
            self.ESS_SOC_User_label.setHidden(False)
            self.ESS_SOC_User_Value.setHidden(False)
            self.ESS_SOC_User_Value.setText(str(ESSsocLimitUser))
            self.ESS_SOC_Dynamic_Value.setText(str(ESSsocLimitDynamic))
            self.ESS_Mode_Value.setText(ESSbatteryLifeStateDict[ESSbatteryLifeState] + "           ESS Type: Optimized (BatteryLife Enabled)")

        # Keep Batteries Charged Mode
        elif ESSbatteryLifeState == 9:
            self.ESS_SOC_Dynamic_label.setHidden(True)
            self.ESS_SOC_Dynamic_Value.setHidden(True)
            self.ESS_SOC_User_label.setHidden(True)
            self.ESS_SOC_User_Value.setHidden(True)
            self.ESS_Mode_Value.setText(ESSbatteryLifeStateDict[ESSbatteryLifeState])


#====================================================================
#   Multiplus Switch
        global MPswitch
        if MPswitch == 1:
            New_MPswitch = "Charger Only"
        elif MPswitch == 2:
            New_MPswitch = "Inverter Only"
        elif MPswitch == 3:
            New_MPswitch = "ON"
        elif MPswitch == 4:
            New_MPswitch = "OFF"

        if New_MPswitch != "ON":
            self.Multiplus_Mode_Value.setStyleSheet("QLineEdit { background: rgb(255, 191, 0); }");
        else:
            self.Multiplus_Mode_Value.setStyleSheet("QLineEdit { background: rgb(0, 155, 0); }");

        #print(f"{TempSensor1} TempSensor1")





#===========================================================================================
# Populate Screen with Variable Values
#===========================================================================================
        # Battery Section
        self.Batt_SOC_progressBar.setRange(0, 100)
        #self.Batt_SOC_progressBar.setMaximum(100)
        self.Batt_SOC_progressBar.setValue(int(BatterySOC))
        self.Batt_SOC_progressBar.setFormat("%.1f %%" % BatterySOC)
        self.Batt_SOC_progressBar.setToolTip(f'{BatterySOC:.1f} Percent')

        self.Batt_Watts_LCD.display(BatteryWatts)
        self.Batt_Amps_LCD.display(BatteryAmps)
        self.Batt_Volts_LCD.display(f"{BatteryVolts:.2f}")
        self.DC_Power_LCD.display(f"{DCsystemPower:.0f}")
        self.Batt_State_lineEdit.setText(New_BatteryState)
        self.Last_Discharge_LCD.display(LastDischarge)
        self.Consumed_AH_LCD.display(ConsumedAH)
        self.Deepest_Discharge_LCD.display(DeepestDischarge)
        self.AVG_Discharge_AH_LCD.display(AvgDischarge)
        self.Max_Charge_Amps_LCD.display(MaxChargeCurrent)
        self.Charge_Cycles_LCD.display(ChargeCycles)
        self.Last_Full_Charge_lineEdit.setText(str(f"{New_LastFullcharge} Ago"))
        self.Time_To_Go_lineEdit.setText(str(New_BatteryTTG))


        # Solar Charger # 1 Section
        self.Solar_Name_1_lineEdit.setText(str(f"#1 {SolarName1} - {Array1}"))
        self.PV_Watts_1_LCD.display(str(f"{SolarWatts1:.0f}"))
        self.Output_Amps_1_LCD.display(str(f"{SolarAmps1:.1f}"))
        self.Output_Amps_Limit_1_label.setText(SolarChargeLimit1)
        self.PV_Volts_1_LCD.display(str(f"{SolarVolts1:.1f}"))
        self.PV_Amps_1_LCD.display(f"{PvAmps1:.2f}")
        self.Max_PV_Watts_Today_1_LCD.display(MaxSolarWatts1)
        self.Max_PV_Watts_Yesterday_1_LCD.display(MaxSolarWattsYest1)
        self.Yield_Today_1_LCD.display(f"{SolarYield1:.3f}")
        self.Yield_Yesterday_1_LCD.display(f"{SolarYieldYest1:.3f}")
        self.Solar_Charger_State_1_lineEdit.setText(SolarStateDict[SolarState1])

        # Solar Charger # 2 Section
        self.Solar_Name_2_lineEdit.setText(f"#2 {SolarName2} - {Array2}")
        self.PV_Watts_2_LCD.display(str(f"{SolarWatts2:.0f}"))
        self.Output_Amps_2_LCD.display(f"{SolarAmps2:.1f}")
        self.Output_Amps_Limit_2_label.setText(SolarChargeLimit2)
        self.PV_Volts_2_LCD.display(SolarVolts2)
        self.PV_Amps_2_LCD.display(f"{PvAmps2:.2f}")
        self.Max_PV_Watts_Today_2_LCD.display(MaxSolarWatts2)
        self.Max_PV_Watts_Yesterday_2_LCD.display(MaxSolarWattsYest2)
        self.Yield_Today_2_LCD.display(f"{SolarYield2:.3f}")
        self.Yield_Yesterday_2_LCD.display(f"{SolarYieldYest2:.3f}")
        self.Solar_Charger_State_2_lineEdit.setText(SolarStateDict[SolarState2])

        # Solar Charger # 3 Section
        self.Solar_Name_3_lineEdit.setText(f"#3 {SolarName3} - {Array3}")
        self.PV_Watts_3_LCD.display(str(f"{SolarWatts3:.0f}"))
        self.Output_Amps_3_LCD.display(f"{SolarAmps3:.1f}")
        self.Output_Amps_Limit_3_label.setText(SolarChargeLimit3)
        self.PV_Volts_3_LCD.display(SolarVolts3)
        self.PV_Amps_3_LCD.display(f"{PvAmps3:.2f}")
        self.Max_PV_Watts_Today_3_LCD.display(MaxSolarWatts3)
        self.Max_PV_Watts_Yesterday_3_LCD.display(MaxSolarWattsYest3)
        self.Yield_Today_3_LCD.display(f"{SolarYield3:.3f}")
        self.Yield_Yesterday_3_LCD.display(f"{SolarYieldYest3:.3f}")
        self.Solar_Charger_State_3_lineEdit.setText(SolarStateDict[SolarState3])


        self.Total_Yield_Label.setText(str(f" Yield Today {TotalYield:.3f} kwh"))
        self.Total_Yield_Label_Yest.setText(str(f" Yield Yesterday {TotalYieldYest:.3f} kwh"))
        self.Max_Watts_Today_Label.setText(str(f"Max Watts Today {MaxTotalWattsToday} W"))
        self.Max_Watts_Yest_Label.setText(str(f"Max Watts Yesterday {MaxTotalWattsYest} W"))

        # Multiplus Section
        self.Grid_Set_Point_LCD.display(GridSetPoint)
        self.Grid_Watts_LCD_L1.display(GridWattsL1)
        self.Grid_Watts_LCD_L2.display(GridWattsL2)
        self.AC_Out_Watts_LCD_L1.display(ACoutWattsL1)
        self.AC_Out_Watts_LCD_L2.display(ACoutWattsL2)
        self.Grid_Amps_LCD_L1.display(GridAmpsL1)
        self.Grid_Amps_LCD_L2.display(GridAmpsL2)
        self.AC_Out_Amps_LCD_L1.display(ACoutAmpsL1)
        self.AC_Out_Amps_LCD_L2.display(ACoutAmpsL2)
        self.Grid_Volts_LCD_L1.display(GridVoltsL1)
        self.Grid_Volts_LCD_L2.display(GridVoltsL2)
        self.AC_Out_Volts_LCD_L1.display(ACoutVoltsL1)
        self.AC_Out_Volts_LCD_L2.display(ACoutVoltsL2)
        self.Grid_Freq_LCD.display(GridHZ)
        self.AC_Out_Freq_LCD.display(ACoutHZ)
        self.Grid_Condition_lineEdit.setText(Condition)
        self.Grid_Current_Limit_LCD.display(GridAmpLimit)
        self.MultiName_label.setText(MultiName)

        # GX Firmware Section
        #self.Firmware_Installed_Value_label.setText(str(f"{FW_Installed}"))
        #self.Firmware_Available_Value_label.setText(str(f"{FW_Available}"))
        #self.Firmware_Backup_Value_label.setText(str(f"{FW_Backup}"))

#===========================================================================================
# Text Browser Log, Event History
        global SolarState1_Old, SolarState2_Old, SolarState3_Old, GridCondition_Old, \
        Mains_Old, Inverter_Old, Absorp_Old, Floatchg_Old, Bulk_Old, ESSbatteryLifeState_Old

        if self.SCC_checkBox.isChecked():
            if SolarState1 != SolarState1_Old:
                self.textBrowser.append(f"<b>{dt_string} ---- | ---- Solar Charger 1 Changed to   {SolarStateDict[SolarState1]}</b>")
                SolarState1_Old = SolarState1
            if SolarState2 != SolarState2_Old:
                self.textBrowser.append(f"<b>{dt_string} ---- | ---- Solar Charger 2 Changed to   {SolarStateDict[SolarState2]}</b>")
                SolarState2_Old = SolarState2
            if SolarState3 != SolarState3_Old:
                self.textBrowser.append(f"<b>{dt_string} ---- | ---- Solar Charger 3 Changed to   {SolarStateDict[SolarState3]}</b>")
                SolarState3_Old = SolarState3


        if self.Grid_checkBox.isChecked():
            if GridCondition != GridCondition_Old:
                if GridCondition == 2:
                    self.textBrowser.append(f"<b>{dt_string} ---- | ---- Grid Lost</b>")
                    GridCondition_Old = GridCondition
                else:
                    self.textBrowser.append(f"<b>{dt_string} ---- | ---- Grid Restored</b>")
                    GridCondition_Old = GridCondition

        if self.Inv_checkBox.isChecked():
            if Inverter != Inverter_Old:
                if Inverter == 0:
                    self.textBrowser.append(f"<b>{dt_string} ---- | ---- Inverter Changed to   OFF</b>")
                    Inverter_Old = Inverter
                elif Inverter == 1:
                    self.textBrowser.append(f"<b>{dt_string} ---- | ---- Inverter Changed to   ON</b>")
                    Inverter_Old = Inverter
                elif Inverter >= 2:
                    self.textBrowser.append(f"<b>{dt_string} ---- | ---- Inverter Changed to Power Assist Active</b>")
                    Inverter_Old = Inverter

        if self.Mains_checkBox.isChecked():
            if Mains != Mains_Old:
                if Mains == 1:
                    self.textBrowser.append(f"<b>{dt_string} ---- | ---- Mains Changed to   Normal</b>")
                    Mains_Old = Mains
                elif Mains >= 2 and GridWattsL1 < 0:
                    self.textBrowser.append(f"<b>{dt_string} ---- | ---- Mains Changed to Feed-In Active</b>")
                    Mains_Old = Mains

        if self.Multi_checkBox.isChecked():
            if Bulk != Bulk_Old:
                if Bulk == 1:
                    self.textBrowser.append(f"<b>{dt_string} ---- | ---- Bulk Charging   ON</b>")
                    Bulk_Old = Bulk
                elif Bulk == 0:
                    self.textBrowser.append(f"<b>{dt_string} ---- | ---- Bulk Charging   OFF</b>")
                    Bulk_Old = Bulk

            if Absorp != Absorp_Old:
                if Absorp == 1:
                    self.textBrowser.append(f"<b>{dt_string} ---- | ---- Absorption Charging   ON</b>")
                    Absorp_Old = Absorp
                elif Absorp == 0:
                    self.textBrowser.append(f"<b>{dt_string} ---- | ---- Absorption Charging   OFF</b>")
                    Absorp_Old = Absorp

            if Floatchg != Floatchg_Old:
                if Floatchg == 1:
                    self.textBrowser.append(f"<b>{dt_string} ---- | ---- Float Charging   ON</b>")
                    Floatchg_Old = Floatchg
                elif Floatchg == 0:
                    self.textBrowser.append(f"<b>{dt_string} ---- | ---- Float Charging   OFF</b>")
                    Floatchg_Old = Floatchg

        if self.ESS_Status_checkBox.isChecked():
            if ESSbatteryLifeState != ESSbatteryLifeState_Old:
                if ESSbatteryLifeState == 9:
                    self.textBrowser.append(f"<b>{dt_string} ---- | ---- ESS Type: Keep Batteries Charged Mode</b>")
                elif ESSbatteryLifeState >= 10:
                    self.textBrowser.append(f"<b>{dt_string} ---- | ---- ESS Type: Optimized (BatteryLife Disabled)</b>")
                elif ESSbatteryLifeState >= 1 and ESSbatteryLifeState <= 8:
                    self.textBrowser.append(f"<b>{dt_string} ---- | ---- ESS Type: Optimized (BatteryLife Enabled)</b>")
                self.textBrowser.append(f"<b>{dt_string} ---- | ---- ESS Battery Life State Changed to {ESSbatteryLifeStateDict[ESSbatteryLifeState]}</b>")
                ESSbatteryLifeState_Old = ESSbatteryLifeState

#===========================================================================================
        if SolarError1 > 0:
            self.Solar_Charger1_Error_Value.setText(SolarErrorDict[SolarError1])
            self.Solar_Charger1_Error_Value.setStyleSheet("QLabel#Solar_Charger1_Error_Value{font-weight: bold; color: red; background-color: black;}");

        else:
            self.Solar_Charger1_Error_Value.setText(SolarErrorDict[SolarError1])
            self.Solar_Charger1_Error_Value.setStyleSheet("QLabel#Solar_Charger1_Error_Value{color: rgb(0, 255, 0);}");

        if SolarError2 > 0:
            self.Solar_Charger2_Error_Value(SolarErrorDict[SolarError2])
            self.Solar_Charger2_Error_Value.setStyleSheet("QLabel#Solar_Charger2_Error_Value{font-weight: bold; color: red; background-color: black;}");

        else:
            self.Solar_Charger2_Error_Value.setText(SolarErrorDict[SolarError2])
            self.Solar_Charger2_Error_Value.setStyleSheet("QLabel#Solar_Charger2_Error_Value{color: rgb(0, 255, 0);}");


        if SolarError3 > 0:
            self.Solar_Charger3_Error_Value.setText(SolarErrorDict[SolarError3])
            self.Solar_Charger3_Error_Value.setStyleSheet("QLabel#Solar_Charger3_Error_Value{font-weight: bold; color: red; background-color: black;}");

        else:
            self.Solar_Charger3_Error_Value.setText(SolarErrorDict[SolarError3])
            self.Solar_Charger3_Error_Value.setStyleSheet("QLabel#Solar_Charger3_Error_Value{color: rgb(0, 255, 0);}");



        self.Multiplus_Mode_Value.setText(str(New_MPswitch))

        if Analog_Inputs.lower() == 'y':
            self.TempSensor1_label.setText(Tempsensor1_Name)
            self.TempSensor2_label.setText(Tempsensor2_Name)
            self.TempSensor3_label.setText(Tempsensor3_Name)


running = True
app = QApplication(sys.argv)
win = Window()
win.show()
sys.exit(app.exec_())
