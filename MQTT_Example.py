#!/usr/bin/python3

import paho.mqtt.client as mqtt
import paho.mqtt.publish as mqttpublish
import json
from datetime import datetime
import sys
import os
import time
import textwrap
import subprocess

VRMid = "XXXXXXXXXXXX"
ip = '192.168.20.156'
'''
 This script depends on the following Victron equipment. BMV, Multiplus with ESS, Solar Charger, Venus GX device.
 MQTT must be enabled in the Venus GX device
 You shouldnt have to change anything but some variables to make this work with your system
 provided you actually have the requisite victron equipment.

==========================================================
                 Change the Variables Below
==========================================================
==========================================================
'''
Analog_Inputs = 'y'  # Y or N (case insensitive) to display Gerbo GX Analog Temperature inputs
ESS_Info      = 'y' # Y or N (case insensitive) to display ESS system information
ip            = "192.168.20.156" # ip address of GX device or if on venus local try localhost

# Value Refresh Rate in seconds
RefreshRate = 1

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
MQTT_TempSensor1_ID    = 24
MQTT_TempSensor2_ID    = 25
MQTT_TempSensor3_ID    = 26
#===================================
# Temp Sensors Name
Sens1 = "Battery Box"
Sens2 = "Cabin"
Sens3 = "Outside"
'''
==========================================================
                Change the Variables Above
==========================================================
==========================================================
'''
#===================================
SolarState          = None
SolarVolts          = None
SolarWatts          = None
SolarAmps           = None
SolarYield          = None
ESSbatteryLifeState = None

tr = textwrap.TextWrapper(width=56, subsequent_indent=" ")
print("\033[H\033[J") # Clear screen
print('\033[?25l', end="") # Hide Blinking Cursor
clear = "\033[K\033[1K" # Eliminates screen flashing / blink during refresh
                        # It clear's to end of line and moves to begining of line then prints
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Begin MQTT Section
# All the topics you want to subscripbe to
def on_connect(client, userdata, flags, rc):
    global flag_connected
    flag_connected = 1
    print(f"\033[38;5;130mConnected to Broker {ip} with result code {str(rc)}\033[0m")

    topics = [
                ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/State",0),
                ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Pv/V",0),
                ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Yield/Power",0),
                ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Dc/0/Current",0),
                ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/History/Daily/0/Yield",0),
                ("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/History/Daily/0/MaxPower",0),
                ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Alarms/GridLost",0),
                ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L1/V",0),
                ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L1/I",0),
                ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L1/F",0),
                ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L1/V",0),
                ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L1/I",0),
                ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L1/F",0),
                ("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/VebusError",0),
                ("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Soc",0),
                ("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Dc/0/Power",0),
                ("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Dc/0/Current",0),
                ("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Dc/0/Voltage",0),
                ("N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Ac/Consumption/L1/Power",0),
                ("N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Ac/Grid/L1/Power",0),
                ("N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/SystemState/State",0),
                ("N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/State",0),
                ("N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/MinimumSocLimit",0),
                ("N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/SocLimit",0),
                ("N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/AcPowerSetPoint",0),
                ("N/"+VRMid+"/temperature/"+str(MQTT_TempSensor1_ID)+"/Temperature",0),
                ("N/"+VRMid+"/temperature/"+str(MQTT_TempSensor2_ID)+"/Temperature",0),
                ("N/"+VRMid+"/temperature/"+str(MQTT_TempSensor3_ID)+"/Temperature",0)
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
        
        print(f"\033[38;5;196mUnexpected Disconnect \033[0m")
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
    #===================================
    # Uncomment to watch all messages come in via terminal output.
    #NEW_message = json.loads(msg.payload)['value']
    #NEW_message = NEW_message['value']
    #print(f"{str(NEW_message): <60} {msg.topic}")
#===================================
    
    
    
    global  BatterySOC, BatteryWatts, BatteryAmps, BatteryVolts, SolarVolts, SolarAmps, SolarWatts, MaxSolarWatts, SolarYield,  \
            SolarState, GridSetPoint, GridCondition, ACoutHZ, ACoutVolts, ACoutAmps, ACoutWatts, GridHZ, GridVolts, GridAmps,  \
            GridWatts, ESSsocLimitUser, ESSsocLimitDynamic, ESSbatteryLifeState, VEbusError, VEbusStatus, \
            TempSensor1, TempSensor2, TempSensor3


#===================================
    # Uncomment to watch all messages come in via terminal output.
    #NEW_message = json.loads(msg.payload)['value']
    #print(f"{str(NEW_message): <60} {msg.topic}")
#===================================

    try:
#Solar Charge Controller
        if msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/State":
            SolarState = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Pv/V":
            SolarVolts = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Yield/Power":
            SolarWatts = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Dc/0/Current":
            SolarAmps = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/History/Daily/0/Yield":
            SolarYield = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/History/Daily/0/MaxPower":
            MaxSolarWatts = json.loads(msg.payload)["value"]
# Multiplus
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Alarms/GridLost":
            GridCondition = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L1/V":
            GridVolts = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L1/I":
            GridAmps = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/ActiveIn/L1/F":
            GridHZ = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L1/V":
            ACoutVolts = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L1/I":
            ACoutAmps = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Ac/Out/L1/F":
            ACoutHZ = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/VebusError":
            VEbusError = json.loads(msg.payload)["value"]
# BMV
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Soc":
            BatterySOC = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Dc/0/Power":
            BatteryWatts = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Dc/0/Current":
            BatteryAmps = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/Dc/0/Voltage":
            BatteryVolts = json.loads(msg.payload)["value"]
#V.E. Bus
        elif msg.topic == "N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Ac/Consumption/L1/Power":
            ACoutWatts = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/Ac/Grid/L1/Power":
            GridWatts = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/SystemState/State":
            VEbusStatus = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/State":
            ESSbatteryLifeState = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/MinimumSocLimit":
            ESSsocLimitUser = json.loads(msg.payload)["value"]
        elif msg.topic == "N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/BatteryLife/SocLimit":
            ESSsocLimitDynamic = json.loads(msg.payload)["value"]
            if ESSsocLimitDynamic <= ESSsocLimitUser: # The ESS value will never be below the user value in the "Remote Console"
                ESSsocLimitDynamic = ESSsocLimitUser
            # https://energytalk.co.za/t/possible-to-manually-change-active-soc-limit-on-victron/294?page=2
        elif msg.topic == "N/"+VRMid+"/settings/"+str(MQTT_VEsystem_ID)+"/Settings/CGwacs/AcPowerSetPoint":
            GridSetPoint = json.loads(msg.payload)["value"]
#Temp Sensors
        elif msg.topic == "N/"+VRMid+"/temperature/"+str(MQTT_TempSensor1_ID)+"/Temperature":
            TempSensor1 = json.loads(msg.payload)["value"] * 1.8 + 32
        elif msg.topic == "N/"+VRMid+"/temperature/"+str(MQTT_TempSensor2_ID)+"/Temperature":
            TempSensor2 = json.loads(msg.payload)["value"] * 1.8 + 32
        elif msg.topic == "N/"+VRMid+"/temperature/"+str(MQTT_TempSensor3_ID)+"/Temperature":
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
#time.sleep(.25) # time to let the keep alive publish resend all values

mqtt_list = [None]
timerstart = time.time()
while None in mqtt_list: # Wait for each list item to have a value other than None. Repopulate list on each loop.
# Not every mqtt variable needs to be verified as once these have been checked all mqtt variables should be populated.
    timerexpired = time.time()
    mqtt_list = [ESSbatteryLifeState, SolarState, SolarVolts, SolarWatts, SolarAmps, SolarYield]
    time.sleep(.01)
    if timerexpired > timerstart + 30: # set this to the keep alive time on the GX device
                                        # because all values would have been sent at that point
        print(f"\033[48;5;197mSome or all MQTT values not Received\033[0m")
        # If we cant get the values in mqtt_list something went wrong with retreiving the MQTT values. Max time would be the keep alive time
        sys.exit()


finish=time.monotonic_ns()
duration = finish -  start
print('\033[38;5;26m'f"Received MQTT messages in {duration//1000000}ms"'\033[0m')
print(f"\033[38;5;28mLoading User Interface\033[0m")


# End MQTT Section
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#===================================
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
#===================================

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
                           5: "Discharge Disabled. SoC below BatteryLife Dynamic SoC",
                           6: "SoC has been below SoC limit for more than 24 hours. Slow Charging battery",
                           7: "Multi is in sustain mode",
                           8: "Recharge, SOC dropped 5% or more below MinSOC",
                           9: "Keep batteries charged mode enabled",
                           10:"Self consumption, SoC at or above minimum SoC",
                           11:"Discharge Disabled (Low SoC), SoC is below minimum SoC",
                           12:"Recharge, SOC dropped 5% or more below minimum"
                                   }

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
                    252:"External Control",
                    256:"Discharging",
                    257:"Sustain",
                    258:"Recharging",
                    259:"Scheduled Charge"
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

try:
    subprocess.call(['resize', '-s', '35', '83'])
except FileNotFoundError:
    pass

#errorindex = 0

while True:
    print("\033[0;0f") # move to col 0 row 0
    screensize = os.get_terminal_size()


    try:



        if Analog_Inputs.lower() == "y":
            try:
                TempSensor1
            except AttributeError:
                TempSensor1 = 777

            try:
                TempSensor2
            except AttributeError:
                TempSensor2 = 777

            try:
                TempSensor3
            except AttributeError:
                TempSensor3 = 777

        # Datetime object containing current date and time
        now = datetime.now()

        # Fri 21 Jan 2022 09:06:57 PM
        dt_string = now.strftime("%a %d %b %Y %r")

        print(clear,colors.fg.purple,f"\n Time & Date............. {dt_string}", sep="")

#===========================================================================================
# Display Section
        # Battery value color
        if BatterySOC >= 60:
            BatteryColor = colors.fg.green
        elif BatterySOC >= 30 and BatterySOC < 60:
            BatteryColor = colors.fg.yelleow
        elif BatterySOC < 30:
            BatteryColor = colors.fg.red
        print(clear,colors.fg.cyan,f" Battery SOC............. ",colors.bold, colors.fg.green,f"{BatterySOC:.1f}", " %", colors.reset, sep="")
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

        print(clear,colors.fg.green,f" Grid Set Point Watts.... {GridSetPoint}", sep="")
        print(clear,f" Grid Watts.............. {GridWatts:.0f}\t\tAC Output Watts......... {ACoutWatts}", sep="")
        print(clear,f" Grid Amps............... {GridAmps:.1f}\t\tAC Output Amps.......... {ACoutAmps:.1f}", sep="")
        print(clear,f" Grid Volts ............. {GridVolts:.1f}\t\tAC Output Volts......... {ACoutVolts:.1f}", sep="")
        print(clear,f" Grid Freq .............. {GridHZ:.1f}\t\tAC Output Freq.......... {ACoutHZ:.1f}",sep="")

        if GridCondition == 0:
            GC = "OK"
            GC_Color = colors.fg.green
        if GridCondition == 1:
            GC = "Grid LOST"
            GC_Color = colors.fg.light_red
        print(clear,f"{GC_Color} Grid Condition.......... {GC}", sep="")
        spacer()
#===========================================================================================
#   VE.Bus Status
        #VEbusStatus = 2
        print(clear,colors.fg.light_blue, end="", sep="")
        if VEbusStatus == 2:
            VEbusStatus_Color = colors.fg.red
        else:
            VEbusStatus_Color = colors.fg.light_blue
        print(clear,f" System State............ {VEbusStatus_Color}{VEbusStatusDict[VEbusStatus]}", sep="")
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
                print(clear,colors.fg.light_blue,f" ESS SOC Limit (Dynamic). {ESSsocLimitDynamic:.0f}%", sep="")
                print(clear,colors.fg.light_blue,f" ESS Mode ............... Optimized (With Battery Life)", sep="")

            elif ESSbatteryLifeState == 9:
                print(clear,colors.fg.light_blue,f" ESS Mode................ Keep Batteries Charged Mode Enabled", sep="")


            elif ESSbatteryLifeState >= 10 and ESSbatteryLifeState <= 12:
                print(clear,colors.fg.light_blue,f" ESS SOC Limit (User).... {ESSsocLimitUser:.0f}% Unless Grid Fails", sep="")
                print(clear,colors.fg.light_blue,f" ESS Mode ............... Optimized (Without Battery Life)", sep="")


            if ESSbatteryLifeState != 9:
                print(clear,colors.fg.light_blue,f" ESS Battery State....... {ESSbatteryLifeStateDict[ESSbatteryLifeState]}", sep="")

# ===========================================================================================
        ###############################################
        ### Begin Cerbo GX Analog Temperature Inputs ##
        ###############################################

        spacer()
        if Analog_Inputs.lower() == "y":

            if TempSensor1 == 777:
                print(clear,colors.fg.pink,f" Temp Sensor 1........... Not installed or unit ID wrong", sep="")
            elif TempSensor1 >= 50:
                print(clear,colors.fg.pink, f" {Sens1} Temp........ {TempSensor1:.1f} °F",colors.fg.red, " Whew...its a tad warm in here", sep="")
            else:
                print(clear,colors.fg.pink, f" {Sens1} Temp........ {TempSensor1:.1f} °F ", sep="")

            if TempSensor2 == 777:
                print(clear,colors.fg.pink," Temp Sensor 2........... Not installed or unit ID wrong", sep="")

            elif TempSensor2 < 40:
                print(clear,colors.fg.pink,f" {Sens2} Temp.............. {TempSensor2:.1f} °F",colors.fg.blue, " Whoa!..Crank up the heat in this place!", sep="")

            else:
                print(clear,colors.fg.pink,f" {Sens2} Temp.............. {TempSensor2:.1f} °F", sep="")

            if TempSensor3 == 777:
                print(clear,colors.fg.pink," Temp Sensor 3........... Not installed or unit ID wrong",colors.reset, sep="")

            elif TempSensor3 < 33:
                print(clear,colors.fg.pink,f" {Sens3} Temp............ {TempSensor3:.1f} °F",colors.fg.blue, " Burr...A Wee Bit Chilly Outside",colors.reset, sep="")

            else:
                print(clear,colors.fg.pink,f" {Sens3} Temp............ {TempSensor3:.1f} °F",colors.reset, sep="")


        print(clear,colors.fg.gray,"\n\tCtrl✞C  To Quit",colors.reset)
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
        quit()

    except AttributeError:
        continue


