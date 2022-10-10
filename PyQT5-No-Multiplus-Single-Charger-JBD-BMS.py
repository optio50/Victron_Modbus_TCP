#!/usr/bin/env python3

# This file is for a Raspi and a single Victron SmartSolar Charger. Also includes a Serial UART BMS (JBD in my case).
# I have no idea if this works with the other compatiable BMS's. I only have a JBD.

# Venus OS Serial BMS info
# https://github.com/Louisvdw/dbus-serialbattery
# USB Serial interface https://overkillsolar.com/product/usb-module-for-bms/
# The connector included did not fit my BMS, YMMV. I cut the BMS BlueTooth cable in half and soldered the UART wire's to the connector wire's




#from PyQt5.QtWidgets import (QMainWindow, QApplication, QGridLayout, QLabel, QTextEdit, QAction,
#QPushButton, QProgressBar, QLCDNumber, QWidget, QVBoxLayout, QInputDialog)
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QTime, QTimer, QProcess
from PyQt5 import uic, QtGui
from PyQt5.QtGui import QColor

import json
import re

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

# Initialise Counter to zero for MQTT request KeepAlive
Counter = 0

# GX Device I.P Address
ip = '192.168.20.167'
client = ModbusClient(ip, port='502')


# VRM Portal ID from GX device. 
# AFAIK this ID is needed even with no internet access as its the name of your venus device.
# Menu -->> Settings -->> "VRM Online Portal -->> VRM Portal ID"
VRMid = "b827eba69d10"


# ModBus Unit ID
SolarCharger_ID = 239
VEsystem_ID     = 100
BatteryBMS_ID   = 1

#===================================
# MQTT Instance ID
# This is the Instance ID not to be confused with the above Unit ID.
# Device List in VRM or crossed referenced in the CCGX-Modbus-TCP-register-list.xlsx Tab #2
MQTT_SolarCharger_ID = 288
MQTT_BatteryBMS_ID   = 1

# Onetime Request to start MQTT
mqttpublish.single("R/"+VRMid+"/system/0/Serial", hostname=ip, port=1883)
# A keepalive request is made in the main loop

#===================================

# Describe The Array
Array1 = "Portable 100W Soft Panel"


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


#===========================================================================================
# Solar Charger Control
def Charger1_On():
        client.write_registers(address=774, values=1, unit=SolarCharger_ID) # Turn On


def Charger1_Off():
        client.write_registers(address=774, values=4, unit=SolarCharger_ID) # Turn Off


#===========================================================================================

class UI(QMainWindow):
    def __init__(self):
        super(UI, self).__init__()
        # Load the ui file
        uic.loadUi("PyQT5-No-Multiplus-Single-Charger-JBD-BMS.ui", self)
        
        # Set Window Icon
        self.setWindowIcon(QtGui.QIcon('Solar-icon.ico'))


# Begin Charts
#===========================================================================================

        # Define crosshair parameters
        kwargs = {Crosshair.ENABLED: True,
        Crosshair.LINE_PEN: pg.mkPen(color="purple", width=1),
        Crosshair.TEXT_KWARGS: {"color": "white"}, }
        #pg.setConfigOption('leftButtonPan', False) # For drawing a zooming box. Only needed once.
        # Because this left button is now false, panning is done by dragging the bottom X time labels or the left side Y labels 

#===========================================================================================
# Chart Solar Watts 24 Hrs
        
        watts_plot = LiveLinePlot(pen="orange", fillLevel=0, brush=(213,129,44,100))

        # Data connectors for each plot with dequeue of max_points points
        self.watts_connector = DataConnector(watts_plot, max_points=86400) # 24 hours in seconds

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        watts_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        # Create plot itself
        self.Solar_graph_Widget = LivePlotWidget(title="Solar Watts 24 Hrs", axisItems={'bottom': watts_bottom_axis}, **kwargs)

        # Show grid
        self.Solar_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        # Set labels
        self.Solar_graph_Widget.setLabel('bottom')
        self.Solar_graph_Widget.setLabel('left', 'Watts')

        # Add Line
        self.Solar_graph_Widget.addItem(watts_plot)

        # Add chart to Layout in Qt Designer
        self.Chart_Watts_Layout.addWidget(self.Solar_graph_Widget)
#===========================================================================================

# Chart Solar Watts 1 Hr
        one_hr_watts_plot = LiveLinePlot(pen="orange", fillLevel=0, brush=(213,129,44,100))

        # Data connectors for each plot with dequeue of max_points points
        self.one_hr_watts_connector = DataConnector(one_hr_watts_plot, max_points=3600) # 1 hour in seconds

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        one_hr_watts_bottom_axis = LiveAxis('bottom', **{Axis.TICK_FORMAT: Axis.TIME})
        #one_hr_watts_left_axis = LiveAxis('left', showValues=True)
        
        # Create plot itself
        self.one_hr_Solar_graph_Widget = LivePlotWidget(title="Solar Watts 1 Hr",axisItems={'bottom': one_hr_watts_bottom_axis}, **kwargs)
                
        # Show grid
        self.one_hr_Solar_graph_Widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Set labels
        self.one_hr_Solar_graph_Widget.setLabel('bottom')
        self.one_hr_Solar_graph_Widget.setLabel('left', 'Watts')

        # Add Line
        self.one_hr_Solar_graph_Widget.addItem(one_hr_watts_plot)

        # Add chart to Layout in Qt Designer
        self.Chart_Watts_one_hr_Layout.addWidget(self.one_hr_Solar_graph_Widget)


#===========================================================================================
# Chart Battery Volts 24 Hrs
        volts_plot = LiveLinePlot(pen="red", fillLevel=0, brush=(102,0,0,100))

        # Data connectors for each plot with dequeue of max_points points
        self.volts_connector = DataConnector(volts_plot, max_points=86400) # 24 hours in seconds

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        volts_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})
        #volts_left_axis = LiveAxis('left', showValues=True)
        
        # Create plot itself
        self.Battery_Volts_graph_Widget = LivePlotWidget(title="Battery Volts 24 Hrs", axisItems={'bottom': volts_bottom_axis}, **kwargs)
        
        # Show grid
        self.Battery_Volts_graph_Widget.showGrid(x=True, y=True, alpha=0.3)
        
        # No reason to see huge range plot here. Limit for several volts above and below nominal
        self.Battery_Volts_graph_Widget.setLimits(yMin=9, yMax=18) # 12V system limits, 9-18. Change for 24V or 48V systems


        # Set labels
        self.Battery_Volts_graph_Widget.setLabel('bottom')
        self.Battery_Volts_graph_Widget.setLabel('left', 'Volts')


        # Add Line
        self.Battery_Volts_graph_Widget.addItem(volts_plot)


        # Add chart to Layout in Qt Designer
        self.Chart_Volts_Layout.addWidget(self.Battery_Volts_graph_Widget)

#===========================================================================================
# Chart Battery Volts 1 Hr
        
        one_hr_volts_plot = LiveLinePlot(pen="red", fillLevel=0, brush=(102,0,0,100))

        # Data connectors for each plot with dequeue of max_points points
        self.one_hr_volts_connector = DataConnector(one_hr_volts_plot, max_points=3600) # 1 hour in seconds

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        one_hr_volts_bottom_axis = LiveAxis('bottom', **{Axis.TICK_FORMAT: Axis.TIME})
        #one_hr_volts_left_axis = LiveAxis('left',showValues=True)
        
        # Create plot itself
        self.one_hr_Volts_graph_Widget = LivePlotWidget(title="Battery Volts 1 Hr",axisItems={'bottom': one_hr_volts_bottom_axis}, **kwargs)
        self.one_hr_Volts_graph_Widget.setLimits(yMin=10.5, yMax=16)
        
        # Show grid
        self.one_hr_Volts_graph_Widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Set labels
        self.one_hr_Volts_graph_Widget.setLabel('bottom')
        self.one_hr_Volts_graph_Widget.setLabel('left', 'Volts')
        
        # Add Line
        self.one_hr_Volts_graph_Widget.addItem(one_hr_volts_plot)

        # Add chart to Layout in Qt Designer
        self.Chart_Volts_one_hr_Layout.addWidget(self.one_hr_Volts_graph_Widget)
#===========================================================================================

# Chart Battery Amps
        amps_plot = LiveLinePlot(pen="blue", fillLevel=0, brush=(55,44,213,100))

        # Data connectors for each plot with dequeue of max_points points
        self.amps_connector = DataConnector(amps_plot, max_points=86400) # 24 hours in seconds

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        amps_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        # Create plot itself
        self.Battery_Amps_graph_Widget = LivePlotWidget(title="Battery Amps 24 Hrs", axisItems={'bottom': amps_bottom_axis}, **kwargs)

        # Show grid
        self.Battery_Amps_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        # Set labels
        self.Battery_Amps_graph_Widget.setLabel('bottom')
        self.Battery_Amps_graph_Widget.setLabel('left', 'Amps')

        # Add Line
        self.Battery_Amps_graph_Widget.addItem(amps_plot)

        # Add chart to Layout in Qt Designer
        self.Chart_Battery_Amps_Layout.addWidget(self.Battery_Amps_graph_Widget)


#===========================================================================================

# Chart Battery Amps 1 Hr
        one_hr_Battery_Amps_plot = LiveLinePlot(pen="blue", fillLevel=0, brush=(55,44,213,100))

        # Data connectors for each plot with dequeue of max_points points
        self.one_hr_Battery_Amps_connector = DataConnector(one_hr_Battery_Amps_plot, max_points=3600) # 1 hours in seconds

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        one_hr_Battery_Amps_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        # Create plot itself
        self.one_hr_Battery_Amps_graph_Widget = LivePlotWidget(title="Battery Amps 1 Hr", axisItems={'bottom': one_hr_Battery_Amps_bottom_axis}, **kwargs)

        # Show grid
        self.one_hr_Battery_Amps_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        # Set labels
        self.one_hr_Battery_Amps_graph_Widget.setLabel('bottom')
        self.one_hr_Battery_Amps_graph_Widget.setLabel('left', 'Amps')

        # Add Line
        self.one_hr_Battery_Amps_graph_Widget.addItem(one_hr_Battery_Amps_plot)

        # Add chart to Layout in Qt Designer
        self.Chart_one_hr_Battery_Amps_Layout.addWidget(self.one_hr_Battery_Amps_graph_Widget)

#===========================================================================================

# Chart Battery SOC
        soc_plot = LiveLinePlot(pen="magenta")

        # Data connectors for each plot with dequeue of max_points points
        self.soc_connector = DataConnector(soc_plot, max_points=86400) # 24 hours in seconds

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        soc_bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        # Create plot itself
        self.Battery_SOC_graph_Widget = LivePlotWidget(title="Battery SOC 24 Hrs", axisItems={'bottom': soc_bottom_axis}, **kwargs)

        # Show grid
        self.Battery_SOC_graph_Widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Set Display Limits
        #self.Battery_SOC_graph_Widget.setLimits(yMin=0, yMax=100)

        # Set labels
        self.Battery_SOC_graph_Widget.setLabel('bottom')
        self.Battery_SOC_graph_Widget.setLabel('left', 'Percent')

        # Add Line
        self.Battery_SOC_graph_Widget.addItem(soc_plot)

        # Add chart to Layout in Qt Designer
        self.Chart_Battery_SOC_Layout.addWidget(self.Battery_SOC_graph_Widget)

#===========================================================================================

# Chart Battery Cells
# Modify if you have more than four cells.

        C1_plot = LiveLinePlot(pen="cyan",   name='Cell 1')
        C2_plot = LiveLinePlot(pen="red",    name='Cell 2')
        C3_plot = LiveLinePlot(pen="yellow", name='Cell 3')
        C4_plot = LiveLinePlot(pen="pink",   name='Cell 4')

        # Data connectors for each plot with dequeue of max_points points
        self.C1_connector = DataConnector(C1_plot, max_points=86400) # 24 hours in seconds
        self.C2_connector = DataConnector(C2_plot, max_points=86400) # 24 hours in seconds
        self.C3_connector = DataConnector(C3_plot, max_points=86400) # 24 hours in seconds
        self.C4_connector = DataConnector(C4_plot, max_points=86400) # 24 hours in seconds


        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        # Create plot itself
        self.Cells_graph_Widget = LivePlotWidget(title="Battery Cells Voltage 24 Hrs", axisItems={'bottom': bottom_axis}, **kwargs)

        # Show grid
        self.Cells_graph_Widget.showGrid(x=True, y=True, alpha=0.3)


        # Set labels
        self.Cells_graph_Widget.setLabel('bottom')
        self.Cells_graph_Widget.setLabel('left', 'Volts')
        
        # Add Floating Legend
        self.Cells_graph_Widget.addLegend() # If plot is named, auto add name to legend


        # Add Line
        self.Cells_graph_Widget.addItem(C1_plot) #1 the addItem sequence effects the legend order
        self.Cells_graph_Widget.addItem(C2_plot) #2
        self.Cells_graph_Widget.addItem(C3_plot) #3
        self.Cells_graph_Widget.addItem(C4_plot) #4


        # Add chart to Layout in Qt Designer
        self.Chart_Cells_Layout.addWidget(self.Cells_graph_Widget)



# End Charts
#===========================================================================================
        def Charger1_Limit():
            answer, ok = QInputDialog.getInt(self, 'Enter Charger Limit', 'Enter Charger Limit', mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Settings/ChargeCurrentLimit"))
            if ok:
                mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Settings/ChargeCurrentLimit",
                                                                   payload=json.dumps({"value": answer}), hostname=ip, port=1883)

        def BG_Change():
            color = QColorDialog.getColor()
            if color.isValid():
                self.centralwidget.setStyleSheet(f"background-color: {color.name()}")
                self.Solar_Name_lineEdit.setStyleSheet(f"background-color: {color.name()}")
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

        # set interval to 1 s. This is the actual refresh rate of the displayed data.
        self.qTimer.setInterval(1000) # 1000 ms = 1 s

        # connect timeout signal to signal handler
        self.qTimer.timeout.connect(self.Update_Values)

        # start timer
        self.qTimer.start()

        # Show The App
        self.show()







    def Update_Values(self):
#===========================================================================================
        # Datetime object containing current date and time
        now = datetime.now()

        # Fri 21 Jan 2022     09:06:57 PM
        dt_string = now.strftime("%a %d %b %Y     %r")
#===========================================================================================

        global Counter
        # This is the Keep Alive MQTT request for Raspi
        if Counter >= 10: # Every 10 Loops send MQTT KeepAlive
            try:
                mqttpublish.single("R/"+VRMid+"/system/0/Serial", hostname=ip, port=1883)
                Counter = 0 # After 10 Loops reset Counter to zero, then begin counting again.
            except OSError:
                print('No Contact to ' + ip)
                print(dt_string)
                pass
        Counter += 1 # Increment the counter by 1

#===========================================================================================
# BEGIN Setting Variables
#===========================================================================================
# Solar Charger Variables
    
        SolarName         = mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Devices/0/ProductName")
        SolarWatts        = modbus_register(789,SolarCharger_ID) / 10
        SolarWatts        = f"{SolarWatts:.0f}"
        SolarAmps         = modbus_register(772,SolarCharger_ID) / 10
        SolarChargeLimit  = mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/Settings/ChargeCurrentLimit")
        SolarVolts        = modbus_register(776,SolarCharger_ID) / 100
        MaxSolarWatts     = modbus_register(785,SolarCharger_ID)
        MaxSolarWattsYest = modbus_register(787,SolarCharger_ID)
        SolarYield        = mqtt_request("N/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_ID)+"/History/Daily/0/Yield")
        SolarYieldYest    = modbus_register(786,SolarCharger_ID) / 10
        SolarState        = modbus_register(775,SolarCharger_ID)
        SolarError        = modbus_register(788,SolarCharger_ID)

#===========================================================================================
# Battery BMS Variables

        BatteryVolts            = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Sum")
        #BatteryVolts            = f"{BatteryVolts:.3f}"
        BatteryAmps             = modbus_register(261,BatteryBMS_ID) / 10
        BatteryWatts            = modbus_register(842,VEsystem_ID)
        BatterySOC              = modbus_register(266,BatteryBMS_ID) / 10
        BatteryCAPRemain        = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Capacity") # Remaining
        BatteryCAPInst          = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/InstalledCapacity") # Installed
        BatterySOCflt           = BatteryCAPRemain / BatteryCAPInst * 100
        BatteryTemp             = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Dc/0/Temperature") * 1.8 + 32 # °F
        MinCellVolts            = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/System/MinCellVoltage")
        MaxCellVolts            = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/System/MaxCellVoltage")
        MinCellVoltsID          = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/System/MinVoltageCellId")
        MaxCellVoltsID          = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/System/MaxVoltageCellId")
        CellVoltsDiff           = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Diff")
        BMSname                 = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/HardwareVersion")
        NumOfCells              = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/System/NrOfCellsPerBattery")
        MaxChargeCurrentNOW     = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Info/MaxChargeCurrent")
        MaxDischargeCurrentNOW  = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Info/MaxDischargeCurrent")
        MaxChargeVoltage        = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Info/MaxChargeVoltage")
        AllowedToCharge         = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Io/AllowToCharge")
        AllowedToDischarge      = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Io/AllowToDischarge")
#===========================================================================================
        # Battery Time To Go. This is a user modified addition in the /data/etc/dbus-serialbattery/utils.py file on the GX Device
        # Editing the utils.py file is ****REQUIRED**** to match the format below
        # All times will be positive regardless of whether charge/discharge.
        # When charging and SoC is >= to a SoC percentage that percentage value will be None (or "*").
        # When discharging and SoC is <= to a SoC percentage that percentage value will be None (or "*").
        # If not charging or discharging all TimeToSoC will be None (or "*").
        
        if BatteryWatts == 0:
            BatteryState = 'Idle'
        
        elif BatteryWatts < 0: 
            BatteryState = 'Discharging'
        
        elif BatteryWatts > 0:
            BatteryState = 'Charging'

#===========================================================================================
# Loop to assign "Time To Go" Values
# TimeToSOC list must match the format in /data/etc/dbus-serialbattery/utils.py on the Venus OS device
        TimeToSOC = [
                     "TimeToSOC_100",
                     "TimeToSOC_95",
                     "TimeToSOC_90",
                     "TimeToSOC_85",
                     "TimeToSOC_75",
                     "TimeToSOC_50",
                     "TimeToSOC_25",
                     "TimeToSOC_20",
                     "TimeToSOC_10",
                     "TimeToSOC_0"
                    ]

        for times in TimeToSOC:

            try:
                # Is there a way to combine these better?
                TimeToSOCvalue    = re.search('\d+$', times)
                TimeToSOCvalue    = TimeToSOCvalue.group() # Regex, Select the digit number such as 100 95 90 ... etc

                TimeToSOCvalue    = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/TimeToSoC/"+str(TimeToSOCvalue)) # [ 00:00:00]
                TimeToSOCvalue    = re.search('(?<=\[)(.*?)(?=\])', TimeToSOCvalue) # Regex, Select everything between brackets [ ]
                TimeToSOCvalue    = TimeToSOCvalue.group() # the result without the brackets
                globals()[times]  = TimeToSOCvalue # assign each item in the TimeToSOC list as a variable with a value of TimeToSOCvalue such as 25% "1 Day hh:mm:ss"
            
            except TypeError: # If variable has no value because SOC has passed X % or battery is idle
                globals()[times]  = '*'
                pass

#===========================================================================================
        if NumOfCells >= 4:
            Cell1V = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell1")
            Cell2V = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell2")
            Cell3V = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell3")
            Cell4V = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell4")
            self.Cell_1_Voltage_Value.setText(f"{Cell1V:.3f} V")
            self.Cell_2_Voltage_Value.setText(f"{Cell2V:.3f} V")
            self.Cell_3_Voltage_Value.setText(f"{Cell3V:.3f} V")
            self.Cell_4_Voltage_Value.setText(f"{Cell4V:.3f} V")
#===========================================================================================
        if NumOfCells >= 8:
            Cell5V = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell5")
            Cell6V = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell6")
            Cell7V = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell7")
            Cell8V = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell8")
            self.Cell_5_Voltage_Value.setText(f"{Cell5V:.3f} V")
            self.Cell_6_Voltage_Value.setText(f"{Cell6V:.3f} V")
            self.Cell_7_Voltage_Value.setText(f"{Cell7V:.3f} V")
            self.Cell_8_Voltage_Value.setText(f"{Cell8V:.3f} V")
#===========================================================================================
        if NumOfCells >= 16:
            Cell9V  = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell9")
            Cell10V = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell10")
            Cell11V = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell11")
            Cell12V = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell12")
            Cell13V = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell13")
            Cell14V = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell14")
            Cell15V = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell15")
            Cell16V = mqtt_request("N/"+VRMid+"/battery/"+str(MQTT_BatteryBMS_ID)+"/Voltages/Cell16")
            self.Cell_9_Voltage_Value.setText(f"{Cell9V:.3f} V")
            self.Cell_10_Voltage_Value.setText(f"{Cell10V:.3f} V")
            self.Cell_11_Voltage_Value.setText(f"{Cell11V:.3f} V")
            self.Cell_12_Voltage_Value.setText(f"{Cell12V:.3f} V")
            self.Cell_13_Voltage_Value.setText(f"{Cell13V:.3f} V")
            self.Cell_14_Voltage_Value.setText(f"{Cell14V:.3f} V")
            self.Cell_15_Voltage_Value.setText(f"{Cell15V:.3f} V")
            self.Cell_16_Voltage_Value.setText(f"{Cell16V:.3f} V")
#===========================================================================================


# Conditional Values
#===========================================================================================
        self.Batt_SOC_progressBar.setRange(0, 100)
        #BatterySOC = 32
        self.Batt_SOC_progressBar.setValue(int(BatterySOC))
        

        if round(BatterySOC) >= 66:
            self.Batt_SOC_progressBar.setStyleSheet("QProgressBar#Batt_SOC_progressBar{selection-background-color:"
                                                    "rgb(0, 153, 0);color: rgb(0, 0, 0)}"); # Green
        elif round(BatterySOC) < 66 and BatterySOC >= 33:
            self.Batt_SOC_progressBar.setStyleSheet("QProgressBar#Batt_SOC_progressBar{selection-background-color:"
                                                    "rgb(255, 255, 0);color: rgb(0, 0, 0)}"); # Yellow
        elif round(BatterySOC) < 33:
            self.Batt_SOC_progressBar.setStyleSheet("QProgressBar#Batt_SOC_progressBar{selection-background-color:"
                                                    "rgb(200, 0, 0);}"); # Red


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
#===========================================================================================

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

        # Solar Charger Section
        self.Total_Watts_label.setText(SolarWatts)
        self.Solar_Name_lineEdit.setText(f"{SolarName} - {Array1}")
        self.PV_Watts_LCD.display(SolarWatts)
        self.Output_Amps_LCD.display(SolarAmps)
        self.Output_Amps_Limit_label.setText(f"{SolarChargeLimit:.0f}A")
        self.PV_Volts_LCD.display(SolarVolts)
        self.Max_PV_Watts_Today_LCD.display(MaxSolarWatts)
        self.Max_PV_Watts_Yesterday_LCD.display(MaxSolarWattsYest)
        self.Yield_Today_LCD.display(f"{SolarYield:.3f}")
        self.Yield_Yesterday_LCD.display(f"{SolarYieldYest:.3f}")
        self.Solar_Charger_State_lineEdit.setText(SolarStateDict[SolarState])
#===========================================================================================

        # Battery BMS Section
        
        self.Battery_Volts_LCD.display(BatteryVolts)
        self.Battery_Amps_LCD.display(BatteryAmps)
        self.Battery_Watts_LCD.display(BatteryWatts)
        self.MinCell_Volts_LCD.display(MinCellVolts)
        self.MaxCell_Volts_LCD.display(MaxCellVolts)
        self.MinCellVoltsID_label.setText(MinCellVoltsID)
        self.MaxCellVoltsID_label.setText(MaxCellVoltsID)
        self.Cell_Volts_Diff_LCD.display(CellVoltsDiff)
        self.Installed_CAP_Value.setText(f"{BatteryCAPInst:.2f} AH")
        self.Remaining_CAP_Value.setText(f"{BatteryCAPRemain:.2f} AH")
        self.Battery_Temp_Value.setText(f"{BatteryTemp:.2f} °F")
        self.BMSname_label.setText(f"BMS Model -- {BMSname}")
        self.Batt_SOC_progressBar.setToolTip(f"{BatterySOCflt:.2f} Percent") # Hover mouse on progressbar to get better resolution
        self.Max_Charge_Current_NOW_Value.setText(f"{MaxChargeCurrentNOW} Amps")
        self.Max_Charge_Current_NOW_label.setToolTip("Charging is limited at High SOC") # https://github.com/Louisvdw/dbus-serialbattery/wiki/Features#charge-current-control-management
        self.Max_Discharge_Current_NOW_Value.setText(f"{MaxDischargeCurrentNOW} Amps")
        self.Max_Discharge_Current_NOW_label.setToolTip("Discharging is limited at Low SOC") # https://github.com/Louisvdw/dbus-serialbattery/wiki/Features#charge-current-control-management
        self.Max_Charge_Voltage_Value.setText(f"{MaxChargeVoltage} V")
        
        # Battery Time To Go Section
        
        self.TimeToSOC_100_Value.setText(TimeToSOC_100)
        self.TimeToSOC_95_Value.setText(TimeToSOC_95)
        self.TimeToSOC_90_Value.setText(TimeToSOC_90)
        self.TimeToSOC_85_Value.setText(TimeToSOC_85)
        self.TimeToSOC_75_Value.setText(TimeToSOC_75)
        self.TimeToSOC_50_Value.setText(TimeToSOC_50)
        self.TimeToSOC_25_Value.setText(TimeToSOC_25)
        self.TimeToSOC_20_Value.setText(TimeToSOC_20)
        self.TimeToSOC_10_Value.setText(TimeToSOC_10)
        self.TimeToSOC_0_Value.setText(TimeToSOC_0)
        self.Battery_State_Value.setText(BatteryState)
#===========================================================================================
        # Allow to Charge and Allow to Discharge LED's Green=Yes, Red=No
        if float(BatteryVolts) >= 13.700 and AllowedToCharge == 0 and BatterySOCflt > 99:
            self.MaxChargingVoltageReached_label.setHidden(False)
            self.MaxChargingVoltageReached_label.setText("Max SOC & Charging Voltage Reached")

        if float(BatteryVolts) < 13.700 and AllowedToCharge == 0 and BatterySOCflt > 99:
            self.MaxChargingVoltageReached_label.setHidden(False)
            self.MaxChargingVoltageReached_label.setText("Max SOC Reached")

        if float(BatteryVolts) < 13.700 and BatterySOCflt < 99 or AllowedToCharge == 1:
            self.MaxChargingVoltageReached_label.setHidden(True)

        if AllowedToCharge == 1:
            self.Charging_Allowed_Value.setStyleSheet("QLabel#Charging_Allowed_Value{color: rgb(0, 153, 0);}"); # Green
        else:
            self.Charging_Allowed_Value.setStyleSheet("QLabel#Charging_Allowed_Value{color: rgb(200, 0, 0);}"); # Red

        if AllowedToDischarge == 1:
            self.Discharging_Allowed_Value.setStyleSheet("QLabel#Discharging_Allowed_Value{color: rgb(0, 153, 0);}"); # Green
        else:
            self.Discharging_Allowed_Value.setStyleSheet("QLabel#Discharging_Allowed_Value{color: rgb(255, 0, 0);}"); # Red

        
#===========================================================================================
        
        # DVCC should be turned on to properly allow the BMS to control charging and discharging
        # https://github.com/Louisvdw/dbus-serialbattery/wiki/How-to-install#settings-for-your-gx-device
        DVCCstatus = mqtt_request("N/"+VRMid+"/system/0/Control/Dvcc")

        if DVCCstatus == 1:
            self.DVCC_Info_Value.setText("ON")
            self.DVCC_Info_Value.setStyleSheet("QLabel""{color : rgb(0, 255, 0);}"); # Green
        else:
            self.DVCC_Info_Value.setText("OFF")
            self.DVCC_Info_Value.setStyleSheet("QLabel""{color : rgb(255, 0, 0);}"); # Red
#===========================================================================================
        if SolarError > 0:
            self.Solar_Charger_Error_Value.setText(SolarErrorDict[SolarError])
            self.Solar_Charger_Error_Value.setStyleSheet("QLabel#Solar_Charger_Error_Value{font-weight: bold; color: red; background-color: black;}");
        else:
            self.Solar_Charger_Error_Value.setText(SolarErrorDict[SolarError])
            self.Solar_Charger_Error_Value.setStyleSheet("QLabel#Solar_Charger_Error_Value{color: rgb(0, 255, 0);}");
#===========================================================================================
        self.statusBar.showMessage(dt_string)

        # Charts
        timestamp = time.time()

        self.watts_connector.cb_append_data_point(int(SolarWatts), timestamp)
        self.one_hr_watts_connector.cb_append_data_point(int(SolarWatts), timestamp)
        self.volts_connector.cb_append_data_point(float(BatteryVolts), timestamp)
        self.one_hr_volts_connector.cb_append_data_point(float(BatteryVolts), timestamp)
        self.soc_connector.cb_append_data_point(float(BatterySOCflt), timestamp)
        self.amps_connector.cb_append_data_point(BatteryAmps, timestamp)
        self.one_hr_Battery_Amps_connector.cb_append_data_point(BatteryAmps, timestamp)
        self.C1_connector.cb_append_data_point(Cell1V, timestamp)
        self.C2_connector.cb_append_data_point(Cell2V, timestamp)
        self.C3_connector.cb_append_data_point(Cell3V, timestamp)
        self.C4_connector.cb_append_data_point(Cell4V, timestamp)

#===========================================================================================


# Initialize The App
app = QApplication(sys.argv)
UIWindow = UI()
app.exec_()
