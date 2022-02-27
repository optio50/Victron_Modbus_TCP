#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pymodbus.constants import Defaults
from pymodbus.constants import Endian
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from pymodbus.payload import BinaryPayloadDecoder
from datetime import datetime
import sys
import os
import time
import textwrap

Analog_Inputs = 'n'  # Y or N (case insensitive) to display Gerbo GX Analog Temperature inputs
ESS_Info = 'n' # Y or N (case insensitive) to display ESS system information
ip = "192.168.20.156" # ip address of GX device or if on venus local try localhost

# Value Refresh Rate in seconds
RefreshRate = 1

# Instance #'s from Cerbo GX and cross referenced to the unit ID in the Victron TCP-MODbus register xls file Tab #2.
# https://github.com/victronenergy/dbus_modbustcp/blob/master/CCGX-Modbus-TCP-register-list.xlsx
SolarChargerID = 226
MultiPlusID = 227
BmvID = 223
VEsystemID = 100

Defaults.Timeout = 25
Defaults.Retries = 5

# Local network ip address of Cerbo GX. Default port 502
client = ModbusClient(ip, port='502')

# Module for standard text colors, foreground and background
"""Colors class: reset all colors with colors.reset
two sub classes
fg for foreground
bg for background
use as  colors.subclass.colorname
i.e. colors.fg.red or colors.bg.green
also, colors.reverse, the generic bold, colors.reverse, disable
colors.reverse, underline, colors.reverse, reverse, colors.reverse, strike through, 
colors.reverse, and invisible work with the main class i.e. colors.bold """

class colors:
    reset = '\033[0m'
    bold = '\033[01m'
    disable = '\033[02m'
    underline = '\033[04m'
    reverse = '\033[07m'
    strikethrough = '\033[09m'
    invisible = '\033[08m'
    blink = '\033[05m'

    class fg:
        red = '\033[38;5;1m'
        light_red = '\033[38;5;9m'
        cyan = '\033[38;5;6m'
        light_cyan = '\033[38;5;14m'
        gray = '\033[38;5;240m'
        light_gray = '\033[38;5;246m'
        white = '\033[38;5;15m'
        black = '\033[38;5;16m'
        orange = '\033[38;5;202m'
        light_orange = '\033[38;5;172m'
        blue = '\033[38;5;21m'
        light_blue = '\033[38;5;39m'
        green = '\033[38;5;28m'
        light_green = '\033[38;5;34m'
        purple = '\033[38;5;93m'
        light_purple = '\033[38;5;99m'
        yellow = '\033[38;5;220m'
        light_yellow = '\033[38;5;227m'
        pink = '\033[38;5;201m'
        light_pink = '\033[38;5;206m'

    class bg:
        red = '\033[48;5;1m'
        light_red = '\033[48;5;9m'
        cyan = '\033[48;5;6m'
        light_cyan = '\033[48;5;14m'
        gray = '\033[48;5;240m'
        light_gray = '\033[48;5;246m'
        white = '\033[48;5;15m'
        black = '\033[48;5;16m'
        orange = '\033[48;5;202m'
        light_orange = '\033[48;5;172m'
        blue = '\033[48;5;21m'
        light_blue = '\033[48;5;39m'
        green = '\033[48;5;28m'
        light_green = '\033[48;5;34m'
        purple = '\033[48;5;93m'
        light_purple = '\033[48;5;99m'
        yellow = '\033[48;5;220m'
        light_yellow = '\033[48;5;227m'

#os.system('clear')
print("\033[H\033[J") # Clear screen
print('\033[?25l', end="") # Hide Blinking Cursor


def spacer():
    print(colors.fg.gray, "="*80 , sep="")




#errorindex = 0
while True:
    
    screensize = os.get_terminal_size()

    try:
        
        # Datetime object containing current date and time
        now = datetime.now()

        # Fri 21 Jan 2022 09:06:57 PM
        dt_string = now.strftime("%a %d %b %Y %r")
        
        print(colors.fg.purple,f"\n Time & Date............. {dt_string}", sep="")
        
        BatterySOC = client.read_input_registers(266, unit=BmvID)
        decoder = BinaryPayloadDecoder.fromRegisters(BatterySOC.registers, byteorder=Endian.Big)
        BatterySOC = decoder.decode_16bit_uint()
        BatterySOC = BatterySOC / 10
        #BatterySOC = 30 # Test value color
        
        # Battery value color
        if BatterySOC >= 60:
            print(colors.fg.cyan,f" Battery SOC............. ",colors.bold, colors.fg.green,f"{BatterySOC:.1f}", " %", colors.reset, sep="")
        elif BatterySOC >= 30 and BatterySOC < 60:
            print(colors.fg.cyan,f" Battery SOC............. ",colors.bold, colors.fg.yellow,f"{BatterySOC:.1f}", " %", colors.reset, sep="")
        elif BatterySOC < 30:
            print(colors.fg.cyan,f" Battery SOC............. ",colors.bold, colors.fg.red,f"{BatterySOC:.1f}", " %", colors.reset, sep="")
        
        BatteryWatts = client.read_input_registers(842, unit=VEsystemID)
        decoder = BinaryPayloadDecoder.fromRegisters(BatteryWatts.registers, byteorder=Endian.Big)
        BatteryWatts = decoder.decode_16bit_int()
        print(colors.fg.cyan,f" Battery Watts........... {BatteryWatts:.0f}", sep="")
        
        BatteryAmps = client.read_input_registers(841, unit=VEsystemID)
        decoder = BinaryPayloadDecoder.fromRegisters(BatteryAmps.registers, byteorder=Endian.Big)
        BatteryAmps = decoder.decode_16bit_int()
        print(colors.fg.cyan,f" Battery Amps............ {BatteryAmps / 10:.1f}", sep="")
        
        BatteryVolts = client.read_input_registers(259, unit=BmvID)
        decoder = BinaryPayloadDecoder.fromRegisters(BatteryVolts.registers, byteorder=Endian.Big)
        BatteryVolts = decoder.decode_16bit_uint()
        print(colors.fg.cyan,f" Battery Volts........... {BatteryVolts / 100:.2f}", colors.reset, sep="")
        
        spacer()
        
        SolarVolts = client.read_input_registers(776, unit=SolarChargerID)
        decoder = BinaryPayloadDecoder.fromRegisters(SolarVolts.registers, byteorder=Endian.Big)
        SolarVolts = decoder.decode_16bit_uint()
        SolarVolts = SolarVolts / 100
        print(colors.fg.orange,f" PV Volts................ {SolarVolts:.2f}", sep="")
        
        # Broken register 777 in GX firmware 2.81
        try:
            SolarAmps = client.read_input_registers(777, unit=SolarChargerID)
            decoder = BinaryPayloadDecoder.fromRegisters(SolarAmps.registers, byteorder=Endian.Big)
            SolarAmps = decoder.decode_16bit_int()
            print(f" PV Amps................. {SolarAmps / 10:.2f}", sep="")
        
        except AttributeError:
            print(f" PV Amps................. No Value, Firmware bug.  Venus OS > v2.82~4 or <= 2.73 Required", sep="")
        
        SolarWatts = client.read_input_registers(789, unit=SolarChargerID)
        decoder = BinaryPayloadDecoder.fromRegisters(SolarWatts.registers, byteorder=Endian.Big)
        SolarWatts = decoder.decode_16bit_uint()
        SolarWatts = SolarWatts / 10
        
        print(f" PV Watts................ {SolarWatts:.0f}", sep="")
                
        MaxSolarWatts = client.read_input_registers(785, unit=SolarChargerID)
        decoder = BinaryPayloadDecoder.fromRegisters(MaxSolarWatts.registers, byteorder=Endian.Big)
        MaxSolarWatts = decoder.decode_16bit_uint()
        print(f" Max PV Watts Today...... {MaxSolarWatts}", sep="")
        
        SolarYield = client.read_input_registers(784, unit=SolarChargerID)
        decoder = BinaryPayloadDecoder.fromRegisters(SolarYield.registers, byteorder=Endian.Big)
        SolarYield = decoder.decode_16bit_int()
        print(f" PV Yield Today.......... {SolarYield / 10:.3f} kWh", sep="")
        
        SolarState = client.read_input_registers(775, unit=SolarChargerID)
        decoder = BinaryPayloadDecoder.fromRegisters(SolarState.registers, byteorder=Endian.Big)
        SolarState = decoder.decode_16bit_int()
        if SolarState == 0:
            print(f" PV Charger State........ OFF", sep="")
        if SolarState == 2:
            print(f" PV Charger State........ Fault", sep="")
        if SolarState == 3:
            print(f" PV Charger State........ Bulk", sep="")
        if SolarState == 4:
            print(f" PV Charger State........ Absorption", sep="")
        if SolarState == 5:
            print(f" PV Charger State........ Float", sep="")
        if SolarState == 6:
            print(f" PV Charger State........ Storage", sep="")
        if SolarState == 7:
            print(f" PV Charger State........ Equalize", colors.reset, sep="")
        if SolarState == 11:
            print(f" PV Charger State........ Other (Hub-1)", colors.reset, sep="")
        if SolarState == 252:
            print(f" PV Charger State........ EXT Control", sep="")
        
        spacer()
        
        GridSetPoint = client.read_input_registers(2700, unit=VEsystemID)
        decoder = BinaryPayloadDecoder.fromRegisters(GridSetPoint.registers, byteorder=Endian.Big)
        GridSetPoint = decoder.decode_16bit_int()
        print(colors.fg.green,f" Grid Set Point Watts.... {GridSetPoint}", sep="")
        
        GridWatts = client.read_input_registers(820, unit=VEsystemID)
        decoder = BinaryPayloadDecoder.fromRegisters(GridWatts.registers, byteorder=Endian.Big)
        GridWatts = decoder.decode_16bit_int()
        print(f" Grid Watts.............. {GridWatts}", sep="")
        
        GridAmps = client.read_input_registers(6, unit=MultiPlusID)
        decoder = BinaryPayloadDecoder.fromRegisters(GridAmps.registers, byteorder=Endian.Big)
        GridAmps = decoder.decode_16bit_int()
        GridAmps = GridAmps / 10
        print(f" Grid Amps............... {GridAmps:.1f}", sep="")
        
        GridVolts = client.read_input_registers(3, unit=MultiPlusID)
        decoder = BinaryPayloadDecoder.fromRegisters(GridVolts.registers, byteorder=Endian.Big)
        GridVolts = decoder.decode_16bit_int()
        GridVolts = GridVolts / 10
        print(f" Grid Volts ............. {GridVolts:.1f}", sep="")
        
        GridHZ = client.read_input_registers(9, unit=MultiPlusID)
        decoder = BinaryPayloadDecoder.fromRegisters(GridHZ.registers, byteorder=Endian.Big)
        GridHZ = decoder.decode_16bit_int()
        GridHZ = GridHZ / 100
        print(f" Grid Freq .............. {GridHZ:.1f}",sep="")
                
        ACoutWatts = client.read_input_registers(817, unit=VEsystemID)
        decoder = BinaryPayloadDecoder.fromRegisters(ACoutWatts.registers, byteorder=Endian.Big)
        ACoutWatts = decoder.decode_16bit_uint()
        print(f" AC Output Watts......... {ACoutWatts}", sep="")
        
        ACoutAmps = client.read_input_registers(18, unit=MultiPlusID)
        decoder = BinaryPayloadDecoder.fromRegisters(ACoutAmps.registers, byteorder=Endian.Big)
        ACoutAmps = decoder.decode_16bit_int()
        ACoutAmps = ACoutAmps / 10
        print(f" AC Output Amps.......... {ACoutAmps:.1f}", sep="")
                
        ACoutVolts = client.read_input_registers(15, unit=MultiPlusID)
        decoder = BinaryPayloadDecoder.fromRegisters(ACoutVolts.registers, byteorder=Endian.Big)
        ACoutVolts = decoder.decode_16bit_int()
        ACoutVolts = ACoutVolts / 10
        print(f" AC Output Volts......... {ACoutVolts:.1f}", sep="")
        
        ACoutHZ = client.read_input_registers(21, unit=MultiPlusID)
        decoder = BinaryPayloadDecoder.fromRegisters(ACoutHZ.registers, byteorder=Endian.Big)
        ACoutHZ = decoder.decode_16bit_int()
        ACoutHZ = ACoutHZ / 100
        print(f" AC Output Freq.......... {ACoutHZ:.1f}", sep="")
                        
        GridCondition = client.read_input_registers(64, unit=MultiPlusID)
        decoder = BinaryPayloadDecoder.fromRegisters(GridCondition.registers, byteorder=Endian.Big)
        GridCondition = decoder.decode_16bit_uint()
        if GridCondition == 0:
            print(colors.fg.green,f" Grid Condition.......... OK", sep="")
        if GridCondition == 1:
            print(colors.fg.light_red,f" Grid Condition ......... Grid LOST", colors.reset, sep="")
        
        spacer()
                
        VEbusStatus = client.read_input_registers(31, unit=MultiPlusID)
        decoder = BinaryPayloadDecoder.fromRegisters(VEbusStatus.registers, byteorder=Endian.Big)
        VEbusStatus = decoder.decode_16bit_uint()
        if VEbusStatus == 3:
            print(colors.fg.light_blue,f" System State............ Bulk Charging",sep="")
        if VEbusStatus == 4:
            print(colors.fg.light_blue,f" System State............ Absorption Charging", sep="")
        if VEbusStatus == 5:
            print(colors.fg.light_blue,f" System State............ Float Charging", sep="")
        
        tr = textwrap.TextWrapper(width=56, subsequent_indent=" ")
            
        # VEbus Error
        VEbusError = client.read_input_registers(32, unit=MultiPlusID)
        decoder = BinaryPayloadDecoder.fromRegisters(VEbusError.registers, byteorder=Endian.Big)
        VEbusError = decoder.decode_16bit_uint()
        
        # error_nos = [0,1,2,3,4,5,6,7,10,14,16,17,18,22,24,25,26]
        # VEbusError = error_nos[errorindex] # Test VEbusError's
        # VEbusError = 18
            
        if VEbusError == 0:
            print(colors.fg.light_blue,f" VE.Bus Error............ ",colors.fg.green, tr.fill(f"No Error"), colors.fg.light_blue, sep="")
        elif VEbusError == 1:
            print(colors.fg.light_blue,f" VE.Bus Error............ ",colors.fg.red, tr.fill(f"Error 1: Device is "
            "switched off because one of the other phases in the system has switched off"), sep="")
        elif VEbusError == 2:
            print(colors.fg.light_blue,f" VE.Bus Error............ ",colors.fg.red, tr.fill(f"Error 2: New and old "
            "types MK2 are mixed in the system"), colors.fg.light_blue, sep="")
        elif VEbusError == 3:
            print(colors.fg.light_blue,f" VE.Bus Error............ ",colors.fg.red, tr.fill(f"Error 3: Not all- or "
             "more than- the expected devices were found in the system"), colors.fg.light_blue, sep="")
        elif VEbusError == 4:
            print(colors.fg.light_blue,f" VE.Bus Error............ ",colors.fg.red, tr.fill(f"Error 4: No other " 
            "device whatsoever detected"), colors.fg.light_blue, sep="")
        elif VEbusError == 5:
            print(colors.fg.light_blue,f" VE.Bus Error............ ",colors.fg.red, tr.fill(f"Error 5: Overvoltage "
            "on AC-out"), colors.fg.light_blue, sep="")
        elif VEbusError == 6:
            print(colors.fg.light_blue,f" VE.Bus Error............ ",colors.fg.red, tr.fill(f"Error 6: in DDC "
            "Program"), colors.fg.light_blue, sep="")
        elif VEbusError == 7:
            print(colors.fg.light_blue,f" VE.Bus Error............ ",colors.fg.red, tr.fill(f"VE.Bus BMS connected- "
            "which requires an Assistant- but no assistant found"), colors.fg.light_blue, sep="")
        elif VEbusError == 10:
            print(colors.fg.light_blue,f" VE.Bus Error............ ",colors.fg.red, tr.fill(f"Error 10: System time "
            " synchronisation problem occurred"), colors.fg.light_blue, sep="")
        elif VEbusError == 14:
            print(colors.fg.light_blue,f" VE.Bus Error............ ",colors.fg.red, tr.fill(f"Error 14: Device cannot "
            "transmit data"), colors.fg.light_blue, sep="")
        elif VEbusError == 16:
            print(colors.fg.light_blue,f" VE.Bus Error............ ",colors.fg.red, tr.fill(f"Error 16: Dongle missing "
            ), colors.fg.light_blue, sep="")
        elif VEbusError == 17:
            print(colors.fg.light_blue,f" VE.Bus Error............ ",colors.fg.red, tr.fill(f"Error 17: One of the "
            "devices assumed master status because the original master failed"), colors.fg.light_blue, sep="")
        elif VEbusError == 18:
            print(colors.fg.light_blue,f" VE.Bus Error............ ",colors.fg.red, tr.fill(f"Error 18: AC Overvoltage "
            "on the output of a slave has occurred while already switched off"), colors.fg.light_blue, sep="")
        elif VEbusError == 22:
            print(colors.fg.light_blue,f" VE.Bus Error............ ",colors.fg.red, tr.fill(f"Error 22: This device "
            "cannot function as slave"), colors.fg.light_blue, sep="")
        elif VEbusError == 24:
            print(colors.fg.light_blue,f" VE.Bus Error............ ",colors.fg.red, tr.fill(f"Error 24: Switch-over "
            "system protection initiated"), colors.fg.light_blue, sep="")
        elif VEbusError == 25:
            print(colors.fg.light_blue,f" VE.Bus Error............ ",colors.fg.red, tr.fill(f"Error 25: Firmware "
            "incompatibility. The firmware of one of the connected devices is not sufficiently up to date"), colors.fg.light_blue, sep="")
        elif VEbusError == 26:
            print(colors.fg.light_blue,f" VE.Bus Error............ ",colors.fg.red, tr.fill(f"Error 26: Internal "
            "error"), colors.fg.light_blue, sep="")
    
        # errorindex += 1
        # if errorindex == len(error_nos):
            # errorindex = 0
        
        if ESS_Info.lower() == 'y':
            ESSsocLimitUser = client.read_input_registers(2901, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(ESSsocLimitUser.registers, byteorder=Endian.Big)
            ESSsocLimitUser = decoder.decode_16bit_uint()
            print(f" ESS SOC Limit (User).... {ESSsocLimitUser / 10:.2f}% Unless Grid Fails", sep="")
           
           # Requires Newer GX Firmware such as 2.82~4 or >
            try:
                ESSsocLimitDynamic = client.read_input_registers(2903, unit=VEsystemID)
                decoder = BinaryPayloadDecoder.fromRegisters(ESSsocLimitDynamic.registers, byteorder=Endian.Big)
                ESSsocLimitDynamic = decoder.decode_16bit_uint()
                print(f" ESS SOC Limit (Dynamic). {ESSsocLimitDynamic / 10:.2f}%", sep="")
            
            except AttributeError:
                print(f" ESS SOC Limit (Dynamic). No Value, Firmware requires. Venus OS > v2.82~4", sep="")
            
            ESSbatteryLifeState = client.read_input_registers(2900, unit=VEsystemID)
            decoder = BinaryPayloadDecoder.fromRegisters(ESSbatteryLifeState.registers, byteorder=Endian.Big)
            ESSbatteryLifeState = decoder.decode_16bit_uint()
            if ESSbatteryLifeState == 0:
                print(f" ESS Battery Life State.. Battery Life Disabled", sep="")
            if ESSbatteryLifeState == 1:
                print(f" ESS Battery Life State.. Restarting", sep="")
            if ESSbatteryLifeState == 2:
                print(f" ESS Battery Life State.. Self-consumption", sep="")
            if ESSbatteryLifeState == 3:
                print(f" ESS Battery Life State.. Self consumption, SoC exceeds 85%", sep="")
            if ESSbatteryLifeState == 4:
                print(f" ESS Battery Life State.. Self consumption, SoC at 100%", sep="")
            if ESSbatteryLifeState == 5:
                print(f" ESS Battery Life State.. SoC below BatteryLife dynamic SoC limit", sep="")
            if ESSbatteryLifeState == 6:
                print(f" ESS Battery Life State.. SoC below SoC limit for more than 24 hours. Slow Charging battery", sep="")
            if ESSbatteryLifeState == 7:
                print(f" ESS Battery Life State.. Multi is in sustain mode", sep="")
            if ESSbatteryLifeState == 8:
                print(f" ESS Battery Life State.. Recharge, SOC dropped 5% or more below MinSOC", sep="")
            if ESSbatteryLifeState == 9:
                print(f" ESS Battery Life State.. Keep batteries charged mode enabled", sep="")
            if ESSbatteryLifeState == 10:
                print(f" ESS Battery Life State.. Self consumption, SoC at or above minimum SoC", sep="")
            if ESSbatteryLifeState == 11:
                print(f" ESS Battery Life State.. Self consumption, SoC is below minimum SoC", sep="")
            if ESSbatteryLifeState == 12:
                print(f" ESS Battery Life State.. Recharge, SOC dropped 5% or more below minimum SoC", colors.reset, sep="")
                
            
        spacer()
        
        ###############################################
        ### Begin Cerbo GX Analog Temperature Inputs ##
        ###############################################
        
        if Analog_Inputs.lower() == "y":
            
            BattBoxTemp = client.read_input_registers(3304, unit= 24) # Input 1
            decoder = BinaryPayloadDecoder.fromRegisters(BattBoxTemp.registers, byteorder=Endian.Big)
            BattBoxTemp = decoder.decode_16bit_int()
            BattBoxTemp = BattBoxTemp / 100 * 1.8 + 32
            if BattBoxTemp > 50:
                print(colors.fg.blue,f" Battery Box Temp........ {BattBoxTemp:.2f} Deg F", colors.fg.red, "  Whew...its a tad warm in here",colors.reset, sep="")
            else:
                print(colors.fg.blue,f" Battery Box Temp........ {BattBoxTemp:.2f} Deg F", sep="")
            
            CabinTemp = client.read_input_registers(3304, unit= 25) # Input 2
            decoder = BinaryPayloadDecoder.fromRegisters(CabinTemp.registers, byteorder=Endian.Big)
            CabinTemp = decoder.decode_16bit_int()
            CabinTemp = CabinTemp / 100 * 1.8 + 32
            if CabinTemp < 45:
                print(colors.fg.blue,f" Cabin Temp.............. {CabinTemp:.2f} Deg F  Whoa...Crank up the heat in this place!", sep="")
            else:
                print(colors.fg.blue,f" Cabin Temp.............. {CabinTemp:.2f} Deg F", sep="")
            
            ExteriorTemp = client.read_input_registers(3304, unit= 26) # Input 3
            decoder = BinaryPayloadDecoder.fromRegisters(ExteriorTemp.registers, byteorder=Endian.Big)
            ExteriorTemp = decoder.decode_16bit_int()
            ExteriorTemp = ExteriorTemp / 100 * 1.8 + 32
            
            if ExteriorTemp < 33:
                print(colors.fg.blue,f" Outside Temp............ {ExteriorTemp:.2f} Deg F  Burr...A Wee Bit Chilly Outside", colors.reset, sep="")
            else:
                print(colors.fg.blue,f" Outside Temp............ {ExteriorTemp:.2f} Deg F", colors.reset, sep="")
        
        print(colors.fg.gray,"\n\tCtrl+C  To Quit",colors.reset)       
        ###############################################
        ### End Cerbo GX Analog Temperature Inputs   ##
        ############################################### 
        
        time.sleep(RefreshRate)
        if screensize != os.get_terminal_size():
            os.system('clear')
        print("\033[%d;%dH" % (0, 0)) # Move cursor to 0 0 instead of clearing screen
        print("\033[H\033[J") # Clear screen
        if VEbusError != 0:
            print("\033[H\033[J") # Clear screen
        #os.system('clear')
        
    except KeyboardInterrupt:
        print(colors.reset)
        print('\033[?25h', end="") # Restore Blinking Cursor
        sys.exit(0)
    except AttributeError:
        continue
