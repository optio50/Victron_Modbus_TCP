#!/usr/bin/env python3
from PyQt5.QtWidgets import QMainWindow, QApplication, QLabel, QTextEdit, QPushButton, QProgressBar, QLCDNumber, QWidget, QVBoxLayout
from PyQt5.QtCore import QTime, QTimer
from PyQt5 import uic
from itertools import cycle
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
import time
from time import strftime
from time import gmtime
import sys


# GX Device I.P Address
ip = '192.168.20.156'

client = ModbusClient(ip, port='502')

# MQTT Request's are for Multiplus LED state's
# VRM Portal ID from GX device. 
# AFAIK this ID is needed even with no internet access as its the name of your venus device.
# Menu -->> Settings -->> "VRM Online Portal -->> VRM Portal ID"
VRMid = "d41243d31a90"

Analog_Inputs  = 'Y'     # Y or N (case insensitive) to display Gerbo GX Analog Temperature inputs
                         # Check Analog Input Address around line 300.

# Unit ID #'s from Cerbo GX.
# Do not confuse UnitID with Instance ID.
# You can also get the UnitID from the GX device. Menu --> Settings --> Services --> ModBusTCP --> Available Services
# https://github.com/victronenergy/dbus_modbustcp/blob/master/CCGX-Modbus-TCP-register-list.xlsx Tab #2
#===================================
# ModBus Unit ID
SolarCharger_1_ID = 226
SolarCharger_2_ID = 224
MultiPlus_ID      = 227
Bmv_ID            = 223
VEsystem_ID       = 100
#===================================
# MQTT Instance ID
# This is the Instance ID not to be confused with the above Unit ID.
# Device List in VRM or crossed referenced in the CCGX-Modbus-TCP-register-list.xlsx Tab #2
MQTT_SolarCharger_1_ID = 279
MQTT_SolarCharger_2_ID = 278
MQTT_MultiPlus_ID      = 276
MQTT_Bmv_ID            = 277
MQTT_VEsystem_ID       = 0
#===================================

# Describe The Arrays
Array1 = "4 X 100W Array" # 4 New Renogy 100W Panels
Array2 = "250W Panel" # Used 250W panel. Typical Ouput 200W



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

def GridFeedIn():
        FeedIn = modbus_register(2707,VEsystem_ID)

        if FeedIn == 1:
            client.write_register(2707, 0) # Off
            
        else:
            client.write_register(2707, 1) # On




# Cycle colors for blinking LED's (Bright / Dark)
blinkred    = cycle(["rgb(255, 0, 0)","rgb(50, 0, 0)"])
blinkyellow = cycle(["rgb(255, 255, 0)","rgb(50, 50, 0)"])
blinkgreen  = cycle(["rgb(115, 210, 22)","rgb(0, 50, 0)"])
blinkblue   = cycle(["rgb(0, 0, 255)","rgb(0, 25, 50)"])

class UI(QMainWindow):
    def __init__(self):
        super(UI, self).__init__()

        # Load the ui file
        uic.loadUi("Solar.ui", self)
        
        def SetGridWatts():
            watts   = self.Set_Grid_Watts_lineEdit.text()
            builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
            builder.reset()
            builder.add_16bit_int(int(watts))
            payload = builder.to_registers()
            client.write_registers(2700, payload[0])
            self.Set_Grid_Watts_lineEdit.setText("")
        
        
        # Keep this out of the timing loop
        self.FeedIn_pushButton.clicked.connect(GridFeedIn)
        self.Set_Grid_Watts_pushButton.clicked.connect(SetGridWatts)

        # make QTimer
        self.qTimer = QTimer()
        
        # set interval to 1 s
        self.qTimer.setInterval(1000) # 1000 ms = 1 s
        
        # connect timeout signal to signal handler
        self.qTimer.timeout.connect(self.Update_Values)
        
        # start timer
        self.qTimer.start()
        
        # Show The App
        self.show()




    def Update_Values(self):
#===========================================================================================
# BEGIN Setting Variables
#===========================================================================================
        
        # Datetime object containing current date and time
        now = datetime.now()

        # Fri 21 Jan 2022     09:06:57 PM
        dt_string = now.strftime("%a %d %b %Y     %r")

#===========================================================================================
        # Battery Section
        BatterySOC       = modbus_register(266,Bmv_ID) / 10
        BatteryWatts     = modbus_register(842,VEsystem_ID)
        BatteryAmps      = modbus_register(261,Bmv_ID) / 10
        BatteryVolts     = modbus_register(259,Bmv_ID) / 100
        DCsystemPower    = modbus_register(860,VEsystem_ID)
        BatteryState     = modbus_register(844,VEsystem_ID) # Battery System State 0=idle 1=charging 2=discharging
        ChargeCycles     = modbus_register(284,Bmv_ID)
        BatteryTTG       = modbus_register(846,VEsystem_ID) / .01
        ConsumedAH       = modbus_register(265,Bmv_ID) / -10
        LastDischarge    = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/History/LastDischarge")
        MaxChargeCurrent = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Dc/0/MaxChargeCurrent")
        LastFullcharge   = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_Bmv_ID)+"/History/TimeSinceLastFullCharge")
        LastFullcharge   = timedelta(seconds = LastFullcharge)
#===========================================================================================
        #   Solar Charge Controller # 1
        # MQTT
        SolarChargeLimit1  = mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Settings/ChargeCurrentLimit")
        SolarYield1        = mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/History/Daily/0/Yield")
        SolarName1         = mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Devices/0/ProductName")
    
        # ModBus
        SolarWatts1        = modbus_register(789,SolarCharger_1_ID) / 10
        SolarWatts         = modbus_register(850,VEsystem_ID)        # Total of all solar chargers
        SolarAmps          = modbus_register(851,VEsystem_ID) / 10   # Total of all solar chargers
        SolarAmps1         = modbus_register(772,SolarCharger_1_ID) / 10
        SolarVolts1        = modbus_register(776,SolarCharger_1_ID) / 100
        MaxSolarWatts1     = modbus_register(785,SolarCharger_1_ID)
        MaxSolarWattsYest1 = modbus_register(787,SolarCharger_1_ID)
        #SolarYield1        = modbus_register(784,SolarCharger_1_ID) / 10
        #TotalSolarYield    = modbus_register(790,SolarCharger_1_ID) / 10
        SolarYieldYest1    = modbus_register(786,SolarCharger_1_ID) / 10
        SolarOn1           = modbus_register(774,SolarCharger_1_ID)
        SolarState1        = modbus_register(775,SolarCharger_1_ID)
        SolarError1        = modbus_register(788,SolarCharger_1_ID)

#===========================================================================================
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
        #SolarYield2         = modbus_register(784,SolarCharger_2_ID) / 10
        #TotalSolarYield    = modbus_register(790,SolarCharger_2_ID) / 10
        SolarYieldYest2     = modbus_register(786,SolarCharger_2_ID) / 10
        SolarOn2           = modbus_register(774,SolarCharger_2_ID)
        SolarState2         = modbus_register(775,SolarCharger_2_ID)
        SolarError2         = modbus_register(788,SolarCharger_2_ID)
        TotalYield = SolarYield1 + SolarYield2
        TotalYieldYest = SolarYieldYest1 + SolarYieldYest2
#===========================================================================================
        # Multiplus Section
        #   Grid Input & A/C Out
                
        FeedIn        = modbus_register(2707,VEsystem_ID)
        GridSetPoint  = modbus_register(2700,VEsystem_ID)
        GridWatts     = modbus_register(820,VEsystem_ID)
        GridAmps      = modbus_register(6,MultiPlus_ID) / 10
        GridVolts     = modbus_register(3,MultiPlus_ID) / 10
        GridHZ        = modbus_register(9,MultiPlus_ID) / 100
        ACoutWatts    = modbus_register(817,VEsystem_ID)
        ACoutAmps     = modbus_register(18,MultiPlus_ID) / 10
        ACoutVolts    = modbus_register(15,MultiPlus_ID) / 10
        ACoutHZ       = modbus_register(21,MultiPlus_ID) / 100
        GridCondition = modbus_register(64,MultiPlus_ID)
        GridAmpLimit  = modbus_register(22,MultiPlus_ID) / 10

        # LED's
        Mains       = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Mains")
        Inverter    = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Inverter")
        Bulk        = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Bulk")
        Overload    = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Overload")
        Absorp      = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Absorption")
        Lowbatt     = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/LowBattery")
        Floatchg    = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Float")
        Temperature = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/Leds/Temperature")
        
        MultiName   = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/ProductName")
        # Switch Position on the Multiplus II
        #MPswitch    = modbus_register(33,MultiPlus_ID)

#===========================================================================================
# END Variables
#===========================================================================================
# Conditional Values
#===========================================================================================
        SolarStateDict = {0:  "OFF",
                      2:  "Fault",
                      3:  "Bulk",
                      4:  "Absorption",
                      5:  "Float",
                      6:  "Storage",
                      7:  "Equalize",
                      11: "Other Hub-1",
                      252:"EXT Control"}
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

        if GridWatts < 0:
            self.Grid_FeedIn_Active_Label.setHidden(False)
            self.Grid_Watts_LCD.setStyleSheet("QLCDNumber { background: rgb(0, 128, 255); }");
            self.Grid_FeedIn_Active_Label.setText(f"FeedIn Active {GridWatts}")
            self.Grid_FeedIn_Active_Label.setStyleSheet("QLabel { background: rgb(0, 128, 255); color: rgb(0, 0, 0); }")
        else:
            self.Grid_FeedIn_Active_Label.setHidden(True)
            self.Grid_Watts_LCD.setStyleSheet("QLCDNumber { background: rgb(136, 138, 133); }")
            #self.Grid_FeedIn_Active_Label.setStyleSheet("QLabel { background: rgb(85, 87, 83); color: rgb(0, 0, 0); }")
            #self.Grid_FeedIn_Active_Label.setText("")
        
        if FeedIn == 1:
            self.FeedIn_pushButton.setText('YES')
        elif FeedIn == 0:
            self.FeedIn_pushButton.setText('NO')
        
        if GridCondition == 0:
            Condition = 'OK'
            self.Grid_Condition_lineEdit.setStyleSheet("QLineEdit { background: rgb(136, 138, 133); }");
        elif GridCondition == 2:
            Condition = 'LOST'
            self.Grid_Condition_lineEdit.setStyleSheet("QLineEdit { background: red; }");
        
        #BatterySOC = 70
        if BatterySOC >= 66:
            self.Batt_SOC_progressBar.setStyleSheet("QProgressBar#Batt_SOC_progressBar{selection-background-color:"
                                                    "rgb(36, 232, 20);color: rgb(0, 0, 0)}"); # Green
        elif BatterySOC < 66 and BatterySOC >= 33:
            self.Batt_SOC_progressBar.setStyleSheet("QProgressBar#Batt_SOC_progressBar{selection-background-color:"
                                                    "rgb(255, 255, 0);color: rgb(0, 0, 0)}"); # Yellow
        elif BatterySOC < 33:
            self.Batt_SOC_progressBar.setStyleSheet("QProgressBar#Batt_SOC_progressBar{selection-background-color:"
                                                    "rgb(200, 0, 0);}"); # Red
        
        # Conditional Modbus Request
        # Analog Temperature Inputs
        # Change the ID to your correct value. *** modbus_register(3304,ID) *** <------Change ID
        if Analog_Inputs.lower() == 'y':
            try:
                TempSensor1 = modbus_register(3304,24) / 100 * 1.8 + 32
            except AttributeError:
                TempSensor1 = "Sensor 1 Disconnected or Wrong Address"
            
            try:
                TempSensor2 = modbus_register(3304,25) / 100 * 1.8 + 32
            except AttributeError:
                TempSensor2 = "Sensor 2 Disconnected or Wrong Address"
            
            try:
                TempSensor3 = modbus_register(3304,26) / 100 * 1.8 + 32
            except AttributeError:
                TempSensor3 = "Sensor 3 Disconnected or Wrong Address"


#====================================================================
# Mains LED
        #Mains = 3
        if Mains == 0: # Off
            self.Mains_LED.setStyleSheet("QLabel#Mains_LED{color: rgb(65, 65, 65);}");
    
        elif Mains == 1: # On
            self.Mains_LED.setStyleSheet("QLabel#Mains_LED{color: rgb(115, 210, 22);}");
       
        elif Mains >= 2: # Blink
            self.Mains_LED.setStyleSheet(f"QLabel#Mains_LED{{color: {next(blinkgreen)};}}");
#====================================================================
# Inverter LED
    
        if Inverter == 0: # Off
            self.Inverting_LED.setStyleSheet("QLabel#Inverting_LED{color: rgb(65, 65, 65);}");
    
        elif Inverter == 1: # On
            self.Inverting_LED.setStyleSheet("QLabel#Inverting_LED{color: rgb(115, 210, 22);}");
       
        elif Inverter >= 2: # Blink
            self.Inverting_LED.setStyleSheet(f"QLabel#Inverting_LED{{color: {next(blinkgreen)};}}");
#====================================================================
# Bulk LED
        #Bulk = 2
        if Bulk == 0: # Off
            self.Bulk_LED.setStyleSheet("QLabel#Bulk_LED{color: rgb(65, 65, 65);}");
    
        elif Bulk == 1: # On
            self.Bulk_LED.setStyleSheet("QLabel#Bulk_LED{color: rgb(255, 255, 0);}");
       
        elif Bulk >= 2: # Blink
            self.Bulk_LED.setStyleSheet(f"QLabel#Bulk_LED{{color: {next(blinkyellow)};}}");
#====================================================================
# Overload LED
        #Overload = 3
        if Overload == 0: # Off
            self.Overload_LED.setStyleSheet("QLabel#Overload_LED{color: rgb(65, 65, 65);}");
    
        elif Overload == 1: # On
            self.Overload_LED.setStyleSheet("QLabel#Overload_LED{color: rgb(255, 0, 0);}");
       
        elif Overload >= 2: # Blink
            self.Overload_LED.setStyleSheet(f"QLabel#Overload_LED{{color: {next(blinkred)};}}");
#====================================================================
# Absorption LED
        #Absorption = 3
        if Absorp == 0: # Off
            self.Absorption_LED.setStyleSheet("QLabel#Absorption_LED{color: rgb(65, 65, 65);}");
    
        elif Absorp == 1: # On
            self.Absorption_LED.setStyleSheet("QLabel#Absorption_LED{color: rgb(255, 255, 0);}");
       
        elif Absorp >= 2: # Blink
            self.Absorption_LED.setStyleSheet(f"QLabel#Absorption_LED{{color: {next(blinkyellow)};}}");
#====================================================================
# Low Battery LED
        #Lowbatt = 3
        if Lowbatt == 0: # Off
            self.Low_Battery_LED.setStyleSheet("QLabel#Low_Battery_LED{color: rgb(65, 65, 65);}");
    
        elif Lowbatt == 1: # On
            self.Low_Battery_LED.setStyleSheet("QLabel#Low_Battery_LED{color: rgb(255, 0, 0);}");
       
        elif Lowbatt >= 2: # Blink
            self.Low_Battery_LED.setStyleSheet(f"QLabel#Low_Battery_LED{{color: {next(blinkred)};}}");
#====================================================================
# Float LED
        #Floatchg = 2
        if Floatchg == 0: # Off
            self.Float_LED.setStyleSheet("QLabel#Float_LED{color: rgb(65, 65, 65);}");
    
        elif Floatchg == 1: # On
            self.Float_LED.setStyleSheet("QLabel#Float_LED{color: rgb(0, 0, 255);}");
       
        elif Floatchg >= 2: # Blink
            self.Float_LED.setStyleSheet(f"QLabel#Float_LED{{color: {next(blinkblue)};}}");
#====================================================================
# Temperature LED
        #Temperature = 3
        if Temperature == 0: # Off
            self.Temperature_LED.setStyleSheet("QLabel#Temperature_LED{color: rgb(65, 65, 65);}");
    
        elif Temperature == 1: # On
            self.Temperature_LED.setStyleSheet("QLabel#Temperature_LED{color: rgb(255, 0, 0);}");
       
        elif Temperature >= 2: # Blink
            self.Temperature_LED.setStyleSheet(f"QLabel#Temperature_LED{{color: {next(blinkred)};}}");


#===========================================================================================
# Populate Screen with Variable Values
#===========================================================================================
        # Battery Section
        self.Batt_SOC_progressBar.setMaximum(100 * 10)
        self.Batt_SOC_progressBar.setValue(BatterySOC * 10)
        self.Batt_SOC_progressBar.setFormat("%.01f %%" % BatterySOC)
        self.Batt_Watts_LCD.display(BatteryWatts)
        self.Batt_Amps_LCD.display(BatteryAmps)
        self.Batt_Volts_LCD.display(BatteryVolts)
        self.DC_Power_LCD.display(DCsystemPower)
        self.Batt_State_lineEdit.setText(BatteryState)
        self.Last_Discharge_LCD.display(LastDischarge)
        self.Consumed_AH_LCD.display(ConsumedAH)
        self.Max_Charge_Amps_LCD.display(MaxChargeCurrent)
        self.Charge_Cycles_LCD.display(ChargeCycles)
        self.Last_Full_Charge_lineEdit.setText(str(f"{LastFullcharge} Ago"))
        self.Time_Label.setText(dt_string)
        self.Time_To_Go_lineEdit.setText(str(BatteryTTG))
        
        
        # Solar Charger # 1 Section
        self.Solar_Name_1_lineEdit.setText(f"#1 {SolarName1} - {Array1}")
        self.PV_Watts_LCD.display(SolarWatts1)
        self.Output_Amps_LCD.display(f"{SolarAmps1:.1f}")
        self.Output_Amps_Limit_label.setText(str(SolarChargeLimit1))
        self.PV_Volts_LCD.display(f"{SolarVolts1:.2f}")
        self.Max_PV_Watts_Today_LCD.display(MaxSolarWatts1)
        self.Max_PV_Watts_Yesterday_LCD.display(MaxSolarWattsYest1)
        self.Yield_Today_LCD.display(f"{SolarYield1:.3f}")
        self.Yield_Yesterday_LCD.display(f"{SolarYieldYest1:.3f}")
        self.Solar_Charger_State_lineEdit.setText(SolarStateDict[SolarState1])
        
        # Solar Charger # 2 Section
        self.Solar_Name_2_lineEdit.setText(f"#2 {SolarName2} - {Array2}")
        self.PV_Watts_2_LCD.display(SolarWatts2)
        self.Output_Amps_2_LCD.display(f"{SolarAmps2:.1f}")
        self.Output_Amps_Limit_2_label.setText(str(SolarChargeLimit2))
        self.PV_Volts_2_LCD.display(SolarVolts2)
        self.Max_PV_Watts_Today_2_LCD.display(MaxSolarWatts2)
        self.Max_PV_Watts_Yesterday_2_LCD.display(MaxSolarWattsYest2)
        self.Yield_Today_2_LCD.display(f"{SolarYield2:.3f}")
        self.Yield_Yesterday_2_LCD.display(f"{SolarYieldYest2:.3f}")
        self.Solar_Charger_State2_lineEdit.setText(SolarStateDict[SolarState2])
        
        # Total Watts
        if SolarWatts <= 0:
            self.Total_Watts_label.setHidden(True)
        else:
            self.Total_Watts_label.setHidden(False)
            self.Total_Watts_label.setText(str(SolarWatts))
            
        self.Total_Yield_Label.setText(str(f" Yield Today {TotalYield:.3f} kwh"))
        self.Total_Yield_Label_Yest.setText(str(f" Yield Yesterday {TotalYieldYest:.3f} kwh"))
        
        # Multiplus Section
        self.Grid_Set_Point_LCD.display(GridSetPoint)
        self.Grid_Watts_LCD.display(GridWatts)
        self.AC_Out_Watts_LCD.display(ACoutWatts)
        self.Grid_Amps_LCD.display(GridAmps)
        self.AC_Out_Amps_LCD.display(ACoutAmps)
        self.Grid_Volts_LCD.display(GridVolts)
        self.AC_Out_Volts_LCD.display(ACoutVolts)
        self.Grid_Freq_LCD.display(GridHZ)
        self.AC_Out_Freq_LCD.display(ACoutHZ)
        self.Grid_Condition_lineEdit.setText(Condition)
        self.Grid_Current_Limit_LCD.display(GridAmpLimit)

        self.MultiName_label.setText(MultiName)
        
        if Analog_Inputs.lower() == 'y':
            self.Battery_Box_lineEdit.setText(str(TempSensor1))
            self.Cabin_Int_lineEdit.setText(str(TempSensor2))
            self.Cabin_Ext_lineEdit.setText(str(TempSensor3))
        else:
            self.Battery_Box_lineEdit.setHidden(True)
            self.Cabin_Int_lineEdit.setHidden(True)
            self.Cabin_Ext_lineEdit.setHidden(True)
            self.Battery_Box_label.setHidden(True)
            self.Cabin_Int_label.setHidden(True)
            self.Cabin_Ext_label.setHidden(True)

#===========================================================================================


# Initialize The App
app = QApplication(sys.argv)
UIWindow = UI()
app.exec_()
