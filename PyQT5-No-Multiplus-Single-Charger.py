#!/usr/bin/env python3

# This file is for a Raspi and a single Victron BlueSmart Solar Charger.

#from PyQt5.QtWidgets import (QMainWindow, QApplication, QGridLayout, QLabel, QTextEdit, QAction,
#QPushButton, QProgressBar, QLCDNumber, QWidget, QVBoxLayout, QInputDialog)
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QTime, QTimer, QProcess
from PyQt5 import uic, QtGui
from PyQt5.QtGui import QColor


from itertools import cycle # Flash the LED's
import json

# MQTT
import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as mqttpublish

# Modbus
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

# Chart
import pyqtgraph as pg
from pglive.kwargs import Axis, Crosshair
from pglive.sources.data_connector import DataConnector
from pglive.sources.live_axis import LiveAxis
from pglive.sources.live_plot import LiveVBarPlot, LiveLinePlot
from pglive.sources.live_plot_widget import LivePlotWidget

Counter = 0

# GX Device I.P Address
Portable_ip = '192.168.20.167'
Portable_client = ModbusClient(Portable_ip, port='502')

# MQTT Request's are for Multiplus LED state's
# VRM Portal ID from GX device. 
# AFAIK this ID is needed even with no internet access as its the name of your venus device.
# Menu -->> Settings -->> "VRM Online Portal -->> VRM Portal ID"
Portable_VRMid = "b827eba69d10"


# ModBus Unit ID
Portable_SolarCharger_ID = 239

#===================================
# MQTT Instance ID
# This is the Instance ID not to be confused with the above Unit ID.
# Device List in VRM or crossed referenced in the CCGX-Modbus-TCP-register-list.xlsx Tab #2
Portable_MQTT_SolarCharger_ID = 288

# Onetime Request to start MQTT
mqttpublish.single("R/"+Portable_VRMid+"/system/0/Serial", hostname=Portable_ip, port=1883)

#===================================

# Describe The Array

Array1 = "Portable 100W Soft Panel"

def Portable_modbus_register(address, unit):
    msg     = Portable_client.read_input_registers(address, unit=unit)
    decoder = BinaryPayloadDecoder.fromRegisters(msg.registers, byteorder=Endian.Big)
    msg     = decoder.decode_16bit_int()
    return msg

def Portable_mqtt_request(mqtt_path):
    topic = subscribe.simple(mqtt_path, hostname=Portable_ip)
    data  = json.loads(topic.payload)
    topic = data['value']
    return topic


#===========================================================================================
# Solar Charger Control
def Charger1_On():
        Portable_client.write_registers(address=774, values=1, unit=Portable_SolarCharger_ID) # Turn On


def Charger1_Off():
        Portable_client.write_registers(address=774, values=4, unit=Portable_SolarCharger_ID) # Turn Off


#===========================================================================================

class UI(QMainWindow):
    def __init__(self):
        super(UI, self).__init__()
        # Load the ui file
        uic.loadUi("PyQT5-No-Multiplus-Single-Charger.ui", self)
        # Set Window Icon
        
        self.setWindowIcon(QtGui.QIcon('Solar.png'))
        
#===========================================================================================

        # Define crosshair parameters
        kwargs = {Crosshair.ENABLED: True,
        Crosshair.LINE_PEN: pg.mkPen(color="red", width=1),
        Crosshair.TEXT_KWARGS: {"color": "white"}}

#===========================================================================================
# Chart Portable Solar Watts
        pg.setConfigOption('leftButtonPan', False) # For drawing a zooming box. Only needed once.
        # Because this left button is now false panning is done by dragging the bottom X time labels or the left side Y labels 
        Portable_watts_plot = LiveLinePlot(pen="orange", fillLevel=0, brush=(213,129,44,100))

        # Data connectors for each plot with dequeue of max_points points
        
        self.Portable_watts_connector = DataConnector(Portable_watts_plot, max_points=86400) # 24 hours in seconds

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        # Create plot itself
        self.Portable_Solar_graph_Widget = LivePlotWidget(title="Solar Watts 24 Hrs", axisItems={'bottom': bottom_axis}, **kwargs)
        
        # Show grid
        self.Portable_Solar_graph_Widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Set labels
        self.Portable_Solar_graph_Widget.setLabel('bottom')
        self.Portable_Solar_graph_Widget.setLabel('left', 'Watts')
        
        # Add Line
        self.Portable_Solar_graph_Widget.addItem(Portable_watts_plot)
        
        # Add chart to Layout in Qt Designer
        self.Portable_Chart_Watts_Layout.addWidget(self.Portable_Solar_graph_Widget)
#===========================================================================================
# Chart Portable Battery Volts
        Portable_volts_plot = LiveLinePlot(pen="red", fillLevel=0, brush=(102,0,0,100))

        # Data connectors for each plot with dequeue of max_points points
        
        self.Portable_volts_connector = DataConnector(Portable_volts_plot, max_points=86400) # 24 hours in seconds

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        # Create plot itself
        self.Portable_Battery_Volts_graph_Widget = LivePlotWidget(title="Battery Volts 24 Hrs", axisItems={'bottom': bottom_axis}, **kwargs)
        
        # Show grid
        self.Portable_Battery_Volts_graph_Widget.showGrid(x=True, y=True, alpha=0.3)
        
        self.Portable_Battery_Volts_graph_Widget.setLimits(yMin=10.5, yMax=16)


        # Set labels
        self.Portable_Battery_Volts_graph_Widget.setLabel('bottom')
        self.Portable_Battery_Volts_graph_Widget.setLabel('left', 'Volts')
        
        
        
        # Add Line
        self.Portable_Battery_Volts_graph_Widget.addItem(Portable_volts_plot)
        
        
        # Add chart to Layout in Qt Designer
        self.Portable_Chart_Volts_Layout.addWidget(self.Portable_Battery_Volts_graph_Widget)
#===========================================================================================


        def Charger1_Limit():
            answer, ok = QInputDialog.getInt(self, 'Enter Charger Limit', 'Enter Charger Limit')
            if ok:
                mqttpublish.single("W/"+Portable_VRMid+"/solarcharger/"+str(Portable_MQTT_SolarCharger_ID)+"/Settings/ChargeCurrentLimit",
                                                                   payload=json.dumps({"value": answer}), hostname=Portable_ip, port=1883)
        
        def BG_Change():
            color = QColorDialog.getColor()
            if color.isValid():
                self.centralwidget.setStyleSheet(f"background-color: {color.name()}")
                self.Portable_Solar_Name_lineEdit.setStyleSheet(f"background-color: {color.name()}")
                self.tabWidget.setStyleSheet(f"background-color: {color.name()}")
                


        self.actionCharger_1_Off.triggered.connect(Charger1_Off)
        self.actionCharger_1_On.triggered.connect(Charger1_On)
        
        
        self.actionSet_Current_Limit_1.triggered.connect(Charger1_Limit)
        
        # Full Screen & Normanl
        self.actionNormal_Screen.triggered.connect(self.showNormal)
        self.actionFull_Screen.triggered.connect(self.showFullScreen)
        self.actionChange_Background_Color.triggered.connect(BG_Change)
        
        
        
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
        global Counter
        # Keep Alive MQTT request for Raspi
        if Counter == 10:
            mqttpublish.single("R/"+Portable_VRMid+"/system/0/Serial", hostname=Portable_ip, port=1883)
            Counter = 0

        Counter += 1

#===========================================================================================
# BEGIN Setting Variables
#===========================================================================================
        
        # Datetime object containing current date and time
        now = datetime.now()

        # Fri 21 Jan 2022     09:06:57 PM
        dt_string = now.strftime("%a %d %b %Y     %r")


#===========================================================================================
# Portable Variables
        Portable_SolarName         = Portable_mqtt_request("N/"+Portable_VRMid+"/solarcharger/"+str(Portable_MQTT_SolarCharger_ID)+"/Devices/0/ProductName")
        Portable_SolarWatts        = Portable_modbus_register(789,Portable_SolarCharger_ID) / 10
        Portable_SolarWattsF       = f"{Portable_SolarWatts:.0f}"
        Portable_SolarAmps         = Portable_modbus_register(772,Portable_SolarCharger_ID) / 10
        Portable_SolarChargeLimit  = Portable_mqtt_request("N/"+Portable_VRMid+"/solarcharger/"+str(Portable_MQTT_SolarCharger_ID)+"/Settings/ChargeCurrentLimit")
        Portable_SolarVolts        = Portable_modbus_register(776,Portable_SolarCharger_ID) / 100
        Portable_MaxSolarWatts     = Portable_modbus_register(785,Portable_SolarCharger_ID)
        Portable_MaxSolarWattsYest = Portable_modbus_register(787,Portable_SolarCharger_ID)
        Portable_SolarYield        = Portable_mqtt_request("N/"+Portable_VRMid+"/solarcharger/"+str(Portable_MQTT_SolarCharger_ID)+"/History/Daily/0/Yield")
        Portable_SolarYieldYest    = Portable_modbus_register(786,Portable_SolarCharger_ID) / 10
        Portable_SolarState        = Portable_modbus_register(775,Portable_SolarCharger_ID)
        Portable_SolarError        = Portable_modbus_register(788,Portable_SolarCharger_ID)
        Portable_BatteryVolts      = Portable_modbus_register(771,Portable_SolarCharger_ID) / 100

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
                      245: "Wake-Up",
                      252:"EXT Control"}
        
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


#===========================================================================================
# Populate Screen with Variable Values
#===========================================================================================

        # Portable Solar Charger Section
        self.Portable_Total_Watts_label.setText(str(Portable_SolarWattsF))
        self.Portable_Solar_Name_lineEdit.setText(f"{Portable_SolarName} - {Array1}")
        self.Portable_PV_Watts_LCD.display(Portable_SolarWatts)
        self.Portable_Output_Amps_LCD.display(f"{Portable_SolarAmps:.1f}")
        self.Portable_Output_Amps_Limit_label.setText(str(Portable_SolarChargeLimit))
        self.Portable_PV_Volts_LCD.display(Portable_SolarVolts)
        self.Portable_Max_PV_Watts_Today_LCD.display(Portable_MaxSolarWatts)
        self.Portable_Max_PV_Watts_Yesterday_LCD.display(Portable_MaxSolarWattsYest)
        self.Portable_Yield_Today_LCD.display(f"{Portable_SolarYield:.3f}")
        self.Portable_Yield_Yesterday_LCD.display(f"{Portable_SolarYieldYest:.3f}")
        self.Portable_Battery_Volts_LCD.display(Portable_BatteryVolts)
        self.Portable_Solar_Charger_State_lineEdit.setText(SolarStateDict[Portable_SolarState])

        #self.Total_Yield_Label.setText(str(f" Yield Today {TotalYield:.3f} kwh"))
        #self.Total_Yield_Label_Yest.setText(str(f" Yield Yesterday {TotalYieldYest:.3f} kwh"))
        
        
        
        if Portable_SolarError > 0:
            self.Portable_Solar_Charger_Error_Value.setText(SolarErrorDict[Portable_SolarError])
            self.Portable_Solar_Charger_Error_Value.setStyleSheet("QLabel#Portable_Solar_Charger_Error_Value{font-weight: bold; color: red; background-color: black;}");

        else:
            self.Portable_Solar_Charger_Error_Value.setText(SolarErrorDict[Portable_SolarError])
            self.Portable_Solar_Charger_Error_Value.setStyleSheet("QLabel#Portable_Solar_Charger_Error_Value{color: rgb(0, 255, 0);}");

        self.statusBar.showMessage(dt_string)
        
        # Chart
        timestamp = time.time()
        
        self.Portable_watts_connector.cb_append_data_point(Portable_SolarWatts, timestamp)
        self.Portable_volts_connector.cb_append_data_point(Portable_BatteryVolts, timestamp)



#===========================================================================================


# Initialize The App
app = QApplication(sys.argv)
UIWindow = UI()
app.exec_()
