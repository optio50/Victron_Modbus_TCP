#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# This script depends on the following Victron equipment. BMV, Multiplus, Solar Charger, Venus GX device.
# Modbus must be enabled in the Venus GX device
# You shouldnt have to change anything but some variables to make this work with your system
# provided you actually have the requsite victron equipment.

from pymodbus.constants import Defaults
from pymodbus.constants import Endian
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from pymodbus.payload import BinaryPayloadDecoder
from datetime import datetime
import sys
import os
import time
import textwrap
import subprocess

Analog_Inputs = 'n'  # Y or N (case insensitive) to display Gerbo GX Analog Temperature inputs
ESS_Info      = 'n' # Y or N (case insensitive) to display ESS system information
ip            = "192.168.20.156" # ip address of GX device or if on venus local try localhost

# Value Refresh Rate in seconds
RefreshRate = 1

# Unit ID #'s from Cerbo GX.
# Do not confuse UnitID with Instance ID.
# You can also get the UnitID from the GX device. Menu --> Settings --> Services --> ModBusTCP --> Available Services
# Or
# https://github.com/victronenergy/dbus_modbustcp/blob/master/CCGX-Modbus-TCP-register-list.xlsx Tab #2
#===================================
SolarChargerID    = 226
MultiPlusID       = 227
BmvID             = 223
VEsystemID        = 100
#===================================

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
    reset         = '\033[0m'
    bold          = '\033[01m'
    disable       = '\033[02m'
    underline     = '\033[04m'
    reverse       = '\033[07m'
    strikethrough = '\033[09m'
    invisible     = '\033[08m'
    blink         = '\033[05m'

    class fg:
        red          = '\033[38;5;1m'
        light_red    = '\033[38;5;9m'
        cyan         = '\033[38;5;6m'
        light_cyan   = '\033[38;5;14m'
        gray         = '\033[38;5;240m'
        light_gray   = '\033[38;5;246m'
        white        = '\033[38;5;15m'
        black        = '\033[38;5;16m'
        orange       = '\033[38;5;202m'
        light_orange = '\033[38;5;172m'
        blue         = '\033[38;5;21m'
        light_blue   = '\033[38;5;39m'
        green        = '\033[38;5;28m'
        light_green  = '\033[38;5;34m'
        purple       = '\033[38;5;93m'
        light_purple = '\033[38;5;99m'
        yellow       = '\033[38;5;220m'
        light_yellow = '\033[38;5;227m'
        pink         = '\033[38;5;201m'
        light_pink   = '\033[38;5;206m'

    class bg:
        red          = '\033[48;5;1m'
        light_red    = '\033[48;5;9m'
        cyan         = '\033[48;5;6m'
        light_cyan   = '\033[48;5;14m'
        gray         = '\033[48;5;240m'
        light_gray   = '\033[48;5;246m'
        white        = '\033[48;5;15m'
        black        = '\033[48;5;16m'
        orange       = '\033[48;5;202m'
        light_orange = '\033[48;5;172m'
        blue         = '\033[48;5;21m'
        light_blue   = '\033[48;5;39m'
        green        = '\033[48;5;28m'
        light_green  = '\033[48;5;34m'
        purple       = '\033[48;5;93m'
        light_purple = '\033[48;5;99m'
        yellow       = '\033[48;5;220m'
        light_yellow = '\033[48;5;227m'


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

ESSbatteryLifeStateDict = {0: "Battery Life Disabled",
                           1: "Restarting",
                           2: "Self-consumption",
                           3: "Self consumption, SoC exceeds 85%",
                           4: "Self consumption, SoC at 100%",
                           5: "Discharge disabled. SoC below BatteryLife Dynamic SoC",
                           6: "SoC has been below SoC limit for more than 24 hours. Slow Charging battery",
                           7: "Multi is in sustain mode",
                           8: "Recharge, SOC dropped 5% or more below MinSOC",
                           9: "Keep batteries charged mode enabled",
                           10:"Self consumption, SoC at or above minimum SoC",
                           11:"Discharge Disabled (Low SoC), SoC is below minimum SoC",
                           12:"Recharge, SOC dropped 5% or more below minimum"
                                   }

VEbusStatusDict = {
                   0:"OFF",
                   1:"Low Power",
                   2:"Fault",
                   3:"Bulk Charging",
                   4:"Absorption Charging",
                   5:"Float Charging",
                   6:"Storage",
                   7:"Equalize",
                   8:"Passthru",
                   9:"Inverting",
                   10:"Power Assist",
                   256:"Discharging",
                   257:"Sustain"
            }

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
#errorindex = 0

def spacer():
    print(colors.fg.gray, "="*80, sep="")

def modbus_register(address, unit):
    msg     = client.read_input_registers(address, unit=unit)
    decoder = BinaryPayloadDecoder.fromRegisters(msg.registers, byteorder=Endian.Big)
    msg     = decoder.decode_16bit_int()
    return msg

try:
    subprocess.call(['resize', '-s', '35', '83'])
except FileNotFoundError:
    pass

print("\033[H\033[J") # Clear screen
print('\033[?25l', end="") # Hide Blinking Cursor
clear = "\033[K\033[1K" # Eliminates screen flashing / blink during refresh
# It clear's to end of line and moves to begining of line then prints

tr = textwrap.TextWrapper(width=56, subsequent_indent=" ")
#errorindex = 0

while True:
    
    print("\033[0;0f") # move to col 0 row 0
    
    screensize = os.get_terminal_size()

    try:
    
    
        BatterySOC    = modbus_register(266,BmvID) / 10
        BatteryWatts  = modbus_register(842, unit=VEsystemID)
        BatteryAmps   = modbus_register(841, unit=VEsystemID) / 10
        BatteryVolts  = modbus_register(259, unit=BmvID) / 100
        
        SolarVolts    = modbus_register(776, unit=SolarChargerID) / 100
        SolarAmps     = modbus_register(777, unit=SolarChargerID) / 10
        SolarWatts    = modbus_register(789, unit=SolarChargerID) /10
        MaxSolarWatts = modbus_register(785, unit=SolarChargerID)
        SolarYield    = modbus_register(784, unit=SolarChargerID) / 10
        SolarState    = modbus_register(775, unit=SolarChargerID)
        
        GridSetPoint  = modbus_register(2700, unit=VEsystemID)
        GridCondition = modbus_register(64, unit=MultiPlusID)
        ACoutHZ       = modbus_register(21, unit=MultiPlusID) / 100
        ACoutVolts    = modbus_register(15, unit=MultiPlusID) / 10
        ACoutAmps     = modbus_register(18, unit=MultiPlusID) / 10
        ACoutWatts    = modbus_register(817, unit=VEsystemID)
        GridHZ        = modbus_register(9, unit=MultiPlusID) / 100
        GridVolts     = modbus_register(3, unit=MultiPlusID) / 10
        GridAmps      = modbus_register(6, unit=MultiPlusID) / 10
        GridWatts     = modbus_register(820, unit=VEsystemID)
        
        ESSsocLimitUser     = modbus_register(2901, unit=VEsystemID) / 10
        ESSsocLimitDynamic  = modbus_register(2903, unit=VEsystemID) / 10
        ESSbatteryLifeState = modbus_register(2900, unit=VEsystemID)
        
        VEbusError  = modbus_register(32, unit=MultiPlusID)
        VEbusStatus = modbus_register(31, unit=MultiPlusID)
        
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
        
        # Datetime object containing current date and time
        now = datetime.now()

        # Fri 21 Jan 2022 09:06:57 PM
        dt_string = now.strftime("%a %d %b %Y %r")
        
        print(clear,colors.fg.purple,f"\n Time & Date............. {dt_string}", sep="")
        
# ===========================================================================================                
        # Battery value color
        if BatterySOC >= 60:
            print(clear,colors.fg.cyan,f" Battery SOC............. ",colors.bold, colors.fg.green,f"{BatterySOC:.1f}", " %", colors.reset, sep="")
        elif BatterySOC >= 30 and BatterySOC < 60:
            print(clear,colors.fg.cyan,f" Battery SOC............. ",colors.bold, colors.fg.yellow,f"{BatterySOC:.1f}", " %", colors.reset, sep="")
        elif BatterySOC < 30:
            print(clear,colors.fg.cyan,f" Battery SOC............. ",colors.bold, colors.fg.red,f"{BatterySOC:.1f}", " %", colors.reset, sep="")

        print(clear,colors.fg.cyan,f" Battery Watts........... {BatteryWatts:.0f}", sep="")
        
        print(clear,colors.fg.cyan,f" Battery Amps............ {BatteryAmps:.1f}", sep="")
        
        print(clear,colors.fg.cyan,f" Battery Volts........... {BatteryVolts:.2f}", colors.reset, sep="")
        
        spacer()

        print(clear,colors.fg.orange,f" PV Watts................ {SolarWatts:.0f}", sep="")
        
        print(clear,f" PV Amps................. {SolarAmps:.2f}", sep="")
        
        print(clear,f" PV Volts................ {SolarVolts:.2f}", sep="")
        
        print(clear,f" Max PV Watts Today...... {MaxSolarWatts}", sep="")
        
        print(clear,f" PV Yield Today.......... {SolarYield:.3f} kWh", sep="")
        
        
        print(clear,f" PV Charger State........ {SolarStateDict[SolarState]}", sep="")


        spacer()
        #print("\033[K", end="")
        print(clear,colors.fg.green,f" Grid Set Point Watts.... {GridSetPoint}", sep="")
        
        print(clear,f" Grid Watts.............. {GridWatts:.0f}\t\tAC Output Watts......... {ACoutWatts}", sep="")
        
        print(clear,f" Grid Amps............... {GridAmps:.1f}\t\tAC Output Amps.......... {ACoutAmps:.1f}", sep="")
        
        print(clear,f" Grid Volts ............. {GridVolts:.1f}\t\tAC Output Volts......... {ACoutVolts:.1f}", sep="")
        
        print(clear,f" Grid Freq .............. {GridHZ:.1f}\t\tAC Output Freq.......... {ACoutHZ:.1f}",sep="")


        if GridCondition == 0:
            print(clear,colors.fg.green,f" Grid Condition.......... OK", sep="")
        if GridCondition == 1:
            print(clear,colors.fg.light_red,f" Grid Condition ......... Grid LOST", colors.reset, sep="")
        
        spacer()
                
        
        
# ===========================================================================================
#   VE.Bus Status
        #VEbusStatus = 2
        print(clear,colors.fg.light_blue, end="", sep="")
        
        if VEbusStatus == 2:
            print(clear,f" System State............ ",colors.fg.red,f"{VEbusStatusDict[VEbusStatus]}", sep="")
           
        else:
            print(clear,colors.fg.light_blue,f" System State............ {VEbusStatusDict[VEbusStatus]}",sep="")
        #
# ===========================================================================================
# VEbus Error
        
        #error_nos = [0,1,2,3,4,5,6,7,10,14,16,17,18,22,24,25,26]
        #VEbusError = error_nos[errorindex] # Test VEbusError's
        #VEbusError = 0
        print(clear,colors.fg.light_blue, end="", sep="")
        
        if VEbusError == 0:
            print(clear,f" VE.Bus Error............ ",colors.fg.green, "No Error", sep="")
        else:
            #print(clear)
            print(clear,f" VE.Bus Error............ ",colors.fg.red, tr.fill(f"{VEbusErrorDict[VEbusError]}"),"\033[K", sep="") #   \033[K    erase to end of line
        
        #errorindex += 1
        #if errorindex == len(error_nos):
        #    errorindex = 0
        
# ===========================================================================================
#   ESS Info

        if ESS_Info.lower() == "y":


            if ESSbatteryLifeState >= 1 and ESSbatteryLifeState <= 8:
                print(clear,colors.fg.light_blue,f" ESS SOC Limit (User).... {ESSsocLimitUser:.0f}% Unless Grid Fails ", sep="")
                
                # Requires Newer GX Firmware such as 2.82~4 or >
                try:
                    ESSsocLimitDynamic = client.read_input_registers(2903, unit=VEsystemID)
                    decoder = BinaryPayloadDecoder.fromRegisters(ESSsocLimitDynamic.registers, byteorder=Endian.Big)
                    ESSsocLimitDynamic = decoder.decode_16bit_uint()
                    ESSsocLimitDynamic = ESSsocLimitDynamic / 10
                    print(clear,colors.fg.light_blue,f" ESS SOC Limit (Dynamic). {ESSsocLimitDynamic:.0f}%", sep="")

                except AttributeError:
                    print(clear,colors.fg.light_blue," ESS SOC Limit (Dynamic). No Value, Firmware requires. Venus OS > v2.82~4", sep="")

                print(clear,colors.fg.light_blue," ESS Mode ............... Optimized (With Battery Life)", sep="")
            
            elif ESSbatteryLifeState == 9:
                print(clear,colors.fg.light_blue," ESS Mode................ Keep Batteries Charged Mode Enabled", sep="")


            elif ESSbatteryLifeState >= 10 and ESSbatteryLifeState <= 12:
                print(clear,colors.fg.light_blue,f" ESS SOC Limit (User).... {ESSsocLimitUser:.0f}% Unless Grid Fails", sep="")
                print(clear,colors.fg.light_blue," ESS Mode ............... Optimized (Without Battery Life)", sep="")

            
            if ESSbatteryLifeState != 9:
                print(clear,colors.fg.light_blue,f" ESS Battery State....... {ESSbatteryLifeStateDict[ESSbatteryLifeState]}", sep="")

# ===========================================================================================
                
            
        spacer()
        
        ###############################################
        ### Begin Cerbo GX Analog Temperature Inputs ##
        ###############################################
        Sens1 = "Battery Box"
        Sens2 = "Cabin"
        Sens3 = "Outside"
        
        if Analog_Inputs.lower() == "y":

            if TempSensor1 == 777:
                print(clear,colors.fg.pink,f" Temp Sensor 1........... Not installed or unit ID wrong", sep="")
            elif TempSensor1 > 49 and TempSensor1 < 120 :
                print(clear,colors.fg.pink, f" {Sens1} Temp........ {TempSensor1:.1f} °F",colors.fg.red, " Whew...its a tad warm in here", sep="")
            else:
                print(clear,colors.fg.pink, f" {Sens1} Temp........ {TempSensor1:.1f} °F ", sep="")
                
            if TempSensor2 == 777:
                print(clear,colors.fg.pink," Temp Sensor 2........... Not installed or unit ID wrong", sep="")
            
            elif TempSensor2 < 45:
                print(clear,colors.fg.pink,f" {Sens2} Temp.............. {TempSensor2:.1f} °F",colors.fg.blue, " Whoa!..Crank up the heat in this place!", sep="")
               
            else:
                print(clear,colors.fg.pink,f" {Sens2} Temp.............. {TempSensor2:.1f} °F", sep="")

            if TempSensor3 == 777:
                print(clear,colors.fg.pink," Temp Sensor 3........... Not installed or unit ID wrong",colors.reset, sep="")
            
            elif TempSensor3 < 33:
                print(clear,colors.fg.pink,f" {Sens3} Temp............ {TempSensor3:.1f} °F",colors.fg.blue, " Burr...A Wee Bit Chilly Outside",colors.reset, sep="")

            else:
                print(clear,colors.fg.pink,f" {Sens3} Temp............ {TempSensor3:.1f} °F",colors.reset, sep="")
                    
        
        print(clear,colors.fg.gray,"\n\tCtrl+C  To Quit",colors.reset)       
        ###############################################
        ### End Cerbo GX Analog Temperature Inputs   ##
        ############################################### 
        
        time.sleep(RefreshRate)
        if screensize != os.get_terminal_size():
            print("\033[H\033[J") # Clear screen
        
        #if VEbusError != 0:
            #print("\033[H\033[J") # Clear screen
         #   print(clear)
        #os.system('clear')



    except KeyboardInterrupt:
        print(clear)
        print("\033[J")
        print(colors.reset)
        print('\033[?25h', end="") # Restore Blinking Cursor
        
        sys.exit(0)

    except AttributeError:
        continue
