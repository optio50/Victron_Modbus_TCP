#!/usr/bin/env python3

import sys
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


# Datetime object containing current date and time
nowStart = datetime.now()
# Fri 21 Jan 2022     09:06:57 PM
dt_stringStart = nowStart.strftime("%a %d %b %Y     %r")




#===================================

# GX Device I.P Address
ip = '192.168.20.156'
client = ModbusClient(ip, port='502')

#===================================

# VRM Portal ID from GX device. 
# AFAIK this ID is needed even with no internet access as its the name of your venus device.
# Menu -->> Settings -->> "VRM Online Portal -->> VRM Portal ID"
VRMid = "d41243d31a90"

#===================================

Analog_Inputs  = 'Y'     # Y or N (case insensitive) to display Gerbo GX Analog Temperature inputs

if Analog_Inputs.lower() == 'y': 
    """
    Change the IDx value to match the cerbo gx input value. If you dont
    use all three inputs you might have to modify the modbus request near line 550
    and comment the unused inputs below.
    """
    Tempsensor1_Name = "Battery Box Temperature     °F"
    ID1 = 24
    Tempsensor2_Name = "Cabin Interior Temperature °F"
    ID2 = 25
    Tempsensor3_Name = "Cabin Exterior Temperature °F"
    ID3 = 26

#===================================
""" intializeing these two variables as None to make sure the QThread has completed before Chart Update Thread is run """
VEbusError = None # MQTT request portion
VEbusStatus  = None # Modbus request portion


#===================================

# ModBus Unit ID
SolarCharger_1_ID = 226
SolarCharger_2_ID = 224
MultiPlus_ID      = 227
Bmv_ID            = 223
VEsystem_ID       = 100

#===================================

# MQTT Instance ID
# This is the Instance ID not to be confused with the above Unit ID.
# Device List in VRM or crossed referenced in the CCGX-Modbus-TCP-register-list.xlsx Tab #2
MQTT_SolarCharger_1_ID = 279
MQTT_SolarCharger_2_ID = 278
MQTT_MultiPlus_ID      = 276
MQTT_Bmv_ID            = 277
MQTT_VEsystem_ID       = 0

#===================================


# Describe The Arrays
Array1 = "400W Panel" # New 400W Panel
Array2 = "310W Panel" # New 310W panel


# ===========================================================================================

# Cycle colors for blinking LED's (Bright / Dark)
blinkred_Temp          = cycle(["rgb(255, 0, 0)",   "rgb(28, 28, 0)"])
blinkred_LowBatt       = cycle(["rgb(255, 0, 0)",   "rgb(28, 28, 0)"])
blinkred_OverLoad      = cycle(["rgb(255, 0, 0)",   "rgb(28, 28, 0)"])
blinkyellow_Bulk       = cycle(["rgb(255, 255, 0)", "rgb(28, 28, 0)"]) 
blinkyellow_Absorption = cycle(["rgb(255, 255, 0)", "rgb(28, 28, 0)"]) 
blinkgreen_Mains       = cycle(["rgb(0,154,23)",    "rgb(28, 28, 0)"])
blinkgreen_Inverter    = cycle(["rgb(0,154,23)",    "rgb(28, 28, 0)"])
blinkblue_Float        = cycle(["rgb(255, 255, 0)", "rgb(28, 28, 0)"]) 

# ===========================================================================================

# If a keep-alive is needed it should be run on the vesus-OS device.
def mqtt_request(mqtt_path):
    topic = subscribe.simple(mqtt_path, hostname=ip)
    data  = json.loads(topic.payload)
    topic = data['value']
    return topic

def modbus_register(address, unit):
    msg     = client.read_input_registers(address, unit=unit)
    decoder = BinaryPayloadDecoder.fromRegisters(msg.registers, byteorder=Endian.Big)
    msg     = decoder.decode_16bit_int()
    return msg

def GridFeedIn():
    FeedIn = modbus_register(2707,VEsystem_ID)

    if FeedIn == 1:
        client.write_register(2707, 0) # Off

    else:
        client.write_register(2707, 1) # On


# Multiplus Control

def Multiplus_Charger():
    client.write_registers(address=33, values=1, unit=MultiPlus_ID)


def Multiplus_Inverter():
    client.write_registers(address=33, values=2, unit=MultiPlus_ID)


def Multiplus_On():
    client.write_registers(address=33, values=3, unit=MultiPlus_ID)


def Multiplus_Off():
    client.write_registers(address=33, values=4, unit=MultiPlus_ID)


def ESSbatteryLifeEnabled():
    client.write_registers(address=2900, values=1, unit=VEsystem_ID)


def ESSbatteryLifeDisabled():
    client.write_registers(address=2900, values=10, unit=VEsystem_ID)


def ESSbatteriesCharged():
    # Mode 9 'Keep batteries charged' mode enabled
    client.write_registers(address=2900, values=9, unit=VEsystem_ID)

#===========================================================================================
# Solar Charger Control
def Charger1_On():
        client.write_registers(address=774, values=1, unit=SolarCharger_1_ID) # Turn On


def Charger1_Off():
        client.write_registers(address=774, values=4, unit=SolarCharger_1_ID) # Turn Off


def Charger2_On():
        client.write_registers(address=774, values=1, unit=SolarCharger_2_ID) # Turn On



def Charger2_Off():
        client.write_registers(address=774, values=4, unit=SolarCharger_2_ID) # Turn Off


# ===========================================================================================

SolarStateDict = {0:  "OFF",
                  2:  "Fault",
                  3:  "Bulk",
                  4:  "Absorption",
                  5:  "Float",
                  6:  "Storage",
                  7:  "Equalize",
                  11: "Other Hub-1",
                  245: "Wake-Up",
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
                    259:"Sched charge"
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


# Thread
# Step 1: Create a worker class
class Worker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(object)



    def run(self):
        """Long-running task."""
        # global variables for the charts that are in a seperate thread
        global VEbusError, VEbusStatus, SolarWatts, SolarWatts1, SolarWatts2, BatterySOC, BatteryWatts ,BatteryAmps, \
        BatteryVolts, BatterySOC, GridWattsL1, GridWattsL2, GridAmpsL1, GridAmpsL2, ACoutWattsL1, ACoutWattsL2,  ACoutAmpsL1, ACoutAmpsL2, Mains, \
        Inverter, Bulk, Floatchg, Absorp, GridCondition, ACoutHZ, timestamp, TempSensor1, TempSensor2, \
        TempSensor3, SolarState1, SolarState2, SolarState1Index, SolarState2Index, dt_string, SolarVolts1, \
        SolarState1_Old, SolarState2_Old, GridCondition_Old, SolarVolts1_Old, Inverter_Old, Mains_Old, \
        Absorp_Old, Floatchg_Old, Bulk_Old, ESSbatteryLifeState_Old



        SolarState1_Old         = modbus_register(775,SolarCharger_1_ID)
        SolarState2_Old         = modbus_register(775,SolarCharger_2_ID)
        GridCondition_Old       = modbus_register(64,MultiPlus_ID)
        SolarVolts1_Old         = modbus_register(776,SolarCharger_1_ID) / 100
        Inverter_Old            = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Inverter")
        Mains_Old               = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Mains")
        Bulk_Old                = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Bulk")
        Absorp_Old              = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Absorption")
        Floatchg_Old            = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Float")
        ESSbatteryLifeState_Old = modbus_register(2900,VEsystem_ID)

        while running:
            try:
#===========================================================================================
# BEGIN Setting Variables
#===========================================================================================
                timestamp           = time.time()

                 # Datetime object containing current date and time
                now = datetime.now()

                # Fri 21 Jan 2022     09:06:57 PM
                dt_string = now.strftime("%a %d %b %Y     %r")
                #start1 = time.monotonic_ns()

#===========================================================================================
                # Battery Section
                BatteryWatts     = modbus_register(842,VEsystem_ID)
                BatteryAmps      = modbus_register(261,Bmv_ID) / 10
                BatteryVolts     = modbus_register(259,Bmv_ID) / 100
                BatteryState     = modbus_register(844,VEsystem_ID) # Battery System State 0=idle 1=charging 2=discharging
                ChargeCycles     = modbus_register(284,Bmv_ID)
                BatteryTTG       = modbus_register(846,VEsystem_ID) / .01
                ConsumedAH       = modbus_register(265,Bmv_ID) / -10
                LastDischarge    = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/History/LastDischarge")
                MaxChargeCurrent = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Dc/0/MaxChargeCurrent")
                LastFullcharge   = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/History/TimeSinceLastFullCharge")
                LastFullcharge   = timedelta(seconds = LastFullcharge)
#===========================================================================================
                #   Solar Charge Controller # 1
                # MQTT
                #global SolarChargeLimit1
                SolarChargeLimit1  = mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Settings/ChargeCurrentLimit")
                SolarChargeLimit1  = f"{SolarChargeLimit1:.0f}"
                SolarYield1        = mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/History/Daily/0/Yield")
                SolarName1         = mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Devices/0/ProductName")
                
                # ModBus
                DCsystemPower      = mqtt_request("N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Dc/System/Power")
                #DCsystemPower      = modbus_register(860,VEsystem_ID)
                BatterySOC         = modbus_register(266,Bmv_ID) / 10
                SolarWatts         = modbus_register(850,VEsystem_ID)        # Total of all solar chargers
                SolarWatts1        = modbus_register(789,SolarCharger_1_ID) / 10
                #SolarAmps          = modbus_register(851,VEsystem_ID) / 10   # Total of all solar chargers
                SolarAmps1         = modbus_register(772,SolarCharger_1_ID) / 10 # Amps To Battery
                SolarVolts1        = modbus_register(776,SolarCharger_1_ID) / 100
                #SolarVolts1        = f"{SolarVolts1:.1f}"
                PvAmps1            = SolarWatts1 / SolarVolts1
                MaxSolarWatts1     = modbus_register(785,SolarCharger_1_ID)
                MaxSolarWattsYest1 = modbus_register(787,SolarCharger_1_ID)
                #SolarYield1        = modbus_register(784,SolarCharger_1_ID) / 10
                #TotalSolarYield    = modbus_register(790,SolarCharger_1_ID) / 10
                SolarYieldYest1    = modbus_register(786,SolarCharger_1_ID) / 10
                #SolarOn1           = modbus_register(774,SolarCharger_1_ID)
                SolarState1        = modbus_register(775,SolarCharger_1_ID)
                SolarError1        = modbus_register(788,SolarCharger_1_ID)

#===========================================================================================
                #   Solar Charge Controller # 2
                # MQTT
                SolarChargeLimit2  = mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Settings/ChargeCurrentLimit")
                SolarChargeLimit2  = f"{SolarChargeLimit2:.0f}"
                SolarYield2        = mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/History/Daily/0/Yield")
                SolarName2         = mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Devices/0/ProductName")

                # ModBus
                SolarWatts2         = modbus_register(789,SolarCharger_2_ID) / 10
                SolarAmps2          = modbus_register(772,SolarCharger_2_ID) / 10 # Amps To Battery
                SolarVolts2         = modbus_register(776,SolarCharger_2_ID) / 100
                PvAmps2             = SolarWatts2 / SolarVolts2
                MaxSolarWatts2      = modbus_register(785,SolarCharger_2_ID)
                MaxSolarWattsYest2  = modbus_register(787,SolarCharger_2_ID)
                #SolarYield2         = modbus_register(784,SolarCharger_2_ID) / 10
                #TotalSolarYield    = modbus_register(790,SolarCharger_2_ID) / 10
                SolarYieldYest2     = modbus_register(786,SolarCharger_2_ID) / 10
                #SolarOn2            = modbus_register(774,SolarCharger_2_ID)
                SolarState2         = modbus_register(775,SolarCharger_2_ID)
                SolarError2         = modbus_register(788,SolarCharger_2_ID)
                TotalYield          = SolarYield1 + SolarYield2
                TotalYieldYest      = SolarYieldYest1 + SolarYieldYest2

                MaxTotalWattsToday  = MaxSolarWatts1 + MaxSolarWatts2
                MaxTotalWattsYest   = MaxSolarWattsYest1 + MaxSolarWattsYest2
#===========================================================================================
                # Multiplus Section
                #   Grid Input & A/C Out
                FeedIn        = modbus_register(2707,VEsystem_ID)
                FeedInLimited = modbus_register(2709,VEsystem_ID)
                FeedInMax     = modbus_register(66,MultiPlus_ID) / .01 # L1
                GridSetPoint  = modbus_register(2700,VEsystem_ID)
                GridWattsL1   = modbus_register(820,VEsystem_ID)
                GridWattsL2   = modbus_register(821,VEsystem_ID)
                GridAmpsL1    = modbus_register(6,MultiPlus_ID) / 10
                GridAmpsL2    = modbus_register(7,MultiPlus_ID) / 10
                GridVoltsL1   = modbus_register(3,MultiPlus_ID) / 10
                GridVoltsL2   = modbus_register(4,MultiPlus_ID) / 10
                GridHZ        = modbus_register(9,MultiPlus_ID) / 100 # Both L1 & L2
                ACoutWattsL1  = modbus_register(817,VEsystem_ID) / 1# 817 VEsystem_ID
                ACoutWattsL2  = modbus_register(818,VEsystem_ID) / 1# 818 VEsystem_ID
                ACoutAmpsL1   = modbus_register(18,MultiPlus_ID) / 10
                ACoutAmpsL2   = modbus_register(19,MultiPlus_ID) / 10
                ACoutVoltsL1  = modbus_register(15,MultiPlus_ID) / 10
                ACoutVoltsL2  = modbus_register(16,MultiPlus_ID) / 10
                ACoutHZ       = modbus_register(21,MultiPlus_ID) / 100 # Both L1 & L2
                GridCondition = modbus_register(64,MultiPlus_ID)
                GridAmpLimit  = modbus_register(22,MultiPlus_ID) / 10


                # LED's
                Mains         = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Mains")
                Inverter      = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Inverter")
                Bulk          = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Bulk")
                Overload      = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Overload")
                Absorp        = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Absorption")
                Lowbatt       = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/LowBattery")
                Floatchg      = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Float")
                Temperature   = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Temperature")

                # Switch Position on the Multiplus II
                MPswitch      = modbus_register(33,MultiPlus_ID)
                MultiName     = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/ProductName")

#===========================================================================================

                #   VEbus Status
                VEbusStatus = mqtt_request("N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/SystemState/State")
                #VEbusStatus = modbus_register(31,MultiPlusID)
        
                #   VEbus Error
                VEbusError  = modbus_register(32,MultiPlus_ID)
                #VEbusError = 55 # Test single error mesg
                #error_nos = [0,1,2,3,4,5,6,7,10,14,16,17,18,22,24,25,26]
                #VEbusError = error_nos[errorindex] # Multiple Test VEbusError's

                # ESS Info
                ESSbatteryLifeState = modbus_register(2900,VEsystem_ID)
                ESSsocLimitUser     = modbus_register(2901,VEsystem_ID) / 10
                ESSsocLimitDynamic  = modbus_register(2903, unit=VEsystem_ID) / 10
                if ESSsocLimitDynamic <= ESSsocLimitUser: # The ESS value will never be below the user value in the "Remote Console"
                # https://energytalk.co.za/t/possible-to-manually-change-active-soc-limit-on-victron/294?page=2
                    ESSsocLimitDynamic = ESSsocLimitUser
                ESSsocLimitDynamic  = f"{ESSsocLimitDynamic:.0f}%"
                ESSsocLimitUser     = f"{ESSsocLimitUser:.0f}%"
                
                
                
                # Conditional Modbus Request
                # Analog Temperature Inputs
                # Change the ID to your correct value. *** modbus_register(3304,IDx) *** <------Change IDx value at top of this file
                if Analog_Inputs.lower() == 'y':
                    try:
                        TempSensor1 = modbus_register(3304,ID1) / 100 * 1.8 + 32
                    except AttributeError:
                        TempSensor1 = 99
                        print("Analog Input Sensor 1 Disconnected or Wrong Address")

                    try:
                        TempSensor2 = modbus_register(3304,ID2) / 100 * 1.8 + 32
                    except AttributeError:
                        TempSensor2 = 99
                        print("Analog Input Sensor 2 Disconnected or Wrong Address")
                    try:
                        TempSensor3 = modbus_register(3304,ID3) / 100 * 1.8 + 32
                    except AttributeError:
                        TempSensor3 = 99
                        print("Analog Input Sensor 3 Disconnected or Wrong Address")
                else:
                    TempSensor1 = None
                    TempSensor2 = None
                    TempSensor3 = None

                # Index number needed for the SolarState charts
                SolarState1Index  = list(SolarStateDict.keys()).index(SolarState1)
                SolarState2Index  = list(SolarStateDict.keys()).index(SolarState2)

                # GX Firmware
                #FW_Installed = mqtt_request("N/"+VRMid+"/platform/0/Firmware/Installed/Version")
                #FW_Available = mqtt_request("N/"+VRMid+"/platform/0/Firmware/Online/AvailableVersion")
                #FW_Backup    = mqtt_request("N/"+VRMid+"/platform/0/Firmware/Backup/AvailableVersion")

#===========================================================================================
# END Variables
#===========================================================================================
            except Exception:
                continue
            results = { "BatterySOC":          BatterySOC,
                        "BatteryWatts":        BatteryWatts,    
                        "BatteryAmps":         BatteryAmps,     
                        "BatteryVolts":        BatteryVolts,     
                        "DCsystemPower":       DCsystemPower,    
                        "BatteryState":        BatteryState,     
                        "ChargeCycles":        ChargeCycles,     
                        "BatteryTTG":          BatteryTTG,
                        "ConsumedAH":          ConsumedAH,      
                        "LastDischarge":       LastDischarge,    
                        "MaxChargeCurrent":    MaxChargeCurrent, 
                        "LastFullcharge":      LastFullcharge,   
                        "LastFullcharge":      LastFullcharge,   
                        "SolarChargeLimit1":   SolarChargeLimit1, 
                        "SolarYield1":         SolarYield1,       
                        "SolarName1":          SolarName1,        
                        "SolarWatts1":         SolarWatts1,       
                        "SolarWatts":          SolarWatts,        
                        "SolarAmps1":          SolarAmps1,        
                        "SolarVolts1":         SolarVolts1,       
                        "PvAmps1":             PvAmps1,           
                        "MaxSolarWatts1":      MaxSolarWatts1,    
                        "MaxSolarWattsYest1":  MaxSolarWattsYest1,
                        "SolarYieldYest1":     SolarYieldYest1,   
                        "SolarState1":         SolarState1,
                        "SolarError1":         SolarError1,       
                        "SolarChargeLimit2":   SolarChargeLimit2, 
                        "SolarYield2":         SolarYield2,       
                        "SolarName2":          SolarName2,        
                        "SolarWatts2":         SolarWatts2,       
                        "SolarAmps2":          SolarAmps2,        
                        "SolarVolts2":         SolarVolts2,       
                        "PvAmps2":             PvAmps2,           
                        "MaxSolarWatts2":      MaxSolarWatts2,    
                        "MaxSolarWattsYest2":  MaxSolarWattsYest2,
                        "SolarYieldYest2":     SolarYieldYest2,   
                        "SolarState2":         SolarState2,       
                        "SolarError2":         SolarError2,       
                        "TotalYield":          TotalYield,        
                        "TotalYieldYest":      TotalYieldYest,    
                        "MaxTotalWattsToday":  MaxTotalWattsToday,
                        "MaxTotalWattsYest":   MaxTotalWattsYest, 
                        "FeedIn":              FeedIn,       
                        "FeedInLimited":       FeedInLimited,
                        "FeedInMax":           FeedInMax,    
                        "GridSetPoint":        GridSetPoint, 
                        "GridWattsL1":         GridWattsL1,    
                        "GridWattsL2":         GridWattsL2,
                        "GridAmpsL1":          GridAmpsL1,     
                        "GridAmpsL2":          GridAmpsL2,
                        "GridVoltsL1":         GridVoltsL1,    
                        "GridVoltsL2":         GridVoltsL2,
                        "GridHZ":              GridHZ,       
                        "ACoutWattsL1":        ACoutWattsL1,
                        "ACoutWattsL2":        ACoutWattsL2,
                        "ACoutAmpsL1":         ACoutAmpsL1,
                        "ACoutAmpsL2":         ACoutAmpsL2,    
                        "ACoutVoltsL1":        ACoutVoltsL1,   
                        "ACoutVoltsL2":        ACoutVoltsL2,
                        "ACoutHZ":             ACoutHZ,      
                        "GridCondition":       GridCondition,
                        "GridAmpLimit":        GridAmpLimit, 
                        "Mains":               Mains,        
                        "Inverter":            Inverter,     
                        "Bulk":                Bulk,         
                        "Overload":            Overload,     
                        "Absorp":              Absorp,       
                        "Lowbatt":             Lowbatt,      
                        "Floatchg":            Floatchg,     
                        "Temperature":         Temperature,  
                        "MPswitch":            MPswitch,     
                        "MultiName":           MultiName,    
                        "VEbusStatus":         VEbusStatus,
                        "VEbusError":          VEbusError,
                        "ESSbatteryLifeState": ESSbatteryLifeState,
                        "ESSsocLimitUser":     ESSsocLimitUser,     
                        "ESSsocLimitDynamic":  ESSsocLimitDynamic,
                        "TempSensor1":         TempSensor1,
                        "TempSensor2":         TempSensor2,
                        "TempSensor3":         TempSensor3,
                        #"FW_Installed":        FW_Installed,
                        #"FW_Available":        FW_Available,
                        #"FW_Backup":           FW_Backup,
                        "timestamp":           timestamp
                        }
            self.progress.emit(results)
            self.finished.emit()
            time.sleep(1.5)


class Window(QMainWindow):

    def __init__(self, parent=None):
        super().__init__()
        # Load the ui file
        uic.loadUi("PyQT5-Dual-Charger.ui", self)
        self.setWindowIcon(QtGui.QIcon('Solar.png'))
        self.runLongTask()
        self.Started_label.setText(f"Chart Recording Started on {dt_stringStart}")
        
        
        def clear_history():
            self.textBrowser.clear()
        
        
        def VEbusReset():
            client.write_registers(address=62, values=1, unit=MultiPlus_ID)
            self.textBrowser.append(f"{dt_string} ---- | ---- Resetting V.E. Bus")


        def Input_Amps_Limit():
            answer, ok = QInputDialog.getInt(self, 'Enter New AC Input Amps Limit', 'Enter New AC Input Amps Limit',
                                            25, 10, 50, 5)
            if ok:
                client.write_registers(address=22, values=answer * 10, unit=MultiPlus_ID)


        self.History_pushButton.clicked.connect(clear_history)
        
        self.Reset_VEbus_pushButton.clicked.connect(VEbusReset)
        
        self.ACin_Amp_Limit_pushButton.clicked.connect(Input_Amps_Limit)

#===========================================================================================
        # Define crosshair parameters
        kwargs = {Crosshair.ENABLED: True,
        Crosshair.LINE_PEN: pg.mkPen(color="green", width=1),
        Crosshair.TEXT_KWARGS: {"color": "pink"}}
#===========================================================================================
#  Begin Charts
        # Chart Total Solar Watts
        watts_plot = LiveLinePlot(pen='orangered', fillLevel=0, brush=(213,129,44,100))

        # Data connectors for each plot with dequeue of max_points points
        self.watts_connector = DataConnector(watts_plot, max_points=40072, update_rate=.75) 

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        watts_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        # Create plot itself
        self.Solar_graph_Widget = LivePlotWidget(title="PV Watts, 24 Hours",
        axisItems={'bottom': watts_bottom_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=900, offset_left=2), **kwargs)

        self.Solar_graph_Widget.x_range_controller.crop_left_offset_to_data = True

        #self.Solar_graph_Widget = LivePlotWidget(title="PV Watts 24 Hrs", axisItems={'bottom': watts_bottom_axis}, **kwargs)

        # Show grid
        self.Solar_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        # SetLimits
        #self.Solar_graph_Widget.setLimits(yMin=-.1)

        # Set labels
        self.Solar_graph_Widget.setLabel('bottom')
        self.Solar_graph_Widget.setLabel('left', 'Watts')

        # Add Line
        self.Solar_graph_Widget.addItem(watts_plot)

        # Add chart to Layout in Qt Designer
        self.Chart_Watts_Layout.addWidget(self.Solar_graph_Widget)
#===========================================================================================

# Chart Battery SOC
        soc_plot = LiveLinePlot(pen="magenta")

        # Data connectors for each plot with dequeue of max_points points
        self.soc_connector = DataConnector(soc_plot, max_points=40072, update_rate=.75) # 1.5 seconds in 24 hrs

        soc_plot.set_leading_line(LeadingLine.HORIZONTAL, pen=mkPen("red"), text_axis=LeadingLine.AXIS_Y)

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        soc_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        # Create plot itself
        self.Battery_SOC_graph_Widget = LivePlotWidget(title="Battery SOC, 24 Hours",
        axisItems={'bottom': soc_bottom_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=900, offset_left=2), **kwargs)

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
        volts_plot     = LiveLinePlot(pen="red", name='Volts')
        bat_watts_plot = LiveLinePlot(pen="blue", name='Watts')
        amps_plot      = LiveLinePlot(pen="green", name='Amps')


        # Data connectors for each plot with dequeue of max_points points
        self.volts_connector     = DataConnector(volts_plot, max_points=40072, update_rate=.75) # 1.5 seconds in 24 hrs
        self.bat_watts_connector = DataConnector(bat_watts_plot, max_points=40072, update_rate=.75) # 1.5 seconds in 24 hrs
        self.amps_connector      = DataConnector(amps_plot, max_points=40072, update_rate=.75) # 1.5 seconds in 24 hrs
        

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        volts_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        # Create plot itself
        self.Battery_Volts_graph_Widget = LivePlotWidget(title="Battery Volts, Watts & Amps 24 Hours",
        axisItems={'bottom': volts_bottom_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=900, offset_left=2), **kwargs)

        self.Battery_Volts_graph_Widget.x_range_controller.crop_left_offset_to_data = True
        
        #self.Battery_Volts_graph_Widget = LivePlotWidget(title="Battery Volts, Watts & Amps 24 Hrs", axisItems={'bottom': volts_bottom_axis}, **kwargs)

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
        self.grid_watts_L1_connector = DataConnector(grid_watts_L1_plot, max_points=40072, update_rate=.75) # 1.5 seconds in 24 hrs
        self.grid_watts_L2_connector = DataConnector(grid_watts_L2_plot, max_points=40072, update_rate=.75) # 1.5 seconds in 24 hrs
        self.grid_amps_L1_connector = DataConnector(grid_amps_L1_plot, max_points=40072, update_rate=.75) # 1.5 seconds in 24 hrs
        self.grid_amps_L2_connector = DataConnector(grid_amps_L2_plot, max_points=40072, update_rate=.75) # 1.5 seconds in 24 hrs

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        grid_watts_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        # Create plot itself
        self.Grid_Watts_graph_Widget = LivePlotWidget(title="Grid Watts & Amps, 24 Hours",
        axisItems={'bottom': grid_watts_bottom_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=900, offset_left=2), **kwargs)

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
        self.Grid_Watts_graph_Widget.addItem(grid_watts_L2_plot)
        self.Grid_Watts_graph_Widget.addItem(grid_amps_L1_plot)
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
            self.Exterior_Temp_connector = DataConnector(Exterior_Temp_plot, max_points=40072, update_rate=.75) # 1.5 seconds in 24 hrs
            self.Interior_Temp_connector = DataConnector(Interior_Temp_plot, max_points=40072, update_rate=.75) # 1.5 seconds in 24 hrs
            self.Box_Temp_connector      = DataConnector(Box_Temp_plot,      max_points=40072, update_rate=.75) # 1.5 seconds in 24 hrs


            # Setup bottom axis with TIME tick format
            # use Axis.DATETIME to show date
            Box_Temp_plot_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

            # Create plot itself
            self.Temperature_graph_Widget = LivePlotWidget(title="Cabin Temperatures °F, 24 Hours",
            axisItems={'bottom': Box_Temp_plot_bottom_axis},
            x_range_controller=LiveAxisRange(roll_on_tick=900, offset_left=2), **kwargs)

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
        self.ac_out_watts_L1_connector = DataConnector(ac_out_watts_L1_plot, max_points=40072, update_rate=.75) # 1.5 seconds in 24 hrs
        self.ac_out_watts_L2_connector = DataConnector(ac_out_watts_L2_plot, max_points=40072, update_rate=.75) # 1.5 seconds in 24 hrs
        self.ac_out_amps_L1_connector  = DataConnector(ac_out_amps_L1_plot,  max_points=40072, update_rate=.75) # 1.5 seconds in 24 hrs
        self.ac_out_amps_L2_connector  = DataConnector(ac_out_amps_L2_plot,  max_points=40072, update_rate=.75) # 1.5 seconds in 24 hrs
        self.ac_out_freq_connector  = DataConnector(ac_out_freq_plot,  max_points=40072, update_rate=.75)

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        ac_out_watts_L1_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})


        # Create plot itself
        self.ac_out_watts_graph_Widget = LivePlotWidget(title="A/C Out Watts, Amps & Freq, 24 Hours",
        axisItems={'bottom': ac_out_watts_L1_bottom_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=900, offset_left=2), **kwargs)

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
# Chart Solar Watts PV 1, PV 2

        PV1watts_plot = LiveLinePlot(pen='orangered',name='PV-1',fillLevel=0, brush=(213,129,44,100))
        PV2watts_plot = LiveLinePlot(pen='cyan',name='PV-2', fillLevel=0, brush=(102,102,255,100))

        # Data connectors for each plot with dequeue of max_points points
        self.PV1watts_connector = DataConnector(PV1watts_plot, max_points=40072, update_rate=.75)
        self.PV2watts_connector = DataConnector(PV2watts_plot, max_points=40072, update_rate=.75) 


        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        pv1_watts_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        # Create plot
        self.PV1_graph_Widget = LivePlotWidget(title="Charger 1 & 2 Watts, 24 Hours",
        axisItems={'bottom': pv1_watts_bottom_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=900, offset_left=2), **kwargs)

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
        self.MP_connector = DataConnector(MP_plot, max_points=13400, update_rate=.2) #  2880 * 5 = 14400
                                                                                     # 86400 / 6.8 = 12705
        
        
        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        
        MP_left_axis = LiveAxis("left", **{Axis.TICK_FORMAT: Axis.CATEGORY, Axis.CATEGORIES: MP_plot.categories})
        MP_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        self.MP_State_graph_Widget = LivePlotWidget(title="Multiplus Status, 24 Hours",
        axisItems={'bottom': MP_bottom_axis,'left': MP_left_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=720, offset_left=2), **kwargs)


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
        self.state1_connector = DataConnector(state1_plot, max_points=13400, update_rate=.2)

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        
        state1_left_axis = LiveAxis("left", **{Axis.TICK_FORMAT: Axis.CATEGORY, Axis.CATEGORIES: state1_plot.categories})
        state1_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})


        # Create plot itself
        ##self.Charger1_State_graph_Widget = LivePlotWidget(title="Charger #1 State 24 Hrs", axisItems={'bottom': state1_bottom_axis, 'left': state1_left_axis}, **kwargs)

        self.Charger1_State_graph_Widget = LivePlotWidget(title="Charger 1 Status, 24 Hours",
        axisItems={'bottom': state1_bottom_axis,'left': state1_left_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=720, offset_left=2), **kwargs)


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
        self.state2_connector = DataConnector(state2_plot, max_points=13400, update_rate=.2) # 24 hours in seconds

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date


        state2_left_axis = LiveAxis("left", **{Axis.TICK_FORMAT: Axis.CATEGORY, Axis.CATEGORIES: state2_plot.categories})
        state2_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})


        # Create plot itself
        ##self.Charger2_State_graph_Widget = LivePlotWidget(title="Charger #2 State 24 Hrs", axisItems={'bottom': state2_bottom_axis, 'left': state2_left_axis}, **kwargs)

        self.Charger2_State_graph_Widget = LivePlotWidget(title="Charger 2 Status, 24 Hours",
        axisItems={'bottom': state2_bottom_axis,'left': state2_left_axis},
        x_range_controller=LiveAxisRange(roll_on_tick=720, offset_left=2), **kwargs)

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
# End Charts
#===========================================================================================

        def SetGridWatts():
            answer, ok = QInputDialog.getInt(self, 'Enter Desired Grid Watts', 'Enter New Grid Watts Value',
                                            25, -1000, 1000, 5)
            if ok:
                watts   = answer
                builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
                builder.reset()
                builder.add_16bit_int(int(watts))
                payload = builder.to_registers()
                client.write_registers(2700, payload[0])
                self.textBrowser.append(f"{dt_string} ---- | ---- Set Grid Watts Changed to    {watts} Watts")




        def ESSuser():
            answer, ok = QInputDialog.getInt(self, 'Enter New ESS User Limit', 'Enter New ESS User Limit',
                                            70, 10, 100, 5)
            if ok:
                client.write_registers(address=2901, values=answer * 10, unit=VEsystem_ID)

        def Charger1_Limit():
            answer, ok = QInputDialog.getInt(self, 'Enter Charger 1 Limit', 'Enter Charger 1 Limit', 20)
            if ok:
                mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Settings/ChargeCurrentLimit",
                                                                   payload=json.dumps({"value": answer}), hostname=ip, port=1883)
                self.textBrowser.append(f"{dt_string} ---- | ---- Charger 1 Limit Changed to    {answer} Amps")

        def Charger2_Limit():
            answer, ok = QInputDialog.getInt(self, 'Enter Charger 2 Limit', 'Enter Charger 2 Limit', 15)
            if ok:
                mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Settings/ChargeCurrentLimit",
                                                                   payload=json.dumps({"value": answer}), hostname=ip, port=1883)
                self.textBrowser.append(f"{dt_string} ---- | ---- Charger 2 Limit Changed to    {answer} Amps")

        def BG_Change():
            color = QColorDialog.getColor()
            if color.isValid():
                self.centralwidget.setStyleSheet(f"background-color: {color.name()}")
                #self.Solar_Name_1_lineEdit.setStyleSheet(f"background-color: {color.name()}")
                #self.Solar_Name_2_lineEdit.setStyleSheet(f"background-color: {color.name()}")
                self.tabWidget.setStyleSheet(f"background-color: {color.name()}")


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
        
        self.actionSet_Current_Limit_1.triggered.connect(Charger1_Limit)
        self.actionSet_Current_Limit_2.triggered.connect(Charger2_Limit)

        # Full Screen & Normanl
        self.actionNormal_Screen.triggered.connect(self.showNormal)
        self.actionFull_Screen.triggered.connect(self.showFullScreen)
        self.actionChange_Background_Color.triggered.connect(BG_Change)

        # Keep this out of the timing loop
        self.FeedIn_pushButton.clicked.connect(GridFeedIn)
        self.Set_Grid_Watts_pushButton.clicked.connect(SetGridWatts)
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
#===============================================
        """        # Clear Text Browser History Every 24 hrs
        self.TextBrowserTimer = QTimer()
        
        self.TextBrowserTimer.setInterval(86400*1000) # 1000 ms = 1s -- 86400 seconds in 24 Hrs

        # connect timeout signal to signal handler
        self.TextBrowserTimer.timeout.connect(clear_history)

        # start timer
        self.TextBrowserTimer.start()
        """
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
                self.Float_LED.setStyleSheet(f"color: {next(blinkblue_Float)}")

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
        while VEbusStatus is None and VEbusError is None:
            """ loading time is much faster with a sleep interval, then an unrestricted loop """
            time.sleep(.01)
            continue
        Thread(target=self.update_charts).start()

#===========================================================================================
    def showTime(self):
        # Datetime object containing current date and time
        nowTime = datetime.now()
        # Fri 21 Jan 2022     09:06:57 PM
        Time_string = nowTime.strftime("%a %d %b %Y     %r")
        self.Time_Label.setText(Time_string)
        self.statusBar.showMessage(Time_string)
#===========================================================================================


    def closeEvent(self, event: QtGui.QCloseEvent):
        global running
        running = False

    
#===========================================================================================
    def update_charts(self):
        #time.sleep(.5) # one time delay before starting to update charts to let GX devive retreive values
        while running:
            try:
            
                # Sleep time is needed in small groups vs one single value to prevent Chart Crosshair lag when appending the deque.
                # 18 plots at 
                #40000 points(MAX) each takes some time to load up. Not quite sure why this works better.
                # Maybe my computer is too slow? (Intel Core i7-8550U, 8G Ram)
    
                # Solar
                #start = time.monotonic_ns()
                
                self.watts_connector.cb_append_data_point(SolarWatts, timestamp)
                self.PV1watts_connector.cb_append_data_point(SolarWatts1, timestamp)
                self.PV2watts_connector.cb_append_data_point(SolarWatts2, timestamp)
                
                ##finish=time.monotonic_ns()
                ##duration = finish -  start
                
                ##print('\033[38;5;10m'f"1st Set Took {duration//1000000}ms")
                time.sleep(.100)
    
                # Battery
               ## start = time.monotonic_ns()
                
                self.bat_watts_connector.cb_append_data_point(BatteryWatts, timestamp)
                self.amps_connector.cb_append_data_point(BatteryAmps, timestamp)
                self.volts_connector.cb_append_data_point(BatteryVolts, timestamp)
                self.soc_connector.cb_append_data_point(BatterySOC, timestamp)
                
                ##finish=time.monotonic_ns()
                ##duration = finish -  start
                ##print('\033[38;5;65m'f"2nd Set Took {duration//1000000}ms")
                
                time.sleep(.100)
    
                # A/C In
                ##start = time.monotonic_ns()
                
                self.grid_amps_L1_connector.cb_append_data_point(GridAmpsL1, timestamp)
                self.grid_amps_L2_connector.cb_append_data_point(GridAmpsL2, timestamp)
                self.grid_watts_L1_connector.cb_append_data_point(GridWattsL1, timestamp)
                self.grid_watts_L2_connector.cb_append_data_point(GridWattsL2, timestamp)
                #self.one_hr_watts_connector.cb_append_data_point(SolarWatts, timestamp)
    
                ##finish=time.monotonic_ns()
                ##duration = finish -  start
                
               ## print('\033[38;5;45m'f"3rd Set Took {duration//1000000}ms")
    
                time.sleep(.150)
    
                # A/C Out
                ##start = time.monotonic_ns()
    
                self.ac_out_watts_L1_connector.cb_append_data_point(ACoutWattsL1, timestamp)
                self.ac_out_watts_L2_connector.cb_append_data_point(ACoutWattsL2, timestamp)
                self.ac_out_amps_L1_connector.cb_append_data_point(ACoutAmpsL1, timestamp)
                self.ac_out_amps_L2_connector.cb_append_data_point(ACoutAmpsL2, timestamp)
                self.ac_out_freq_connector.cb_append_data_point(ACoutHZ, timestamp)
    
                ##finish=time.monotonic_ns()
                ##duration = finish -  start
    
                ##print('\033[38;5;26m'f"4th Set Took {duration//1000000}ms")
    
                time.sleep(.150)
    
                if Analog_Inputs.lower() == 'y':
                    ##start = time.monotonic_ns()
    
                    self.Box_Temp_connector.cb_append_data_point(TempSensor1, timestamp)
                    self.Interior_Temp_connector.cb_append_data_point(TempSensor2, timestamp)
                    self.Exterior_Temp_connector.cb_append_data_point(TempSensor3, timestamp)
    
    
                    ##finish=time.monotonic_ns()
                    ##duration = finish -  start
    
                   ## print('\033[38;5;101m'f"5th Set Took {duration//1000000}ms")
                    time.sleep(.500)
                
    
    
    
                self.state1_connector.cb_append_data_point([categories[SolarState1Index]], timestamp)
                self.state2_connector.cb_append_data_point([categories[SolarState2Index]], timestamp)
                time.sleep(.500)
    
                ##start = time.monotonic_ns()
    
                # MP Charger State Chart
                if Bulk == 1 and Absorp != 1 and Floatchg != 1: #Charging LED's
                    MP_State = 2 # Bulk State
                elif Absorp == 1 and Bulk != 1 and Floatchg != 1: #Charging LED's
                    MP_State = 1 # Absorption State
                elif Floatchg == 1 and Bulk != 1 and Absorp != 1: #Charging LED's
                    MP_State = 0 # Float State
    
               #    Index          0            1         2          3        4         5
               # MP_categories   Float     Absorption    Bulk    Inverting   Mains   Grid Lost
                if GridCondition == 2:
                    # Inverting On & Grid Lost (2 active bars on chart). There is no charger status LED in this state.
                    self.MP_connector.cb_append_data_point([MP_categories[3],MP_categories[5]], timestamp)
    
                elif Inverter >= 1 and Mains >= 1:
                    # Chargeing Status, Inverting On & Grid Connected (3 active bars on chart)
                    self.MP_connector.cb_append_data_point([MP_categories[MP_State],MP_categories[3],MP_categories[4]], timestamp)
    
                elif Inverter == 0 and Mains >= 1: # Inverting Off & Grid Connected
                    # Chargeing Status, Inverting Off & Grid Connected (2 active bars on chart)
                    self.MP_connector.cb_append_data_point([MP_categories[MP_State],MP_categories[4]], timestamp)
               
                time.sleep(.500)
            except NameError:
                continue

#===========================================================================================
    def update(self, results): # Update all the UI widgets

        global Counter
        Counter = 0
        # This is the Keep Alive MQTT request for Raspi
        if Counter >= 5: # Every 5 Loops send MQTT KeepAlive
            try:
                mqttpublish.single("R/"+VRMid+"/system/0/Serial", hostname=ip, port=1883)
                Counter = 0 # After 5 Loops reset Counter to zero, then begin counting again.
            except OSError:
                print('No Contact to ' + ip)
                print(dt_string)
                pass
        Counter += 1 # Increment the counter by 1


        # Battery Time To Go
        if results["BatteryTTG"] == 0.0:
            results["BatteryTTG"] = "Infinite"
        else:
            results["BatteryTTG"] = timedelta(seconds = results["BatteryTTG"])

        # Current Battery State
        if results["BatteryState"] == 0:
            results["BatteryState"] = "Idle"
        elif results["BatteryState"] == 1:
            results["BatteryState"] = "Charging"
        elif results["BatteryState"] == 2:
            results["BatteryState"] = "Discharging"

        # If grid watts is less than zero feedin is active and show the label "FeedIn Active"
        if results["GridWattsL1"] < 0 and results["Mains"] >= 2:
            self.Grid_FeedIn_Active_Label.setHidden(False)
            self.Grid_Watts_LCD_L1.setStyleSheet("QLCDNumber { background: rgb(0, 128, 255); }");
            self.Grid_FeedIn_Active_Label.setText(f"FeedIn Active {results['GridWattsL1']}")
            self.Grid_FeedIn_Active_Label.setStyleSheet("QLabel { background: rgb(0, 128, 255); color: rgb(0, 0, 0); }")

        # If grid watts is NOT less than zero, Hide the label "FeedIn Active"
        else:
            self.Grid_FeedIn_Active_Label.setHidden(True)
            self.Grid_Watts_LCD_L1.setStyleSheet("QLCDNumber { background: rgb(85, 87, 83); }")

        # If "Feedin" is allowed and it is limited, show thw label and its limit
        if results["FeedIn"] == 1 and results["FeedInLimited"] == 1:
            self.Grid_FeedIn_Limit_Label.setHidden(False)
            self.Grid_FeedIn_Limit_Label.setText(f"Feed In Limited to {results['FeedInMax']:.0f} W per Phase")
        else:
            self.Grid_FeedIn_Limit_Label.setHidden(True)

        # If "Feedin" is allowed. Show the label on the button
        if results["FeedIn"] == 1:
            self.FeedIn_pushButton.setText('Enabled')

        # If "Feedin" is NOT allowed. Show the label on the button
        elif results["FeedIn"] == 0:
            self.FeedIn_pushButton.setText('Disabled')

        # If grid power is in a normal state, Show label "OK"
        if results["GridCondition"] == 0:
            Condition = 'OK'
            self.Grid_Condition_lineEdit.setStyleSheet("QLineEdit { background: rgb(136, 138, 133); }");
        
        # If grid power is NOT in a normal state, Show label "LOST"
        elif results["GridCondition"] == 2:
            Condition = 'LOST'
            self.Grid_Condition_lineEdit.setStyleSheet("QLineEdit { background: red; }");

        # Change color of progressbar based on value
        if results["BatterySOC"] >= 66:
            self.Batt_SOC_progressBar.setStyleSheet("QProgressBar#Batt_SOC_progressBar{selection-background-color:"
                                                    "rgb(36, 232, 20);color: rgb(0, 0, 0)}"); # Green
        elif results["BatterySOC"] < 66 and BatterySOC >= 33:
            self.Batt_SOC_progressBar.setStyleSheet("QProgressBar#Batt_SOC_progressBar{selection-background-color:"
                                                    "rgb(255, 255, 0);color: rgb(0, 0, 0)}"); # Yellow
        elif results["BatterySOC"] < 33:
            self.Batt_SOC_progressBar.setStyleSheet("QProgressBar#Batt_SOC_progressBar{selection-background-color:"
                                                    "rgb(200, 0, 0);}"); # Red

        # The Big Font Watts Label
        self.Total_Watts_label.setText(str(results["SolarWatts"]))

        # If you have the temperature inputs enabled
        if Analog_Inputs.lower() == 'y':
            self.TempSensor1_lcdNumber.display(f"{results['TempSensor1']:.1f}")
            self.TempSensor2_lcdNumber.display(str(f"{results['TempSensor2']:.1f}"))
            self.TempSensor3_lcdNumber.display(str(f"{results['TempSensor3']:.1f}"))
        else:
            self.TempSensor1_lcdNumber.setHidden(True)
            self.TempSensor2_lcdNumber.setHidden(True)
            self.TempSensor3_lcdNumber.setHidden(True)
            self.TempSensor1_label.setHidden(True)
            self.TempSensor2_label.setHidden(True)
            self.TempSensor3_label.setHidden(True)

# ===========================================================================================
#====================================================================
# Mains LED
        #results["Mains"] = 3
        if results["Mains"] == 0: # Off
            if self.qTimerMains.isActive():
                self.qTimerMains.stop()
            self.Mains_LED.setStyleSheet("color: rgb(28, 28, 28)") # dark

        elif results["Mains"] == 1: # On
            if self.qTimerMains.isActive():
                self.qTimerMains.stop()
            self.Mains_LED.setStyleSheet("color: rgb(0,154,23)") # bright Green

        elif results["Mains"] >= 2: # Blink
            if not self.qTimerMains.isActive():
                self.qTimerMains.start()
#====================================================================
# Inverter LED
        #results["Inverter"] = 3
        if results["Inverter"] == 0: # Off
            if self.qTimerInverter.isActive():
                self.qTimerInverter.stop()
            self.Inverting_LED.setStyleSheet("color: rgb(28, 28, 28)") # dark
        elif results["Inverter"] == 1: # On
            if self.qTimerInverter.isActive():
                self.qTimerInverter.stop()
            self.Inverting_LED.setStyleSheet("color: rgb(0,154,23)") # bright Green
        elif results["Inverter"] >= 2: # Blink
            if not self.qTimerInverter.isActive():
                self.qTimerInverter.start()
#====================================================================
# Bulk LED
        #results["Bulk"] = 3
        if results["Bulk"] == 0: # Off
            if self.qTimerBulk.isActive():
                self.qTimerBulk.stop()
            self.Bulk_LED.setStyleSheet("color: rgb(28, 28, 28)") # dark
        elif results["Bulk"] == 1: # On
            if self.qTimerBulk.isActive():
                self.qTimerBulk.stop()
            self.Bulk_LED.setStyleSheet("color: rgb(255, 255, 0)") # yellow
        elif results["Bulk"] >= 2: # Blink
            if not self.qTimerBulk.isActive():
                self.qTimerBulk.start()
#====================================================================
# Overload LED
        if results["Overload"] == 0: # Off
            if self.qTimerOverload.isActive():
                self.qTimerOverload.stop()
            self.Overload_LED.setStyleSheet("color: rgb(28, 28, 28)"); # dark

        elif results["Overload"] == 1: # On
            if self.qTimerOverload.isActive():
                self.qTimerOverload.stop()
            self.Overload_LED.setStyleSheet("color: rgb(255, 0, 0)"); # red

        elif results["Overload"] >= 2: # Blink
            if not self.qTimerOverload.isActive():
                self.qTimerOverload.start()
#====================================================================
# Absorption LED
        #results["Absorp"] = 3
        if results["Absorp"] == 0: # Off
            if self.qTimerAbsorp.isActive():
                self.qTimerAbsorp.stop()
            self.Absorption_LED.setStyleSheet("color: rgb(28, 28, 28)"); # dark
                                                         # Orange rgb(247, 119, 7)
        elif results["Absorp"] == 1: # On
            if self.qTimerAbsorp.isActive():
                self.qTimerAbsorp.stop()
            self.Absorption_LED.setStyleSheet("color: rgb(255, 255, 0)"); # yellow

        elif results["Absorp"] >= 2: # Blink
            if not self.qTimerAbsorp.isActive():
                self.qTimerAbsorp.start()
#====================================================================
# Low Battery LED
        if results["Lowbatt"] == 0: # Off
            if self.qTimerLowBatt.isActive():
                self.qTimerLowBatt.stop()
            self.Low_Battery_LED.setStyleSheet("color: rgb(28, 28, 28)"); # dark
                                                         # Orange rgb(247, 119, 7)
        elif results["Lowbatt"] == 1: # On
            if self.qTimerLowBatt.isActive():
                self.qTimerLowBatt.stop()
            self.Low_Battery_LED.setStyleSheet("color: rgb(255, 0, 0)"); # red

        elif results["Lowbatt"] >= 2: # Blink
            if not self.qTimerLowBatt.isActive():
                self.qTimerLowBatt.start()
#====================================================================
# Float LED
        #results["Floatchg"] = 3
        if results["Floatchg"] == 0: # Off
            if self.qTimerFloat.isActive():
                self.qTimerFloat.stop()
            self.Float_LED.setStyleSheet("color: rgb(28, 28, 28)"); # dark

        elif results["Floatchg"] == 1: # On
            if self.qTimerFloat.isActive():
                self.qTimerFloat.stop()
            self.Float_LED.setStyleSheet("color: rgb(255, 255, 0)"); # yellow
                                                         # Orange rgb(247, 119, 7)
        elif results["Floatchg"] >= 2: # Blink
            if not self.qTimerFloat.isActive():
                self.qTimerFloat.start()
#====================================================================
# Temperature LED
        if results["Temperature"] == 0: # Off
            if self.qTimerTemp.isActive():
                self.qTimerTemp.stop()
            self.Temperature_LED.setStyleSheet("color: rgb(28, 28, 28)"); # dark

        elif results["Temperature"] == 1: # On
            if self.qTimerTemp.isActive():
                self.qTimerTemp.stop()
            self.Temperature_LED.setStyleSheet("color: rgb(255, 0, 0)"); # red

        elif results["Temperature"] >= 2: # Blink
            if not self.qTimerTemp.isActive():
                self.qTimerTemp.start()

#====================================================================
#   VE.Bus Status
        if results["VEbusStatus"] == 2:
            self.System_State_Value.setText(str(VEbusStatusDict[results["VEbusStatus"]]))
            self.System_State_Value.setStyleSheet("QLabel#System_State_Value{font-weight: bold; color: red; background-color: black;}");

        else:
            self.System_State_Value.setText(str(VEbusStatusDict[results["VEbusStatus"]]))
            self.System_State_Value.setStyleSheet("QLabel#System_State_Value{font-weight: bold; color: rgb(0, 0, 0);}");
#====================================================================
#   VE.Bus Error
        if results["VEbusError"] > 0:
            self.VE_Bus_Error_Value.setText(str(VEbusErrorDict[results["VEbusError"]]))
            self.VE_Bus_Error_Value.setStyleSheet("QLabel#VE_Bus_Error_Value{font-weight: bold; color: red; background-color: black;}");

        else:
            self.VE_Bus_Error_Value.setText(str(VEbusErrorDict[results["VEbusError"]]))
            self.VE_Bus_Error_Value.setStyleSheet("QLabel#VE_Bus_Error_Value{font-weight: bold; color: rgb(0, 255, 0);}");

        # Battery Life Disabled
        if results["ESSbatteryLifeState"] >= 10:
            self.ESS_SOC_Dynamic_label.setHidden(True)
            self.ESS_SOC_Dynamic_Value.setHidden(True)
            self.ESS_SOC_User_Value.setText(str(results["ESSsocLimitUser"]))
            self.ESS_Mode_Value.setText(ESSbatteryLifeStateDict[results["ESSbatteryLifeState"]] + "           Optimized (BatteryLife Disabled)")
        # Battery Life Enabled
        elif results["ESSbatteryLifeState"] >= 1 and results["ESSbatteryLifeState"] <= 8:
            self.ESS_SOC_Dynamic_label.setHidden(False)
            self.ESS_SOC_Dynamic_Value.setHidden(False)
            self.ESS_SOC_User_label.setHidden(False)
            self.ESS_SOC_User_Value.setHidden(False)
            self.ESS_SOC_User_Value.setText(str(results["ESSsocLimitUser"]))
            self.ESS_SOC_Dynamic_Value.setText(str(results["ESSsocLimitDynamic"]))
            self.ESS_Mode_Value.setText(ESSbatteryLifeStateDict[results["ESSbatteryLifeState"]] + "           Optimized (BatteryLife Enabled)")
        # Keep Batteries Charged Mode
        elif results["ESSbatteryLifeState"] == 9:
            self.ESS_SOC_Dynamic_label.setHidden(True)
            self.ESS_SOC_Dynamic_Value.setHidden(True)
            self.ESS_SOC_User_label.setHidden(True)
            self.ESS_SOC_User_Value.setHidden(True)
            self.ESS_Mode_Value.setText(ESSbatteryLifeStateDict[results["ESSbatteryLifeState"]])


#====================================================================
#   Multiplus Switch
        if results["MPswitch"] == 1:
            results["MPswitch"] = "Charger Only"
        elif results["MPswitch"] == 2:
            results["MPswitch"] = "Inverter Only"
        elif results["MPswitch"] == 3:
            results["MPswitch"] = "ON"
        elif results["MPswitch"] == 4:
            results["MPswitch"] = "OFF"
        
        if results["MPswitch"] != "ON":
            self.Multiplus_Mode_Value.setStyleSheet("QLineEdit { background: rgb(255, 191, 0); }");
        else:
            self.Multiplus_Mode_Value.setStyleSheet("QLineEdit { background: ; }");



#===========================================================================================
# Populate Screen with Variable Values
#===========================================================================================
        # Battery Section
    
        self.Batt_SOC_progressBar.setRange(0, 100)
        self.Batt_SOC_progressBar.setValue(round(results["BatterySOC"]))
        self.Batt_SOC_progressBar.setToolTip(f'{results["BatterySOC"]:.1f} Percent')
        
        self.Batt_Watts_LCD.display(results["BatteryWatts"])
        self.Batt_Amps_LCD.display(results["BatteryAmps"])
        self.Batt_Volts_LCD.display(f"{results['BatteryVolts']:.2f}")
        self.DC_Power_LCD.display(f"{results['DCsystemPower']:.0f}")
        self.Batt_State_lineEdit.setText(results["BatteryState"])
        self.Last_Discharge_LCD.display(results["LastDischarge"])
        self.Consumed_AH_LCD.display(results["ConsumedAH"])
        self.Max_Charge_Amps_LCD.display(results["MaxChargeCurrent"])
        self.Charge_Cycles_LCD.display(results["ChargeCycles"])
        self.Last_Full_Charge_lineEdit.setText(str(f"{results['LastFullcharge']} Ago"))
        self.Time_To_Go_lineEdit.setText(str(results["BatteryTTG"]))


        # Solar Charger # 1 Section
        self.Solar_Name_1_lineEdit.setText(str(f"#1 {results['SolarName1']} - {Array1}"))
        self.PV_Watts_LCD.display(str(f"{results['SolarWatts1']:.0f}"))
        self.Output_Amps_LCD.display(str(f"{results['SolarAmps1']:.1f}"))
        self.Output_Amps_Limit_label.setText(results["SolarChargeLimit1"])
        self.PV_Volts_LCD.display(str(f"{results['SolarVolts1']:.1f}"))
        self.PV_Amps1_LCD.display(f"{results['PvAmps1']:.2f}")
        self.Max_PV_Watts_Today_LCD.display(results["MaxSolarWatts1"])
        self.Max_PV_Watts_Yesterday_LCD.display(results["MaxSolarWattsYest1"])
        self.Yield_Today_LCD.display(f"{results['SolarYield1']:.3f}")
        self.Yield_Yesterday_LCD.display(f"{results['SolarYieldYest1']:.3f}")
        self.Solar_Charger_State_lineEdit.setText(SolarStateDict[SolarState1])

        # Solar Charger # 2 Section
        self.Solar_Name_2_lineEdit.setText(f"#2 {results['SolarName2']} - {Array2}")
        self.PV_Watts_2_LCD.display(str(f"{results['SolarWatts2']:.0f}"))
        self.Output_Amps_2_LCD.display(f"{results['SolarAmps2']:.1f}")
        self.Output_Amps_Limit_2_label.setText(results['SolarChargeLimit2'])
        self.PV_Volts_2_LCD.display(results["SolarVolts2"])
        self.PV_Amps_2_LCD.display(f"{results['PvAmps2']:.2f}")
        self.Max_PV_Watts_Today_2_LCD.display(results["MaxSolarWatts2"])
        self.Max_PV_Watts_Yesterday_2_LCD.display(results["MaxSolarWattsYest2"])
        self.Yield_Today_2_LCD.display(f"{results['SolarYield2']:.3f}")
        self.Yield_Yesterday_2_LCD.display(f"{results['SolarYieldYest2']:.3f}")
        self.Solar_Charger_State2_lineEdit.setText(SolarStateDict[SolarState2])


        self.Total_Yield_Label.setText(str(f" Yield Today {results['TotalYield']:.3f} kwh"))
        self.Total_Yield_Label_Yest.setText(str(f" Yield Yesterday {results['TotalYieldYest']:.3f} kwh"))
        self.Max_Watts_Today_Label.setText(str(f"Max Watts Today {results['MaxTotalWattsToday']} W"))
        self.Max_Watts_Yest_Label.setText(str(f"Max Watts Yesterday {results['MaxTotalWattsYest']} W"))

        # Multiplus Section
        self.Grid_Set_Point_LCD.display(results["GridSetPoint"])
        self.Grid_Watts_LCD_L1.display(results["GridWattsL1"])
        self.Grid_Watts_LCD_L2.display(results["GridWattsL2"])
        self.AC_Out_Watts_LCD_L1.display(results["ACoutWattsL1"])
        self.AC_Out_Watts_LCD_L2.display(results["ACoutWattsL2"])
        self.Grid_Amps_LCD_L1.display(results["GridAmpsL1"])
        self.Grid_Amps_LCD_L2.display(results["GridAmpsL2"])
        self.AC_Out_Amps_LCD_L1.display(results["ACoutAmpsL1"])
        self.AC_Out_Amps_LCD_L2.display(results["ACoutAmpsL2"])
        self.Grid_Volts_LCD_L1.display(results["GridVoltsL1"])
        self.Grid_Volts_LCD_L2.display(results["GridVoltsL2"])
        self.AC_Out_Volts_LCD_L1.display(results["ACoutVoltsL1"])
        self.AC_Out_Volts_LCD_L2.display(results["ACoutVoltsL2"])
        self.Grid_Freq_LCD.display(results["GridHZ"])
        self.AC_Out_Freq_LCD.display(results["ACoutHZ"])
        self.Grid_Condition_lineEdit.setText(Condition)
        self.Grid_Current_Limit_LCD.display(results["GridAmpLimit"])
        self.MultiName_label.setText(results["MultiName"])
        
        # GX Firmware Section
        #self.Firmware_Installed_Value_label.setText(str(f"{results['FW_Installed']}"))
        #self.Firmware_Available_Value_label.setText(str(f"{results['FW_Available']}"))
        #self.Firmware_Backup_Value_label.setText(str(f"{results['FW_Backup']}"))
        
#===========================================================================================
# Text Browser Log, Event History
        global SolarState1_Old, SolarState2_Old, GridCondition_Old, \
        Mains_Old, Inverter_Old, Absorp_Old, Floatchg_Old, Bulk_Old, ESSbatteryLifeState_Old
        
        if self.SCC_checkBox.isChecked():
            if SolarState1 != SolarState1_Old:
                self.textBrowser.append(f"{dt_string} ---- | ---- Solar Charger 1 Changed to   {SolarStateDict[SolarState1]}")
                SolarState1_Old = SolarState1
            if SolarState2 != SolarState2_Old:
                self.textBrowser.append(f"{dt_string} ---- | ---- Solar Charger 2 Changed to   {SolarStateDict[SolarState2]}")
                SolarState2_Old = SolarState2

        if self.Grid_checkBox.isChecked():
            if GridCondition != GridCondition_Old:
                if GridCondition == 2:
                    self.textBrowser.append(f"{dt_string} ---- | ---- Grid Lost")
                    GridCondition_Old = GridCondition
                else:
                    self.textBrowser.append(f"{dt_string} ---- | ---- Grid Restored")
                    GridCondition_Old = GridCondition

        if self.Inv_checkBox.isChecked():
            if Inverter != Inverter_Old:
                if Inverter == 0:
                    self.textBrowser.append(f"{dt_string} ---- | ---- Inverter Changed to   OFF")
                    Inverter_Old = Inverter
                elif Inverter == 1:
                    self.textBrowser.append(f"{dt_string} ---- | ---- Inverter Changed to   ON")
                    Inverter_Old = Inverter
                elif Inverter >= 2:
                    self.textBrowser.append(f"{dt_string} ---- | ---- Inverter Changed to Power Assist Active")
                    Inverter_Old = Inverter
        
        if self.Mains_checkBox.isChecked():
            if Mains != Mains_Old:
                if Mains == 1:
                    self.textBrowser.append(f"{dt_string} ---- | ---- Mains Changed to   Normal")
                    Mains_Old = Mains
                elif Mains >= 2 and GridWattsL1 < 0:
                    self.textBrowser.append(f"{dt_string} ---- | ---- Mains Changed to Feed-In Active")
                    Mains_Old = Mains

        if self.Multi_checkBox.isChecked():
            if Bulk != Bulk_Old:
                if Bulk == 1:
                    self.textBrowser.append(f"{dt_string} ---- | ---- Bulk Charging   ON")
                    Bulk_Old = Bulk
                elif Bulk == 0:
                    self.textBrowser.append(f"{dt_string} ---- | ---- Bulk Charging   OFF")
                    Bulk_Old = Bulk
    
            if Absorp != Absorp_Old:
                if Absorp == 1:
                    self.textBrowser.append(f"{dt_string} ---- | ---- Absorption Charging   ON")
                    Absorp_Old = Absorp
                elif Absorp == 0:
                    self.textBrowser.append(f"{dt_string} ---- | ---- Absorption Charging   OFF")
                    Absorp_Old = Absorp
    
            if Floatchg != Floatchg_Old:
                if Floatchg == 1:
                    self.textBrowser.append(f"{dt_string} ---- | ---- Float Charging   ON")
                    Floatchg_Old = Floatchg
                elif Floatchg == 0:
                    self.textBrowser.append(f"{dt_string} ---- | ---- Float Charging   OFF")
                    Floatchg_Old = Floatchg
        
        if self.ESS_Status_checkBox.isChecked():
            if results["ESSbatteryLifeState"] != ESSbatteryLifeState_Old:
                self.textBrowser.append(f"{dt_string} ---- | ---- ESS Battery Life State Changed to {ESSbatteryLifeStateDict[results['ESSbatteryLifeState']]}")
                ESSbatteryLifeState_Old = results["ESSbatteryLifeState"]

        #self.textBrowser.append(f"{dt_string} ---- Test String==================================")
#===========================================================================================
        if results["SolarError1"] > 0:
            self.Solar_Charger1_Error_Value.setText(SolarErrorDict[results['SolarError1']])
            self.Solar_Charger1_Error_Value.setStyleSheet("QLabel#Solar_Charger1_Error_Value{font-weight: bold; color: red; background-color: black;}");

        else:
            self.Solar_Charger1_Error_Value.setText(SolarErrorDict[results['SolarError1']])
            self.Solar_Charger1_Error_Value.setStyleSheet("QLabel#Solar_Charger1_Error_Value{color: rgb(0, 255, 0);}");

        if results["SolarError2"] > 0:
            self.Solar_Charger2_Error_Value(SolarErrorDict[results['SolarError2']])
            self.Solar_Charger2_Error_Value.setStyleSheet("QLabel#Solar_Charger2_Error_Value{font-weight: bold; color: red; background-color: black;}");

        else:
            self.Solar_Charger2_Error_Value.setText(SolarErrorDict[results['SolarError2']])
            self.Solar_Charger2_Error_Value.setStyleSheet("QLabel#Solar_Charger2_Error_Value{color: rgb(0, 255, 0);}");


        self.Multiplus_Mode_Value.setText(str(results["MPswitch"]))
        
        if Analog_Inputs.lower() == 'y':
            self.TempSensor1_label.setText(Tempsensor1_Name)
            self.TempSensor2_label.setText(Tempsensor2_Name)
            self.TempSensor3_label.setText(Tempsensor3_Name)

#===========================================================================================

    def runLongTask(self):
        # Step 2: Create a QThread object
        self.thread = QThread()

        # Step 3: Create a worker object
        self.worker = Worker()

        # Step 4: Move worker to the thread
        self.worker.moveToThread(self.thread)
        
        # Step 5: Connect signals and slots
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.progress.connect(self.update)
        
        # Step 6: Start the thread
        self.thread.start()

        # Final resets
        #self.thread.finished.connect()

running = True
app = QApplication(sys.argv)
win = Window()
win.show()
sys.exit(app.exec_())
