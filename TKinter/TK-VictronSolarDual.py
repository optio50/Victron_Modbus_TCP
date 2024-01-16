#!/usr/bin/env python3

##################################################################
# The TKinter files no longer work with the newest Venus firmware
# These files were an example only and are now unmaintained
##################################################################


from tkinter import *
from tkinter import ttk
from itertools import cycle
from tkinter import simpledialog
from tkinter import messagebox
#import tk_tools
#import random
import json
import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as mqttpublish
from pymodbus.constants import Defaults
from pymodbus.constants import Endian
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.payload import BinaryPayloadBuilder
from datetime import datetime
from datetime import timedelta
from time import strftime
from time import gmtime

root = Tk()
#root.iconbitmap(r'/home/chromebox/Scripts/Python/Solar-icon.png')
root.title("Victron Solar")
root.geometry("895x950")
root.configure(bg='black')
icon = PhotoImage(master=root, file='Solar.png')
root.wm_iconphoto(True, icon)



my_menu = Menu(root, bg='grey30', fg='darkgray',activebackground='grey')
root.config(menu=my_menu)

RefreshRate = 1000   # Refresh Rate in mseconds. Auto increased to 1.5 (from 1 second) if LED's enabled For MQTT requests

# Describe the Solar Array
Array1 = "4 X 100W Array" # 4 New Renogy 100W Panels
Array2 = "250W Panel" # Used 250W panel. Typical Ouput 200W

# GX Device I.P Address
ip = '192.168.20.156'

# MQTT Request's are for Multiplus LED state's
# VRM Portal ID from GX device. 
# AFAIK this ID is needed even with no internet access as its the name of your venus device.
# Menu -->> Settings -->> "VRM Online Portal -->> VRM Portal ID"
VRMid = "d41243d31a90"

Analog_Inputs  = 'y'     # Y or N (case insensitive) to display Gerbo GX Analog Temperature inputs
ESS_Info       = 'y'     # Y or N (case insensitive) to display ESS system information


# Unit ID #'s from Cerbo GX.
# Do not confuse UnitID with Instance ID.
# You can also get the UnitID from the GX device. Menu --> Settings --> Services --> ModBusTCP --> Available Services
# https://github.com/victronenergy/dbus_modbustcp/blob/master/CCGX-Modbus-TCP-register-list.xlsx Tab #2
#===================================
# ModBus Unit ID
SolarCharger_1_ID = 226
SolarCharger_2_ID = 224
MultiPlusID       = 227
BmvID             = 223
VEsystemID        = 100
#===================================
# MQTT Instance ID
# This is the Instance ID not to be confused with the above Unit ID.
# Device List in VRM or crossed referenced in the CCGX-Modbus-TCP-register-list.xlsx Tab #2
MQTT_SolarCharger_1_ID = 279
MQTT_SolarCharger_2_ID = 278
MQTT_MultiPlusID       = 276
MQTT_BmvID             = 277
MQTT_VEsystemID        = 0
#===================================


# GX Device I.P Address
ip = '192.168.20.156'
client = ModbusClient(ip, port='502')

# Cycle colors for blinking LED's (Bright / Dark)
blinkred_Temp          = cycle(["red","grey7"])
blinkred_LowBatt       = cycle(["red","grey7"])
blinkred_OverLoad      = cycle(["red","grey7"])
blinkyellow_Bulk       = cycle(["yellow","grey7"])
blinkyellow_Absorption = cycle(["yellow","grey7"])
blinkgreen_Mains       = cycle(["green1","grey7"])
blinkgreen_Inverter    = cycle(["green1","grey7"])
blinkblue_Float        = cycle(["blue","grey7"])

arrow       = cycle(['<','<<','<<<','<<<<'])
BlinkLED = cycle(['on', 'off'])

def Multiplus_Charger():
    client.write_registers(address=33, values=1, unit=MultiPlusID)


def Multiplus_Inverter():
    client.write_registers(address=33, values=2, unit=MultiPlusID)


def Multiplus_On():
    client.write_registers(address=33, values=3, unit=MultiPlusID)


def Multiplus_Off():
    client.write_registers(address=33, values=4, unit=MultiPlusID)



def Charger1():
    if SolarOn1 == 1:
        client.write_registers(address=774, values=4, unit=SolarCharger_1_ID) # Turn Off
        showMessage('Charger #1 Off')
    elif SolarOn1 == 4:
        client.write_registers(address=774, values=1, unit=SolarCharger_1_ID) # Turn On
        showMessage('Charger #1 On')


def Charger2():
    if SolarOn2 == 1:
        client.write_registers(address=774, values=4, unit=SolarCharger_2_ID) # Turn Off
        showMessage('Charger #2 Off')
    elif SolarOn2 == 4:
        client.write_registers(address=774, values=1, unit=SolarCharger_2_ID) # Turn On
        showMessage('Charger #2 On')


def showMessage(message, type='info', timeout=3000, parent=root):
    import tkinter as tk
    from tkinter import messagebox as msgb

    root = tk.Tk()
    root.withdraw()
    try:
        root.after(timeout, root.destroy)
        if type == 'info':
            msgb.showinfo('Info', message, master=root)
        elif type == 'warning':
            msgb.showwarning('Warning', message, master=root)
        elif type == 'error':
            msgb.showerror('Error', message, master=root)
    except:
        pass


def Solar_Current1():
    answer = simpledialog.askinteger("Solar Charger #1 Current Limit", "Enter The New Amps Limit",
                                parent=root,
                                minvalue=0, maxvalue=35)
    if answer is not None:
        mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Settings/ChargeCurrentLimit", payload=json.dumps({"value": answer}), hostname=ip, port=1883)


def Solar_Current2():
    answer = simpledialog.askinteger("Solar Charger #1 Current Limit", "Enter The New Amps Limit",
                                parent=root,
                                minvalue=0, maxvalue=35)
    if answer is not None:
        mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Settings/ChargeCurrentLimit", payload=json.dumps({"value": answer}), hostname=ip, port=1883)


def SetGridWatts():
    watts   = ChangeGridSetPoint.get()
    builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
    builder.reset()
    builder.add_16bit_int(int(watts))
    payload = builder.to_registers()
    client.write_register(2700, payload[0])
    ChangeGridSetPoint.delete(0, END)

def GridFeedIn():
    FeedIn = modbus_register(2707,VEsystemID)
    if FeedIn == 1:
        client.write_register(2707, 0) # Off
    elif FeedIn == 0:
        client.write_register(2707, 1) # On


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

def wait():
    root.after(2000)


def ESSuser():
    answer = simpledialog.askinteger("ESS SOC", "Enter The New ESS SOC %",
                                parent=root,
                                minvalue=0, maxvalue=100) * 10
    if answer is not None:
        client.write_registers(address=2901, values=answer, unit=VEsystemID)
        #ESSsocLimitUser = modbus_register(2901,VEsystemID) / 10
        wait()
        if ESSbatteryLifeState >= 1 and ESSbatteryLifeState <= 8:
            ESSbatteryLifeEnabled()
        elif ESSbatteryLifeState == 10:
            ESSbatteryLifeDisabled()


def ESSbatteryLifeEnabled():
    # for widget in frame4.winfo_children():
        # widget.destroy()
    client.write_registers(address=2900, values=1, unit=VEsystemID)
    wait()

def ESSbatteryLifeDisabled():
    # for widget in frame4.winfo_children():
        # widget.destroy()
    client.write_registers(address=2900, values=10, unit=VEsystemID)
    wait()

def ESSbatteriesCharged():
    # Mode 9 'Keep batteries charged' mode enabled
    client.write_registers(address=2900, values=9, unit=VEsystemID)
    wait()



ess_menu = Menu(my_menu, bg='grey11', fg='dark gray',tearoff=False)
my_menu.add_cascade(label   = "ESS Modes", menu=ess_menu, underline=0)
# Mode 1  Change the ESS mode to "Optimized (BatteryLife Enabled)"
ess_menu.add_command(label = "Optimized (Battery Life Enabled)", command=ESSbatteryLifeEnabled)
ess_menu.add_separator()
# Mode 10  Change the ESS mode to "Optimized (BatteryLife Disabled)"
ess_menu.add_command(label = "Optimized (Battery Life Disabled)", command=ESSbatteryLifeDisabled)
ess_menu.add_separator()
ess_menu.add_command(label = "Keep Batteries Charged", command=ESSbatteriesCharged)
ess_menu.add_separator()
ess_menu.add_command(label = "Change ESS SOC User Limit", command=ESSuser)


multiplus_menu = Menu(my_menu, bg='grey11', fg='dark gray',tearoff=False)
my_menu.add_cascade(label   = "Multiplus Modes", menu=multiplus_menu, underline=0)
multiplus_menu.add_command(label = "Charger Only", command=Multiplus_Charger)
multiplus_menu.add_separator()
multiplus_menu.add_command(label = "Inverter Only", command=Multiplus_Inverter)
multiplus_menu.add_separator()
multiplus_menu.add_command(label = "On", command=Multiplus_On)
multiplus_menu.add_separator()
multiplus_menu.add_command(label = "Off", command=Multiplus_Off)


scc_menu = Menu(my_menu, bg='grey11', fg='dark gray',tearoff=False)
my_menu.add_cascade(label   = "Solar Charger", menu=scc_menu, underline=0)
scc_menu.add_command(label = "Solar Charger #1 On/Off", command=Charger1)
scc_menu.add_separator()
scc_menu.add_command(label = "Solar Charger #2 On/Off", command=Charger2)
scc_menu.add_separator()
scc_menu.add_command(label = "Solar Charger #1 Current Limit", command=Solar_Current1)
scc_menu.add_separator()
scc_menu.add_command(label = "Solar Charger #2 Current Limit", command=Solar_Current2)


def my_mainloop():
    try:
        global SolarOn1
        global SolarOn2
        global ESSbatteryLifeState
        global ESSsocLimitUser
        
        # ===========================================================================================
    #   Conditional MQTT Request's because Multiplus II status LED's are not available with ModbusTCP
    
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
        BatteryState  = modbus_register(844,VEsystemID) # Battery System State 0=idle 1=charging 2=discharging
        BatteryWatts  = modbus_register(842,VEsystemID)
        BatteryAmps   = modbus_register(261,BmvID) / 10
        BatteryVolts  = modbus_register(259,BmvID) / 100
        BatteryTTG    = modbus_register(846,VEsystemID) / .01
        ChargeCycles  = modbus_register(284,BmvID)
        ChargePower   = modbus_register(855,VEsystemID)
        ConsumedAH    = modbus_register(265,BmvID) / -10
        DCsystemPower = modbus_register(860,VEsystemID)
    
    # ===========================================================================================
    
    #   Solar Charge Controller # 1
    
        # MQTT
        SolarChargeLimit1  = mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Settings/ChargeCurrentLimit")
        SolarYield1        = mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/History/Daily/0/Yield")
        SolarName1         = mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Devices/0/ProductName")
    
        # ModBus
        SolarWatts1        = modbus_register(789,SolarCharger_1_ID) / 10
        SolarWatts         = modbus_register(850,VEsystemID)        # Total of all solar chargers
        SolarAmps          = modbus_register(851,VEsystemID) / 10   # Total of all solar chargers
        SolarAmps1         = modbus_register(772,SolarCharger_1_ID) / 10
        SolarVolts1        = modbus_register(776,SolarCharger_1_ID) / 100
        MaxSolarWatts1     = modbus_register(785,SolarCharger_1_ID)
        MaxSolarWattsYest1 = modbus_register(787,SolarCharger_1_ID)
        #SolarYield1        = modbus_register(784,SolarCharger_1_ID) / 10
        #TotalSolarYield    = modbus_register(790,SolarCharger_1_ID) / 10
        SolarYieldYest1    = modbus_register(786,SolarCharger_1_ID) / 10
        SolarOn1           = modbus_register(774,SolarCharger_1_ID)
        SolarOn2           = modbus_register(774,SolarCharger_2_ID)
        SolarState1        = modbus_register(775,SolarCharger_1_ID)
        SolarError1        = modbus_register(788,SolarCharger_1_ID)
    
    
        #SolarError = 20 # Test
        #error_nos = [0,1,2,3,4,5,6,7,8,9,17,18,19,20,22,23,33,34]
        #SolarError = error_nos[errorindex] # Display Test PV Error's
    # ===========================================================================================
    
    #   Solar Charge Controller # 2
    
        # MQTT
        SolarChargeLimit2  = mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Settings/ChargeCurrentLimit")
        SolarYield2        = mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/History/Daily/0/Yield")
        SolarName2         = mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Devices/0/ProductName")
    
        # ModBus
        SolarWatts2         = modbus_register(789,SolarCharger_2_ID) / 10
        SolarAmps2          = modbus_register(772,SolarCharger_2_ID) / 10
        SolarVolts2         = modbus_register(776,SolarCharger_2_ID) / 100
        MaxSolarWatts2      = modbus_register(785,SolarCharger_2_ID)
        MaxSolarWattsYest2  = modbus_register(787,SolarCharger_2_ID)
        SolarYield2         = modbus_register(784,SolarCharger_2_ID) / 10
        #TotalSolarYield    = modbus_register(790,SolarCharger_2_ID) / 10
        SolarYieldYest2     = modbus_register(786,SolarCharger_2_ID) / 10
        SolarState2         = modbus_register(775,SolarCharger_2_ID)
        SolarError2         = modbus_register(788,SolarCharger_2_ID)
    
    
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
    

# ESS Info
        ESSbatteryLifeState = modbus_register(2900,VEsystemID)
        ESSsocLimitUser     = modbus_register(2901,VEsystemID) / 10
        ESSsocLimitDynamic  = modbus_register(2903, unit=VEsystemID) / 10
        
    
    # ===========================================================================================
    
    # Conditional Modbus Request
    # Analog Temperature Inputs
    # Change the ID to your correct value
    
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

# Datetime object containing current date and time
        now = datetime.now()
    
        # Fri 21 Jan 2022 09:06:57 PM
        dt_string = now.strftime("%a %d %b %Y %r")
    
    # ===========================================================================================
    
        if BatteryTTG == 0.0:
            BatteryTTG = "Infinite"
        else:
            BatteryTTG = timedelta(seconds = BatteryTTG)
        if BatteryState == 0:
            BatteryState = "Idle"
        elif BatteryState == 1:
            BatteryState = "Charging"
        elif BatteryState == 2:
            BatteryState = "Discharging"
    
        SolarStateDict = {0:  "OFF",
                          2:  "Fault",
                          3:  "Bulk",
                          4:  "Absorption",
                          5:  "Float",
                          6:  "Storage",
                          7:  "Equalize",
                          11: "Other Hub-1",
                          252:"EXT Control"
                          }
    
        SolarErrorDict = {0: "No Error",
                          1: "Error 1: Battery temperature too high",
                          2: "Error 2: Battery voltage too high",
                          3: "Error 3: Battery temperature sensor miswired (+)",
                          4: "Error 4: Battery temperature sensor miswired (-)",
                          5: "Error 5: Battery temperature sensor disconnected",
                          6: "Error 6: Battery voltage sense miswired (+)",
                          7: "Error 7: Battery voltage sense miswired (-)",
                          8: "Error 8: Battery voltage sense disconnected",
                          9: "Error 9: Battery voltage wire losses too high",
                          17:"Error 17: Charger temperature too high",
                          18:"Error 18: Charger over-current",
                          19:"Error 19: Charger current polarity reversed",
                          20:"Error 20: Bulk time limit exceeded",
                          22:"Error 22: Charger temperature sensor miswired",
                          23:"Error 23: Charger temperature sensor disconnected",
                          33:"Error 33: Input voltage too high",
                          34:"Error 34: Input current too high"
                          }
    
        if BatterySOC >= 70:
            batcolor = 'green1'
        elif BatterySOC >= 30 and BatterySOC < 70:
            batcolor = 'yellow1'
        elif BatterySOC < 30:
            batcolor = 'red1'
    
        LastFullcharge = timedelta(seconds = LastFullcharge)

    
    # ===========================================================================================
    # Battery
    
        DateTime_label.config(text=f" Time & Date............... {dt_string}",
                                width= 55,
                                fg='indianred',
                                bg='black',
                                font='Terminal 10 bold')
    
        BatterySOC_label.config(text=f" Battery SOC............... ",
                                fg='cyan3',
                                bg='black',
                                font='Terminal 10 ')
    
        BatterySOCValue_label.config(text=f"{BatterySOC}%",
                                fg=batcolor,
                                bg='black',
                                font='Terminal 10 bold ')
    
        BatteryWatts_label.config(text=f" Battery Watts............. {BatteryWatts}",
                                fg='cyan3',
                                bg='black',
                                font='Terminal 10 ')
    
        BatteryAmps_label.config(text=f" Battery Amps.............. {BatteryAmps}",
                                fg='cyan3',
                                bg='black' ,
                                font='Terminal 10 ')
    
        BatteryVolts_label.config(text=f" Battery Volts............. {BatteryVolts}",
                                fg='cyan3',
                                bg='black' ,
                                font='Terminal 10 ')
        ChargeCycles_label.config(text=f" Battery Charge Cycles..... {ChargeCycles}",
                                fg='cyan3',
                                bg='black' ,
                                font='Terminal 10 ')
    
        DCsystemPower_label.config(text=f" DC System Power........... {DCsystemPower} W",
                                fg='cyan3',
                                bg='black' ,
                                font='Terminal 10 ')
        
        BatteryTTG_label.config(text=f" Battery Time To Go........ {BatteryTTG}",
                                width= 65,
                                fg='cyan3',
                                bg='black' ,
                                font='Terminal 10 ')
    
        BatteryState_label.config(text=f" Battery State........... {BatteryState}",
                                fg='cyan3',
                                bg='black' ,
                                font='Terminal 10 ')
    
        LastDischarge_label.config(text=f" Last Discharge.......... {LastDischarge:.1f} AH",
                                fg='cyan3',
                                bg='black' ,
                                font='Terminal 10 ')
    
        ConsumedAH_label.config(text=f" Consumed AH............. {ConsumedAH:.1f} AH",
                                fg='cyan3',
                                bg='black',
                                font='Terminal 10 ')
        MaxChargeCurrent_label.config(text=f" Max Charge Amps Multi+.. {MaxChargeCurrent:.1f} A",
                                fg='cyan3',
                                bg='black' ,
                                font='Terminal 10 ')
        LastFullcharge_label.config(text=f" Last Full Charge........ {LastFullcharge}",
                                fg='cyan3',
                                bg='black',
                                font='Terminal 10 ')
    
    # ===========================================================================================
    # Solar Charger 1
        #SolarWatts = random.randrange(0, 400, 10)
        #SolarWatts = 650
        
        SolarName1_label.config(text=f" {SolarName1} # 1 - {Array1}",
                                fg='gold',
                                bg='black' ,
                                font='Terminal 8')
        
        SolarWatts1_label.config(text=f" PV Watts{'.'*18} {SolarWatts1:.0f}",
                                fg='orangered1',
                                bg='black' ,
                                font='Terminal 10 ')
    
        BigSolarWatts_label.config(text=f"{SolarWatts:.0f} W",
                                fg='orangered1',
                                bg='black' ,
                                font='Terminal 47 bold ')
    
        TotalYield = SolarYield1 + SolarYield2
        TotalYield_label.config(text=f" Yield Today {TotalYield:.3f} kwh",
                                    fg='orchid',
                                    bg='black' ,
                                    font='Terminal 13 bold ')
        
    
        SolarAmps1_label.config(text=f" Output Amps & Limit{'.'*8} ",
                                fg='orangered1',
                                bg='black' ,
                                font='Terminal 10 ')
        SolarAmps1_label_Value.config(text=f" {SolarAmps1:.1f}",
                                fg='green4',
                                bg='black' ,
                                font='Terminal 10 ')
    
        SolarChargeLimit1_label.config(text=f"/ {SolarChargeLimit1:.0f} A",
                                fg='orangered1',
                                bg='black' ,
                                font='Terminal 7 ')
        
        SolarVolts1_label.config(text=f" PV Volts{'.'*18} {SolarVolts1:.1f}",
                                fg='orangered1',
                                bg='black' ,
                                font='Terminal 10 ')
        MaxSolarWatts1_label.config(text=f" Max PV Watts Today{'.'*8} {MaxSolarWatts1:.0f}",
                                fg='orangered1',
                                bg='black' ,
                                font='Terminal 10 ')
    
        MaxSolarWattsYest1_label.config(text=f" Max PV Watts Yesterday{'.'*4} {MaxSolarWattsYest1:.0f}",
                                fg='orangered1',
                                bg='black' ,
                                font='Terminal 10 ')
    
        SolarYield1_label.config(text=f" Solar Yield{'.'*15} {SolarYield1:.3f} kwh",
                                fg='orangered1',
                                bg='black' ,
                                font='Terminal 10 ')
    
        SolarYieldYest1_label.config(text=f" Solar Yield Yesterday{'.'*5} {SolarYieldYest1:.3f} kwh",
                                fg='orangered1',
                                bg='black' ,
                                font='Terminal 10 ')
    
        
    
        SolarState1_label.config(text=f" Solar Charger # 1 State{'.'*3} {SolarStateDict[SolarState1]}",
                                fg='orangered1',
                                bg='black' ,
                                font='Terminal 10 ')
    
        if SolarError1 > 0:
            ErrorColor1fg = 'white'
            ErrorColor1bg = 'red'
        else:
            ErrorColor1fg = 'orangered1'
            ErrorColor1bg = 'black'
        
        SolarError1_label.config(text=f" Solar Charger # 1 Error... {SolarErrorDict[SolarError1]}",
                                fg=ErrorColor1fg,
                                bg=ErrorColor1bg ,
                                font='Terminal 10 ')
    
    
    # ===========================================================================================
    # Solar Charger 2
    
        SolarName2_label.config(text=f" {SolarName2} # 2 - {Array2}",
                                fg='gold',
                                bg='black' ,
                                font='Terminal 8')
    
        SolarWatts2_label.config(text=f"PV Watts................. {SolarWatts2:.0f}",
                                fg='orangered1',
                                bg='black' ,
                                font='Terminal 10 ')
    
        SolarAmps2_label.config(text=f"Output Amps & Limit...... ",
                                fg='orangered1',
                                bg='black' ,
                                font='Terminal 10 ')
    
        SolarAmps2_label_Value.config(text=f" {SolarAmps2:.1f}",
                                fg='green4',
                                bg='black' ,
                                font='Terminal 10 ')
    
        SolarChargeLimit2_label.config(text=f"/ {SolarChargeLimit2:.0f} A",
                                fg='orangered1',
                                bg='black' ,
                                font='Terminal 7 ')
    
    
        SolarVolts2_label.config(text=f"PV Volts................. {SolarVolts2:.1f}",
                                fg='orangered1',
                                bg='black' ,
                                font='Terminal 10 ')
        
        MaxSolarWatts2_label.config(text=f"Max PV Watts Today....... {MaxSolarWatts2:.0f}",
                                fg='orangered1',
                                bg='black' ,
                                font='Terminal 10 ')
    
        MaxSolarWattsYest2_label.config(text=f"Max PV Watts Yesterday... {MaxSolarWattsYest2:.0f}",
                                fg='orangered1',
                                bg='black' ,
                                font='Terminal 10 ')
    
        SolarYield2_label.config(text=f"Solar Yield.............. {SolarYield2:.3f} kwh",
                                fg='orangered1',
                                bg='black' ,
                                font='Terminal 10 ')
    
        SolarYieldYest2_label.config(text=f"Solar Yield Yesterday.... {SolarYieldYest2:.3f} kwh",
                                fg='orangered1',
                                bg='black' ,
                                font='Terminal 10 ')
    
    
        SolarState2_label.config(text=f"Solar Charger # 2 State.. {SolarStateDict[SolarState2]}",
                                fg='orangered1',
                                bg='black' ,
                                font='Terminal 10 ')
    
        if SolarError2 > 0:
            ErrorColor2fg = 'white'
            ErrorColor2bg = 'red'
        else:
            ErrorColor2fg = 'orangered1'
            ErrorColor2bg = 'black'
        
        SolarError2_label.config(text=f" Solar Charger # 2 Error... {SolarErrorDict[SolarError2]}",
                                fg=ErrorColor2fg,
                                bg=ErrorColor2bg ,
                                font='Terminal 10 ')
    
    # ===========================================================================================
    # Grid & A/C Out
        
        FeedIn_label.config(text=f" Feed Excess PV To Grid?... ",
                                fg='green4',
                                bg='black',
                                font='Terminal 10 ')
        if FeedIn == 1:
            FeedInValue = "YES"
            FeedInColor = 'red'
        elif FeedIn == 0:
            FeedInValue = "NO"
            FeedInColor = 'dodgerblue3'
        
        if FeedIn == 1 and Mains >= 2: # and GridWatts < 0:
            FeedInActive_label.config(text=f"Feed-In Active {GridWatts} W",
                                fg='deeppink1',
                                bg='black',
                                font='Terminal 15 ')
    
        else:
            FeedInActive_label.config(text="",
                                bg='black')
        
        FeedIn_Button_Label.config(text=FeedInValue,
                                   fg=FeedInColor,
                                   bg='grey18',
                                   highlightthickness = 0,
                                   bd=0,
                                   command=GridFeedIn)
    
        GridSetPoint_label.config(text=f" Grid Set Point............ {GridSetPoint}W",
                                fg='green4',
                                bg='black',
                                font='Terminal 10 ')
    
        GridWatts_label.config(text=f" Grid Watts................ {GridWatts}",
                                fg='green4',
                                bg='black',
                                font='Terminal 10 ')
    
        SetGridWatts_Label.config(text="Set Grid Watts",
                                  bg='grey15',
                                  fg='grey54',
                                  bd=0 ,
                                  command=SetGridWatts)
        
        GridAmps_label.config(text=f" Grid Amps................. {GridAmps}",
                                fg='green4',
                                bg='black',
                                font='Terminal 10 ')
    
        GridVolts_label.config(text=f" Grid Volts................ {GridVolts}",
                                fg='green4',
                                bg='black' ,
                                font='Terminal 10 ')
    
        GridHZ_label.config(text=f" Grid Freq ................ {GridHZ}",
                                fg='green4',
                                bg='black' ,
                                font='Terminal 10 ')
        GridAmpLimit_label.config(text=f" Grid Current Limit........ {GridAmpLimit} A",
                                fg='green4',
                                bg='black' ,
                                font='Terminal 10 ')
       
        if GridCondition == 0:
            Condition = 'OK'
            GridColor = 'green4'
            
        elif GridCondition == 2:
            Condition = 'LOST'
            GridColor = 'red'
            
        GridCondition_label.config(text=f" Grid Condition............ ",
                                  fg='green4',
                                  bg='black' ,
                                  font='Terminal 10 ')
                                  
        GridCondition_label_Value.config(text=f"{Condition}",
                                  fg=GridColor,
                                  bg='black' ,
                                  font='Terminal 10 ')
    
        ACoutWatts_label.config(text=f"AC Output Watts......... {ACoutWatts}",
                                fg='green4',
                                bg='black' ,
                                font='Terminal 10 ')
    
        ACoutAmps_label.config(text=f"AC Output Amps.......... {ACoutAmps}",
                                fg='green4',
                                bg='black' ,
                                font='Terminal 10 ')
    
        ACoutVolts_label.config(text=f"AC Output Volts......... {ACoutVolts}",
                                fg='green4',
                                bg='black' ,
                                font='Terminal 10 ')
    
        ACoutHZ_label.config(text=f"AC Output Freq.......... {ACoutHZ}",
                                fg='green4',
                                bg='black',
                                font='Terminal 10 ')
    
        if SystemType != 777:
            SystemType_label.config(text=f" System Type............... {SystemType}",
                                    fg='green4',
                                    bg='black' ,
                                    font='Terminal 10 ')
        else:
            SystemType_label.config(text=f" System Type............... Unknown ESS Type",
                                    fg='green4',
                                    bg='black' ,
                                    font='Terminal 10 ')
                                    
        if MPswitch == 1:
            MPswitch = "Charger Only"
        elif MPswitch == 2:
            MPswitch = "Inverter Only"
        elif MPswitch == 3:
            MPswitch = "ON"
        elif MPswitch == 4:
            MPswitch = "OFF"
        
        Multiplus_Switch_label.config(text=f"Multiplus Mode is {MPswitch}",
                                fg='lightgoldenrod',
                                bg='black',
                                font='Terminal 10 ')
#====================================================================
# Mains LED
        #Mains = 2
        if Mains == 0: # Off
            Mains_label.config(text=f"Mains",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
            
            Mains_label_LED.config(text=f"●",
                                fg='grey11',
                                bg='black' ,
                                font='Terminal 22')
    
        elif Mains == 1: # On
            Mains_label.config(text=f"Mains",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
    
            Mains_label_LED.config(text=f"●",
                                fg='green1',
                                bg='black' ,
                                font='Terminal 22')
    
        elif Mains >= 2: # Blink
            Mains_label.config(text=f"Mains",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
    
            Mains_label_LED.config(text=f"●",
                                fg=next(blinkgreen_Mains),
                                bg='black' ,
                                font='Terminal 22')
    
#====================================================================
# Inverter LED
    
        if Inverter == 0: # Off
            Inverter_label.config(text=f"Inverting",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
    
            Inverter_label_LED.config(text=f"●",
                                fg='grey11',
                                bg='black' ,
                                font='Terminal 22')
    
        elif Inverter == 1: # On
            Inverter_label.config(text=f"Inverting",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
    
            Inverter_label_LED.config(text=f"●",
                                fg='green1',
                                bg='black' ,
                                font='Terminal 22')
    
        elif Inverter >= 2: # Blink
            Inverter_label.config(text=f"Inverting",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
                               
            Inverter_label_LED.config(text=f"●",
                                fg=next(blinkgreen_Inverter),
                                bg='black' ,
                                font='Terminal 22')
#====================================================================
# Bulk LED
        if Bulk == 0: # Off
                Bulk_label.config(text=f"Bulk",
                                   fg='grey50',
                                   bg='black',
                                   font='Terminal 10 bold')
                                   
                Bulk_label_LED.config(text=f"●",
                                    fg='grey11',
                                    bg='black' ,
                                    font='Terminal 22')
    
        elif Bulk == 1: # On
            Bulk_label.config(text=f"Bulk",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
                               
            Bulk_label_LED.config(text=f"●",
                                fg='yellow',
                                bg='black' ,
                                font='Terminal 22')
    
        elif Bulk >= 2: # Blink
            Bulk_label.config(text=f"Bulk",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
                               
            Bulk_label_LED.config(text=f"●",
                                fg=next(blinkyellow_Bulk),
                                bg='black' ,
                                font='Terminal 22')
    
#====================================================================
# Overload LED
    
        if Overload == 0: # Off
            Overload_label.config(text=f"Overload",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
    
            Overload_label_LED.config(text=f"●",
                                fg='grey11',
                                bg='black' ,
                                font='Terminal 22')
    
        elif Overload == 1: # On
            Overload_label.config(text=f"Overload",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
    
            Overload_label_LED.config(text=f"●",
                                fg='red',
                                bg='black' ,
                                font='Terminal 22')
    
        elif Overload >= 2: # Blink
            Overload_label.config(text=f"Overload",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
    
            Overload_label_LED.config(text=f"●",
                                fg=next(blinkred_OverLoad),
                                bg='black' ,
                                font='Terminal 22')
#====================================================================
# Absorption LED
        if Absorp == 0: # Off
            Absorp_label.config(text=f"Absorption",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
                               
            Absorp_label_LED.config(text=f"●",
                                fg='grey11',
                                bg='black' ,
                                font='Terminal 22')
    
        elif Absorp == 1: # On
            Absorp_label.config(text=f"Absorption",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
                               
            Absorp_label_LED.config(text=f"●",
                                fg='yellow',
                                bg='black' ,
                                font='Terminal 22')
    
        elif Absorp >= 2: # Blink
            Absorp_label.config(text=f"Absorption",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
                               
            Absorp_label_LED.config(text=f"●",
                                fg=next(blinkyellow_Absorption),
                                bg='black' ,
                                font='Terminal 22')
    
#====================================================================
# Low Battery LED
        if Lowbatt == 0: # Off
            Lowbatt_label.config(text=f"Low Battery",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
                               
            Lowbatt_label_LED.config(text=f"●",
                                fg='grey11',
                                bg='black' ,
                                font='Terminal 22')
    
        elif Lowbatt == 1: # On
            Lowbatt_label.config(text=f"Low Battery",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
                               
            Lowbatt_label_LED.config(text=f"●",
                                fg='red',
                                bg='black' ,
                                font='Terminal 22')
    
        elif Lowbatt >= 2: # Blink
            Lowbatt_label.config(text=f"Low Battery",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
                               
            Lowbatt_label_LED.config(text=f"●",
                                fg=next(blinkred_LowBatt),
                                bg='black' ,
                                font='Terminal 22')
#====================================================================
# Float LED
        #Floatchg = 2
        if Floatchg == 0: # Off
            Float_label.config(text=f"Float",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
                               
            Float_label_LED.config(text=f"●",
                                fg='grey11',
                                bg='black' ,
                                font='Terminal 22')
    
        elif Floatchg == 1: # On
            Float_label.config(text=f"Float",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
                               
            Float_label_LED.config(text=f"●",
                                fg='dodgerblue3',
                                bg='black' ,
                                font='Terminal 22')
    
        elif Floatchg >= 2: # Blink
            Float_label.config(text=f"Float",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
                               
            Float_label_LED.config(text=f"●",
                                fg=next(blinkblue_Float),
                                bg='black' ,
                                font='Terminal 22')
    
#====================================================================
# Temperature LED
        #Temperature = 2
        if Temperature == 0: # Off
            Temperature_label.config(text=f"Temperature",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
                               
            Temperature_label_LED.config(text=f"●",
                                fg='grey11',
                                bg='black' ,
                                font='Terminal 22')
    
        elif Temperature == 1: # On
            Temperature_label.config(text=f"Temperature",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
                               
            Temperature_label_LED.config(text=f"●",
                                fg='red',
                                bg='black' ,
                                font='Terminal 22')
    
        elif Temperature >= 2: # Blink
            Temperature_label.config(text=f"Temperature",
                               fg='grey50',
                               bg='black',
                               font='Terminal 10 bold')
                               
            Temperature_label_LED.config(text=f"●",
                                fg=next(blinkred_Temp),
                                bg='black' ,
                                font='Terminal 22')
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
            # https://www.victronenergy.com/live/ve.bus:ve.bus_error_codes#vebus_error_codes1
            #VEbusErrorList = [0,1,2,3,4,5,6,7,10,14,16,17,18,22,24,25,26]
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
                                   8: "Recharge, SOC dropped 5% or more below MinSOC",
                                   9: "Keep batteries charged mode enabled",
                                   10:"Self consumption, SoC at or above minimum SoC",
                                   11:"Discharge Disabled (Low SoC), SoC is below minimum SoC",
                                   12:"Recharge, SOC dropped 5% or more below minimum"
                                   }
    
     # Battery Life Disabled
        if ESSbatteryLifeState >= 10:
            if ESSsocLimitDynamic_label.winfo_ismapped():
                ESSsocLimitDynamic_label.grid_forget()
                ESSsocLimitDynamic_label_Value.grid_forget()
                ESSmode_label_Value.grid_forget()
    
            if VEbusStatus == 2:
            
                VEbusStatus_label.config(text=f" System State.............. ",
                                        fg='dodgerblue2',
                                        bg='black',
                                        font='Terminal 10 bold')
    
                VEbusStatus_label_Value.config(text=f"{VEbusStatusDict[VEbusStatus]}",
                                        fg='red',
                                        bg='black',
                                        font='Terminal 10 bold')
            else:
                VEbusStatus_label.config(text=f" System State.............. ",
                                        fg='dodgerblue2',
                                        bg='black',
                                        font='Terminal 10 bold')
    
                try:
                    VEbusStatus_label_Value.config(text=f"{VEbusStatusDict[VEbusStatus]}",
                                        fg='dodgerblue2',
                                        bg='black',
                                        font='Terminal 10 bold')
    
                except KeyError:
    
                    VEbusStatus_label_Value.config(text=f"Unknown State",
                                            fg='gold',
                                            bg='black',
                                            font='Terminal 10 bold')
            #VEbusError = 25
            if VEbusError != 0:
    
                VEbusError_label.config(text=f" VE.Bus Error.............. ",
                                        fg='dodgerblue2',
                                        bg='black',
                                        font='Terminal 10 bold')
                
                
                VEbusError_label_Value.config(text=f"{VEbusErrorDict[VEbusError]}",
                                        fg='red',
                                        bg='black',
                                        font='Terminal 10 bold')
            else:
                try:
                    VEbusError_label.config(text=f" VE.Bus Error.............. ",
                                            fg='dodgerblue2',
                                            bg='black',
                                            font='Terminal 10 bold')
                    
                    VEbusError_label_Value.config(text=f"{VEbusErrorDict[VEbusError]}",
                                            fg='green4',
                                            bg='black',
                                            font='Terminal 10 bold')
                except KeyError:
        
                    VEbusError_label_Value.config(text=f"Unknown Error",
                                            fg='red',
                                            bg='black',
                                            font='Terminal 10 bold')
    
            ESSmode_label.config(text=f" ESS Mode ................. ",
                                fg='dodgerblue2',
                                bg='black',
                                font='Terminal 10 bold')
    
            ESSmode_label_Value.config(text=f"Optimized (Battery Life Disabled)",
                                fg='dodgerblue2',
                                bg='black',
                                font='Terminal 10 bold')
            if not ESSmode_label_Value.winfo_ismapped():
                ESSmode_label_Value.grid(sticky='w',row=2, column=1)
    
            ESSbatteryLifeLimit_label.config(text=f" ESS SOC Limit (User)...... ",
                                            fg='dodgerblue2',
                                            bg='black',
                                            font='Terminal 10 bold')
            if not ESSbatteryLifeLimit_label.winfo_ismapped():
                ESSbatteryLifeLimit_label.grid(sticky='w',row=3, column=0)
    
            ESSbatteryLifeLimit_label_Value.config(text=f"{ESSsocLimitUser:.0f}% Unless Grid Fails",
                                            fg='dodgerblue2',
                                            bg='black',
                                            font='Terminal 10 bold')
            if not ESSbatteryLifeLimit_label_Value.winfo_ismapped():
                ESSbatteryLifeLimit_label_Value.grid(sticky='w',row=3, column=1)
    
            ESSbatteryLifeState_label.config(text=f" ESS Battery State ........",
                                            fg='dodgerblue2',
                                            bg='black',
                                            font='Terminal 10 bold')
            
            ESSbatteryLifeState_label_Value.config(text=f"{ESSbatteryLifeStateDict[ESSbatteryLifeState]}",
                                            fg='dodgerblue2',
                                            bg='black',
                                            font='Terminal 10 bold')
    
    # Battery Life Enabled
        elif ESSbatteryLifeState >= 1 and ESSbatteryLifeState <= 8:
            
            if VEbusStatus == 2:
            
                VEbusStatus_label.config(text=f" System State.............. ",
                                        fg='dodgerblue2',
                                        bg='black',
                                        font='Terminal 10 bold')
        
        
                VEbusStatus_label_Value.config(text=f"{VEbusStatusDict[VEbusStatus]}",
                                        fg='red',
                                        bg='black',
                                        font='Terminal 10 bold')
        
            else:
        
                VEbusStatus_label.config(text=f" System State.............. ",
                                        fg='dodgerblue2',
                                        bg='black',
                                        font='Terminal 10 bold')
        
                try:
                    VEbusStatus_label_Value.config(text=f"{VEbusStatusDict[VEbusStatus]}",
                                        fg='dodgerblue2',
                                        bg='black',
                                        font='Terminal 10 bold')
        
        
                except KeyError:
        
                    VEbusStatus_label_Value.config(text=f"Unknown State",
                                            fg='gold',
                                            bg='black',
                                            font='Terminal 10 bold')
            
            #VEbusError = 25
            if VEbusError != 0:
    
                VEbusError_label.config(text=f" VE.Bus Error.............. ",
                                        fg='dodgerblue2',
                                        bg='black',
                                        font='Terminal 10 bold')
    
                VEbusError_label_Value.config(text=f"{VEbusErrorDict[VEbusError]}",
                                        fg='red',
                                        bg='black',
                                        font='Terminal 10 bold')
    
            else:
                try:
                    VEbusError_label.config(text=f" VE.Bus Error.............. ",
                                            fg='dodgerblue2',
                                            bg='black',
                                            font='Terminal 10 bold')
                    
                    VEbusError_label_Value.config(text=f"{VEbusErrorDict[VEbusError]}",
                                            fg='green4',
                                            bg='black',
                                            font='Terminal 10 bold')
                    
                    
                except KeyError:
        
                    VEbusError_label_Value.config(text=f"Unknown Error",
                                            fg='red',
                                            bg='black',
                                            font='Terminal 10 bold')
    
            ESSmode_label.config(text=f" ESS Mode ................. ",
                                            fg='dodgerblue2',
                                            bg='black',
                                            font='Terminal 10 bold')
    
            ESSmode_label_Value.config(text=f"Optimized (Battery Life Enabled)",
                                            fg='dodgerblue2',
                                            bg='black',
                                            font='Terminal 10 bold')
            
            ESSbatteryLifeLimit_label.config(text=f" ESS SOC Limit (User)...... ",
                                            fg='dodgerblue2',
                                            bg='black',
                                            font='Terminal 10 bold')
            if not ESSbatteryLifeLimit_label.winfo_ismapped():
                ESSbatteryLifeLimit_label.grid(sticky='w',row=3, column=0)
    
    
            ESSbatteryLifeLimit_label_Value.config(text=f"{ESSsocLimitUser:.0f}% Unless Grid Fails",
                                            fg='dodgerblue2',
                                            bg='black',
                                            font='Terminal 10 bold')
            if not ESSbatteryLifeLimit_label_Value.winfo_ismapped():
                ESSbatteryLifeLimit_label_Value.grid(sticky='w',row=3, column=1)
    
            ESSsocLimitDynamic_label.config(text=f" ESS SOC Limit (Dynamic)... ",
                                            fg='dodgerblue2',
                                            bg='black',
                                            font='Terminal 10 bold')
            if not ESSsocLimitDynamic_label.winfo_ismapped():
                ESSsocLimitDynamic_label.grid(sticky='w',row=4, column=0)
            
            ESSsocLimitDynamic_label_Value.config(text=f"{ESSsocLimitDynamic:.0f}%",
                                            fg='dodgerblue2',
                                            bg='black',
                                            font='Terminal 10 bold')
            if not ESSsocLimitDynamic_label_Value.winfo_ismapped():
                ESSsocLimitDynamic_label_Value.grid(sticky='w',row=4, column=1)
            
            ESSbatteryLifeState_label.config(text=f" ESS Battery State ........",
                                            fg='dodgerblue2',
                                            bg='black',
                                            font='Terminal 10 bold')
            
            ESSbatteryLifeState_label_Value.config(text=f"{ESSbatteryLifeStateDict[ESSbatteryLifeState]}",
                                            fg='dodgerblue2',
                                            bg='black',
                                            font='Terminal 10 bold')
    
    # Keep Batteries Charged Mode
        elif ESSbatteryLifeState == 9:
    
            if ESSbatteryLifeLimit_label.winfo_ismapped():
                ESSbatteryLifeLimit_label.grid_forget()
                ESSbatteryLifeLimit_label_Value.grid_forget()
    
            if ESSsocLimitDynamic_label.winfo_ismapped():
                ESSsocLimitDynamic_label.grid_forget()
                ESSsocLimitDynamic_label_Value.grid_forget()
    
            if ESSbatteryLifeState_label.winfo_ismapped():
                ESSbatteryLifeState_label.grid_forget()
                ESSbatteryLifeState_label_Value.grid_forget()
    
    
            if VEbusStatus == 2:
            
                VEbusStatus_label.config(text=f" System State.............. ",
                                        fg='dodgerblue2',
                                        bg='black',
                                        font='Terminal 10 bold')
    
                VEbusStatus_label_Value.config(text=f"{VEbusStatusDict[VEbusStatus]}",
                                        fg='red',
                                        bg='black',
                                        font='Terminal 10 bold')
    
            else:
    
                VEbusStatus_label.config(text=f" System State.............. ",
                                        fg='dodgerblue2',
                                        bg='black',
                                        font='Terminal 10 bold')
    
                try:
                    VEbusStatus_label_Value.config(text=f"{VEbusStatusDict[VEbusStatus]}",
                                        fg='dodgerblue2',
                                        bg='black',
                                        font='Terminal 10 bold')
    
                except KeyError:
        
                    VEbusStatus_label_Value.config(text=f"Unknown State",
                                            fg='gold',
                                            bg='black',
                                            font='Terminal 10 bold')
            #VEbusError = 25
            if VEbusError != 0:
    
                VEbusError_label.config(text=f" VE.Bus Error.............. ",
                                        fg='dodgerblue2',
                                        bg='black',
                                        font='Terminal 10 bold')
    
                VEbusError_label_Value.config(text=f"{VEbusErrorDict[VEbusError]}",
                                        fg='red',
                                        bg='black',
                                        font='Terminal 10 bold')
    
            else:
                try:
                    VEbusError_label.config(text=f" VE.Bus Error.............. ",
                                            fg='dodgerblue2',
                                            bg='black',
                                            font='Terminal 10 bold')
                    
                    VEbusError_label_Value.config(text=f"{VEbusErrorDict[VEbusError]}",
                                            fg='green4',
                                            bg='black',
                                            font='Terminal 10 bold')
    
                except KeyError:
    
                    VEbusError_label_Value.config(text=f"Unknown Error",
                                            fg='red',
                                            bg='black',
                                            font='Terminal 10 bold')
    
            ESSmode_label.config(text=f" ESS Mode ................. ",
                                fg='dodgerblue2',
                                bg='black',
                                font='Terminal 10 bold')
    
            ESSmode_label_Value.config(text=f"Keep Batteries Charged Mode Enabled",
                                fg='dodgerblue2',
                                bg='black',
                                font='Terminal 10 bold')

        if Analog_Inputs.lower() == "y":
            BatteryBox_label.config(text=f" Battery Box Temp ......... ",
                                    fg='deeppink',
                                    bg='black',
                                    font='Terminal 10 bold')
        
            BatteryBox_label_Value.config(text=f"{TempSensor1:.1f}",
                                    fg='deeppink',
                                    bg='black',
                                    font='Terminal 10 bold')
        
            Cabin_label.config(text=f" Cabin Interior Temp ...... ",
                                    fg='deeppink',
                                    bg='black',
                                    font='Terminal 10 bold')
        
            Cabin_label_Value.config(text=f"{TempSensor2:.1f}",
                                    fg='deeppink',
                                    bg='black',
                                    font='Terminal 10 bold')
        
            Exterior_label.config(text=f" Exterior Temp ............ ",
                                    fg='deeppink',
                                    bg='black',
                                    font='Terminal 10 bold')
        
            Exterior_label_Value.config(text=f"{TempSensor3:.1f}",
                                    fg='deeppink',
                                    bg='black',
                                    font='Terminal 10 bold')
    except (AttributeError, ConnectionRefusedError, TimeoutError, UnboundLocalError, json.decoder.JSONDecodeError):
        now = datetime.now()
        # # Fri 21 Jan 2022 09:06:57 PM
        dt_string = now.strftime("%a %d %b %Y %r")
        print(dt_string)
        print("ERROR LOG: AttributeError, ConnectionRefusedError, UnboundLocalError, TimeoutError")

    root.after(RefreshRate, my_mainloop)  # run again after Refresh (ms)

frame1 = LabelFrame(root, bg='black', width= 875, height= 175, relief=SUNKEN)
frame1.grid(padx=(10,10),pady=(20,10))
root.grid_propagate(False)
frame1.grid_propagate(False)

frame2 = LabelFrame(root, bg='black', width= 875, height= 250, relief=SUNKEN)
frame2.grid(padx=10,pady=10)
frame2.grid_propagate(False)

frame3 = LabelFrame(root, bg='black', width= 875, height= 215, relief=SUNKEN)
frame3.grid(padx=10,pady=10)
frame3.grid_propagate(False)


frame4 = LabelFrame(root, bg='black', width= 875, height= 210, relief=SUNKEN)
frame4.grid(padx=10,pady=10)
frame4.grid_propagate(False)


#=====================================================================
# Off window frame to hold Modbus input entry.
# frame5 = LabelFrame(root,bg='black', width=500 , height= 100, relief=SUNKEN)
# frame5.place(x=1000, y=500)


# def print_value():
    # #print(Devices_cb.get())
    # #print(RegisterEntry.get())
    # #print(ValueEntry.get())
    # #value   = 
    # builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
    # builder.reset()
    # builder.add_16bit_int(int(ValueEntry.get()))
    # payload = builder.to_registers()
    # client.write_register(int(RegisterEntry.get()), payload, 226)
    # ValueEntry.delete(0, END)


# Devices_cb = ttk.Combobox(frame5, values =['SolarCharger_1_ID',
        # SolarCharger_1_ID,
        # 'SolarCharger_2_ID',
        # SolarCharger_2_ID,
        # 'MultiPlusID',
        # MultiPlusID,
        # 'BmvID',
        # BmvID,
        # 'VEsystemID',
        # VEsystemID ])
# Devices_cb['state'] = 'readonly'
# Devices_cb.grid(sticky='w', row=0,column=0)
# frame5.grid_propagate(False)

# RegisterEntry_label = Label(frame5,anchor = 'w', text='Register #', width=11)
# RegisterEntry_label.grid(sticky='w', row=1,column=0)
# RegisterEntry = Entry(frame5,bd =1, width=11)
# RegisterEntry.grid(sticky='w', row=1,column=0, padx=80)



# ValueEntry_label = Label(frame5,anchor = 'w', width=11, text='Value')
# ValueEntry_label.grid(sticky='w', row=2,column=0)
# ValueEntry = Entry(frame5,bd =1, width=11)
# ValueEntry.grid(sticky='w',row=2,column=0, padx=80)

# ModBus_Button_Label = Button(frame5, text='Write', command=print_value)
# ModBus_Button_Label.grid(row=3,column=0, padx=80)
#=====================================================================

DateTime_label = Label(frame1,anchor = 'w')
DateTime_label.grid(sticky='w', row=0,column=0)

BatterySOC_label = Label(frame1,anchor = 'w')
BatterySOC_label.grid(sticky='w', row=1,column=0)

BatterySOCValue_label = Label(frame1,anchor = 'w')
BatterySOCValue_label.grid(sticky='w', row=1,column=0, padx=225)

BatteryWatts_label = Label(frame1,anchor = 'w')
BatteryWatts_label.grid(sticky='w', row=2,column=0)

BatteryAmps_label = Label(frame1,anchor = 'w')
BatteryAmps_label.grid(sticky='w', row=3,column=0)

BatteryVolts_label = Label(frame1,anchor = 'w')
BatteryVolts_label.grid(sticky='w', row=4,column=0)

ChargeCycles_label = Label(frame1,anchor = 'w')
ChargeCycles_label.grid(sticky='w', row=5,column=0)

DCsystemPower_label = Label(frame1,anchor = 'w')
DCsystemPower_label.grid(sticky='w', row=6,column=0)

BatteryTTG_label = Label(frame1,anchor = 'w')
BatteryTTG_label.grid(sticky='w',row=7,column=0)

BatteryState_label = Label(frame1)
BatteryState_label.grid(sticky= 'w', row=1,column=1)

LastDischarge_label = Label(frame1)
LastDischarge_label.grid(sticky= 'w', row=2,column=1)

ConsumedAH_label = Label(frame1)
ConsumedAH_label.grid(sticky= 'w', row=3,column=1)

MaxChargeCurrent_label = Label(frame1)
MaxChargeCurrent_label.grid(sticky= 'w', row=4,column=1)

LastFullcharge_label = Label(frame1)
LastFullcharge_label.grid(sticky= 'w', row=5,column=1,)

# ===========================================================================================
'''
 Solar Charge Controllers 1 & 2

 #1
'''

SolarName1_label = Label(frame2,anchor = 'w')
SolarName1_label.grid(row=0,column=0,sticky='w')

SolarWatts1_label = Label(frame2,anchor = 'w')
SolarWatts1_label.grid(row=1,column=0,sticky='w', pady=(3,0))

SolarAmps1_label = Label(frame2,anchor = 'w')
SolarAmps1_label.grid(row=2,column=0,sticky='w')

SolarAmps1_label_Value = Label(frame2,anchor = 'w')
SolarAmps1_label_Value.place(x=217, y=40)

SolarChargeLimit1_label = Label(frame2,anchor = 'w')
SolarChargeLimit1_label.place(x=260, y=43)

SolarVolts1_label = Label(frame2,anchor = 'w')
SolarVolts1_label.grid(row=3,column=0,sticky='w')

MaxSolarWatts1_label = Label(frame2,anchor = 'w')
MaxSolarWatts1_label.grid(row=4,column=0,sticky='w')

MaxSolarWattsYest1_label = Label(frame2,anchor = 'w')
MaxSolarWattsYest1_label.grid(row=5,column=0,sticky='w')

SolarYield1_label = Label(frame2,anchor = 'w')
SolarYield1_label.grid(row=6,column=0,sticky='w')

SolarYieldYest1_label = Label(frame2,anchor = 'w')
SolarYieldYest1_label.grid(row=7,column=0,sticky='w')

SolarState1_label = Label(frame2,anchor = 'w', width=39)
SolarState1_label.grid(row=8,column=0,sticky='w')

SolarError1_label = Label(frame2,anchor = 'w')
SolarError1_label.place(x=0, y=200)

# Separator object
separator1 = Frame(frame2, relief='sunken')
separator1.place(x=320, y=0, width=0, height=195)

separator2 = Frame(frame2, relief='sunken')
separator2.place(x=0, y=195, width=870, height=1)

separator3 = Frame(frame2, relief='sunken')
separator3.place(x=637, y=0, width=0, height=195)

# ===========================================================================================
# 2

SolarName2_label = Label(frame2,anchor = 'w')
SolarName2_label.grid(row=0,column=1,sticky='w', padx=5)

SolarWatts2_label = Label(frame2,anchor = 'w')
SolarWatts2_label.grid(row=1, column=1, padx=20, sticky='w')

SolarAmps2_label = Label(frame2,anchor = 'w')
SolarAmps2_label.grid(row=2, column=1, padx=20, sticky='w')

SolarAmps2_label_Value = Label(frame2,anchor = 'w')
SolarAmps2_label_Value.place(x=535, y=40)

SolarChargeLimit2_label = Label(frame2,anchor = 'w')
SolarChargeLimit2_label.place(x=580, y=43)

SolarVolts2_label = Label(frame2,anchor = 'w')
SolarVolts2_label.grid(row=3, column=1, padx=20, sticky='w')


MaxSolarWatts2_label = Label(frame2,anchor = 'w')
MaxSolarWatts2_label.grid(row=4, column=1, padx=20, sticky='w')

MaxSolarWattsYest2_label = Label(frame2,anchor = 'w')
MaxSolarWattsYest2_label.grid(row=5, column=1, padx=20, sticky='w')

SolarYield2_label = Label(frame2,anchor = 'w')
SolarYield2_label.grid(row=6, column=1, padx=20, sticky='w')

SolarYieldYest2_label = Label(frame2,anchor = 'w')
SolarYieldYest2_label.grid(row=7, column=1, padx=20, sticky='w')


SolarState2_label = Label(frame2,anchor = 'w')
SolarState2_label.grid(row=8, column=1, padx=20, sticky='w')

SolarError2_label = Label(frame2,anchor = 'w')
SolarError2_label.place(x=0, y=220)

BigSolarWatts_label = Label(frame2)
BigSolarWatts_label.place(x=638, y=15)

TotalYield_label = Label(frame2,anchor = 'w',justify='center')
TotalYield_label.place(x=638, y=91)


# ===========================================================================================

FeedIn_label = Label(frame3)
FeedIn_label.grid(sticky= 'w')

FeedIn_Button_Label = Button(frame3,)
FeedIn_Button_Label.place(x=225, y=2, height=16, width=30)

GridSetPoint_label = Label(frame3,anchor = 'w')
GridSetPoint_label.grid(sticky='w')

ChangeGridSetPoint_label = Label(frame3, relief=SUNKEN)
ChangeGridSetPoint = Entry(frame3,bd =1, width=5, bg='grey27')
ChangeGridSetPoint.place(x=260, y=22, height=18)
ChangeGridSetPoint.focus()

SetGridWatts_Label = Button(frame3)
SetGridWatts_Label.place(x=307, y=22, height=18)

GridWatts_label = Label(frame3,anchor = 'w')
GridWatts_label.grid(sticky='w')

GridAmps_label = Label(frame3,anchor = 'center')
GridAmps_label.grid(sticky='w')

GridVolts_label = Label(frame3,anchor = 'w')
GridVolts_label.grid(sticky='w')

GridHZ_label = Label(frame3,anchor = 'w')
GridHZ_label.grid(sticky='w')

GridCondition_label = Label(frame3,anchor = 'w')
GridCondition_label.grid(sticky='w')

GridCondition_label_Value = Label(frame3,anchor = 'w')
GridCondition_label_Value.place(x=225, y=125)

GridAmpLimit_label = Label(frame3,anchor = 'w')
GridAmpLimit_label.grid(sticky='w')

SystemType_label = Label(frame3,anchor = 'w')
SystemType_label.grid(sticky='w')

ACoutWatts_label = Label(frame3,anchor = 'w',)
ACoutWatts_label.grid(sticky= 'w', row=2,column=1, padx=(45,0))

ACoutAmps_label = Label(frame3,anchor = 'w')
ACoutAmps_label.grid(sticky= 'w', row=3,column=1, padx=(45,0))

ACoutVolts_label = Label(frame3,anchor = 'w')
ACoutVolts_label.grid(sticky= 'w', row=4,column=1, padx=(45,0))

ACoutHZ_label = Label(frame3,anchor = 'w')
ACoutHZ_label.grid(sticky= 'w', row=5,column=1, padx=(45,0))

FeedInActive_label = Label(frame3,anchor = 'w', width=30, height=1)
FeedInActive_label.place(x=310, y=150)

Multiplus_Switch_label = Label(frame3,anchor = 'w')
Multiplus_Switch_label.grid(row=9,column=1, padx=100)

Mains_label = Label(frame3,anchor = 'w')
Mains_label.place(x=580, y=12)

Mains_label_LED = Label(frame3,anchor = 'w')
Mains_label_LED.place(x=668, y=0)

Inverter_label = Label(frame3,anchor = 'w')
Inverter_label.place(x=725, y=12)

Inverter_label_LED = Label(frame3,anchor = 'w')
Inverter_label_LED.place(x=830, y=0)

Bulk_label = Label(frame3,anchor = 'w')
Bulk_label.place(x=580, y=43)

Bulk_label_LED = Label(frame3,anchor = 'w')
Bulk_label_LED.place(x=668, y=32)

Overload_label = Label(frame3,anchor = 'w')
Overload_label.place(x=725, y=43)

Overload_label_LED = Label(frame3,anchor = 'w')
Overload_label_LED.place(x=830, y=32)

Absorp_label = Label(frame3,anchor = 'w')
Absorp_label.place(x=580, y=74)

Absorp_label_LED = Label(frame3,anchor = 'w')
Absorp_label_LED.place(x=668, y=63)

Lowbatt_label = Label(frame3,anchor = 'w')
Lowbatt_label.place(x=725, y=74)

Lowbatt_label_LED = Label(frame3,anchor = 'w')
Lowbatt_label_LED.place(x=830, y=63)

Float_label = Label(frame3,anchor = 'w')
Float_label.place(x=580, y=105)

Float_label_LED = Label(frame3,anchor = 'w')
Float_label_LED.place(x=668, y=94)

Temperature_label = Label(frame3,anchor = 'w')
Temperature_label.place(x=725, y=105)

Temperature_label_LED = Label(frame3,anchor = 'w')
Temperature_label_LED.place(x=830, y=94)

#===========================================================================
VEbusStatus_label = Label(frame4,anchor = 'w') # System State
VEbusStatus_label.grid(sticky='w',row=0, column=0) 

VEbusStatus_label_Value = Label(frame4,anchor = 'w') # System State Value
VEbusStatus_label_Value.grid(sticky= 'w', row=0, column=1)

VEbusError_label = Label(frame4,anchor = 'w') # VEbus Error 
VEbusError_label.grid(sticky='w',row=1, column=0)

VEbusError_label_Value = Label(frame4,anchor = 'w', wraplength=600, justify='left') # VEbus Error Value
VEbusError_label_Value.grid(sticky='w',row=1, column=1)

ESSmode_label = Label(frame4,anchor = 'w') # ESS Mode
ESSmode_label.grid(sticky='w',row=2, column=0)

ESSmode_label_Value = Label(frame4,anchor = 'w') # ESS Mode Value
ESSmode_label_Value.grid(sticky='w',row=2, column=1)

ESSbatteryLifeLimit_label = Label(frame4,anchor = 'w') # ESS User
ESSbatteryLifeLimit_label.grid(sticky='w',row=3, column=0)

ESSbatteryLifeLimit_label_Value = Label(frame4,anchor = 'w') # ESS User Value
ESSbatteryLifeLimit_label_Value.grid(sticky='w',row=3, column=1)

ESSsocLimitDynamic_label = Label(frame4,anchor = 'w') # ESS Dymanic
ESSsocLimitDynamic_label.grid(sticky='w',row=4, column=0)

ESSsocLimitDynamic_label_Value = Label(frame4,anchor = 'w') # ESS Dymanic Value
ESSsocLimitDynamic_label_Value.grid(sticky='w',row=4, column=1)

ESSbatteryLifeState_label = Label(frame4,anchor = 'w') # ESS Battery State
ESSbatteryLifeState_label.grid(sticky='w',row=5, column=0)

ESSbatteryLifeState_label_Value = Label(frame4,anchor = 'w') # ESS Battery State Value
ESSbatteryLifeState_label_Value.grid(sticky='w',row=5, column=1)

if Analog_Inputs.lower() == "y":
    BatteryBox_label = Label(frame4,anchor = 'w') # Battery Box Temperature
    BatteryBox_label.grid(sticky='w',row=6, column=0)
    
    BatteryBox_label_Value = Label(frame4,anchor = 'w') # Battery Box Temperature Value
    BatteryBox_label_Value.grid(sticky='w',row=6, column=1)

    Cabin_label = Label(frame4,anchor = 'w') # Cabin Temperature
    Cabin_label.grid(sticky='w',row=7, column=0)
    
    Cabin_label_Value = Label(frame4,anchor = 'w') # Cabin Temperature Value
    Cabin_label_Value.grid(sticky='w',row=7, column=1)
    
    Exterior_label = Label(frame4,anchor = 'w') # Cabin Temperature
    Exterior_label.grid(sticky='w',row=8, column=0)
    
    Exterior_label_Value = Label(frame4,anchor = 'w') # Cabin Temperature Value
    Exterior_label_Value.grid(sticky='w',row=8, column=1)

root.after(0,my_mainloop) # run first time after 1000ms (1s)
root.mainloop()
