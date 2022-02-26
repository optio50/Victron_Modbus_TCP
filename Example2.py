#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# This script depends on the following Victron equipment. BMV, Multiplus, Solar Charger, Venus GX device.
# Modbus & mqtt must be enabled in the Venus GX device
# You shouldnt have to change anything but some variables to make this work with your system
# provided you actually have the requsite victron equipment.

# Some items are simply not available via ModBusTCP and MQTT will be used to aqquire those values.


# The changeable variables:
# ip, VRMid, SolarChargerID, MQTT_SolarChargerID, MultiPlusID, MQTT_MultiPlusID, BmvID, MQTT_BmvID, VEsystemID
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

Analog_Inputs = 'n'     # Y or N (case insensitive) to display Gerbo GX Analog Temperature inputs
ESS_Info = 'n'          # Y or N (case insensitive) to display ESS system information
Multiplus_Leds = 'n'    # Y or N (case insensitive) to display Multiplus LED'S


# Unit ID #'s from Cerbo GX.
# Do not confuse UnitID with Instance ID.
# You can also get the UnitID from the GX device. Menu --> Settings --> Services --> ModBusTCP --> Available Services
# https://github.com/victronenergy/dbus_modbustcp/blob/master/CCGX-Modbus-TCP-register-list.xlsx Tab #2
#===================================
# ModBus Unit ID
SolarChargerID = 226
MultiPlusID = 227
BmvID = 223
VEsystemID = 100
#===================================
# MQTT Instance ID
# This is the Instance ID not to be confused with the above Unit ID.
# Device List in VRM or crossed referenced in the CCGX-Modbus-TCP-register-list.xlsx Tab #2
MQTT_SolarChargerID = 279
MQTT_MultiPlusID = 276
MQTT_BmvID = 277
MQTT_VEsystemID = 100
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
curses.init_color(0, 0, 0, 0)
curses.init_pair(100, 82, -1)  # Fluorescent Green
curses.init_pair(101, 93, -1)  # Purple
curses.init_pair(102, 2, -1)   # Green
curses.init_pair(103, 226, -1) # Yellow
curses.init_pair(104, 160, -1) # Red
curses.init_pair(105, 37, -1)  # Cyan
curses.init_pair(106, 202, -1) # Orange
curses.init_pair(107, 33, -1)  # Lt Blue
curses.init_pair(108, 21, -1)  # Blue1
curses.init_pair(109, 239, -1) # Gray
curses.init_pair(110, 197, -1) # Lt Pink
curses.init_pair(111, 201, -1) # Pink
curses.init_pair(112, 137, -1) # Lt Salmon
curses.init_pair(113, 234, -1) # Gray_7
curses.init_pair(114, 178, -1) # gold_3b
curses.init_pair(115, 236, -1) # gray_19
#=======================================================================
#=======================================================================
fgreen = curses.color_pair(100)
purple = curses.color_pair(101)
green = curses.color_pair(102)
yellow = curses.color_pair(103)
red = curses.color_pair(104)
cyan = curses.color_pair(105)
orange = curses.color_pair(106)
ltblue = curses.color_pair(107)
blue1 = curses.color_pair(108)
gray = curses.color_pair(109)
ltpink = curses.color_pair(110)
pink = curses.color_pair(111)
ltsalmon = curses.color_pair(112)
gray7 = curses.color_pair(113)
gold = curses.color_pair(114)
gray19 = curses.color_pair(115)






def spacer():
    stdscr.addnstr("═"*80 + "\n",100, gray)
    stdscr.clrtoeol()


def spacer2():
    stdscr.addnstr("—"*80 + "\n",100, gray)
    stdscr.clrtoeol()
    stdscr.clearok(1)


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

    errorindex = 0
    while True:
        screensize = os.get_terminal_size()
        stdscr.clear()

        try:
# ===========================================================================================
#   Conditional MQTT Request's because Multiplus II status LED's are not available with ModbusTCP

            if Multiplus_Leds.lower() == "y":

                msg = subscribe.simple("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlusID)+"/Leds/Mains", hostname=ip)
                data = json.loads(msg.payload)
                mains = data['value']

                msg = subscribe.simple("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlusID)+"/Leds/Inverter", hostname=ip)
                data = json.loads(msg.payload)
                inverter = data['value']

                msg = subscribe.simple("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlusID)+"/Leds/Bulk", hostname=ip)
                data = json.loads(msg.payload)
                bulk = data['value']

                msg = subscribe.simple("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlusID)+"/Leds/Overload", hostname=ip)
                data = json.loads(msg.payload)
                overload = data['value']

                msg = subscribe.simple("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlusID)+"/Leds/Absorption", hostname=ip)
                data = json.loads(msg.payload)
                absorp = data['value']

                msg = subscribe.simple("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlusID)+"/Leds/LowBattery", hostname=ip)
                data = json.loads(msg.payload)
                lowbatt = data['value']

                msg = subscribe.simple("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlusID)+"/Leds/Float", hostname=ip)
                data = json.loads(msg.payload)
                floatchg = data['value']

                msg = subscribe.simple("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlusID)+"/Leds/Temperature", hostname=ip)
                data = json.loads(msg.payload)
                temperature = data['value']

                # Switch Position on the Multiplus II
                MPswitch = client.read_input_registers(33, unit=MultiPlusID)
                decoder = BinaryPayloadDecoder.fromRegisters(MPswitch.registers, byteorder=Endian.Big)
                MPswitch = decoder.decode_16bit_uint()

# ===========================================================================================
#   Unconditional ModbusTCP Request's

#   Battery
            # MQTT LastDischarge, LastFullcharge
            msg = subscribe.simple("N/"+VRMid+"/battery/"+str(MQTT_BmvID)+"/History/LastDischarge", hostname=ip)
            data = json.loads(msg.payload)
            LastDischarge = data['value']

            msg = subscribe.simple("N/"+VRMid+"/battery/"+str(MQTT_BmvID)+"/History/TimeSinceLastFullCharge", hostname=ip)
            data = json.loads(msg.payload)
            LastFullcharge = data['value']

            msg = subscribe.simple("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlusID)+"/Dc/0/MaxChargeCurrent", hostname=ip)
            data = json.loads(msg.payload)
            MaxChargeCurrent = data['value']
            
            BatterySOC = client.read_input_registers(266, unit=BmvID)
            decoder = BinaryPayloadDecoder.fromRegisters(BatterySOC.registers, byteorder=Endian.Big)
            BatterySOC = decoder.decode_16bit_uint()
            BatterySOC = BatterySOC / 10

            BatteryWatts = client.read_input_registers(842, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(BatteryWatts.registers, byteorder=Endian.Big)
            BatteryWatts = decoder.decode_16bit_int()

            BatteryAmps = client.read_input_registers(841, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(BatteryAmps.registers, byteorder=Endian.Big)
            BatteryAmps = decoder.decode_16bit_int()
            BatteryAmps  = BatteryAmps / 10

            BatteryVolts = client.read_input_registers(259, unit=BmvID)
            decoder = BinaryPayloadDecoder.fromRegisters(BatteryVolts.registers, byteorder=Endian.Big)
            BatteryVolts = decoder.decode_16bit_uint()
            BatteryVolts = BatteryVolts / 100

            BatteryTTG = client.read_input_registers(846, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(BatteryTTG.registers, byteorder=Endian.Big)
            BatteryTTG = decoder.decode_16bit_uint()
            BatteryTTG = BatteryTTG / .01

            ChargeCycles = client.read_input_registers(284, unit=BmvID)
            decoder = BinaryPayloadDecoder.fromRegisters(ChargeCycles.registers, byteorder=Endian.Big)
            ChargeCycles = decoder.decode_16bit_uint()

            ChargePower = client.read_input_registers(855, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(ChargePower.registers, byteorder=Endian.Big)
            ChargePower = decoder.decode_16bit_uint()
            
            ConsumedAH = client.read_input_registers(845, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(ConsumedAH.registers, byteorder=Endian.Big)
            ConsumedAH = decoder.decode_16bit_uint()
            ConsumedAH = ConsumedAH / -10

# ===========================================================================================

#   Solar Charge Controller
            
            # MQTT, Couldnt find the equivalent ModBus register
            msg = subscribe.simple("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarChargerID)+"/Settings/ChargeCurrentLimit", hostname=ip)
            data = json.loads(msg.payload)
            SolarChargeLimit = data['value']
            
            SolarWatts = client.read_input_registers(789, unit=SolarChargerID)
            decoder = BinaryPayloadDecoder.fromRegisters(SolarWatts.registers, byteorder=Endian.Big)
            SolarWatts = decoder.decode_16bit_uint()
            SolarWatts = SolarWatts / 10

            # Broken register 777 in GX firmware 2.81
            try:
                SolarAmps = client.read_input_registers(777, unit=SolarChargerID)
                decoder = BinaryPayloadDecoder.fromRegisters(SolarAmps.registers, byteorder=Endian.Big)
                SolarAmps = decoder.decode_16bit_int()
                SolarAmps = SolarAmps / 10

            except AttributeError:
                SolarAmps = 'No Value, Firmware bug.'

            SolarVolts = client.read_input_registers(776, unit=SolarChargerID)
            decoder = BinaryPayloadDecoder.fromRegisters(SolarVolts.registers, byteorder=Endian.Big)
            SolarVolts = decoder.decode_16bit_uint()
            SolarVolts = SolarVolts / 100

            MaxSolarWatts = client.read_input_registers(785, unit=SolarChargerID)
            decoder = BinaryPayloadDecoder.fromRegisters(MaxSolarWatts.registers, byteorder=Endian.Big)
            MaxSolarWatts = decoder.decode_16bit_uint()

            MaxSolarWattsYest = client.read_input_registers(787, unit=SolarChargerID)
            decoder = BinaryPayloadDecoder.fromRegisters(MaxSolarWattsYest.registers, byteorder=Endian.Big)
            MaxSolarWattsYest = decoder.decode_16bit_uint()

            SolarYield = client.read_input_registers(784, unit=SolarChargerID)
            decoder = BinaryPayloadDecoder.fromRegisters(SolarYield.registers, byteorder=Endian.Big)
            SolarYield = decoder.decode_16bit_uint()
            SolarYield = SolarYield / 10
            
            SolarYieldYest = client.read_input_registers(786, unit=SolarChargerID)
            decoder = BinaryPayloadDecoder.fromRegisters(SolarYieldYest.registers, byteorder=Endian.Big)
            SolarYieldYest = decoder.decode_16bit_uint()
            SolarYieldYest = SolarYield / 10
            
            TotalSolarYield = client.read_input_registers(790, unit=SolarChargerID)
            decoder = BinaryPayloadDecoder.fromRegisters(TotalSolarYield.registers, byteorder=Endian.Big)
            TotalSolarYield = decoder.decode_16bit_uint()
            TotalSolarYield = TotalSolarYield / 10

            SolarState = client.read_input_registers(775, unit=SolarChargerID)
            decoder = BinaryPayloadDecoder.fromRegisters(SolarState.registers, byteorder=Endian.Big)
            SolarState = decoder.decode_16bit_uint()
            
            SolarError = client.read_input_registers(788, unit=SolarChargerID)
            decoder = BinaryPayloadDecoder.fromRegisters(SolarError.registers, byteorder=Endian.Big)
            SolarError = decoder.decode_16bit_uint()
            #SolarError = 20 # Test
            #error_nos = [0,1,2,3,4,5,6,7,8,9,17,18,19,20,22,23,33,34]
            #SolarError = error_nos[errorindex] # Display Test PV Error's
# ===========================================================================================

#   Grid Input & A/C out
            FeedIn = client.read_input_registers(2707, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(FeedIn.registers, byteorder=Endian.Big)
            FeedIn = decoder.decode_16bit_int()

            GridSetPoint = client.read_input_registers(2700, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(GridSetPoint.registers, byteorder=Endian.Big)
            GridSetPoint = decoder.decode_16bit_int()

            GridWatts = client.read_input_registers(820, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(GridWatts.registers, byteorder=Endian.Big)
            GridWatts = decoder.decode_16bit_int()

            GridAmps = client.read_input_registers(6, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(GridAmps.registers, byteorder=Endian.Big)
            GridAmps = decoder.decode_16bit_int()
            GridAmps = GridAmps / 10

            GridAmpLimit = client.read_input_registers(22, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(GridAmpLimit.registers, byteorder=Endian.Big)
            GridAmpLimit = decoder.decode_16bit_int()
            GridAmpLimit = GridAmpLimit / 10
            
            GridVolts = client.read_input_registers(3, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(GridVolts.registers, byteorder=Endian.Big)
            GridVolts = decoder.decode_16bit_int()
            GridVolts = GridVolts / 10

            GridHZ = client.read_input_registers(9, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(GridHZ.registers, byteorder=Endian.Big)
            GridHZ = decoder.decode_16bit_int()
            GridHZ = GridHZ / 100

            ACoutWatts = client.read_input_registers(817, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(ACoutWatts.registers, byteorder=Endian.Big)
            ACoutWatts = decoder.decode_16bit_uint()

            ACoutAmps = client.read_input_registers(18, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(ACoutAmps.registers, byteorder=Endian.Big)
            ACoutAmps = decoder.decode_16bit_int()
            ACoutAmps = ACoutAmps / 10

            ACoutVolts = client.read_input_registers(15, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(ACoutVolts.registers, byteorder=Endian.Big)
            ACoutVolts = decoder.decode_16bit_int()
            ACoutVolts = ACoutVolts / 10

            ACoutHZ = client.read_input_registers(21, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(ACoutHZ.registers, byteorder=Endian.Big)
            ACoutHZ = decoder.decode_16bit_int()
            ACoutHZ = ACoutHZ / 100

            GridCondition = client.read_input_registers(64, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(GridCondition.registers, byteorder=Endian.Big)
            GridCondition = decoder.decode_16bit_uint()
# ===========================================================================================

#   VEbus Status
            VEbusStatus = client.read_input_registers(31, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(VEbusStatus.registers, byteorder=Endian.Big)
            VEbusStatus = decoder.decode_16bit_uint()
# ===========================================================================================

#   VEbus Error
            VEbusError = client.read_input_registers(32, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(VEbusError.registers, byteorder=Endian.Big)
            VEbusError = decoder.decode_16bit_uint()
            #VEbusError = 55 # Test single error mesg
            #error_nos = [0,1,2,3,4,5,6,7,10,14,16,17,18,22,24,25,26]
            #VEbusError = error_nos[errorindex] # Multiple Test VEbusError's
# ===========================================================================================

# Conditional Modbus Request
# ESS Info
            if ESS_Info.lower() == "y":
                ESSbatteryLifeState = client.read_input_registers(2900, unit=VEsystemID)
                decoder = BinaryPayloadDecoder.fromRegisters(ESSbatteryLifeState.registers, byteorder=Endian.Big)
                ESSbatteryLifeState = decoder.decode_16bit_uint()

                ESSsocLimitUser = client.read_input_registers(2901, unit=VEsystemID)
                decoder = BinaryPayloadDecoder.fromRegisters(ESSsocLimitUser.registers, byteorder=Endian.Big)
                ESSsocLimitUser = decoder.decode_16bit_uint()
                ESSsocLimitUser_W = ESSsocLimitUser # Variable to be used in the on press function
                ESSsocLimitUser = ESSsocLimitUser / 10
# ===========================================================================================

# Conditional Modbus Request
# Analog Temperature Inputs
# Change the unit=Value to your correct value

            if Analog_Inputs.lower() == "y":
                try:
                    TempSensor1 = client.read_input_registers(3304, unit= 24) # Input 1
                    decoder = BinaryPayloadDecoder.fromRegisters(TempSensor1.registers, byteorder=Endian.Big)
                    TempSensor1 = decoder.decode_16bit_int()
                    TempSensor1 = TempSensor1 / 100 * 1.8 + 32
                except AttributeError:
                    TempSensor1 = 777
                
                try:
                    TempSensor2 = client.read_input_registers(3304, unit= 25) # Input 2
                    decoder = BinaryPayloadDecoder.fromRegisters(TempSensor2.registers, byteorder=Endian.Big)
                    TempSensor2 = decoder.decode_16bit_int()
                    TempSensor2 = TempSensor2 / 100 * 1.8 + 32
                except AttributeError:
                    TempSensor2 = 777
                
                try:
                    TempSensor3 = client.read_input_registers(3304, unit= 26) # Input 3
                    decoder = BinaryPayloadDecoder.fromRegisters(TempSensor3.registers, byteorder=Endian.Big)
                    TempSensor3 = decoder.decode_16bit_int()
                    TempSensor3 = TempSensor3 / 100 * 1.8 + 32
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


            stdscr.addnstr(f" Battery Watts........... {BatteryWatts} W",50, cyan)
            stdscr.addnstr(3,38,f"║ Last Discharge .......... {LastDischarge:.2f} AH\n",50, cyan)


            stdscr.addnstr(f" Battery Amps............ {BatteryAmps} A",50, cyan)
            stdscr.addnstr(4,38,f"║ Consumed AH ............. {ConsumedAH} AH\n",50, cyan)


            stdscr.addnstr(f" Battery Volts........... {BatteryVolts} V",50, cyan)
            stdscr.addnstr(5,38,f"║ Max Charge Current....... {MaxChargeCurrent} A\n",50, cyan)

            
            
            if BatteryTTG == 0.0:
                BatteryTTG = "Infinite"
            else:
                BatteryTTG = timedelta(seconds = BatteryTTG)
            
            LastFullcharge = timedelta(seconds = LastFullcharge)
            
            stdscr.addnstr(f" Battery Charge Cycles... {ChargeCycles}",50, cyan)
            stdscr.addnstr(6,38,f"║ Last Full Charge......... {LastFullcharge} \n",50, cyan)

            stdscr.addnstr(f" Battery Time to Go...... {BatteryTTG}\n",50, cyan)
            
            
            
            spacer()

# ===========================================================================================
#   Solar Charge Controller

            #SolarWatts = random.randrange(0, 400, 10) # Test Progressbar
            if SolarVolts < 10:
                stdscr.addstr(f" PV Watts ............... {SolarWatts:.0f}", orange)
                stdscr.addstr(9,39,f"🌛\n", orange)
                
            ###################################
            ###         400W array          ###
            ###################################
            elif SolarWatts >= 50 and SolarWatts < 100:
                stdscr.addstr(f" PV Watts ............... {SolarWatts:.0f}", orange)
                stdscr.addstr(9,39,f"🌞\n", orange)
            elif SolarWatts >= 100 and SolarWatts < 200:
                stdscr.addstr(f" PV Watts ............... {SolarWatts:.0f}", orange)
                stdscr.addstr(9,39,f"🌞   🌞\n", orange)
            elif SolarWatts >= 200 and SolarWatts < 300:
                stdscr.addstr(f" PV Watts ............... {SolarWatts:.0f}", orange)
                stdscr.addstr(9,39,f"🌞   🌞   🌞\n", orange)
            elif SolarWatts >= 300 and SolarWatts < 350:
                stdscr.addstr(f" PV Watts ............... {SolarWatts:.0f}", orange)
                stdscr.addstr(9,39,f"🌞   🌞   🌞   🌞\n", orange)
            elif SolarWatts >= 350:
                stdscr.addstr(f" PV Watts ............... {SolarWatts:.0f}", orange)
                stdscr.addstr(9,39,f"🌞   🌞   🌞   🌞   🌞\n", orange)
            elif SolarWatts < 50:
                stdscr.addstr(f" PV Watts ............... {SolarWatts:.0f}", orange)
                stdscr.addstr(9,39,f"⛅\n", orange)
            


            stdscr.addnstr(" PV Amps................. ",100, orange)
            if SolarAmps == 'No Value, Firmware bug.':
                stdscr.addnstr("No Value, Firmware bug. Update GX Firmware >= 2.84\n",100, red)
            else:
                stdscr.addnstr("{:.1f}\n".format(SolarAmps),100, orange)

            
            stdscr.addnstr(f" PV Volts................ {SolarVolts:.2f}",100, orange)
            stdscr.addnstr(11,38,f"║ PV Charge Limit............. {SolarChargeLimit}  A\n",100, orange)
            
            stdscr.addnstr(f" Max PV Watts Today...... {MaxSolarWatts:.0f}",100, orange)
            stdscr.addnstr(12,38,f"║ PV Yield Today.............. {SolarYield:.3f} kWh\n",100, orange)

            stdscr.addnstr(f" Max PV Watts Yesterday.. {MaxSolarWattsYest}",50, orange)
            stdscr.addnstr(13,38,f"║ PV Yield Yesterday.......... {SolarYieldYest:.3f} kWh\n",100, orange)

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

            stdscr.addnstr(14,38,f"║ Total PV Yield Since Reset.. {TotalSolarYield:.3f} kWh\n",100, orange)
            
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
                stdscr.addnstr("YES",90, green)
                stdscr.addnstr(17,47,"[  or  ] Brackets To Change Value\n",100, gray7)
            else:
                stdscr.addnstr("NO ",90, red)
                stdscr.addnstr(17,47,"[  or  ] Brackets To Change Value\n",100, gray7)
            
            stdscr.addnstr(" Grid Set Point Watts.... ",100, green)
            stdscr.addnstr("{:.0f} ".format(GridSetPoint),100, green)
            stdscr.addnstr(18,47,"(↑) or (↓) Arrows To Change Value\n",100, gray7)
            stdscr.addnstr(" Grid Watts.............. ",100, green)
            if GridWatts < 0 and FeedIn == 1:
                stdscr.addnstr("{:.0f} ".format(GridWatts),100, green)
                stdscr.addnstr(19,39,"<<<< Feeding Into Grid $$$\n", 90,purple)
            else:
                stdscr.addnstr("{:.0f} \n".format(GridWatts),100, green)

            stdscr.addnstr(" Grid Amps............... ",100, green)
            stdscr.addnstr("{:.1f}".format(GridAmps),100, green)
            stdscr.addnstr(20,38,f"║ Grid Amps Current Limit..... {GridAmpLimit} A\n",100, green)
            #stdscr.move(22,0)
            
            stdscr.addnstr(" Grid Volts ............. ",100, green)
            stdscr.addnstr("{:.1f} ".format(GridVolts),100, green)
            
            if GridCondition == 0:
                stdscr.addstr(21,38,f"║ Grid Condition.............. OK \n", green)
                
            elif GridCondition == 2:
                
                stdscr.addstr(21,38,f"║ Grid Condition ............. ", green)
                stdscr.addstr("Grid LOST!\n", red | curses.A_BLINK)
            
            
            stdscr.addnstr(" Grid Freq .............. ",100, green)
            stdscr.addnstr("{:.1f} \n".format(GridHZ),100, green)

            stdscr.addnstr(" AC Output Watts......... ",100, green)
            stdscr.addnstr("{:.0f} \n".format(ACoutWatts),100, green)

            stdscr.addnstr(" AC Output Amps.......... ",100, green)
            stdscr.addnstr("{:.1f} \n".format(ACoutAmps),100, green)

            stdscr.addnstr(" AC Output Volts......... ",100, green)
            stdscr.addnstr("{:.1f} \n".format(ACoutVolts),100, green)


            stdscr.addnstr(" AC Output Freq.......... ",100, green)
            stdscr.addnstr("{:.1f} \n".format(ACoutHZ),100, green)


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
            elif VEbusStatus == 11:
                stdscr.addnstr(" System State............ Power Supply\n",100, ltblue)
            elif VEbusStatus == 252:
                stdscr.addnstr(" System State............ Bulk Protection\n",100, ltblue)
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
                    stdscr.addnstr(" ESS Mode ............... ",100, ltblue)
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

                stdscr.addnstr(f"{'': <24}Victron Multiplus II{'': <20}\n",100, blue1)

                if mains == 0:
                    stdscr.addnstr(f"{'': <10}Mains       ⚫{'': <20}",100, ltsalmon)
                elif mains == 1:
                    stdscr.addnstr(f"{'': <10}Mains       🟢{'': <20}",100, ltsalmon)
                elif mains == 2:
                    stdscr.addnstr(f"{'': <10}Mains       ",100, ltsalmon)
                    stdscr.addnstr(f"🟢{'': <20}",100, ltsalmon | curses.A_BLINK)

                if inverter == 0:
                    stdscr.addnstr("Inverting    ⚫\n",100, ltsalmon)
                elif inverter == 1:
                    stdscr.addnstr("Inverting    🟢\n",100, ltsalmon)
                elif inverter == 2:
                    stdscr.addnstr("Inverting    ",100, ltsalmon)
                    stdscr.addnstr("🟢\n",100, ltsalmon | curses.A_BLINK)

                if bulk == 0:
                    stdscr.addnstr(f"{'': <10}Bulk        ⚫{'': <20}",100, ltsalmon)
                elif bulk == 1:
                    stdscr.addnstr(f"{'': <10}Bulk        🟡{'': <20}",100, ltsalmon)
                elif bulk == 2:
                    stdscr.addnstr(f"{'': <10}Bulk        ",100, ltsalmon)
                    stdscr.addnstr(f"🟡{'': <20}",100, ltsalmon | curses.A_BLINK)

                if overload == 0:
                    stdscr.addnstr("OverLoad     ⚫\n",100, ltsalmon)
                elif overload == 1:
                    stdscr.addnstr("OverLoad     🔴\n",100, ltsalmon)
                elif overload == 2:
                    stdscr.addnstr("OverLoad     ",100, ltsalmon)
                    stdscr.addnstr("🔴\n",100, ltsalmon | curses.A_BLINK)

                if absorp == 0:
                    stdscr.addnstr(f"{'': <10}Absorption  ⚫{'': <20}",100, ltsalmon)
                elif absorp == 1:
                    stdscr.addnstr(f"{'': <10}Absorption  🟡{'': <20}",100, ltsalmon)
                elif absorp == 2:
                    stdscr.addnstr(f"{'': <10}Absorption  ",100, ltsalmon)
                    stdscr.addnstr(f"🟡{'': <20}",100, ltsalmon | curses.A_BLINK)

                if lowbatt == 0:
                    stdscr.addnstr("Low Battery  ⚫\n",100, ltsalmon)
                elif lowbatt == 1:
                    stdscr.addnstr("Low Battery  🔴\n",100, ltsalmon)
                elif lowbatt == 2:
                    stdscr.addnstr("Low Battery  ",100, ltsalmon)
                    stdscr.addnstr("🔴\n",100, ltsalmon | curses.A_BLINK)

                if floatchg == 0:
                    stdscr.addnstr(f"{'': <10}Float       ⚫{'': <20}",100, ltsalmon)
                elif floatchg == 1:
                    stdscr.addnstr(f"{'': <10}Float       🔵{'': <20}",100, ltsalmon)
                elif floatchg == 2:
                    stdscr.addnstr(f"{'': <10}Float       ",100, ltsalmon)
                    stdscr.addnstr(f"🔵{'': <20}",100, ltsalmon | curses.A_BLINK)

                if temperature == 0:
                    stdscr.addnstr("Temperature  ⚫\n",100, ltsalmon)
                elif temperature == 1:
                    stdscr.addnstr("Temperature  🔴\n",100, ltsalmon)
                elif temperature == 2:
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
                elif TempSensor1 > 49 and TempSensor1 < 200 :
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

            stdscr.addnstr(" M -- Multiplus LED's on/off",100, gray7)
            stdscr.addnstr(f"{'': <15}K -- Keep Batteries Charged\n",100, gray7)
            stdscr.addnstr(" E -- ESS display on/off",100, gray7)
            stdscr.addnstr(f"{'': <19}B -- Battery Life Enabled\n",100, gray7)
            stdscr.addnstr(" A -- Analog inputs Temperature on/off",100, gray7)
            stdscr.addnstr(f"{'': <5}D -- Battery Life Disabled\n",100, gray7)
            stdscr.addnstr(" Q -- Quit \n✞",100, gray7)

            c = stdscr.getch()


            if ESS_Info.lower() == 'y':
                if c == curses.KEY_LEFT and ESSbatteryLifeState != 9:
                    # Decrease ESS SoC by 5W
                    client.write_registers(address=2901, values=ESSsocLimitUser_W - 50, unit=VEsystemID)
                    continue
                elif c == curses.KEY_RIGHT and ESSbatteryLifeState != 9:
                    # Increase ESS SoC by 5W
                    client.write_registers(address=2901, values=ESSsocLimitUser_W + 50, unit=VEsystemID)
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
                client.write_register(2700, payload[0])
                continue
                #else:
                #   client.write_registers(address=2700, values=GridSetPoint + 10, unit=VEsystemID)
                #continue
            elif c == curses.KEY_DOWN: # Decrease AC Grid set point by 10W
                builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
                builder.reset()
                builder.add_16bit_int(GridSetPoint - 10)
                payload = builder.to_registers()
                client.write_register(2700, payload[0])
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
                # #curses.initscr()

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
