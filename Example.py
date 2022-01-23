#!/usr/bin/env python3

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

new_line = '\n'
tab = '\t'
tab3 = '\t\t\t'

# Value Refresh Rate in seconds
RefreshRate = 2

# Instance #'s from Cerbo GX and cross referenced to the unit ID in the Victron TCP-MODbus register xls file.
# https://github.com/victronenergy/dbus_modbustcp/blob/master/CCGX-Modbus-TCP-register-list.xlsx
SolarChargerID = 226
MultiPlusID = 227
BmvID = 223
VEsystemID = 100

# Local network ip address of Cerbo GX. Default port 502
client = ModbusClient('192.168.20.156', port='502')

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

os.system('clear')
print('\033[?25l', end="") # Hide Blinking Cursor






while True:

    try:
        
        # Datetime object containing current date and time
        now = datetime.now()

        # Fri 21 Jan 2022 09:06:57 PM
        dt_string = now.strftime("%a %d %b %Y %r")
        
        print(colors.fg.purple,f"\nTime & Date............. {dt_string}", sep="")
        
        BatterySOC = client.read_input_registers(266, unit=BmvID)
        decoder = BinaryPayloadDecoder.fromRegisters(BatterySOC.registers, byteorder=Endian.Big)
        BatterySOC = decoder.decode_16bit_uint()
        print(colors.fg.cyan,f"Battery SOC............. {BatterySOC / 10:.2f}%🔋", sep="")
        
        ESSsocLimitUser = client.read_input_registers(2901, unit=VEsystemID)
        decoder = BinaryPayloadDecoder.fromRegisters(ESSsocLimitUser.registers, byteorder=Endian.Big)
        ESSsocLimitUser = decoder.decode_16bit_uint()
        print(colors.fg.cyan,f"ESS SOC Limit (User).... {ESSsocLimitUser / 10:.2f}% Unless Grid Fails", sep="")
        
        BatteryWatts = client.read_input_registers(842, unit=VEsystemID)
        decoder = BinaryPayloadDecoder.fromRegisters(BatteryWatts.registers, byteorder=Endian.Big)
        BatteryWatts = decoder.decode_16bit_int()
        print(colors.fg.cyan,f"Battery Watts........... {BatteryWatts:.2f}", sep="")
        
        BatteryAmps = client.read_input_registers(841, unit=VEsystemID)
        decoder = BinaryPayloadDecoder.fromRegisters(BatteryAmps.registers, byteorder=Endian.Big)
        BatteryAmps = decoder.decode_16bit_int()
        print(colors.fg.cyan,f"Battery Amps............ {BatteryAmps / 10:.2f}", sep="")
        
        BatteryVolts = client.read_input_registers(259, unit=BmvID)
        decoder = BinaryPayloadDecoder.fromRegisters(BatteryVolts.registers, byteorder=Endian.Big)
        BatteryVolts = decoder.decode_16bit_uint()
        print(colors.fg.cyan,f"Battery Volts........... {BatteryVolts / 100:.2f}\n", colors.reset, sep="", end="")
        
        print(colors.fg.gray,"="*80, colors.reset, sep="")
        
        SolarVolts = client.read_input_registers(776, unit=SolarChargerID)
        decoder = BinaryPayloadDecoder.fromRegisters(SolarVolts.registers, byteorder=Endian.Big)
        SolarVolts = decoder.decode_16bit_uint()
        print(colors.fg.orange,f"PV Volts................ {SolarVolts / 100:.2f} ⚡", sep="")
        
        SolarAmps = client.read_input_registers(777, unit=SolarChargerID)
        decoder = BinaryPayloadDecoder.fromRegisters(SolarAmps.registers, byteorder=Endian.Big)
        SolarAmps = decoder.decode_16bit_int()
        print(f"PV Amps................. {SolarAmps / 10:.2f}", sep="")
        
        SolarWatts = client.read_input_registers(789, unit=SolarChargerID)
        decoder = BinaryPayloadDecoder.fromRegisters(SolarWatts.registers, byteorder=Endian.Big)
        SolarWatts = decoder.decode_16bit_uint()
        print(f"PV Watts................ {SolarWatts / 10:.0f} 🌞", sep="")
        
        MaxSolarWatts = client.read_input_registers(785, unit=SolarChargerID)
        decoder = BinaryPayloadDecoder.fromRegisters(MaxSolarWatts.registers, byteorder=Endian.Big)
        MaxSolarWatts = decoder.decode_16bit_int()
        print(f"Max PV Watts Today...... {MaxSolarWatts}", sep="")
        
        SolarYield = client.read_input_registers(784, unit=SolarChargerID)
        decoder = BinaryPayloadDecoder.fromRegisters(SolarYield.registers, byteorder=Endian.Big)
        SolarYield = decoder.decode_16bit_int()
        print(f"PV Yield Today.......... {SolarYield / 10:.3f} kWh", sep="")
        
        SolarState = client.read_input_registers(775, unit=SolarChargerID)
        decoder = BinaryPayloadDecoder.fromRegisters(SolarState.registers, byteorder=Endian.Big)
        SolarState = decoder.decode_16bit_int()
        if SolarState == 0:
            print(f"PV Charger State........ OFF", colors.reset, sep="")
        if SolarState == 2:
            print(f"PV Charger State........ Fault", colors.reset, sep="")
        if SolarState == 3:
            print(f"PV Charger State........ Bulk", colors.reset, sep="")
        if SolarState == 4:
            print(f"PV Charger State........ Absorption", colors.reset, sep="")
        if SolarState == 5:
            print(f"PV Charger State........ Float", colors.reset, sep="")
        if SolarState == 6:
            print(f"PV Charger State........ Storage", colors.reset, sep="")
        if SolarState == 7:
            print(f"PV Charger State........ Equalize", colors.reset, sep="")
        if SolarState == 11:
            print(f"PV Charger State........ Other (Hub-1)", colors.reset, sep="")
        if SolarState == 252:
            print(f"PV Charger State........ EXT Control", colors.reset, sep="")
        print(colors.fg.gray,"="*80, colors.reset, sep="")
        
        GridWatts = client.read_input_registers(820, unit=VEsystemID)
        decoder = BinaryPayloadDecoder.fromRegisters(GridWatts.registers, byteorder=Endian.Big)
        GridWatts = decoder.decode_16bit_int()
        print(colors.fg.green,f"Grid Watts.............. {GridWatts}", sep="")
        
        GridAmps = client.read_input_registers(6, unit=MultiPlusID)
        decoder = BinaryPayloadDecoder.fromRegisters(GridAmps.registers, byteorder=Endian.Big)
        GridAmps = decoder.decode_16bit_int()
        print(f"Grid Amps............... {GridAmps / 10}", sep="")
        
        OutWatts = client.read_input_registers(817, unit=VEsystemID)
        decoder = BinaryPayloadDecoder.fromRegisters(OutWatts.registers, byteorder=Endian.Big)
        OutWatts = decoder.decode_16bit_uint()
        print(f"Load AC Watts........... {OutWatts} 💡", colors.reset, sep="")
        
        GridCondition = client.read_input_registers(64, unit=MultiPlusID)
        decoder = BinaryPayloadDecoder.fromRegisters(GridCondition.registers, byteorder=Endian.Big)
        GridCondition = decoder.decode_16bit_uint()
        if GridCondition == 0:
            print(colors.fg.green,f"Grid Condition.......... OK 🆗", sep="")
        if GridCondition == 1:
            print(colors.fg.light_red,f"Grid Condition ......... Grid LOST ❌", colors.reset, sep="")
                
        GridSetPoint = client.read_input_registers(2700, unit=VEsystemID)
        decoder = BinaryPayloadDecoder.fromRegisters(GridSetPoint.registers, byteorder=Endian.Big)
        GridSetPoint = decoder.decode_16bit_int()
        print(colors.fg.green,f"Grid Set Point Watts.... {GridSetPoint}", sep="")
        print(colors.fg.gray,"="*80, colors.reset, sep="")
        
        VEbusStatus = client.read_input_registers(31, unit=MultiPlusID)
        decoder = BinaryPayloadDecoder.fromRegisters(VEbusStatus.registers, byteorder=Endian.Big)
        VEbusStatus = decoder.decode_16bit_uint()
        if VEbusStatus == 3:
            print(colors.fg.light_blue,f"System State............ Bulk Charging 🟡",sep="")
        if VEbusStatus == 4:
            print(colors.fg.light_blue,f"System State............ Absorption Charging 🟡", sep="")
        if VEbusStatus == 5:
            print(colors.fg.light_blue,f"System State............ Float Charging 🟢", sep="")
            
        ESSbatteryLifeState = client.read_input_registers(2900, unit=VEsystemID)
        decoder = BinaryPayloadDecoder.fromRegisters(ESSbatteryLifeState.registers, byteorder=Endian.Big)
        ESSbatteryLifeState = decoder.decode_16bit_uint()
        if ESSbatteryLifeState == 0:
            print(f"ESS Battery Life State.. Battery Life Disabled", sep="")
        if ESSbatteryLifeState == 1:
            print(f"ESS Battery Life State.. Restarting", sep="")
        if ESSbatteryLifeState == 2:
            print(f"ESS Battery Life State.. Self-consumption", sep="")
        if ESSbatteryLifeState == 3:
            print(f"ESS Battery Life State.. Self consumption, SoC exceeds 85%", sep="")
        if ESSbatteryLifeState == 4:
            print(f"ESS Battery Life State.. Self consumption, SoC at 100%", sep="")
        if ESSbatteryLifeState == 5:
            print(f"ESS Battery Life State.. SoC below BatteryLife dynamic SoC limit", sep="")
        if ESSbatteryLifeState == 6:
            print(f"ESS Battery Life State.. SoC has been below SoC limit for more than 24 hours.{new_line}{tab3} Slow Charging battery", sep="")
        if ESSbatteryLifeState == 7:
            print(f"ESS Battery Life State.. Multi is in sustain mode", sep="")
        if ESSbatteryLifeState == 8:
            print(f"ESS Battery Life State.. Recharge, SOC dropped 5% or more below MinSOC", sep="")
        if ESSbatteryLifeState == 9:
            print(f"ESS Battery Life State.. Keep batteries charged mode enabled", sep="")
        if ESSbatteryLifeState == 10:
            print(f"ESS Battery Life State.. Self consumption, SoC at or above minimum SoC", sep="")
        if ESSbatteryLifeState == 11:
            print(f"ESS Battery Life State.. Self consumption, SoC is below minimum SoC", sep="")
        if ESSbatteryLifeState == 12:
            print(f"ESS Battery Life State.. Recharge, SOC dropped 5% or more below minimum SoC", colors.reset, sep="")
                
        print(colors.fg.gray,"="*80, colors.reset, sep="")
        
        ###############################################
        ### Begin Cerbo GX Analog Temperature Inputs ##
        ###############################################
        
        BattBoxTemp = client.read_input_registers(3304, unit= 24) # Input 1
        decoder = BinaryPayloadDecoder.fromRegisters(BattBoxTemp.registers, byteorder=Endian.Big)
        BattBoxTemp = decoder.decode_16bit_int()
        BattBoxTemp = BattBoxTemp / 100 * 1.8 + 32
        if BattBoxTemp > 50:
            print(colors.fg.blue,f"Battery Box Temp........ {BattBoxTemp:.2f} Deg F  🥵", colors.fg.red, " Whew...its a tad warm in here",colors.reset, sep="")
        else:
            print(colors.fg.blue,f"Battery Box Temp........ {BattBoxTemp:.2f} Deg F", sep="")
        
        CabinTemp = client.read_input_registers(3304, unit= 25) # Input 2
        decoder = BinaryPayloadDecoder.fromRegisters(CabinTemp.registers, byteorder=Endian.Big)
        CabinTemp = decoder.decode_16bit_int()
        CabinTemp = CabinTemp / 100 * 1.8 + 32
        if CabinTemp < 45:
            print(colors.fg.blue,f"Cabin Temp.............. {CabinTemp:.2f} Deg F  🥶 Whoa...Crank up the heat in this place!", sep="")
        else:
            print(colors.fg.blue,f"Cabin Temp.............. {CabinTemp:.2f} Deg F", sep="")
        
        ExteriorTemp = client.read_input_registers(3304, unit= 26) # Input 3
        decoder = BinaryPayloadDecoder.fromRegisters(ExteriorTemp.registers, byteorder=Endian.Big)
        ExteriorTemp = decoder.decode_16bit_int()
        ExteriorTemp = ExteriorTemp / 100 * 1.8 + 32
        
        if ExteriorTemp < 33:
            print(colors.fg.blue,f"Outside Temp............ {ExteriorTemp:.2f} Deg F  🥶 Burr...A Wee Bit Chilly Outside", colors.reset, sep="")
        else:
            print(colors.fg.blue,f"Outside Temp............ {ExteriorTemp:.2f} Deg F", colors.reset, sep="")
        print(colors.fg.gray,"="*80, colors.reset, sep="")
        
        ###############################################
        ### End Cerbo GX Analog Temperature Inputs   ##
        ############################################### 
        
        time.sleep(RefreshRate)
        os.system('clear')
        
    except KeyboardInterrupt:
        print(colors.reset)
        print('\033[?25h', end="") # Restore Blinking Cursor
        sys.exit(0)
