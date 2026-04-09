#!/usr/bin/env python3

import paho.mqtt.client as mqtt
import paho.mqtt.publish as mqttpublish
import json
from datetime import datetime
import os
import time
import textwrap
import subprocess

# User-configurable variables
VRMid = "xxxxxxxxxxx"  # Replace with your actual VRM ID
ip = "192.168.20.156"  # IP address of GX device or localhost
Analog_Inputs = 'n'    # Y or N (case insensitive) to display Cerbo GX Analog Temperature inputs
ESS_Info = 'n'         # Y or N (case insensitive) to display ESS system information
RefreshRate = 1        # Value Refresh Rate in seconds

# MQTT Instance IDs (from VRM or CCGX-Modbus-TCP-register-list.xlsx Tab #2)
MQTT_SolarCharger_1_ID = 279
MQTT_SolarCharger_2_ID = 280
MQTT_SolarCharger_3_ID = 288
MQTT_MultiPlus_ID = 276
MQTT_Bmv_ID = 277
MQTT_VEsystem_ID = 0
MQTT_TempSensor1_ID = 24
MQTT_TempSensor2_ID = 25
MQTT_TempSensor3_ID = 26

# Temp Sensors Names
Sens1 = "Battery Box"
Sens2 = "Cabin"
Sens3 = "Outside"

# Global variables for MQTT data
SolarState = None
SolarVolts = None
SolarWatts = None
SolarAmps = None
SolarYield = None
MaxSolarWatts = None
GridCondition = None
GridVolts = None
GridAmps = None
GridHZ = None
ACoutVolts = None
ACoutAmps = None
ACoutHZ = None
VEbusError = None
BatterySOC = None
BatteryWatts = None
BatteryAmps = None
BatteryVolts = None
ACoutWatts = None
GridWatts = None
VEbusStatus = None
ESSbatteryLifeState = None
ESSsocLimitUser = None
ESSsocLimitDynamic = None
GridSetPoint = None
TempSensor1 = None
TempSensor2 = None
TempSensor3 = None

tr = textwrap.TextWrapper(width=56, subsequent_indent=" ")
print("\033[H\033[J")  # Clear screen
print('\033[?25l', end="")  # Hide Blinking Cursor
clear = "\033[K\033[1K"  # Clear line to prevent screen flashing

# MQTT Section
flag_connected = 0

def on_connect(client, userdata, flags, rc, properties=None):
    global flag_connected
    flag_connected = 1
    print(f"\033[38;5;130mConnected to Broker {ip} with result code {str(rc)}\033[0m")

    topics = [
        ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/State", 0),
        ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Pv/V", 0),
        ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Yield/Power", 0),
        ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Dc/0/Current", 0),
        ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/History/Daily/0/Yield", 0),
        ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/History/Daily/0/MaxPower", 0),
        ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Alarms/GridLost", 0),
        ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L1/V", 0),
        ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L1/I", 0),
        ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L1/F", 0),
        ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L1/V", 0),
        ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L1/I", 0),
        ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L1/F", 0),
        ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/VebusError", 0),
        ("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Soc", 0),
        ("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Dc/0/Power", 0),
        ("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Dc/0/Current", 0),
        ("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Dc/0/Voltage", 0),
        ("N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Ac/Consumption/L1/Power", 0),
        ("N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Ac/Grid/L1/Power", 0),
        ("N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/SystemState/State", 0),
        ("N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/State", 0),
        ("N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/MinimumSocLimit", 0),
        ("N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/SocLimit", 0),
        ("N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/AcPowerSetPoint", 0),
        ("N/"+VRMid+"/temperature/"+str(MQTT_TempSensor1_ID)+"/Temperature", 0),
        ("N/"+VRMid+"/temperature/"+str(MQTT_TempSensor2_ID)+"/Temperature", 0),
        ("N/"+VRMid+"/temperature/"+str(MQTT_TempSensor3_ID)+"/Temperature", 0)
    ]

    client.subscribe(topics)
    print("\033[38;5;127mReceiving MQTT Broker Messages\033[0m")

def on_disconnect(client, userdata, flags, rc, properties=None):
    global flag_connected
    flag_connected = 0
    RC = {5: "Connection Refused", 6: "Connection Not Found", 7: "Connection Lost"}
    if rc != 0:
        print(f"\033[38;5;196mUnexpected Disconnect \033[0m")
        print(f"Disconnect Code {rc} {RC.get(rc, 'Unknown')}")
        print(f"\033[38;5;196mTrying to Reconnect....\033[0m")
        try:
            client.reconnect()
        except ConnectionRefusedError:
            print(f"Connection Refused Error...Retrying")
        except TimeoutError:
            print(f"Connection Timeout Error...Retrying")
    else:
        client.loop_stop()
        print(f"\033[38;5;148mStopping MQTT Loop")
        print(f"Disconnect Result Code {str(rc)}\033[0m\n")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload)
        value = payload.get('value', None)
        if value is None:
            print(f"No 'value' field in payload for topic {msg.topic}: {payload}")
            return
        #print(f"Received: {value: <60} Topic: {msg.topic}")
        if msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/State":
            global SolarState
            SolarState = value
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Pv/V":
            global SolarVolts
            SolarVolts = value
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Yield/Power":
            global SolarWatts
            SolarWatts = value
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Dc/0/Current":
            global SolarAmps
            SolarAmps = value
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/History/Daily/0/Yield":
            global SolarYield
            SolarYield = value
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/History/Daily/0/MaxPower":
            global MaxSolarWatts
            MaxSolarWatts = value
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Alarms/GridLost":
            global GridCondition
            GridCondition = value
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L1/V":
            global GridVolts
            GridVolts = value
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L1/I":
            global GridAmps
            GridAmps = value
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L1/F":
            global GridHZ
            GridHZ = value
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L1/V":
            global ACoutVolts
            ACoutVolts = value
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L1/I":
            global ACoutAmps
            ACoutAmps = value
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L1/F":
            global ACoutHZ
            ACoutHZ = value
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/VebusError":
            global VEbusError
            VEbusError = value
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Soc":
            global BatterySOC
            BatterySOC = value
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Dc/0/Power":
            global BatteryWatts
            BatteryWatts = value
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Dc/0/Current":
            global BatteryAmps
            BatteryAmps = value
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Dc/0/Voltage":
            global BatteryVolts
            BatteryVolts = value
        elif msg.topic == "N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Ac/Consumption/L1/Power":
            global ACoutWatts
            ACoutWatts = value
        elif msg.topic == "N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Ac/Grid/L1/Power":
            global GridWatts
            GridWatts = value
        elif msg.topic == "N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/SystemState/State":
            global VEbusStatus
            VEbusStatus = value
        elif msg.topic == "N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/State":
            global ESSbatteryLifeState
            ESSbatteryLifeState = value
        elif msg.topic == "N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/MinimumSocLimit":
            global ESSsocLimitUser
            ESSsocLimitUser = value
        elif msg.topic == "N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/SocLimit":
            global ESSsocLimitDynamic
            ESSsocLimitDynamic = value
            if ESSsocLimitDynamic <= ESSsocLimitUser:
                ESSsocLimitDynamic = ESSsocLimitUser
        elif msg.topic == "N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/AcPowerSetPoint":
            global GridSetPoint
            GridSetPoint = value
        elif msg.topic == "N/"+VRMid+"/temperature/"+str(MQTT_TempSensor1_ID)+"/Temperature":
            global TempSensor1
            TempSensor1 = value * 1.8 + 32
        elif msg.topic == "N/"+VRMid+"/temperature/"+str(MQTT_TempSensor2_ID)+"/Temperature":
            global TempSensor2
            TempSensor2 = value * 1.8 + 32
        elif msg.topic == "N/"+VRMid+"/temperature/"+str(MQTT_TempSensor3_ID)+"/Temperature":
            global TempSensor3
            TempSensor3 = value * 1.8 + 32
    except (ValueError, TypeError) as e:
        print(f"Error decoding JSON for topic {msg.topic}: {e}")
        return

# Create MQTT client
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect
client.reconnect_delay_set(min_delay=1, max_delay=60)

# Connect to the broker
print(f"\n\033[38;5;28mTrying to Connect To Broker {ip}\033[0m")
client.connect(ip, 1883, 60)

# Start the loop
start = time.monotonic_ns()
client.loop_start()
mqttpublish.single("R/"+VRMid+"/keepalive", hostname=ip)

# Wait for MQTT data
mqtt_list = [SolarState, SolarVolts, SolarWatts, SolarAmps, SolarYield]
if ESS_Info.lower() == 'y':
    mqtt_list.append(ESSbatteryLifeState)
timerstart = time.time()
while None in mqtt_list:
    timerexpired = time.time()
    mqtt_list = [SolarState, SolarVolts, SolarWatts, SolarAmps, SolarYield]
    if ESS_Info.lower() == 'y':
        mqtt_list.append(ESSbatteryLifeState)
    print(f"Waiting for MQTT data: {mqtt_list}")
    time.sleep(0.01)
    if timerexpired > timerstart + 60:
        print(f"\033[48;5;197mSome or all MQTT values not Received: {mqtt_list}\033[0m")
        sys.exit()

finish = time.monotonic_ns()
duration = finish - start
print('\033[38;5;26m'f"Received MQTT messages in {duration//1000000}ms"'\033[0m')
print(f"\033[38;5;28mLoading User Interface\033[0m")

# Colors class for terminal formatting
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

# Dictionaries for status mapping
SolarStateDict = {
    0: "OFF", 2: "Fault", 3: "Bulk", 4: "Absorption", 5: "Float",
    6: "Storage", 7: "Equalize", 11: "Other Hub-1", 245: "Wake-Up", 252: "EXT Control"
}

ESSbatteryLifeStateDict = {
    0: "Battery Life Disabled", 1: "Restarting", 2: "Self-consumption",
    3: "Self consumption, SoC exceeds 85%", 4: "Self consumption, SoC at 100%",
    5: "Discharge Disabled. SoC below BatteryLife Dynamic SoC",
    6: "SoC has been below SoC limit for more than 24 hours. Slow Charging battery",
    7: "Multi is in sustain mode", 8: "Recharge, SOC dropped 5% or more below MinSOC",
    9: "Keep batteries charged mode enabled", 10: "Self consumption, SoC at or above minimum SoC",
    11: "Discharge Disabled (Low SoC), SoC is below minimum SoC",
    12: "Recharge, SOC dropped 5% or more below minimum"
}

VEbusStatusDict = {
    0: "OFF", 1: "Low Power", 2: "Fault", 3: "Bulk Charging", 4: "Absorption Charging",
    5: "Float Charging", 6: "Storage", 7: "Equalize", 8: "Passthru", 9: "Inverting",
    10: "Power Assist", 11: "Power Supply Mode", 246: "Repeated Absorption",
    247: "Equalize", 248: "Battery Safe", 249: "Test", 250: "Blocked",
    251: "Test", 252: "External Control", 256: "Discharging", 257: "Sustain",
    258: "Recharging", 259: "Scheduled Charge"
}

VEbusErrorDict = {
    0: "No Error", 1: "Error 1: Device is switched off because one of the other phases in the system has switched off",
    2: "Error 2: New and old types MK2 are mixed in the system",
    3: "Error 3: Not all- or more than- the expected devices were found in the system",
    4: "Error 4: No other device whatsoever detected", 5: "Error 5: Overvoltage on AC-out",
    6: "Error 6: in DDC Program", 7: "VE.Bus BMS connected- which requires an Assistant- but no assistant found",
    8: "Error 8: Ground Relay Test Failed", 9: "VE.Bus Error 9",
    10: "VE.Bus Error 10: System time synchronisation problem occurred",
    11: "Error 11: Relay Test Fault - Installation error or possibly relay failure",
    12: "Error 12: - Config mismatch with 2nd mcu", 13: "VE.Bus Error 13",
    14: "Error 14: Device cannot transmit data", 15: "Error 15 - VE.Bus combination error",
    16: "Error 16: Dongle missing", 17: "Error 17: One of the devices assumed master status because the original master failed",
    18: "Error 18: AC Overvoltage on the output of a slave has occurred while already switched off",
    19: "Error 19 - Slave does not have AC input!", 20: "Error 20: - Configuration mismatch",
    21: "VE.Bus Error 21", 22: "Error 22: This device cannot function as slave",
    23: "VE.Bus Error 23", 24: "Error 24: Switch-over system protection initiated",
    25: "Error 25: Firmware incompatibility. The firmware of a connected device is not sufficiently up to date.",
    26: "Error 26: Internal error", 27: "VE.Bus Error 27", 28: "VE.Bus Error 28",
    29: "VE.Bus Error 29", 30: "VE.Bus Error 30", 31: "VE.Bus Error 31", 32: "VE.Bus Error 32"
}

def spacer():
    print(colors.fg.gray, "="*80, sep="")

try:
    subprocess.call(['resize', '-s', '35', '83'])
except FileNotFoundError:
    pass

while True:
    print("\033[0;0f")  # Move to col 0 row 0
    screensize = os.get_terminal_size()

    try:
        if Analog_Inputs.lower() == "y":
            if TempSensor1 is None:
                TempSensor1 = 777
            if TempSensor2 is None:
                TempSensor2 = 777
            if TempSensor3 is None:
                TempSensor3 = 777

        now = datetime.now()
        dt_string = now.strftime("%a %d %b %Y %r")
        print(clear, colors.fg.purple, f"\n Time & Date............. {dt_string}", sep="")

        # Battery value color
        if BatterySOC is not None:
            if BatterySOC >= 60:
                BatteryColor = colors.fg.green
            elif BatterySOC >= 30:
                BatteryColor = colors.fg.yellow
            else:
                BatteryColor = colors.fg.red
        else:
            BatteryColor = colors.fg.red

        print(clear, colors.fg.cyan, f" Battery SOC............. ", BatteryColor, f"{BatterySOC:.1f}" if BatterySOC is not None else "N/A", " %", colors.reset, sep="")
        print(clear, colors.fg.cyan, f" Battery Watts........... {BatteryWatts:.0f}" if BatteryWatts is not None else "N/A", sep="")
        print(clear, colors.fg.cyan, f" Battery Amps............ {BatteryAmps:.1f}" if BatteryAmps is not None else "N/A", sep="")
        print(clear, colors.fg.cyan, f" Battery Volts........... {BatteryVolts:.2f}" if BatteryVolts is not None else "N/A", colors.reset, sep="")
        spacer()

        print(clear, colors.fg.orange, f" PV Watts................ {SolarWatts:.0f}" if SolarWatts is not None else "N/A", sep="")
        print(clear, f" PV Amps................. {SolarAmps:.2f}" if SolarAmps is not None else "N/A", sep="")
        print(clear, f" PV Volts................ {SolarVolts:.2f}" if SolarVolts is not None else "N/A", sep="")
        print(clear, f" Max PV Watts Today...... {MaxSolarWatts}" if MaxSolarWatts is not None else "N/A", sep="")
        print(clear, f" PV Yield Today.......... {SolarYield:.3f} kWh" if SolarYield is not None else "N/A", sep="")
        print(clear, f" PV Charger State........ {SolarStateDict.get(SolarState, 'Unknown')}" if SolarState is not None else "N/A", sep="")
        spacer()

        print(clear, colors.fg.green, f" Grid Set Point Watts.... {GridSetPoint}" if GridSetPoint is not None else "N/A", sep="")
        print(clear, f" Grid Watts.............. {GridWatts:.0f}\t\tAC Output Watts......... {ACoutWatts}" if ACoutWatts is not None else 'N/A', sep="")
        print(clear, f" Grid Amps............... {GridAmps:.1f}\t\tAC Output Amps.......... {ACoutAmps:.1f}" if ACoutAmps is not None else 'N/A', sep="")
        print(clear, f" Grid Volts ............. {GridVolts:.1f}\t\tAC Output Volts......... {ACoutVolts:.1f}" if ACoutVolts is not None else 'N/A', sep="")
        print(clear, f" Grid Freq .............. {GridHZ:.1f}\t\tAC Output Freq.......... {ACoutHZ:.1f}" if ACoutHZ is not None else 'N/A', sep="")

        if GridCondition == 0:
            GC = "OK"
            GC_Color = colors.fg.green
        elif GridCondition == 1:
            GC = "Grid LOST"
            GC_Color = colors.fg.light_red
        else:
            GC = "Unknown"
            GC_Color = colors.fg.red
        print(clear, f"{GC_Color} Grid Condition.......... {GC}", sep="")
        spacer()

        # VE.Bus Status
        print(clear, colors.fg.light_blue, end="", sep="")
        VEbusStatus_Color = colors.fg.red if VEbusStatus == 2 else colors.fg.light_blue
        print(clear, f" System State............ {VEbusStatus_Color}{VEbusStatusDict.get(VEbusStatus, 'Unknown') if VEbusStatus is not None else 'N/A'}", sep="")

        # VE.Bus Error
        if VEbusError == 0:
            print(clear, f" VE.Bus Error............ ", colors.fg.green, "No Error", sep="")
        else:
            print(clear, f" VE.Bus Error............ ", colors.fg.red, tr.fill(f"{VEbusErrorDict.get(VEbusError, 'Unknown') if VEbusError is not None else 'N/A'}"), "\033[K", sep="")

        # ESS Info
        if ESS_Info.lower() == "y":
            if ESSbatteryLifeState is not None and 1 <= ESSbatteryLifeState <= 8:
                print(clear, colors.fg.light_blue, f" ESS SOC Limit (User).... {ESSsocLimitUser:.0f}% Unless Grid Fails" if ESSsocLimitUser is not None else "N/A", sep="")
                print(clear, colors.fg.light_blue, f" ESS SOC Limit (Dynamic). {ESSsocLimitDynamic:.0f}%" if ESSsocLimitDynamic is not None else "N/A", sep="")
                print(clear, colors.fg.light_blue, f" ESS Mode ............... Optimized (With Battery Life)", sep="")
            elif ESSbatteryLifeState == 9:
                print(clear, colors.fg.light_blue, f" ESS Mode................ Keep Batteries Charged Mode Enabled", sep="")
            elif ESSbatteryLifeState is not None and 10 <= ESSbatteryLifeState <= 12:
                print(clear, colors.fg.light_blue, f" ESS SOC Limit (User).... {ESSsocLimitUser:.0f}% Unless Grid Fails" if ESSsocLimitUser is not None else "N/A", sep="")
                print(clear, colors.fg.light_blue, f" ESS Mode ............... Optimized (Without Battery Life)", sep="")
            if ESSbatteryLifeState != 9:
                print(clear, colors.fg.light_blue, f" ESS Battery State....... {ESSbatteryLifeStateDict.get(ESSbatteryLifeState, 'Unknown') if ESSbatteryLifeState is not None else 'N/A'}", sep="")

        # Temperature Sensors
        if Analog_Inputs.lower() == "y":
            if TempSensor1 == 777:
                print(clear, colors.fg.pink, f" Temp Sensor 1........... Not installed or unit ID wrong", sep="")
            elif TempSensor1 >= 50:
                print(clear, colors.fg.pink, f" {Sens1} Temp........ {TempSensor1:.1f} °F", colors.fg.red, " Whew...its a tad warm in here", sep="")
            else:
                print(clear, colors.fg.pink, f" {Sens1} Temp........ {TempSensor1:.1f} °F ", sep="")

            if TempSensor2 == 777:
                print(clear, colors.fg.pink, " Temp Sensor 2........... Not installed or unit ID wrong", sep="")
            elif TempSensor2 < 40:
                print(clear, colors.fg.pink, f" {Sens2} Temp.............. {TempSensor2:.1f} °F", colors.fg.blue, " Whoa!..Crank up the heat in this place!", sep="")
            else:
                print(clear, colors.fg.pink, f" {Sens2} Temp.............. {TempSensor2:.1f} °F", sep="")

            if TempSensor3 == 777:
                print(clear, colors.fg.pink, " Temp Sensor 3........... Not installed or unit ID wrong", colors.reset, sep="")
            elif TempSensor3 < 33:
                print(clear, colors.fg.pink, f" {Sens3} Temp............ {TempSensor3:.1f} °F", colors.fg.blue, " Burr...A Wee Bit Chilly Outside", colors.reset, sep="")
            else:
                print(clear, colors.fg.pink, f" {Sens3} Temp............ {TempSensor3:.1f} °F", colors.reset, sep="")

        print(clear, colors.fg.gray, "\n\tCtrl+C To Quit", colors.reset)
        time.sleep(RefreshRate)
        if screensize != os.get_terminal_size():
            print("\033[H\033[J")  # Clear screen

    except KeyboardInterrupt:
        print(clear)
        print("\033[J")
        print(colors.reset)
        print('\033[?25h', end="")  # Restore Blinking Cursor
        client.loop_stop()
        client.disconnect()
        quit()
    except AttributeError:
        continue
