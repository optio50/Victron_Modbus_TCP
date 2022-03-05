#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# This script depends on the following Victron equipment. BMV, Multiplus, Solar Charger, Venus GX device.
# Modbus & mqtt must be enabled in the Venus GX device
# You shouldnt have to change anything but some variables to make this work with your system
# provided you actually have the requsite victron equipment.

# Some items are simply not available via ModBusTCP and MQTT will be used to aqquire those values.


# The changeable variables:
# ip, VRMid, SolarCharger_1_ID, MQTT_SolarCharger_1_ID, MultiPlusID, MQTT_MultiPlusID, BmvID, MQTT_BmvID, VEsystemID
# MQTT_VEsystemID, Multiplus_Leds, ESS_Info, Analog_Inputs


# Key press detection (lowercase M E A Q)
# These can also be turned off before program startup by changing the variables to a value of 'n'
    # M to Turn Multiplus LED's on/off
    # E to Turn ESS display on/off
    # A to Turn Analog inputs (Temperature) on/off
    # Q to Exit

import json
import curses
from curses import wrapper
import paho.mqtt.subscribe as subscribe
from pymodbus.constants import Defaults
from pymodbus.constants import Endian
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.payload import BinaryPayloadBuilder
################
#import argparse
#import struct
#from pymodbus.client.sync import ModbusTcpClient
################
import textwrap
from datetime import datetime
from datetime import timedelta
import sys
import os
import subprocess
import time
from time import strftime
from time import gmtime
#import random

# Wrap text on display (lines too long)
tr = textwrap.TextWrapper(width=55, subsequent_indent=" ")

RefreshRate = 1   # Refresh Rate in seconds. Auto increased to 1.5 (from 1 second) if LED's enabled For MQTT requests

# GX Device I.P Address
ip = '192.168.20.156'

# MQTT Request's are for Multiplus LED state's
# VRM Portal ID from GX device. 
# AFAIK this ID is needed even with no internet access as its the name of your venus device.
# Menu -->> Settings -->> "VRM Online Portal -->> VRM Portal ID"
VRMid = "d41243d31a90"

Analog_Inputs  = 'Y'     # Y or N (case insensitive) to display Gerbo GX Analog Temperature inputs
ESS_Info       = 'Y'          # Y or N (case insensitive) to display ESS system information
Multiplus_Leds = 'Y'    # Y or N (case insensitive) to display Multiplus LED'S


# Unit ID #'s from Cerbo GX.
# Do not confuse UnitID with Instance ID.
# You can also get the UnitID from the GX device. Menu --> Settings --> Services --> ModBusTCP --> Available Services
# https://github.com/victronenergy/dbus_modbustcp/blob/master/CCGX-Modbus-TCP-register-list.xlsx Tab #2
#===================================
# ModBus Unit ID
SolarCharger_1_ID = 226
#SolarCharger_2_ID =
MultiPlusID       = 227
BmvID             = 223
VEsystemID        = 100
#===================================
# MQTT Instance ID
# This is the Instance ID not to be confused with the above Unit ID.
# Device List in VRM or crossed referenced in the CCGX-Modbus-TCP-register-list.xlsx Tab #2
MQTT_SolarCharger_1_ID = 279
#MQTT_SolarCharger_2_ID =
MQTT_MultiPlusID       = 276
MQTT_BmvID             = 277
MQTT_VEsystemID        = 0
#===================================


# Local network ip address of Cerbo GX. Default port 502
client = ModbusClient(ip, port='502')
builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)

Defaults.Timeout = 25
Defaults.Retries = 5

stdscr = curses.initscr()
curses.resize_term(55, 90)
stdscr.nodelay(True)

# Pathetic Progressbar :-)
Pbar0  = "▒░░░░░░░░░░░░░░░░░░░░░"
Pbar10 = "▒▒░░░░░░░░░░░░░░░░░░░░"
Pbar20 = "▒▒▒▒░░░░░░░░░░░░░░░░░░"
Pbar30 = "▒▒▒▒▒▒░░░░░░░░░░░░░░░░"
Pbar40 = "▒▒▒▒▒▒▒▒░░░░░░░░░░░░░░"
Pbar50 = "▒▒▒▒▒▒▒▒▒▒░░░░░░░░░░░░"
Pbar60 = "▒▒▒▒▒▒▒▒▒▒▒▒░░░░░░░░░░"
Pbar70 = "▒▒▒▒▒▒▒▒▒▒▒▒▒▒░░░░░░░░"
Pbar80 = "▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒░░░░░░"
Pbar90 = "▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒░░░░"
Pbar100 ="▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒"


# Text Colors
# Find More Color Numbers and Names Here.
# https://github.com/optio50/PythonColors/blob/main/color-test.py
#curses.can_change_color():
curses.curs_set(False)
curses.start_color()
curses.use_default_colors()
curses.init_color(0, 0, 0,  0)
curses.init_pair(100, 82,  -1)  # Fluorescent Green
curses.init_pair(101, 93,  -1)  # Purple
curses.init_pair(102, 2,   -1)   # Green
curses.init_pair(103, 226, -1) # Yellow
curses.init_pair(104, 160, -1) # Red
curses.init_pair(105, 37,  -1)  # Cyan
curses.init_pair(106, 202, -1) # Orange
curses.init_pair(107, 33,  -1)  # Lt Blue
curses.init_pair(108, 21,  -1)  # Blue1
curses.init_pair(109, 239, -1) # Gray
curses.init_pair(110, 197, -1) # Lt Pink
curses.init_pair(111, 201, -1) # Pink
curses.init_pair(112, 137, -1) # Lt Salmon
curses.init_pair(113, 234, -1) # Gray_7
curses.init_pair(114, 178, -1) # gold_3b
curses.init_pair(115, 236, -1) # gray_19
#=======================================================================
#=======================================================================
fgreen   = curses.color_pair(100)
purple   = curses.color_pair(101)
green    = curses.color_pair(102)
yellow   = curses.color_pair(103)
red      = curses.color_pair(104)
cyan     = curses.color_pair(105)
orange   = curses.color_pair(106)
ltblue   = curses.color_pair(107)
blue1    = curses.color_pair(108)
gray     = curses.color_pair(109)
ltpink   = curses.color_pair(110)
pink     = curses.color_pair(111)
ltsalmon = curses.color_pair(112)
gray7    = curses.color_pair(113)
gold     = curses.color_pair(114)
gray19   = curses.color_pair(115)


def modbus_register(address, unit):
        msg     = client.read_input_registers(address, unit=unit)
        decoder = BinaryPayloadDecoder.fromRegisters(msg.registers, byteorder=Endian.Big)
        msg     = decoder.decode_16bit_int()
        return msg


def mqtt_request(mqtt_path):
    topic = subscribe.simple(mqtt_path, hostname=ip)
    data  = json.loads(topic.payload)
    topic = data['value']
    return topic


def spacer():
    stdscr.addnstr("═"*80 + "\n",100, gray)



def spacer2():
    stdscr.addnstr("—"*80 + "\n",100, gray)


def clean_exit():
    curses.curs_set(True)
    curses.nocbreak()
    stdscr.keypad(False)
    curses.echo()
    curses.endwin()
    curses.flushinp()
    sys.exit(0)


def main(stdscr):
    global Multiplus_Leds
    global ESS_Info
    global Analog_Inputs
    stdscr.nodelay(True)


    #errorindex = 0
    while True:
        screensize = os.get_terminal_size()
        stdscr.clear()

        try:
# ===========================================================================================
#   Conditional MQTT Request's because Multiplus II status LED's are not available with ModbusTCP
            
            if Multiplus_Leds.lower() == "y":

                Mains       = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlusID)+"/Leds/Mains")
                Inverter    = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlusID)+"/Leds/Inverter")
                Bulk        = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlusID)+"/Leds/Bulk")
                Overload    = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlusID)+"/Leds/Overload")
                Absorp      = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlusID)+"/Leds/Absorption")
                Lowbatt     = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlusID)+"/Leds/LowBattery")
                Floatchg    = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlusID)+"/Leds/Float")
                Temperature = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlusID)+"/Leds/Temperature")
                MultiName   = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlusID)+"/ProductName")

                # Switch Position on the Multiplus II
                MPswitch    = modbus_register(33,MultiPlusID)

# ===========================================================================================
#   Unconditional Request's

#   Battery
            # MQTT LastDischarge, LastFullcharge, MaxChargeCurrent
            LastDischarge    = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BmvID)+"/History/LastDischarge")
            LastFullcharge   = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BmvID)+"/History/TimeSinceLastFullCharge")
            MaxChargeCurrent = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlusID)+"/Dc/0/MaxChargeCurrent")
           
            # ModbusTCP
            BatterySOC    = modbus_register(266,BmvID) / 10
            BatteryWatts  = modbus_register(842,VEsystemID)
            BatteryAmps   = modbus_register(261,BmvID) / 10
            BatteryVolts  = modbus_register(259,BmvID) / 100
            BatteryTTG    = modbus_register(846,VEsystemID) / .01
            ChargeCycles  = modbus_register(284,BmvID)
            ChargePower   = modbus_register(855,VEsystemID)
            ConsumedAH    = modbus_register(265,BmvID) / -10
            DCsystemPower = modbus_register(860,VEsystemID)

# ===========================================================================================

#   Solar Charge Controller
            
            # MQTT, Couldnt find the equivalent ModBus register
            SolarChargeLimit  = mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Settings/ChargeCurrentLimit")
            
            # Solar Charger # 1
            SolarWatts1       = modbus_register(789,SolarCharger_1_ID) / 10
            # Solar Charger # 2
            SolarWatts2       = "Not Installed"#modbus_register(789,SolarCharger_2_ID) / 10
            
            # Total of all solar chargers
            SolarWatts        = modbus_register(850,VEsystemID)
            # Total of all solar chargers
            SolarAmps         = modbus_register(851,VEsystemID) / 10
            SolarVolts        = modbus_register(776,SolarCharger_1_ID) / 100
            MaxSolarWatts     = modbus_register(785,SolarCharger_1_ID)
            MaxSolarWattsYest = modbus_register(787,SolarCharger_1_ID)
            SolarYield        = modbus_register(784,SolarCharger_1_ID) / 10
            SolarYieldYest    = modbus_register(786,SolarCharger_1_ID) / 10
            TotalSolarYield   = modbus_register(790,SolarCharger_1_ID) / 10
            SolarState        = modbus_register(775,SolarCharger_1_ID)
            SolarError        = modbus_register(788,SolarCharger_1_ID)
            #SolarError = 20 # Test
            #error_nos = [0,1,2,3,4,5,6,7,8,9,17,18,19,20,22,23,33,34]
            #SolarError = error_nos[errorindex] # Display Test PV Error's
# ===========================================================================================

#   Grid Input & A/C out
            
            FeedIn        = modbus_register(2707,VEsystemID)
            GridSetPoint  = modbus_register(2700,VEsystemID)
            GridWatts     = modbus_register(820,VEsystemID)
            GridAmps      = modbus_register(6,MultiPlusID) / 10
            GridVolts     = modbus_register(3,MultiPlusID) / 10
            GridHZ        = modbus_register(9,MultiPlusID) / 100
            ACoutWatts    = modbus_register(817,VEsystemID)
            ACoutAmps     = modbus_register(18,MultiPlusID) / 10
            ACoutVolts    = modbus_register(15,MultiPlusID) / 10
            ACoutHZ       = modbus_register(21,MultiPlusID) / 100
            GridCondition = modbus_register(64,MultiPlusID)
            GridAmpLimit  = modbus_register(22,MultiPlusID) / 10

            # System Type ex: ESS, Hub-*
            try:
                SystemType  = mqtt_request("N/"+VRMid+"/system/0/SystemType")
            except AttributeError:
                SystemType = 777

# ===========================================================================================

#   VEbus Status
            VEbusStatus = mqtt_request("N/"+VRMid+"/system/"+str(MQTT_VEsystemID)+"/SystemState/State")
            #VEbusStatus = modbus_register(31,MultiPlusID)
# ===========================================================================================

#   VEbus Error
            VEbusError  = modbus_register(32,MultiPlusID)
            #VEbusError = 55 # Test single error mesg
            #error_nos = [0,1,2,3,4,5,6,7,10,14,16,17,18,22,24,25,26]
            #VEbusError = error_nos[errorindex] # Multiple Test VEbusError's
# ===========================================================================================

# Conditional Modbus Request
# ESS Info
            if ESS_Info.lower() == "y":
                ESSbatteryLifeState = modbus_register(2900,VEsystemID)
                ESSsocLimitUser     = modbus_register(2901,VEsystemID) / 10

# ===========================================================================================

# Conditional Modbus Request
# Analog Temperature Inputs
# Change the ID to your correct value

            if Analog_Inputs.lower() == "y":
                try:
                    TempSensor1 = modbus_register(3304,24) / 100 * 1.8 + 32
                except AttributeError:
                    TempSensor1 = 777
                
                try:
                    TempSensor2 = modbus_register(3304,25) / 100 * 1.8 + 32
                except AttributeError:
                    TempSensor2 = 777
                
                try:
                    TempSensor3 = modbus_register(3304,26) / 100 * 1.8 + 32
                except AttributeError:
                    TempSensor3 = 777
                
                
# ^^^ End Modbus Request's
# ===========================================================================================
# Start populating the screen

# Datetime object containing current date and time
            now = datetime.now()

            # Fri 21 Jan 2022 09:06:57 PM
            dt_string = now.strftime("%a %d %b %Y %r")
            try:
                stdscr.addnstr("\n Time & Date............. ",100, purple)
                stdscr.addnstr(dt_string + "\n",100, purple)
            except curses.error:
                pass
# ===========================================================================================
#   Battery
            if BatterySOC <= 10:
                BpBar = Pbar0
                color = red
            elif BatterySOC > 10 and BatterySOC <= 20:
                BpBar = Pbar20
                color = red
            elif BatterySOC > 20 and BatterySOC <= 30:
                BpBar = Pbar30
                color = yellow
            elif BatterySOC > 30 and BatterySOC <= 40:
                BpBar = Pbar40
                color = yellow
            elif BatterySOC > 40 and BatterySOC <= 50:
                BpBar = Pbar50
                color = yellow
            elif BatterySOC > 50 and BatterySOC <= 60:
                BpBar = Pbar60
                color = yellow
            elif BatterySOC > 60 and BatterySOC <= 70:
                BpBar = Pbar70
                color = green
            elif BatterySOC > 70 and BatterySOC <= 80:
                BpBar = Pbar80
                color = green
            elif BatterySOC > 80 and BatterySOC <= 90:
                BpBar = Pbar90
                color = green
            elif BatterySOC > 90:
                BpBar = Pbar100
                color = green
            
            if color != red:
                stdscr.addstr(" Battery SOC............. ", cyan)
                stdscr.addstr("{:.1f}%".format(BatterySOC), color | curses.A_BOLD)
                stdscr.addstr(2,39, BpBar +"\n", color | curses.A_BOLD)
            
            else:
                stdscr.addstr(" Battery SOC............. ", cyan)
                stdscr.addstr("{:.1f}%".format(BatterySOC), color | curses.A_BLINK)
                stdscr.addstr(2,39, BpBar +"\n", color)


            stdscr.addnstr(f" Battery Watts........... {BatteryWatts}\n",50, cyan)
            


            stdscr.addnstr(f" Battery Amps............ {BatteryAmps}",50, cyan)
            stdscr.addnstr(4,38,f"║ Last Discharge .......... {LastDischarge:.1f} AH\n",50, cyan)


            stdscr.addnstr(f" Battery Volts........... {BatteryVolts}",50, cyan)
            stdscr.addnstr(5,38,f"║ Consumed AH ............. {ConsumedAH}\n",50, cyan)

            
            
            if BatteryTTG == 0.0:
                BatteryTTG = "Infinite"
            else:
                BatteryTTG = timedelta(seconds = BatteryTTG)
            
            LastFullcharge = timedelta(seconds = LastFullcharge)
            
            stdscr.addnstr(f" Battery Charge Cycles... {ChargeCycles}",50, cyan)
            stdscr.addnstr(6,38,f"║ Max Charge Current....... {MaxChargeCurrent} A\n",50, cyan)

            stdscr.addnstr(f" DC System Power......... {DCsystemPower} W",50, cyan)
            stdscr.addnstr(7,38,f"║ Last Full Charge......... {LastFullcharge} \n",50, cyan)
            
            
            stdscr.addnstr(f" Battery Time to Go...... {BatteryTTG}\n",50, cyan)
            
            
            
            spacer()

# ===========================================================================================
#   Solar Charge Controller

            #SolarWatts = random.randrange(0, 400, 10) # Test Progressbar
            if SolarVolts < 15 and SolarState == 0:
                stdscr.addstr(f" PV Watts Total.......... {SolarWatts:.0f}", orange)
                stdscr.addstr(10,32,f"🌛\n", orange)
                
            ###################################
            ###         400W array          ###
            ###################################
            elif SolarWatts >= 50 and SolarWatts < 100:
                stdscr.addstr(f" PV Watts Total.......... {SolarWatts:.0f}", orange)
                stdscr.addstr(10,39,f"🌞\n", orange)
            elif SolarWatts >= 100 and SolarWatts < 200:
                stdscr.addstr(f" PV Watts Total.......... {SolarWatts:.0f}", orange)
                stdscr.addstr(10,39,f"🌞   🌞\n", orange)
            elif SolarWatts >= 200 and SolarWatts < 300:
                stdscr.addstr(f" PV Watts Total.......... {SolarWatts:.0f}", orange)
                stdscr.addstr(10,39,f"🌞   🌞   🌞\n", orange)
            elif SolarWatts >= 300 and SolarWatts < 350:
                stdscr.addstr(f" PV Watts Total.......... {SolarWatts:.0f}", orange)
                stdscr.addstr(10,39,f"🌞   🌞   🌞   🌞\n", orange)
            elif SolarWatts >= 350:
                stdscr.addstr(f" PV Watts Total.......... {SolarWatts:.0f}", orange)
                stdscr.addstr(10,39,f"🌞   🌞   🌞   🌞   🌞\n", orange)
            elif SolarWatts < 50:
                stdscr.addstr(f" PV Watts Total.......... {SolarWatts:.0f}", orange)
                stdscr.addstr(10,39,f"⛅\n", orange)
            


            stdscr.addnstr(f" PV Watts Charger # 1.... {SolarWatts1:.0f}",100, orange)
            #if SolarAmps == 'No Value, Firmware bug.':
            #    stdscr.addnstr("No Value, Firmware bug. Update GX Firmware >= 2.84",100, red)
            #else:
            #    stdscr.addnstr(f"{SolarAmps:.1f}",100, orange)
            stdscr.addnstr(11,38,f"║ PV Charger # 1 Limit........ {SolarChargeLimit} A\n",100, orange)
            
            stdscr.addnstr(f" PV Watts Charger # 2.... ❌",100, orange)
            stdscr.addnstr(12,38,f"║ PV Charger # 2 Limit........ ❌\n",100, orange)
            
            stdscr.addnstr(f" Max PV Watts Today...... {MaxSolarWatts:.0f}",100, orange)
            stdscr.addnstr(13,38,f"║ PV Yield Today.............. {SolarYield:.3f} kWh\n",100, orange)

            stdscr.addnstr(f" Max PV Watts Yesterday.. {MaxSolarWattsYest}",50, orange)
            stdscr.addnstr(14,38,f"║ PV Yield Yesterday.......... {SolarYieldYest:.3f} kWh\n",100, orange)

            if SolarState == 0:
                stdscr.addnstr(" PV Charger State........ OFF \n",100, orange)
            elif SolarState == 2:
                stdscr.addnstr(" PV Charger State........ Fault\n",100, orange)
            elif SolarState == 3:
                stdscr.addnstr(" PV Charger State........ Bulk\n",100, orange)
            elif SolarState == 4:
                stdscr.addnstr(" PV Charger State........ Absorption\n",100, orange)
            elif SolarState == 5:
                stdscr.addnstr(" PV Charger State........ Float\n",100, orange)
            elif SolarState == 6:
                stdscr.addnstr(" PV Charger State........ Storage\n",100, orange)
            elif SolarState == 7:
                stdscr.addnstr(" PV Charger State........ Equalize\n",100, orange)
            elif SolarState == 11:
                stdscr.addnstr(" PV Charger State........ Other (Hub-1)\n",100, orange)
            elif SolarState == 252:
                stdscr.addnstr(" PV Charger State........ EXT Control\n",100, orange)

            stdscr.addnstr(15,38,f"║ Total PV Yield Since Reset.. {TotalSolarYield:.3f} kWh\n",100, orange)
            
            #PVErrorList = [0,1,2,3,4,5,6,7,8,9,17,18,19,20,22,23,33,34]
            #SolarError = errorindex
            
            if SolarError == 0:
                stdscr.addnstr(" PV Charger Error........ ",100, orange)
                stdscr.addnstr("No Error \n", -1, green)
            elif SolarError == 1:
                stdscr.addnstr(" PV Charger Error........ ",100, orange)
                stdscr.addnstr("Error 1: Battery temperature too high\n", -1, red)
            elif SolarError == 2:
                stdscr.addnstr(" PV Charger Error........ ",100, orange)
                stdscr.addnstr("Error 2: Battery voltage too high\n", -1, red)
            elif SolarError == 3:
                stdscr.addnstr(" PV Charger Error........ ",100, orange)
                stdscr.addnstr("Error 3: Battery temperature sensor miswired (+)\n", -1, red)
            elif SolarError == 4:
                stdscr.addnstr(" PV Charger Error........ ",100, orange)
                stdscr.addnstr("Error 4: Battery temperature sensor miswired (-)\n", -1, red)
            elif SolarError == 5:
                stdscr.addnstr(" PV Charger Error........ ",100, orange)
                stdscr.addnstr("Error 5: Battery temperature sensor disconnected\n", -1, red)
            elif SolarError == 6:
                stdscr.addnstr(" PV Charger Error........ ",100, orange)
                stdscr.addnstr("Error 6: Battery voltage sense miswired (+)\n", -1, red)
            elif SolarError == 7:
                stdscr.addnstr(" PV Charger Error........ ",100, orange)
                stdscr.addnstr("Error 7: Battery voltage sense miswired (-)\n", -1, red)
            elif SolarError == 8:
                stdscr.addnstr(" PV Charger Error........ ",100, orange)
                stdscr.addnstr("Error 8: Battery voltage sense disconnected \n", -1, red)
            elif SolarError == 9:
                stdscr.addnstr(" PV Charger Error........ ",100, orange)
                stdscr.addnstr("Error 9: Battery voltage wire losses too high\n", -1, red)
            elif SolarError == 17:
                stdscr.addnstr(" PV Charger Error........ ",100, orange)
                stdscr.addnstr("Error 17: Charger temperature too high\n", -1, red)
            elif SolarError == 18:
                stdscr.addnstr(" PV Charger Error........ ",100, orange)
                stdscr.addnstr("Error 18: Charger over-current\n", -1, red)
            elif SolarError == 19:
                stdscr.addnstr(" PV Charger Error........ ",100, orange)
                stdscr.addnstr("Error 19: Charger current polarity reversed\n", -1, red)
            elif SolarError == 20:
                stdscr.addnstr(" PV Charger Error........ ",100, orange)
                stdscr.addnstr("Error 20: Bulk time limit exceeded\n", -1, red)
            elif SolarError == 22:
                stdscr.addnstr(" PV Charger Error........ ",100, orange)
                stdscr.addnstr("Error 22: Charger temperature sensor miswired\n", -1, red)
            elif SolarError == 23:
                stdscr.addnstr(" PV Charger Error........ ",100, orange)
                stdscr.addnstr("Error 23: Charger temperature sensor disconnected\n", -1, red)
            elif SolarError == 33:
                stdscr.addnstr(" PV Charger Error........ ",100, orange)
                stdscr.addnstr("Error 33: Input voltage too high\n", -1, red)
            elif SolarError == 34:
                stdscr.addnstr(" PV Charger Error........ ",100, orange)
                stdscr.addnstr("Error 34: Input current too high\n", -1, red)
            else:
                stdscr.addnstr(" PV Charger Error........ ",100, orange)
                stdscr.addnstr(f"Error {SolarError}: Unknown Description\n", -1, red)
            
            # errorindex += 1
            # if errorindex == len(PVErrorList): # Test PV error's
                # errorindex = 0
            
            spacer()
# ===========================================================================================
#   Grid In & A/C Out

            stdscr.addnstr(f" Feed Excess PV To Grid?. ",100, green)
            if FeedIn == 1:
                stdscr.addnstr("YES",90, red)
                stdscr.addnstr(18,47,"[  or  ] Brackets To Change Value\n",100, gray7)
            else:
                stdscr.addnstr("NO ",90, green)
                stdscr.addnstr(18,47,"[  or  ] Brackets To Change Value\n",100, gray7)
            
            stdscr.addnstr(" Grid Set Point Watts.... ",100, green)
            stdscr.addnstr("{:.0f} ".format(GridSetPoint),100, green)
            stdscr.addnstr(19,47,"(↑) or (↓) Arrows To Change Value\n",100, gray7)
            
            if GridWatts > 0:
                stdscr.addnstr(f" Grid Watts.............. {GridWatts}",100, green)
                stdscr.addnstr(20,38," AC Output Watts......... ",100, green)
                stdscr.addnstr("{:.0f}\n".format(ACoutWatts),100, green)
            elif GridWatts < 0 and FeedIn == 1:
                stdscr.addnstr(f" Grid Watts............. {GridWatts}",100, green)
                stdscr.addnstr(20,14,f"Feed-In", 90,red | curses.A_BLINK)
                stdscr.addnstr(f".... {GridWatts}",100, green)
                stdscr.addnstr(20,38," AC Output Watts......... ",100, green)
                stdscr.addnstr("{:.0f}\n".format(ACoutWatts),100, green)

            stdscr.addnstr(" Grid Amps............... ",100, green)
            stdscr.addnstr("{:.1f}".format(GridAmps),100, green)
            stdscr.addnstr(21,38," AC Output Amps.......... ",100, green)
            stdscr.addnstr("{:.1f} \n".format(ACoutAmps),100, green)
            
            stdscr.addnstr(" Grid Volts.............. ",100, green)
            stdscr.addnstr("{:.1f} ".format(GridVolts),100, green)
            stdscr.addnstr(22,38," AC Output Volts......... ",100, green)
            stdscr.addnstr("{:.1f} \n".format(ACoutVolts),100, green)
            
            stdscr.addnstr(" Grid Freq .............. ",100, green)
            stdscr.addnstr("{:.1f}".format(GridHZ),100, green)
            stdscr.addnstr(23,38," AC Output Freq.......... ",100, green)
            stdscr.addnstr("{:.1f} \n".format(ACoutHZ),100, green)
            
            stdscr.addnstr(f" Grid Current Limit...... {GridAmpLimit} A\n",100, green)
            
            if SystemType != 777:
                stdscr.addnstr(24,38,f" System Type............. {SystemType}\n",100, gold)
            else:
                stdscr.addnstr(24,38,f" System Type............. Unknown Type\n",100, gold)
            
            if GridCondition == 0:
                stdscr.addstr(f" Grid Condition.......... OK \n", green)
                
            elif GridCondition == 2:
                
                stdscr.addstr(f" Grid Condition ......... ", green)
                stdscr.addstr("Grid LOST!\n", red | curses.A_BLINK)

            spacer()

# ===========================================================================================
#   VE.Bus Status
            
            if VEbusStatus == 0:
                stdscr.addnstr(" System State............ OFF\n",100, ltblue)
            elif VEbusStatus == 1:
                stdscr.addnstr(" System State............ Low Power\n",100, ltblue)
            elif VEbusStatus == 2:
                stdscr.addnstr(" System State............ Fault\n",100, red)
            elif VEbusStatus == 3:
                stdscr.addnstr(" System State............ Bulk Charging\n",100, ltblue)
            elif VEbusStatus == 4:
                stdscr.addnstr(" System State............ Absorption Charging\n",100, ltblue)
            elif VEbusStatus == 5:
                stdscr.addnstr(" System State............ Float Charging\n",100, ltblue)
            elif VEbusStatus == 6:
                stdscr.addnstr(" System State............ Storage\n",100, ltblue)
            elif VEbusStatus == 7:
                stdscr.addnstr(" System State............ Equalize\n",100, ltblue)
            elif VEbusStatus == 8:
                stdscr.addnstr(" System State............ Passthru\n",100, ltblue)
            elif VEbusStatus == 9:
                stdscr.addnstr(" System State............ Inverting\n",100, ltblue)
            elif VEbusStatus == 10:
                stdscr.addnstr(" System State............ Power Assist\n",100, ltblue)
            elif VEbusStatus == 256:
                stdscr.addnstr(" System State............ Discharging\n",100, ltblue)
            elif VEbusStatus == 257:
                stdscr.addnstr(" System State............ Sustain\n",100, ltblue)
            else:
                stdscr.addnstr(" System State............ Unknown State\n",100, ltblue)
# ===========================================================================================
#   VE.Bus Error            
            # https://www.victronenergy.com/live/ve.bus:ve.bus_error_codes#vebus_error_codes1
            #VEbusErrorList = [0,1,2,3,4,5,6,7,10,14,16,17,18,22,24,25,26]
            if VEbusError == 0:
                stdscr.addnstr(" VE.Bus Error............ ",90, ltblue)
                stdscr.addnstr("No Error\n",90, green)
            elif VEbusError == 1:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr(tr.fill("Error 1: Device is switched off because one of the other "
                "phases in the system has switched off") + "\n", -1, red)
            elif VEbusError == 2:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr("Error 2: New and old types MK2 are mixed in the system \n",90, red)
            elif VEbusError == 3:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr(tr.fill("Error 3: Not all- or more than- the expected devices "
                "were found in the system") + "\n", -1, red)
            elif VEbusError == 4:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr("Error 4: No other device whatsoever detected\n",90, red)
            elif VEbusError == 5:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr("Error 5: Overvoltage on AC-out\n", 90, red)
            elif VEbusError == 6:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr("Error 6: in DDC Program\n", 90, red)
            elif VEbusError == 7:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr(tr.fill("VE.Bus BMS connected- which requires an Assistant- "
                "but no assistant found") + "\n", -1, red)
            elif VEbusError == 8:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr(tr.fill("Error 8: Ground Relay Test Failed") + "\n", -1, red)
            elif VEbusError == 10:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr("Error 10: System time synchronisation problem occurred\n",90, red)
            elif VEbusError == 11:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr("Relay Test Fault - Installation error or possibly relay failure\n",90, red)
            elif VEbusError == 12:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr("Error 12 - Config mismatch with 2nd mcu\n",90, red)
            elif VEbusError == 14:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr("Error 14: Device cannot transmit data\n",90, red)
            elif VEbusError == 15:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr("Error 15 - VE.Bus combination error\n",90, red)
            elif VEbusError == 16:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr("Error 16: Dongle missing\n", 90, red)
            elif VEbusError == 17:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr(tr.fill("Error 17: One of the devices assumed master "
                "status because the original master failed") + "\n", -1, red)
            elif VEbusError == 18:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr(tr.fill("Error 18: AC Overvoltage on the output "
                "of a slave has occurred while already switched off") + "\n", -1, red)
            elif VEbusError == 19:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr("Error 19 - Slave does not have AC input!\n",90, red)
            elif VEbusError == 20:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr("Error 20: - Configuration mismatch\n",90, red)
            elif VEbusError == 22:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr("Error 22: This device cannot function as slave\n",-1, red)
            elif VEbusError == 24:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr("Error 24: Switch-over system protection initiated\n", -1, red)
            elif VEbusError == 25:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr(tr.fill("Error 25: Firmware incompatibility. "
                "The firmware of one of the connected device is not sufficiently up to date") + "\n", -1, red)
            elif VEbusError == 26:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr("Error 26: Internal error\n",90, red)
            else:
                stdscr.addnstr(" VE.Bus Error............ ", 90, ltblue)
                stdscr.addnstr(f"Error {VEbusError}: Unknown Description\n", -1, red)
            
            # errorindex += 1
            # if errorindex == len(error_nos):
                # errorindex = 0

# ===========================================================================================
#   ESS Info

            if ESS_Info.lower() == "y":


                if ESSbatteryLifeState >= 1 and ESSbatteryLifeState <= 8:
                    stdscr.addnstr(" ESS SOC Limit (User).... ",100, ltblue)
                    stdscr.addnstr("{:.0f}% Unless Grid Fails ".format(ESSsocLimitUser),100, ltblue)
                    stdscr.addnstr("(←) or (→) Arrows To Change Value \n",100, gray7)

                    # Requires Newer GX Firmware such as 2.82~4 or >
                    try:
                        ESSsocLimitDynamic = client.read_input_registers(2903, unit=VEsystemID)
                        decoder = BinaryPayloadDecoder.fromRegisters(ESSsocLimitDynamic.registers, byteorder=Endian.Big)
                        ESSsocLimitDynamic = decoder.decode_16bit_uint()
                        ESSsocLimitDynamic = ESSsocLimitDynamic / 10
                        stdscr.addnstr(" ESS SOC Limit (Dynamic). ",100, ltblue)
                        stdscr.addnstr("{:.0f}%\n".format(ESSsocLimitDynamic),100, ltblue)
                    except AttributeError:
                        stdscr.addnstr(" ESS SOC Limit (Dynamic). No Value, Firmware requires. Venus OS > v2.82~4\n",100, ltblue)

                    stdscr.addnstr(" ESS Mode ............... ",100, ltblue)
                    stdscr.addnstr("Optimized (With Battery Life)\n",100, ltblue)
                
                
                
                elif ESSbatteryLifeState == 9:
                    stdscr.addnstr(" ESS Mode................ ",100, ltblue)
                    stdscr.addnstr("Keep Batteries Charged Mode Enabled\n",100, ltblue)


                elif ESSbatteryLifeState >= 10 and ESSbatteryLifeState <= 12:
                    stdscr.addnstr(" ESS SOC Limit (User).... ",100, ltblue)
                    stdscr.addnstr("{:.0f}% Unless Grid Fails ".format(ESSsocLimitUser),100, ltblue)
                    stdscr.addnstr("(←) or (→) Arrows To Change Value \n",100, gray7)
                    stdscr.addnstr(" ESS Mode ............... ",100, ltblue)
                    stdscr.addnstr("Optimized (Without Battery Life)\n",100, ltblue)


                if ESSbatteryLifeState == 0:
                    ESSstate =" ESS Battery State....... Battery Life Disabled"
                elif ESSbatteryLifeState == 1:
                    ESSstate =" ESS Battery State....... Restarting"
                elif ESSbatteryLifeState == 2:
                    ESSstate =" ESS Battery State....... Self-consumption"
                elif ESSbatteryLifeState == 3:
                    ESSstate =" ESS Battery State....... Self consumption, SoC exceeds 85%"
                elif ESSbatteryLifeState == 4:
                    ESSstate =" ESS Battery State....... Self consumption, SoC at 100%"
                elif ESSbatteryLifeState == 5:
                    ESSstate =" ESS Battery State....... Discharge disabled. SoC below BatteryLife Dynamic SoC"
                elif ESSbatteryLifeState == 6:
                    ESSstate =" ESS Battery State....... SoC has been below SoC limit for more than 24 hours.\n\t\t\t  Slow Charging battery"
                elif ESSbatteryLifeState == 7:
                    ESSstate =" ESS Battery State....... Multi is in sustain mode"
                elif ESSbatteryLifeState == 8:
                    ESSstate =" ESS Battery State....... Recharge, SOC dropped 5% or more below MinSOC"
                #elif ESSbatteryLifeState == 9:
                #    ESSstate =" ESS Battery State....... Keep batteries charged mode enabled"
                elif ESSbatteryLifeState == 10:
                    ESSstate =" ESS Battery State....... Self consumption, SoC at or above minimum SoC"
                elif ESSbatteryLifeState == 11:
                    ESSstate =" ESS Battery State....... Discharge Disabled (Low SoC), SoC is below minimum SoC"
                elif ESSbatteryLifeState == 12:
                    ESSstate =" ESS Battery State....... Recharge, SOC dropped 5% or more below minimum"
                
                if ESSbatteryLifeState != 9:
                    stdscr.addnstr(f"{ESSstate}\n",110, ltblue)



# ===========================================================================================
#   Multiplus II status LED's

            if Multiplus_Leds.lower() == "y":

                spacer()

                stdscr.addnstr(f"{'': <22}{MultiName}{'': <20}\n",100, blue1)

                if Mains == 0:
                    stdscr.addnstr(f"{'': <10}Mains       ⚫{'': <20}",100, ltsalmon)
                elif Mains == 1:
                    stdscr.addnstr(f"{'': <10}Mains       🟢{'': <20}",100, ltsalmon)
                elif Mains == 2:
                    stdscr.addnstr(f"{'': <10}Mains       ",100, ltsalmon)
                    stdscr.addnstr(f"🟢{'': <20}",100, ltsalmon | curses.A_BLINK)

                if Inverter == 0:
                    stdscr.addnstr("Inverting    ⚫\n",100, ltsalmon)
                elif Inverter == 1:
                    stdscr.addnstr("Inverting    🟢\n",100, ltsalmon)
                elif Inverter == 2:
                    stdscr.addnstr("Inverting    ",100, ltsalmon)
                    stdscr.addnstr("🟢\n",100, ltsalmon | curses.A_BLINK)

                if Bulk == 0:
                    stdscr.addnstr(f"{'': <10}Bulk        ⚫{'': <20}",100, ltsalmon)
                elif Bulk == 1:
                    stdscr.addnstr(f"{'': <10}Bulk        🟡{'': <20}",100, ltsalmon)
                elif Bulk == 2:
                    stdscr.addnstr(f"{'': <10}Bulk        ",100, ltsalmon)
                    stdscr.addnstr(f"🟡{'': <20}",100, ltsalmon | curses.A_BLINK)

                if Overload == 0:
                    stdscr.addnstr("OverLoad     ⚫\n",100, ltsalmon)
                elif Overload == 1:
                    stdscr.addnstr("OverLoad     🔴\n",100, ltsalmon)
                elif Overload == 2:
                    stdscr.addnstr("OverLoad     ",100, ltsalmon)
                    stdscr.addnstr("🔴\n",100, ltsalmon | curses.A_BLINK)

                if Absorp == 0:
                    stdscr.addnstr(f"{'': <10}Absorption  ⚫{'': <20}",100, ltsalmon)
                elif Absorp == 1:
                    stdscr.addnstr(f"{'': <10}Absorption  🟡{'': <20}",100, ltsalmon)
                elif Absorp == 2:
                    stdscr.addnstr(f"{'': <10}Absorption  ",100, ltsalmon)
                    stdscr.addnstr(f"🟡{'': <20}",100, ltsalmon | curses.A_BLINK)

                if Lowbatt == 0:
                    stdscr.addnstr("Low Battery  ⚫\n",100, ltsalmon)
                elif Lowbatt == 1:
                    stdscr.addnstr("Low Battery  🔴\n",100, ltsalmon)
                elif Lowbatt == 2:
                    stdscr.addnstr("Low Battery  ",100, ltsalmon)
                    stdscr.addnstr("🔴\n",100, ltsalmon | curses.A_BLINK)

                if Floatchg == 0:
                    stdscr.addnstr(f"{'': <10}Float       ⚫{'': <20}",100, ltsalmon)
                elif Floatchg == 1:
                    stdscr.addnstr(f"{'': <10}Float       🔵{'': <20}",100, ltsalmon)
                elif Floatchg == 2:
                    stdscr.addnstr(f"{'': <10}Float       ",100, ltsalmon)
                    stdscr.addnstr(f"🔵{'': <20}",100, ltsalmon | curses.A_BLINK)

                if Temperature == 0:
                    stdscr.addnstr("Temperature  ⚫\n",100, ltsalmon)
                elif Temperature == 1:
                    stdscr.addnstr("Temperature  🔴\n",100, ltsalmon)
                elif Temperature == 2:
                    stdscr.addnstr("Temperature  ",100, ltsalmon)
                    stdscr.addnstr("🔴\n",100, ltsalmon | curses.A_BLINK)

                if MPswitch == 1:
                    MPswitch = "Charger Only"
                elif MPswitch == 2:
                    MPswitch = "Inverter Only"
                elif MPswitch == 3:
                    MPswitch = "ON"
                elif MPswitch == 4:
                    MPswitch = "OFF"

                stdscr.addnstr(f"{'': <20}Multiplus Switch is in the ",100, gray19)
                stdscr.addnstr(f"{MPswitch} ",100, orange)
                stdscr.addnstr(f"Position\n",100, gray19)
                spacer()
            else:
                spacer()


# ===========================================================================================
# Cerbo GX Analog Temperature Inputs
# Change the word's "Battery Box" "Cabin" "Outside" for each of the 3 sensor's you have
            Sens1 = "Battery Box"
            Sens2 = "Cabin"
            Sens3 = "Outside"

            if Analog_Inputs.lower() == "y":

                if TempSensor1 == 777:
                    stdscr.addnstr(" Temp Sensor............. Not installed or unit ID wrong\n",100, pink)
                elif TempSensor1 > 49 and TempSensor1 < 120 :
                    stdscr.addnstr(f" {Sens1} Temp........ {TempSensor1:.1f} °F ",100, pink)
                    stdscr.addnstr(" 🥵 Whew...its a tad warm in here\n",100, red)
                else:
                    stdscr.addnstr(f" {Sens1} Temp........ {TempSensor1:.1f} °F \n",100, pink)
                    
                if TempSensor2 == 777:
                    stdscr.addnstr(" Temp Sensor............. Not installed or unit ID wrong\n",100, pink)
                
                elif TempSensor2 < 45:
                    stdscr.addnstr(f" {Sens2} Temp.............. {TempSensor2:.1f} °F ",100, pink)
                    stdscr.addnstr(" 🥶 Whoa...Crank up the heat in this place!\n",100, blue1)
                else:
                    stdscr.addnstr(f" {Sens2} Temp.............. {TempSensor2:.1f} °F \n",100, pink)

                if TempSensor3 == 777:
                    stdscr.addnstr(" Temp Sensor............. Not installed or unit ID wrong\n",100, pink)
                
                elif TempSensor3 < 33:
                    stdscr.addnstr(f" {Sens3} Temp............ {TempSensor3:.1f} °F ",100, pink)
                    stdscr.addnstr(" 🥶 Burr...A Wee Bit Chilly Outside\n",100, blue1)
                else:
                    stdscr.addnstr(f" {Sens3} Temp............ {TempSensor3:.1f} °F \n",100, pink)
                    
                spacer()

# ===========================================================================================
# Key Press Detection

            stdscr.addnstr(f" M -- Multiplus LED's on/off",100, gray7)
            stdscr.addnstr(f"{'': <15}K -- Keep Batteries Charged\n",100, gray7)
            stdscr.addnstr(f" E -- ESS display on/off",100, gray7)
            stdscr.addnstr(f"{'': <19}B -- Battery Life Enabled\n",100, gray7)
            stdscr.addnstr(f" A -- Analog inputs Temperature on/off",100, gray7)
            stdscr.addnstr(f"{'': <5}D -- Battery Life Disabled\n",100, gray7)
            stdscr.addnstr(f" Q -- Quit \n✞",100, gray7)

            c = stdscr.getch() # also acts as refresh


            if ESS_Info.lower() == 'y':
                if c == curses.KEY_LEFT and ESSbatteryLifeState != 9:
                    # Decrease ESS SoC by 5W
                    client.write_registers(address=2901, values=int(ESSsocLimitUser) * 10 - 50, unit=VEsystemID)
                    continue
                elif c == curses.KEY_RIGHT and ESSbatteryLifeState != 9:
                    # Increase ESS SoC by 5W
                    client.write_registers(address=2901, values=int(ESSsocLimitUser) * 10 + 50, unit=VEsystemID)
                    continue

            if c == ord('q'):
                clean_exit()
# ============================================
# ESS, Multiplus LED's & Analog Inputs Display
            elif c == ord('e'):
                if ESS_Info.lower() == 'y':
                    ESS_Info = 'n'
                    continue
                else:
                    ESS_Info = 'y'
                    continue
            elif c == ord('m'):
                if Multiplus_Leds.lower() == 'y':
                    Multiplus_Leds = 'n'
                    continue
                else:
                    Multiplus_Leds = 'y'
                    continue
            elif c == ord('a'):
                if Analog_Inputs.lower() == 'y':
                    Analog_Inputs = 'n'
                    continue
                else:
                    Analog_Inputs = 'y'
                    continue
# ============================================
# Grid Set Point & Feed-in (for negative values we need BinaryPayloadBuilder)

            elif c == curses.KEY_UP: # Increase AC Grid set point by 10W
                builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
                builder.reset()
                builder.add_16bit_int(GridSetPoint + 10)
                payload = builder.to_registers()
                client.write_modbus_register(2700, payload[0])
                continue
                #else:
                #   client.write_registers(address=2700, values=GridSetPoint + 10, unit=VEsystemID)
                #continue
            elif c == curses.KEY_DOWN: # Decrease AC Grid set point by 10W
                builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
                builder.reset()
                builder.add_16bit_int(GridSetPoint - 10)
                payload = builder.to_registers()
                client.write_modbus_register(2700, payload[0])
                continue
                #else:    
                #    client.write_registers(address=2700, values=GridSetPoint - 10, unit=VEsystemID)
                #continue
            elif c == ord('['): # Turn grid feed-in on
                client.write_registers(address=2707, values=1, unit=VEsystemID)
                continue
            elif c == ord(']'): # Turn grid feed-in off
                client.write_registers(address=2707, values=0, unit=VEsystemID)
                continue
# ============================================
# Battery Life Modes
            elif c == ord('k') and ESS_Info.lower() == 'y':
                 # Mode 9 'Keep batteries charged' mode enabled
                client.write_registers(address=2900, values=9, unit=VEsystemID)
                continue
            elif c == ord('b') and ESS_Info.lower() == 'y':
                 # Mode 1  Change the ESS mode to "Optimized (BatteryLife Enabled)"
                client.write_registers(address=2900, values=1, unit=VEsystemID)
                continue
            elif c == ord('d') and ESS_Info.lower() == 'y':
                # Mode 10  Change the ESS mode to "Optimized (BatteryLife Disabled)"
                client.write_registers(address=2900, values=10, unit=VEsystemID)
                continue

# ============================================
# Adjust the screen when resizing with the mouse
            elif c == curses.KEY_RESIZE:
                #stdscr.clear()
                curses.resize_term(55, 90)
                stdscr.refresh()
                continue

            curses.flushinp()
# ^^^ End Key Press Detection
# ===========================================================================================


            if Multiplus_Leds.lower() == 'y' and RefreshRate == 1:
                time.sleep(1)
            else:
                time.sleep(RefreshRate)

        except curses.error:
            pass

        except AttributeError:
            pass

        except KeyboardInterrupt:
            clean_exit()

try:
    subprocess.call(['resize', '-s', '52', '85'])
except FileNotFoundError:
    pass

wrapper(main)
