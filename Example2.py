#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Modbus & mqtt must be enabled in the Venus GX device


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
################
import argparse
import struct
from pymodbus.client.sync import ModbusTcpClient
################
from datetime import datetime
from datetime import timedelta
import sys
import os
import time
from time import strftime
from time import gmtime
import signal


RefreshRate = 1      # Refresh Rate in seconds. Auto increased to 1.5 (from 1 second) if LED's enabled For MQTT requests

# GX Device I.P Address
ip = '192.168.20.156'

# VRM Portal ID from GX device. Not needed if Multiplus LEDS are not enabled
# Menu -->> settings -->> "VRM Online Portal -->> VRM Portal ID"
VRMid = "d41243d31a90"

# Instance #'s from Cerbo GX and cross referenced to the unit ID in the Victron TCP-MODbus register xls file Tab #2.
# https://github.com/victronenergy/dbus_modbustcp/blob/master/CCGX-Modbus-TCP-register-list.xlsx
SolarChargerID = 226
MultiPlusID = 227
BmvID = 223
VEsystemID = 100


# Local network ip address of Cerbo GX. Default port 502
client = ModbusClient(ip, port='502')

Defaults.Timeout = 25
Defaults.Retries = 5

stdscr = curses.initscr()
stdscr.nodelay(True)


# Pathetic Progressbar :-)
Pbar0  = " ║▒░░░░░░░░░░░░░░░░░░░║"
Pbar10 = " ║▒▒░░░░░░░░░░░░░░░░░░║"
Pbar20 = " ║▒▒▒▒░░░░░░░░░░░░░░░░║"
Pbar30 = " ║▒▒▒▒▒▒░░░░░░░░░░░░░░║"
Pbar40 = " ║▒▒▒▒▒▒▒▒░░░░░░░░░░░░║"
Pbar50 = " ║▒▒▒▒▒▒▒▒▒▒░░░░░░░░░░║"
Pbar60 = " ║▒▒▒▒▒▒▒▒▒▒▒▒░░░░░░░░║"
Pbar70 = " ║▒▒▒▒▒▒▒▒▒▒▒▒▒▒░░░░░░║"
Pbar80 = " ║▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒░░░░║"
Pbar90 = " ║▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒░░║"
Pbar100 =" ║▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒║"


#
# Find More Color Numbers and Names Here.
# https://github.com/optio50/PythonColors/blob/main/color-test.py
if curses.can_change_color():
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
    curses.init_pair(108, 21, -1)  # Blue
    curses.init_pair(109, 239, -1) # Gray
    curses.init_pair(113, 233, -1) # Gray2
    curses.init_pair(110, 197, -1) # Lt Pink
    curses.init_pair(111, 201, -1) # Pink
    curses.init_pair(112, 137, -1) # Lt Salmon
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
    blue = curses.color_pair(108)
    gray = curses.color_pair(109)
    ltpink = curses.color_pair(110)
    pink = curses.color_pair(111)
    ltsalmon = curses.color_pair(112)
    gray2 = curses.color_pair(113)





def spacer():
    stdscr.addstr("="*80 + "\n",gray)


def clean_exit():
    curses.curs_set(True)
    curses.nocbreak()
    stdscr.keypad(False)
    curses.echo()
    curses.endwin()
    curses.flushinp()
    sys.exit(0)


def main(stdscr):
        
    stdscr.nodelay(True)
    
    Analog_Inputs = 'y'  # Y or N (case insensitive) to display Gerbo GX Analog Temperature inputs
    ESS_Info = 'y' # Y or N (case insensitive) to display ESS system information
    Multiplus_Leds = 'y' # Y or N (case insensitive) to display Multiplus LED'S

    while True:
        
        
        stdscr.clear()
        

        if Multiplus_Leds == "Y" or Multiplus_Leds == "y":

            msg = subscribe.simple("N/"+VRMid+"/vebus/276/Leds/Mains", hostname=ip)
            data = json.loads(msg.payload)
            mains = data['value']

            msg = subscribe.simple("N/"+VRMid+"/vebus/276/Leds/Inverter", hostname=ip)
            data = json.loads(msg.payload)
            inverter = data['value']

            msg = subscribe.simple("N/"+VRMid+"/vebus/276/Leds/Bulk", hostname=ip)
            data = json.loads(msg.payload)
            bulk = data['value']

            msg = subscribe.simple("N/"+VRMid+"/vebus/276/Leds/Overload", hostname=ip)
            data = json.loads(msg.payload)
            overload = data['value']

            msg = subscribe.simple("N/"+VRMid+"/vebus/276/Leds/Absorption", hostname=ip)
            data = json.loads(msg.payload)
            absorp = data['value']

            msg = subscribe.simple("N/"+VRMid+"/vebus/276/Leds/LowBattery", hostname=ip)
            data = json.loads(msg.payload)
            lowbatt = data['value']

            msg = subscribe.simple("N/"+VRMid+"/vebus/276/Leds/Float", hostname=ip)
            data = json.loads(msg.payload)
            floatchg = data['value']

            msg = subscribe.simple("N/"+VRMid+"/vebus/276/Leds/Temperature", hostname=ip)
            data = json.loads(msg.payload)
            temperature = data['value']

        try:

            # Datetime object containing current date and time
            now = datetime.now()

            # Fri 21 Jan 2022 09:06:57 PM
            dt_string = now.strftime("%a %d %b %Y %r")
            try:
                stdscr.addstr("\n Time & Date............. ",purple)
                stdscr.addstr(dt_string + "\n",purple)
            except curses.error:
                pass

            BatterySOC = client.read_input_registers(266, unit=BmvID)
            decoder = BinaryPayloadDecoder.fromRegisters(BatterySOC.registers, byteorder=Endian.Big)
            BatterySOC = decoder.decode_16bit_uint()
            BatterySOC = BatterySOC / 10
            #BatterySOC = 9

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
            if BatterySOC >= 10:
                stdscr.addstr(" Battery SOC............. ",cyan)
                stdscr.addstr("{:.1f}% ".format(BatterySOC),color | curses.A_BOLD)
                stdscr.addstr("🔋" + BpBar + "\n",color)
            else:
                stdscr.addstr(" Battery SOC............. ",cyan)
                stdscr.addstr("{:.1f}% ".format(BatterySOC),color | curses.A_BLINK)
                stdscr.addstr("🔋" + BpBar + "\n",color)


            BatteryWatts = client.read_input_registers(842, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(BatteryWatts.registers, byteorder=Endian.Big)
            BatteryWatts = decoder.decode_16bit_int()
            stdscr.addstr(" Battery Watts........... ",cyan)
            stdscr.addstr(str(BatteryWatts) + "\n",cyan)

            BatteryAmps = client.read_input_registers(841, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(BatteryAmps.registers, byteorder=Endian.Big)
            BatteryAmps = decoder.decode_16bit_int()
            BatteryAmps  = BatteryAmps / 10
            stdscr.addstr(" Battery Amps............ ",cyan)
            stdscr.addstr(str(BatteryAmps) + "\n",cyan)

            BatteryVolts = client.read_input_registers(259, unit=BmvID)
            decoder = BinaryPayloadDecoder.fromRegisters(BatteryVolts.registers, byteorder=Endian.Big)
            BatteryVolts = decoder.decode_16bit_uint()
            BatteryVolts = BatteryVolts / 100
            stdscr.addstr(" Battery Volts........... ",cyan)
            stdscr.addstr(str(BatteryVolts) + "\n",cyan)

            BatteryTTG = client.read_input_registers(846, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(BatteryTTG.registers, byteorder=Endian.Big)
            BatteryTTG = decoder.decode_16bit_uint()
            BatteryTTG = BatteryTTG / .01
            if BatteryTTG == 0.0:
                BatteryTTG = "Infinite"
            else:
                BatteryTTG = timedelta(seconds = BatteryTTG)
            stdscr.addstr(" Battery Time to Go...... ",cyan)
            stdscr.addstr(str(BatteryTTG) + "\n",cyan)

            spacer()

            SolarVolts = client.read_input_registers(776, unit=SolarChargerID)
            decoder = BinaryPayloadDecoder.fromRegisters(SolarVolts.registers, byteorder=Endian.Big)
            SolarVolts = decoder.decode_16bit_uint()
            SolarVolts = SolarVolts / 100
            if SolarVolts <= 10:
                SVpBar = Pbar0
            elif SolarVolts > 10 and SolarVolts <= 20:
                SVpBar = Pbar10
            elif SolarVolts > 20 and SolarVolts <= 30:
                SVpBar = Pbar20
            elif SolarVolts > 30 and SolarVolts <= 40:
                SVpBar = Pbar30
            elif SolarVolts > 40 and SolarVolts <= 50:
                SVpBar = Pbar40
            elif SolarVolts > 50 and SolarVolts <= 60:
                SVpBar = Pbar50
            elif SolarVolts > 60 and SolarVolts <= 70:
                SVpBar = Pbar60
            elif SolarVolts > 70 and SolarVolts <= 80:
                SVpBar = Pbar70
            elif SolarVolts > 80 and SolarVolts <= 90:
                SVpBar = Pbar80
            elif SolarVolts > 90:
                SVpBar = Pbar100
            stdscr.addstr(" PV Volts................ ",orange)
            stdscr.addstr("{:.2f}".format(SolarVolts) + SVpBar + "\n",orange)

            # Broken register 777 in GX firmware 2.81
            try:
                SolarAmps = client.read_input_registers(777, unit=SolarChargerID)
                decoder = BinaryPayloadDecoder.fromRegisters(SolarAmps.registers, byteorder=Endian.Big)
                SolarAmps = decoder.decode_16bit_int()
                SolarAmps = SolarAmps / 10
                stdscr.addstr(" PV Amps................. ",orange)
                stdscr.addstr("{:.2f}\n".format(SolarAmps),orange)

            except AttributeError:
                stdscr.addstr(" PV Amps................. No Value, Firmware bug.  Venus OS > v2.82~4 or <= 2.73 Required",orange)

            SolarWatts = client.read_input_registers(789, unit=SolarChargerID)
            decoder = BinaryPayloadDecoder.fromRegisters(SolarWatts.registers, byteorder=Endian.Big)
            SolarWatts = decoder.decode_16bit_uint()
            SolarWatts = SolarWatts / 10
            if SolarVolts < 15:
                stdscr.addstr(" PV Watts ............... ",orange)
                stdscr.addstr("{:.0f} 🌛\n".format(SolarWatts),orange)

            ###################################
            ###         400W array          ###
            ###################################
            elif SolarWatts >= 50 and SolarWatts < 100:
                stdscr.addstr(" PV Watts ............... ",orange)
                stdscr.addstr("{:.0f}   ║🌞░░░░░░░░░░░░░░░░║\n".format(SolarWatts),orange)
            elif SolarWatts >= 100 and SolarWatts < 200:
                stdscr.addstr(" PV Watts ............... ",orange)
                stdscr.addstr("{:.0f}   ║🌞  🌞░░░░░░░░░░░░║\n".format(SolarWatts),orange)
            elif SolarWatts >= 200 and SolarWatts < 300:
                stdscr.addstr(" PV Watts ............... ",orange)
                stdscr.addstr("{:.0f}   ║🌞  🌞  🌞░░░░░░░░║\n".format(SolarWatts),orange)
            elif SolarWatts >= 300 and SolarWatts < 350:
                stdscr.addstr(" PV Watts ............... ",orange)
                stdscr.addstr("{:.0f}   ║🌞  🌞  🌞  🌞░░░░║\n".format(SolarWatts),orange)
            elif SolarWatts >= 350:
                stdscr.addstr(" PV Watts ............... ",orange)
                stdscr.addstr("{:.0f}   ║🌞  🌞  🌞  🌞  🌞║\n".format(SolarWatts),orange)
            else:
                stdscr.addstr(" PV Watts ............... ",orange)
                stdscr.addstr("{:.0f}   ║⛅░░░░░░░░░░░░░░░░║\n".format(SolarWatts),orange)

            MaxSolarWatts = client.read_input_registers(785, unit=SolarChargerID)
            decoder = BinaryPayloadDecoder.fromRegisters(MaxSolarWatts.registers, byteorder=Endian.Big)
            MaxSolarWatts = decoder.decode_16bit_uint()
            stdscr.addstr(" Max PV Watts Today...... ",orange)
            stdscr.addstr("{:.0f} \n".format(MaxSolarWatts),orange)

            SolarYield = client.read_input_registers(784, unit=SolarChargerID)
            decoder = BinaryPayloadDecoder.fromRegisters(SolarYield.registers, byteorder=Endian.Big)
            SolarYield = decoder.decode_16bit_int()
            SolarYield = SolarYield / 10
            stdscr.addstr(" PV Yield Today.......... ",orange)
            stdscr.addstr("{:.3f} kWh \n".format(SolarYield),orange)

            SolarState = client.read_input_registers(775, unit=SolarChargerID)
            decoder = BinaryPayloadDecoder.fromRegisters(SolarState.registers, byteorder=Endian.Big)
            SolarState = decoder.decode_16bit_int()
            if SolarState == 0:
                stdscr.addstr(" PV Charger State........ OFF \n",orange)
            elif SolarState == 2:
                stdscr.addstr(" PV Charger State........ Fault\n",orange)
            elif SolarState == 3:
                stdscr.addstr(" PV Charger State........ Bulk\n",orange)
            elif SolarState == 4:
                stdscr.addstr(" PV Charger State........ Absorption\n",orange)
            elif SolarState == 5:
                stdscr.addstr(" PV Charger State........ Float\n",orange)
            elif SolarState == 6:
                stdscr.addstr(" PV Charger State........ Storage\n",orange)
            elif SolarState == 7:
                stdscr.addstr(" PV Charger State........ Equalize\n",orange)
            elif SolarState == 11:
                stdscr.addstr(" PV Charger State........ Other (Hub-1)\n",orange)
            elif SolarState == 252:
                stdscr.addstr(" PV Charger State........ EXT Control\n",orange)

            spacer()

            GridSetPoint = client.read_input_registers(2700, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(GridSetPoint.registers, byteorder=Endian.Big)
            GridSetPoint = decoder.decode_16bit_int()
            stdscr.addstr(" Grid Set Point Watts.... ",green)
            stdscr.addstr("{:.0f} \n".format(GridSetPoint),green)

            GridWatts = client.read_input_registers(820, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(GridWatts.registers, byteorder=Endian.Big)
            GridWatts = decoder.decode_16bit_int()
            stdscr.addstr(" Grid Watts.............. ",green)
            if GridWatts < 0:
                stdscr.addstr("{:.0f} ".format(GridWatts),green)
                stdscr.addstr("Feeding Into Grid \n",red)
            else:
                stdscr.addstr("{:.0f} \n".format(GridWatts),green)

            GridAmps = client.read_input_registers(6, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(GridAmps.registers, byteorder=Endian.Big)
            GridAmps = decoder.decode_16bit_int()
            GridAmps = GridAmps / 10
            stdscr.addstr(" Grid Amps............... ",green)
            stdscr.addstr("{:.1f} \n".format(GridAmps),green)

            GridVolts = client.read_input_registers(3, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(GridVolts.registers, byteorder=Endian.Big)
            GridVolts = decoder.decode_16bit_int()
            GridVolts = GridVolts / 10
            stdscr.addstr(" Grid Volts ............. ",green)
            stdscr.addstr("{:.1f} \n".format(GridVolts),green)

            GridHZ = client.read_input_registers(9, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(GridHZ.registers, byteorder=Endian.Big)
            GridHZ = decoder.decode_16bit_int()
            GridHZ = GridHZ / 100
            stdscr.addstr(" Grid Freq .............. ",green)
            stdscr.addstr("{:.1f} \n".format(GridHZ),green)

            ACoutWatts = client.read_input_registers(817, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(ACoutWatts.registers, byteorder=Endian.Big)
            ACoutWatts = decoder.decode_16bit_uint()
            stdscr.addstr(" AC Output Watts......... ",green)
            stdscr.addstr("{:.0f} \n".format(ACoutWatts),green)

            ACoutAmps = client.read_input_registers(18, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(ACoutAmps.registers, byteorder=Endian.Big)
            ACoutAmps = decoder.decode_16bit_int()
            ACoutAmps = ACoutAmps / 10
            stdscr.addstr(" AC Output Amps.......... ",green)
            stdscr.addstr("{:.1f} \n".format(ACoutAmps),green)

            ACoutVolts = client.read_input_registers(15, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(ACoutVolts.registers, byteorder=Endian.Big)
            ACoutVolts = decoder.decode_16bit_int()
            ACoutVolts = ACoutVolts / 10
            stdscr.addstr(" AC Output Volts......... ",green)
            stdscr.addstr("{:.1f} \n".format(ACoutVolts),green)

            ACoutHZ = client.read_input_registers(21, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(ACoutHZ.registers, byteorder=Endian.Big)
            ACoutHZ = decoder.decode_16bit_int()
            ACoutHZ = ACoutHZ / 100
            stdscr.addstr(" AC Output Freq.......... ",green)
            stdscr.addstr("{:.1f} \n".format(ACoutHZ),green)

            GridCondition = client.read_input_registers(64, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(GridCondition.registers, byteorder=Endian.Big)
            GridCondition = decoder.decode_16bit_uint()
            if GridCondition == 0:
                stdscr.addstr(" Grid Condition.......... OK 🆗\n",green)
            elif GridCondition == 1:
                stdscr.addstr(" Grid Condition ......... Grid LOST ❌\n",green | curses.A_BLINK)

            spacer()

            VEbusStatus = client.read_input_registers(31, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(VEbusStatus.registers, byteorder=Endian.Big)
            VEbusStatus = decoder.decode_16bit_uint()
            if VEbusStatus == 3:
                stdscr.addstr(" System State............ Bulk Charging\n",ltblue)
            elif VEbusStatus == 4:
                stdscr.addstr(" System State............ Absorption Charging\n",ltblue)
            elif VEbusStatus == 5:
                stdscr.addstr(" System State............ Float Charging\n",ltblue)

            if ESS_Info == "Y" or ESS_Info == "y":
                ESSsocLimitUser = client.read_input_registers(2901, unit=VEsystemID)
                decoder = BinaryPayloadDecoder.fromRegisters(ESSsocLimitUser.registers, byteorder=Endian.Big)
                ESSsocLimitUser = decoder.decode_16bit_uint()
                ESSsocLimitUser_W = ESSsocLimitUser # Global variable to be used in the on press function
                ESSsocLimitUser = ESSsocLimitUser / 10
                stdscr.addstr(" ESS SOC Limit (User).... ",ltblue)
                stdscr.addstr("{:.0f}% - Unless Grid Fails  ".format(ESSsocLimitUser),ltblue)
                stdscr.addstr("[ and ] To Change Value \n",fgreen) 
                #stdscr.addstr(str(ESSsocLimitUser_P)+"\n",pink)
                #stdscr.addstr(str(ESSsocLimitUser_M)+"\n",pink)
                
               # Requires Newer GX Firmware such as 2.82~4 or >
                try:
                    ESSsocLimitDynamic = client.read_input_registers(2903, unit=VEsystemID)
                    decoder = BinaryPayloadDecoder.fromRegisters(ESSsocLimitDynamic.registers, byteorder=Endian.Big)
                    ESSsocLimitDynamic = decoder.decode_16bit_uint()
                    ESSsocLimitDynamic = ESSsocLimitDynamic / 10
                    stdscr.addstr(" ESS SOC Limit (Dynamic). ",ltblue)
                    stdscr.addstr("{:.0f}%\n".format(ESSsocLimitDynamic),ltblue)

                except AttributeError:
                    stdscr.addstr(" ESS SOC Limit (Dynamic). No Value, Firmware requires. Venus OS > v2.82~4",ltblue)

                ESSbatteryLifeState = client.read_input_registers(2900, unit=VEsystemID)
                decoder = BinaryPayloadDecoder.fromRegisters(ESSbatteryLifeState.registers, byteorder=Endian.Big)
                ESSbatteryLifeState = decoder.decode_16bit_uint()
                if ESSbatteryLifeState == 0:
                    stdscr.addstr(" ESS Battery Life State.. Battery Life Disabled\n",ltblue)
                elif ESSbatteryLifeState == 1:
                    stdscr.addstr(" ESS Battery Life State.. Restarting\n",ltblue)
                elif ESSbatteryLifeState == 2:
                    stdscr.addstr(" ESS Battery Life State.. Self-consumption\n",ltblue)
                elif ESSbatteryLifeState == 3:
                    stdscr.addstr(" ESS Battery Life State.. Self consumption, SoC exceeds 85%\n",ltblue)
                elif ESSbatteryLifeState == 4:
                    stdscr.addstr(" ESS Battery Life State.. Self consumption, SoC at 100%\n",ltblue)
                elif ESSbatteryLifeState == 5:
                    stdscr.addstr(" ESS Battery Life State.. SoC below BatteryLife dynamic SoC limit\n",ltblue)
                elif ESSbatteryLifeState == 6:
                    stdscr.addstr(" ESS Battery Life State.. SoC has been below SoC limit for more than 24 hours.\n\t\t\t  Slow Charging battery\n",ltblue)
                elif ESSbatteryLifeState == 7:
                    stdscr.addstr(" ESS Battery Life State.. Multi is in sustain mode\n",ltblue)
                elif ESSbatteryLifeState == 8:
                    stdscr.addstr(" ESS Battery Life State.. Recharge, SOC dropped 5% or more below MinSOC\n",ltblue)
                elif ESSbatteryLifeState == 9:
                    stdscr.addstr(" ESS Battery Life State.. Keep batteries charged mode enabled\n",ltblue)
                elif ESSbatteryLifeState == 10:
                    stdscr.addstr(" ESS Battery Life State.. Self consumption, SoC at or above minimum SoC\n",ltblue)
                elif ESSbatteryLifeState == 11:
                    stdscr.addstr(" ESS Battery Life State.. Self consumption, SoC is below minimum SoC\n",ltblue)
                elif ESSbatteryLifeState == 12:
                    stdscr.addstr(" ESS Battery Life State.. Recharge, SOC dropped 5% or more below minimum SoC\n",ltblue)

            if Multiplus_Leds == "Y" or Multiplus_Leds == "y":

                spacer()

                stdscr.addstr(f"{'': <24}Victron Multiplus II{'': <20}\n",blue)

                if mains == 0:
                    stdscr.addstr(f"{'': <10}Mains       ⚫      ",ltsalmon)
                elif mains == 1:
                    stdscr.addstr(f"{'': <10}Mains       🟢{'': <20}",ltsalmon)
                elif mains == 2:
                    stdscr.addstr(f"{'': <10}Mains       ",ltsalmon)
                    stdscr.addstr(f"🟢{'': <20}",ltsalmon | curses.A_BLINK)

                if inverter == 0:
                    stdscr.addstr("Inverting    ⚫\n",ltsalmon)
                elif inverter == 1:
                    stdscr.addstr("Inverting    🟢\n",ltsalmon)
                elif inverter == 2:
                    stdscr.addstr("Inverting    ",ltsalmon)
                    stdscr.addstr("🟢\n",ltsalmon | curses.A_BLINK)

                if bulk == 0:
                    stdscr.addstr(f"{'': <10}Bulk        ⚫{'': <20}",ltsalmon)
                elif bulk == 1:
                    stdscr.addstr(f"{'': <10}Bulk        🟡{'': <20}",ltsalmon)
                elif bulk == 2:
                    stdscr.addstr(f"{'': <10}Bulk        ",ltsalmon)
                    stdscr.addstr(f"🟡{'': <20}",ltsalmon | curses.A_BLINK)

                if overload == 0:
                    stdscr.addstr("OverLoad     ⚫\n",ltsalmon)
                elif overload == 1:
                    stdscr.addstr("OverLoad     🔴\n",ltsalmon)
                elif overload == 2:
                    stdscr.addstr("OverLoad     ",ltsalmon)
                    stdscr.addstr("🔴\n",ltsalmon | curses.A_BLINK)

                if absorp == 0:
                    stdscr.addstr(f"{'': <10}Absorption  ⚫{'': <20}",ltsalmon)
                elif absorp == 1:
                    stdscr.addstr(f"{'': <10}Absorption  🟡{'': <20}",ltsalmon)
                elif absorp == 2:
                    stdscr.addstr(f"{'': <10}Absorption  ",ltsalmon)
                    stdscr.addstr(f"🟡{'': <20}",ltsalmon | curses.A_BLINK)

                if lowbatt == 0:
                    stdscr.addstr("Low Battery  ⚫\n",ltsalmon)
                elif lowbatt == 1:
                    stdscr.addstr("Low Battery  🔴\n",ltsalmon)
                elif lowbatt == 2:
                    stdscr.addstr("Low Battery  ",ltsalmon)
                    stdscr.addstr("🔴\n",ltsalmon | curses.A_BLINK)

                if floatchg == 0:
                    stdscr.addstr(f"{'': <10}Float       ⚫{'': <20}",ltsalmon)
                elif floatchg == 1:
                    stdscr.addstr(f"{'': <10}Float       🔵{'': <20}",ltsalmon)
                elif floatchg == 2:
                    stdscr.addstr(f"{'': <10}Float       ",ltsalmon)
                    stdscr.addstr(f"🔵{'': <20}",ltsalmon | curses.A_BLINK)

                if temperature == 0:
                    stdscr.addstr("Temperature  ⚫\n",ltsalmon)
                elif temperature == 1:
                    stdscr.addstr("Temperature  🔴\n",ltsalmon)
                elif temperature == 2:
                    stdscr.addstr("Temperature  ",ltsalmon)
                    stdscr.addstr("🔴\n",ltsalmon | curses.A_BLINK)
                spacer()
            else:
                spacer()
            ###############################################
            ### Begin Cerbo GX Analog Temperature Inputs ##
            ###############################################
            if Analog_Inputs == "Y" or Analog_Inputs == "y":
                BattBoxTemp = client.read_input_registers(3304, unit= 24) # Input 1
                decoder = BinaryPayloadDecoder.fromRegisters(BattBoxTemp.registers, byteorder=Endian.Big)
                BattBoxTemp = decoder.decode_16bit_int()
                BattBoxTemp = BattBoxTemp / 100 * 1.8 + 32
                if BattBoxTemp > 49:
                    stdscr.addstr(" Battery Box Temp........ ",pink)
                    stdscr.addstr("{:.1f} °F  🥵 Whew...its a tad warm in here\n".format(BattBoxTemp),pink)


                else:
                    stdscr.addstr(" Battery Box Temp........ ",pink)
                    stdscr.addstr("{:.1f} °F \n".format(BattBoxTemp),pink)

                CabinTemp = client.read_input_registers(3304, unit= 25) # Input 2
                decoder = BinaryPayloadDecoder.fromRegisters(CabinTemp.registers, byteorder=Endian.Big)
                CabinTemp = decoder.decode_16bit_int()
                CabinTemp = CabinTemp / 100 * 1.8 + 32
                if CabinTemp < 45:
                    stdscr.addstr(" Cabin Temp.............. ",pink)
                    stdscr.addstr("{:.1f} °F  🥶 Whoa...Crank up the heat in this place!\n".format(CabinTemp),pink)
                else:
                    stdscr.addstr(" Cabin Temp.............. ",pink)
                    stdscr.addstr("{:.1f} °F\n".format(CabinTemp),pink)

                ExteriorTemp = client.read_input_registers(3304, unit= 26) # Input 3
                decoder = BinaryPayloadDecoder.fromRegisters(ExteriorTemp.registers, byteorder=Endian.Big)
                ExteriorTemp = decoder.decode_16bit_int()
                ExteriorTemp = ExteriorTemp / 100 * 1.8 + 32

                if ExteriorTemp < 33:
                    stdscr.addstr(" Outside Temp............ ",pink)
                    stdscr.addstr("{:.1f} °F  🥶 Burr...A Wee Bit Chilly Outside\n".format(ExteriorTemp),pink)
                else:
                    stdscr.addstr(" Outside Temp............ ",pink)
                    stdscr.addstr("{:.1f} °F \n".format(ExteriorTemp),pink)

                spacer()

            # ###############################################
            # ### End Cerbo GX Analog Temperature Inputs   ##
            # ###############################################

            stdscr.addstr(" M Multiplus LED's on/off\n",gray2)
            stdscr.addstr(" E ESS display on/off\n",gray2)
            stdscr.addstr(" A Analog inputs Temperature on/off\n",gray2)
            stdscr.addstr(" Q Quit or Ctrl-C",gray2)
            
            
            c = stdscr.getch()
            
            # Detect Key Press
            if c == ord('['):
                client.write_registers(address=2901, values=ESSsocLimitUser_W - 100, unit=100)
            elif c == ord(']'):
                client.write_registers(address=2901, values=ESSsocLimitUser_W + 100, unit=100)
            elif c == ord('q'):
                clean_exit()
            elif c == ord('e'):
                if ESS_Info == 'y':
                    ESS_Info = 'n'
                else:
                    ESS_Info = 'y'
            elif c == ord('m'): 
                if Multiplus_Leds == 'y':
                    Multiplus_Leds = 'n'
                else:
                    Multiplus_Leds = 'y'
            elif c == ord('a'): 
                if Analog_Inputs == 'y':
                    Analog_Inputs = 'n'
                else:
                    Analog_Inputs = 'y'
            
            
            
            curses.flushinp()
            if Multiplus_Leds == 'y' and RefreshRate == 1:
                time.sleep(1.5)
            else:
                time.sleep(RefreshRate)
        
        except curses.error:
            pass

        except AttributeError:
            continue

        except KeyboardInterrupt:
            clean_exit()
wrapper(main)
