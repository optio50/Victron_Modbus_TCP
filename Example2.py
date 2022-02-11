#!/usr/bin/env python3
import json
import curses
from curses import wrapper
import paho.mqtt.subscribe as subscribe
from pymodbus.constants import Defaults
from pymodbus.constants import Endian
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from pymodbus.payload import BinaryPayloadDecoder
from datetime import datetime
import sys
import os
import time
import signal

Defaults.Timeout = 25
Defaults.Retries = 5

Analog_Inputs = 'y'  # Y or N (case insensitive) to display Gerbo GX Analog Temperature inputs
Multiplus_Leds = 'y' # Y or N (case insensitive) to display Multiplus LED'S

RefreshRate = 1      # Refresh Rate in seconds. Auto reduced to 3 seconds if LED's enabled
                     # For MQQT requests

# GX Device I.P Address
ip = '192.168.20.156'

# Instance #'s from Cerbo GX and cross referenced to the unit ID in the Victron TCP-MODbus register xls file Tab #2.
# https://github.com/victronenergy/dbus_modbustcp/blob/master/CCGX-Modbus-TCP-register-list.xlsx
SolarChargerID = 226
MultiPlusID = 227
BmvID = 223
VEsystemID = 100



# Local network ip address of Cerbo GX. Default port 502
client2 = ModbusClient(ip, port='502')

stdscr = curses.initscr()
curses.curs_set(False)
curses.start_color()
curses.use_default_colors()
#
# Find More Color Numbers and Names Here.
# https://github.com/optio50/PythonColors/blob/main/color-test.py
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


def spacer():
    stdscr.addstr("="*80 + "\n",gray)


def clean_exit():
    curses.curs_set(True)
    curses.nocbreak()
    stdscr.keypad(False)
    curses.echo()
    curses.endwin()
    sys.exit(0)



def main(stdscr):
    while True:
        
        # MQTT subscribe to get LED values on the Multiplus
        # The LEDS are not available on ModBusTCP AFAIK
        if Multiplus_Leds == "Y" or Multiplus_Leds == "y":
            
            msg = subscribe.simple("N/d41243d31a90/vebus/276/Leds/Mains", hostname=ip)
            data = json.loads(msg.payload)
            mains = data['value']
            
            msg = subscribe.simple("N/d41243d31a90/vebus/276/Leds/Inverter", hostname=ip)
            data = json.loads(msg.payload)
            inverter = data['value']
            
            msg = subscribe.simple("N/d41243d31a90/vebus/276/Leds/Bulk", hostname=ip)
            data = json.loads(msg.payload)
            bulk = data['value']
            
            msg = subscribe.simple("N/d41243d31a90/vebus/276/Leds/Overload", hostname=ip)
            data = json.loads(msg.payload)
            overload = data['value']
            
            msg = subscribe.simple("N/d41243d31a90/vebus/276/Leds/Absorption", hostname=ip)
            data = json.loads(msg.payload)
            absorp = data['value']
            
            msg = subscribe.simple("N/d41243d31a90/vebus/276/Leds/LowBattery", hostname=ip)
            data = json.loads(msg.payload)
            lowbatt = data['value']
            
            msg = subscribe.simple("N/d41243d31a90/vebus/276/Leds/Float", hostname=ip)
            data = json.loads(msg.payload)
            floatchg = data['value']
            
            msg = subscribe.simple("N/d41243d31a90/vebus/276/Leds/Temperature", hostname=ip)
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
            
            BatterySOC = client2.read_input_registers(266, unit=BmvID)
            decoder = BinaryPayloadDecoder.fromRegisters(BatterySOC.registers, byteorder=Endian.Big)
            BatterySOC = decoder.decode_16bit_uint()
            BatterySOC = BatterySOC / 10
            #BatterySOC = 64
            
            if BatterySOC >= 90:
                stdscr.addstr(" Battery SOC............. ",cyan)
                stdscr.addstr("{:.1f}%  ║▒▒▒▒▒▒▒▒▒▒▒▒║\n".format(BatterySOC),green | curses.A_BOLD)
            elif BatterySOC >= 65 and BatterySOC < 90:
                stdscr.addstr(" Battery SOC............. ",cyan)
                stdscr.addstr("{:.1f}%  ║▒▒▒▒▒▒▒▒░░░░║\n".format(BatterySOC),green)
            elif BatterySOC >= 35 and BatterySOC < 65:
                stdscr.addstr(" Battery SOC............. ",cyan)
                stdscr.addstr("{:.1f}%  ║▒▒▒▒▒▒░░░░░░║\n".format(BatterySOC),yellow)
            elif BatterySOC >= 10 and BatterySOC < 35:
                stdscr.addstr(" Battery SOC............. ",cyan)
                stdscr.addstr("{:.1f}%  ║▒▒▒▒░░░░░░░░║\n".format(BatterySOC),red)
            elif BatterySOC < 10:
                stdscr.addstr(" Battery SOC............. ",cyan)
                stdscr.addstr("{:.1f}%".format(BatterySOC),red | curses.A_BLINK)
                stdscr.addstr("  ║▒░░░░░░░░░░░║\n".format(BatterySOC),red)
            
            BatteryWatts = client2.read_input_registers(842, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(BatteryWatts.registers, byteorder=Endian.Big)
            BatteryWatts = decoder.decode_16bit_int()
            stdscr.addstr(" Battery Watts........... ",cyan)
            stdscr.addstr(str(BatteryWatts) + "\n",cyan)
            
            BatteryAmps = client2.read_input_registers(841, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(BatteryAmps.registers, byteorder=Endian.Big)
            BatteryAmps = decoder.decode_16bit_int()
            BatteryAmps  = BatteryAmps / 10
            stdscr.addstr(" Battery Amps............ ",cyan)
            stdscr.addstr(str(BatteryAmps) + "\n",cyan)
            
            BatteryVolts = client2.read_input_registers(259, unit=BmvID)
            decoder = BinaryPayloadDecoder.fromRegisters(BatteryVolts.registers, byteorder=Endian.Big)
            BatteryVolts = decoder.decode_16bit_uint()
            BatteryVolts = BatteryVolts / 100
            stdscr.addstr(" Battery Volts........... ",cyan)
            stdscr.addstr(str(BatteryVolts) + "\n",cyan)
            
            spacer()
            
            SolarVolts = client2.read_input_registers(776, unit=SolarChargerID)
            decoder = BinaryPayloadDecoder.fromRegisters(SolarVolts.registers, byteorder=Endian.Big)
            SolarVolts = decoder.decode_16bit_uint()
            SolarVolts = SolarVolts / 100
            stdscr.addstr(" PV Volts................ ",orange)
            stdscr.addstr("{:.2f}".format(SolarVolts) + "\n",orange)
            # Broken register 777 in GX firmware 2.81
            try:
                SolarAmps = client2.read_input_registers(777, unit=SolarChargerID)
                decoder = BinaryPayloadDecoder.fromRegisters(SolarAmps.registers, byteorder=Endian.Big)
                SolarAmps = decoder.decode_16bit_int()
                SolarAmps = SolarAmps / 10
                stdscr.addstr(" PV Amps................. ",orange)
                stdscr.addstr("{:.2f}\n".format(SolarAmps),orange)
            
            except AttributeError:
                stdscr.addstr(" PV Amps................. No Value, Firmware bug.  Venus OS > v2.82~4 or <= 2.73 Required",orange)
            
            SolarWatts = client2.read_input_registers(789, unit=SolarChargerID)
            decoder = BinaryPayloadDecoder.fromRegisters(SolarWatts.registers, byteorder=Endian.Big)
            SolarWatts = decoder.decode_16bit_uint()
            SolarWatts = SolarWatts / 10
            if SolarVolts < 15:
                stdscr.addstr(" PV Watts ............... ",orange)
                stdscr.addstr("{:.0f} 🌛\n".format(SolarWatts),orange)
                
            ###################################
            ###         400W array          ###
            ###################################
            elif SolarWatts > 49 and SolarWatts < 100:
                stdscr.addstr(" PV Watts ........... ",orange)
                stdscr.addstr("{:.0f} 🌞\n".format(SolarWatts),orange)
            elif SolarWatts > 99 and SolarWatts < 200:
                stdscr.addstr(" PV Watts ........... ",orange)
                stdscr.addstr("{:.0f} 🌞🌞\n".format(SolarWatts),orange)
            elif SolarWatts > 199 and SolarWatts < 300:
                stdscr.addstr(" PV Watts ........... ",orange)
                stdscr.addstr("{:.0f} 🌞🌞🌞\n".format(SolarWatts),orange)
            elif SolarWatts > 299 and SolarWatts < 350:
                stdscr.addstr(" PV Watts ........... ",orange)
                stdscr.addstr("{:.0f} 🌞🌞🌞🌞\n".format(SolarWatts),orange)
            elif SolarWatts > 349:
                stdscr.addstr(" PV Watts ........... ",orange)
                stdscr.addstr("{:.0f} 🌞🌞🌞🌞🌞\n".format(SolarWatts),orange)
            else:
                stdscr.addstr(" PV Watts ........... ",orange)
                stdscr.addstr("{:.0f} ⛅\n".format(SolarWatts),orange)
                        
            MaxSolarWatts = client2.read_input_registers(785, unit=SolarChargerID)
            decoder = BinaryPayloadDecoder.fromRegisters(MaxSolarWatts.registers, byteorder=Endian.Big)
            MaxSolarWatts = decoder.decode_16bit_uint()
            stdscr.addstr(" Max PV Watts Today...... ",orange)
            stdscr.addstr("{:.0f} \n".format(MaxSolarWatts),orange)
            
            SolarYield = client2.read_input_registers(784, unit=SolarChargerID)
            decoder = BinaryPayloadDecoder.fromRegisters(SolarYield.registers, byteorder=Endian.Big)
            SolarYield = decoder.decode_16bit_int()
            SolarYield = SolarYield / 10
            stdscr.addstr(" PV Yield Today.......... ",orange)
            stdscr.addstr("{:.3f} kWh \n".format(SolarYield),orange)
                    
            SolarState = client2.read_input_registers(775, unit=SolarChargerID)
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
            
            GridWatts = client2.read_input_registers(820, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(GridWatts.registers, byteorder=Endian.Big)
            GridWatts = decoder.decode_16bit_int()
            stdscr.addstr(" Grid Watts.............. ",green)
            stdscr.addstr("{:.0f} \n".format(GridWatts),green)
                    
            GridSetPoint = client2.read_input_registers(2700, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(GridSetPoint.registers, byteorder=Endian.Big)
            GridSetPoint = decoder.decode_16bit_int()
            stdscr.addstr(" Grid Set Point Watts.... ",green)
            stdscr.addstr("{:.0f} \n".format(GridSetPoint),green)
                    
            GridAmps = client2.read_input_registers(6, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(GridAmps.registers, byteorder=Endian.Big)
            GridAmps = decoder.decode_16bit_int()
            GridAmps = GridAmps / 10
            stdscr.addstr(" Grid Amps............... ",green)
            stdscr.addstr("{:.1f} \n".format(GridAmps),green)
            
            ACoutWatts = client2.read_input_registers(817, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(ACoutWatts.registers, byteorder=Endian.Big)
            ACoutWatts = decoder.decode_16bit_uint()
            stdscr.addstr(" AC Load Watts........... ",green)
            stdscr.addstr("{:.0f} 💡 \n".format(ACoutWatts),green)
            
            DCoutWatts = client2.read_input_registers(860, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(DCoutWatts.registers, byteorder=Endian.Big)
            DCoutWatts = decoder.decode_16bit_int()
            stdscr.addstr(" DC Load Watts........... ",green)
            stdscr.addstr("{:.0f} 🔋 \n".format(DCoutWatts),green)
            
            
            GridCondition = client2.read_input_registers(64, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(GridCondition.registers, byteorder=Endian.Big)
            GridCondition = decoder.decode_16bit_uint()
            if GridCondition == 0:
                stdscr.addstr(" Grid Condition.......... OK 🆗\n",green)
            elif GridCondition == 1:
                stdscr.addstr(" Grid Condition ......... Grid LOST ❌\n",green | curses.A_BLINK)
            
            spacer()
                    
            VEbusStatus = client2.read_input_registers(31, unit=MultiPlusID)
            decoder = BinaryPayloadDecoder.fromRegisters(VEbusStatus.registers, byteorder=Endian.Big)
            VEbusStatus = decoder.decode_16bit_uint()
            if VEbusStatus == 3:
                stdscr.addstr(" System State............ Bulk Charging\n",ltblue)
            elif VEbusStatus == 4:
                stdscr.addstr(" System State............ Absorption Charging\n",ltblue)
            elif VEbusStatus == 5:
                stdscr.addstr(" System State............ Float Charging\n",ltblue)
            
            ESSsocLimitUser = client2.read_input_registers(2901, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(ESSsocLimitUser.registers, byteorder=Endian.Big)
            ESSsocLimitUser = decoder.decode_16bit_uint()
            ESSsocLimitUser = ESSsocLimitUser / 10
            stdscr.addstr(" ESS SOC Limit (User).... ",ltblue)
            stdscr.addstr("{:.0f}% - Unless Grid Fails \n".format(ESSsocLimitUser),ltblue)
           
           # Requires Newer GX Firmware such as 2.82~4 or >
            try:
                ESSsocLimitDynamic = client2.read_input_registers(2903, unit=VEsystemID)
                decoder = BinaryPayloadDecoder.fromRegisters(ESSsocLimitDynamic.registers, byteorder=Endian.Big)
                ESSsocLimitDynamic = decoder.decode_16bit_uint()
                ESSsocLimitDynamic = ESSsocLimitDynamic / 10
                stdscr.addstr(" ESS SOC Limit (Dynamic). ",ltblue)
                stdscr.addstr("{:.0f}%\n".format(ESSsocLimitDynamic),ltblue)
            
            except AttributeError:
                stdscr.addstr(" ESS SOC Limit (Dynamic). No Value, Firmware requires. Venus OS > v2.82~4",ltblue)
            
            ESSbatteryLifeState = client2.read_input_registers(2900, unit=VEsystemID)
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
                    stdscr.addstr("f{'': <10}Absorption  ",ltsalmon)
                    stdscr.addstr("f🟡{'': <20}",ltsalmon | curses.A_BLINK)
                
                if lowbatt == 0:
                    stdscr.addstr("Low Battery  ⚫\n",ltsalmon)
                elif lowbatt == 1:
                    stdscr.addstr("Low Battery  🔴\n",ltsalmon)
                elif lowbatt == 2:
                    stdscr.addstr("Low Battery     ",ltsalmon)
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
                    stdscr.addstr("Temperature     ",ltsalmon)
                    stdscr.addstr("🔴\n",ltsalmon | curses.A_BLINK)
                spacer()
            else:
                spacer()
            ###############################################
            ### Begin Cerbo GX Analog Temperature Inputs ##
            ###############################################
            if Analog_Inputs == "Y" or Analog_Inputs == "y":
                BattBoxTemp = client2.read_input_registers(3304, unit= 24) # Input 1
                decoder = BinaryPayloadDecoder.fromRegisters(BattBoxTemp.registers, byteorder=Endian.Big)
                BattBoxTemp = decoder.decode_16bit_int()
                BattBoxTemp = BattBoxTemp / 100 * 1.8 + 32
                if BattBoxTemp > 49:
                    stdscr.addstr(" Battery Box Temp........ ",pink)
                    stdscr.addstr("{:.1f} °F  🥵 Whew...its a tad warm in here\n".format(BattBoxTemp),pink)
                    
                    
                else:
                    stdscr.addstr(" Battery Box Temp........ ",pink)
                    stdscr.addstr("{:.1f} °F \n".format(BattBoxTemp),pink)
                
                CabinTemp = client2.read_input_registers(3304, unit= 25) # Input 2
                decoder = BinaryPayloadDecoder.fromRegisters(CabinTemp.registers, byteorder=Endian.Big)
                CabinTemp = decoder.decode_16bit_int()
                CabinTemp = CabinTemp / 100 * 1.8 + 32
                if CabinTemp < 45:
                    stdscr.addstr(" Cabin Temp.............. ",pink)
                    stdscr.addstr("{:.1f} °F  🥶 Whoa...Crank up the heat in this place!\n".format(CabinTemp),pink)
                else:
                    stdscr.addstr(" Cabin Temp.............. ",pink)
                    stdscr.addstr("{:.1f} °F\n".format(CabinTemp),pink)
                
                ExteriorTemp = client2.read_input_registers(3304, unit= 26) # Input 3
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
            
            stdscr.addstr("\nCtrl-C to Exit",gray)
            stdscr.refresh()
            if Multiplus_Leds == "Y" or Multiplus_Leds == "y":
                time.sleep(3)
            else:
                time.sleep(RefreshRate)
            stdscr.erase()
            
            
        except AttributeError:
            continue
            
        except KeyboardInterrupt:
            clean_exit()
wrapper(main)

