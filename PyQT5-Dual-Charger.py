#!/usr/bin/env python3
from PyQt5.QtWidgets import (QMainWindow, QApplication, QGridLayout, QLabel, QTextEdit, QAction,
QPushButton, QProgressBar, QLCDNumber, QWidget, QVBoxLayout, QInputDialog)
from PyQt5.QtCore import QTime, QTimer, QProcess
from PyQt5 import uic, QtGui


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
from pglive.kwargs import Crosshair, Axis
from pglive.sources.data_connector import DataConnector
from pglive.sources.live_axis import LiveAxis
from pglive.sources.live_plot import LiveVBarPlot, LiveLinePlot
from pglive.sources.live_plot_widget import LivePlotWidget


# GX Device I.P Address
ip = '192.168.20.156'

client = ModbusClient(ip, port='502')


# MQTT Request's are for Multiplus LED state's
# VRM Portal ID from GX device. 
# AFAIK this ID is needed even with no internet access as its the name of your venus device.
# Menu -->> Settings -->> "VRM Online Portal -->> VRM Portal ID"
VRMid = "d41243d31a90"


Analog_Inputs  = 'y'     # Y or N (case insensitive) to display Gerbo GX Analog Temperature inputs
                         # Check Analog Input Address around line 360.

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

# Multiplus Control

def Multiplus_Charger():
    client.write_registers(address=33, values=1, unit=MultiPlus_ID)


def Multiplus_Inverter():
    client.write_registers(address=33, values=2, unit=MultiPlus_ID)


def Multiplus_On():
    client.write_registers(address=33, values=3, unit=MultiPlus_ID)


def Multiplus_Off():
    client.write_registers(address=33, values=4, unit=MultiPlus_ID)


def ESSbatteryLifeEnabled():
    client.write_registers(address=2900, values=1, unit=VEsystem_ID)


def ESSbatteryLifeDisabled():
    client.write_registers(address=2900, values=10, unit=VEsystem_ID)


def ESSbatteriesCharged():
    # Mode 9 'Keep batteries charged' mode enabled
    client.write_registers(address=2900, values=9, unit=VEsystem_ID)

#===========================================================================================
# Solar Charger Control
def Charger1_On():
        client.write_registers(address=774, values=1, unit=SolarCharger_1_ID) # Turn On


def Charger1_Off():
        client.write_registers(address=774, values=4, unit=SolarCharger_1_ID) # Turn Off


def Charger2_On():
        client.write_registers(address=774, values=1, unit=SolarCharger_2_ID) # Turn On



def Charger2_Off():
        client.write_registers(address=774, values=4, unit=SolarCharger_2_ID) # Turn Off

#===========================================================================================

# Cycle colors for blinking LED's (Bright / Dark)
blinkred_Temp          = cycle(["rgb(255, 0, 0)","rgb(50, 0, 0)"])
blinkred_LowBatt       = cycle(["rgb(255, 0, 0)","rgb(50, 0, 0)"])
blinkred_OverLoad      = cycle(["rgb(255, 0, 0)","rgb(50, 0, 0)"])
blinkyellow_Bulk       = cycle(["rgb(255, 255, 0)","rgb(50, 50, 0)"])
blinkyellow_Absorption = cycle(["rgb(255, 255, 0)","rgb(50, 50, 0)"])
blinkgreen_Mains       = cycle(["rgb(115, 210, 22)","rgb(0, 50, 0)"])
blinkgreen_Inverter    = cycle(["rgb(115, 210, 22)","rgb(0, 50, 0)"])
blinkblue_Float        = cycle(["rgb(0, 0, 255)","rgb(0, 25, 50)"])


class UI(QMainWindow):
    def __init__(self):
        super(UI, self).__init__()
        # Load the ui file
        uic.loadUi("PyQT5-Dual-Charger.ui", self)
        # Set Window Icon
        self.setWindowIcon(QtGui.QIcon('Solar.png'))

#===========================================================================================
# Chart Solar Watts

        pg.setConfigOption('leftButtonPan', False) # Only needed once.
        watts_plot = LiveLinePlot(pen='orange', fillLevel=0, brush=(213,129,44,100))

        # Data connectors for each plot with dequeue of max_points points
        self.watts_connector = DataConnector(watts_plot, max_points=86400) # 24 hours in seconds

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        # Define crosshair parameters
        kwargs = {Crosshair.ENABLED: True,
        Crosshair.LINE_PEN: pg.mkPen(color="red", width=1),
        Crosshair.TEXT_KWARGS: {"color": "white"}}

        # Create plot itself
        self.Solar_graph_Widget = LivePlotWidget(title="Solar Watts 24 Hrs", axisItems={'bottom': bottom_axis}, **kwargs)

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
# Chart Battery Watts
        #pg.setConfigOption('leftButtonPan', False) # Only needed once.
        bat_watts_plot = LiveLinePlot(pen='purple', fillLevel=0, brush=(88,55,88))

        # Data connectors for each plot with dequeue of max_points points
        self.bat_watts_connector = DataConnector(bat_watts_plot, max_points=86400) # 24 hours in seconds

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        # Create plot itself
        self.Solar_graph_Widget = LivePlotWidget(title="Battery Watts 24 Hrs", axisItems={'bottom': bottom_axis}, **kwargs)

        # Show grid
        self.Solar_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        # Set labels
        self.Solar_graph_Widget.setLabel('bottom')
        self.Solar_graph_Widget.setLabel('left', 'Watts')

        # Add Line
        self.Solar_graph_Widget.addItem(bat_watts_plot)

        # Add chart to Layout in Qt Designer
        self.Chart_Bat_Watts_Layout.addWidget(self.Solar_graph_Widget)
#===========================================================================================
# Chart Battery Amps
        amps_plot = LiveLinePlot(pen="blue", fillLevel=0, brush=(55,44,213,100))

        # Data connectors for each plot with dequeue of max_points points
        self.amps_connector = DataConnector(amps_plot, max_points=86400) # 24 hours in seconds

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        # Create plot itself
        self.Battery_Amps_graph_Widget = LivePlotWidget(title="Battery Amps 24 Hrs", axisItems={'bottom': bottom_axis}, **kwargs)

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
# Chart Battery SOC
        soc_plot = LiveLinePlot(pen="magenta")

        # Data connectors for each plot with dequeue of max_points points
        self.soc_connector = DataConnector(soc_plot, max_points=86400) # 24 hours in seconds

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        # Create plot itself
        self.Battery_SOC_graph_Widget = LivePlotWidget(title="Battery SOC 24 Hrs", axisItems={'bottom': bottom_axis}, **kwargs)

        # Show grid
        self.Battery_SOC_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        # Set labels
        self.Battery_SOC_graph_Widget.setLabel('bottom')
        self.Battery_SOC_graph_Widget.setLabel('left', 'Percent')

        # Add Line
        self.Battery_SOC_graph_Widget.addItem(soc_plot)

        # Add chart to Layout in Qt Designer
        self.Chart_Battery_SOC_Layout.addWidget(self.Battery_SOC_graph_Widget)

#===========================================================================================
# Chart Battery Volts
        volts_plot = LiveLinePlot(pen="red", fillLevel=0, brush=(102,0,0,100))

        # Data connectors for each plot with dequeue of max_points points
        self.volts_connector = DataConnector(volts_plot, max_points=86400) # 24 hours in seconds

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        # Create plot itself
        self.Battery_Volts_graph_Widget = LivePlotWidget(title="Battery Volts 24 Hrs", axisItems={'bottom': bottom_axis}, **kwargs)

        # Show grid
        self.Battery_Volts_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        # Set labels
        self.Battery_Volts_graph_Widget.setLabel('bottom')
        self.Battery_Volts_graph_Widget.setLabel('left', 'Volts')

        # SetLimits
        self.Battery_Volts_graph_Widget.setLimits(yMin=10.5, yMax=16)

        # Add Line
        self.Battery_Volts_graph_Widget.addItem(volts_plot)

        # Add chart to Layout in Qt Designer
        self.Chart_Volts_Layout.addWidget(self.Battery_Volts_graph_Widget)
#===========================================================================================
# Chart Grid Watts
        grid_plot = LiveLinePlot(pen="green", fillLevel=0, brush=(0,102,0,100))

        # Data connectors for each plot with dequeue of max_points points
        self.grid_connector = DataConnector(grid_plot, max_points=86400) # 24 hours in seconds

        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        # Create plot itself
        self.Grid_Watts_graph_Widget = LivePlotWidget(title="Grid Watts 24 Hrs", axisItems={'bottom': bottom_axis}, **kwargs)

        # Show grid
        self.Grid_Watts_graph_Widget.showGrid(x=True, y=True, alpha=0.3)

        # Set labels
        self.Grid_Watts_graph_Widget.setLabel('bottom')
        self.Grid_Watts_graph_Widget.setLabel('left', 'Watts')

        # Add Line
        self.Grid_Watts_graph_Widget.addItem(grid_plot)

        # Add chart to Layout in Qt Designer
        self.Chart_Grid_Watts_Layout.addWidget(self.Grid_Watts_graph_Widget)

#===========================================================================================
# Chart Cabin Temperatures
        Exterior_Temp_plot = LiveLinePlot(pen="cyan", name='Cabin Exterior')
        Interior_Temp_plot = LiveLinePlot(pen="red", name='Cabin Interior')
        Box_Temp_plot = LiveLinePlot(pen="yellow", name='Battery Box')

        # Data connectors for each plot with dequeue of max_points points
        self.Exterior_Temp_connector = DataConnector(Exterior_Temp_plot, max_points=86400) # 24 hours in seconds
        self.Interior_Temp_connector = DataConnector(Interior_Temp_plot, max_points=86400) # 24 hours in seconds
        self.Box_Temp_connector = DataConnector(Box_Temp_plot, max_points=86400) # 24 hours in seconds


        # Setup bottom axis with TIME tick format
        # use Axis.DATETIME to show date
        bottom_axis = LiveAxis("bottom", **{Axis.TICK_FORMAT: Axis.TIME})

        # Create plot itself
        self.Temperature_graph_Widget = LivePlotWidget(title="Cabin Temperatures °F 24 Hrs", axisItems={'bottom': bottom_axis}, **kwargs)

        # Show grid
        self.Temperature_graph_Widget.showGrid(x=True, y=True, alpha=0.3)


        # Set labels
        self.Temperature_graph_Widget.setLabel('bottom')
        #self.Temperature_graph_Widget.setLabel('bottom', 'Time', units='hh:mm:ss' )
        #self.Temperature_graph_Widget.getAxis('bottom').enableAutoSIPrefix(False)
        self.Temperature_graph_Widget.setLabel('left', '°F')
        
        # Add Floating Legend
        self.Temperature_graph_Widget.addLegend() # If plot is named auto add name to legend

        # Add Line
        self.Temperature_graph_Widget.addItem(Box_Temp_plot) #1 the addItem sequence effects the legend order
        self.Temperature_graph_Widget.addItem(Exterior_Temp_plot) #2
        self.Temperature_graph_Widget.addItem(Interior_Temp_plot) #3


        # Add chart to Layout in Qt Designer
        self.Temperature_Layout.addWidget(self.Temperature_graph_Widget)
#===========================================================================================

        def SetGridWatts():
            watts   = self.Set_Grid_Watts_lineEdit.text()
            builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
            builder.reset()
            builder.add_16bit_int(int(watts))
            payload = builder.to_registers()
            client.write_registers(2700, payload[0])
            self.Set_Grid_Watts_lineEdit.setText("")


        def ESSuser():
            answer, ok = QInputDialog.getInt(self, 'Enter New ESS User Limit', 'Enter New ESS User Limit',
                                            70, 10, 100, 5)
            if ok:
                client.write_registers(address=2901, values=answer * 10, unit=VEsystem_ID)

        def Charger1_Limit():
            answer, ok = QInputDialog.getInt(self, 'Enter Charger 1 Limit', 'Enter Charger 1 Limit')
            if ok:
                mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_1_ID)+"/Settings/ChargeCurrentLimit",
                                                                   payload=json.dumps({"value": answer}), hostname=ip, port=1883)

        def Charger2_Limit():
            answer, ok = QInputDialog.getInt(self, 'Enter Charger 1 Limit', 'Enter Charger 1 Limit')
            if ok:
                mqttpublish.single("W/"+VRMid+"/solarcharger/"+str(MQTT_SolarCharger_2_ID)+"/Settings/ChargeCurrentLimit",
                                                                   payload=json.dumps({"value": answer}), hostname=ip, port=1883)

        self.actionOptimized_Battery_Life_Enabled.triggered.connect(ESSbatteryLifeEnabled)
        self.actionOptimized_Battery_Life_Disabled.triggered.connect(ESSbatteryLifeDisabled)
        self.actionKeep_Batteries_Charged.triggered.connect(ESSbatteriesCharged)
        self.actionChange_ESS_User_Limit.triggered.connect(ESSuser)
        self.actionCharger_Only.triggered.connect(Multiplus_Charger)
        self.actionInverter_Only.triggered.connect(Multiplus_Inverter)
        self.actionOff.triggered.connect(Multiplus_Off)
        self.actionOn.triggered.connect(Multiplus_On)

        self.actionCharger_1_Off.triggered.connect(Charger1_Off)
        self.actionCharger_1_On.triggered.connect(Charger1_On)
        self.actionCharger_2_Off.triggered.connect(Charger2_Off)
        self.actionCharger_2_On.triggered.connect(Charger2_On)
        
        self.actionSet_Current_Limit_1.triggered.connect(Charger1_Limit)
        self.actionSet_Current_Limit_2.triggered.connect(Charger2_Limit)

        # Full Screen & Normanl
        self.actionNormal_Screen.triggered.connect(self.showNormal)
        self.actionFull_Screen.triggered.connect(self.showFullScreen)

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

        # Switch Position on the Multiplus II
        MPswitch    = modbus_register(33,MultiPlus_ID)
        MultiName   = mqtt_request("N/"+VRMid+"/vebus/"+str(MQTT_MultiPlus_ID)+"/ProductName")

#===========================================================================================

        #   VEbus Status
        VEbusStatus = mqtt_request("N/"+VRMid+"/system/"+str(MQTT_VEsystem_ID)+"/SystemState/State")
        #VEbusStatus = modbus_register(31,MultiPlusID)

        #   VEbus Error
        VEbusError  = modbus_register(32,MultiPlus_ID)
        #VEbusError = 55 # Test single error mesg
        #error_nos = [0,1,2,3,4,5,6,7,10,14,16,17,18,22,24,25,26]
        #VEbusError = error_nos[errorindex] # Multiple Test VEbusError's

        # ESS Info
        ESSbatteryLifeState = modbus_register(2900,VEsystem_ID)
        ESSsocLimitUser     = modbus_register(2901,VEsystem_ID) / 10
        ESSsocLimitUser     = f"{ESSsocLimitUser:.0f}%"
        ESSsocLimitDynamic  = modbus_register(2903, unit=VEsystem_ID) / 10
        ESSsocLimitDynamic  = f"{ESSsocLimitDynamic:.0f}%"
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

        # Total Watts
        #if SolarWatts < 1:
        #    self.Total_Watts_label.setHidden(True)
        #else:
        #    self.Total_Watts_label.setHidden(False)
        self.Total_Watts_label.setText(str(SolarWatts))



        # Conditional Modbus Request
        # Analog Temperature Inputs
        # Change the ID to your correct value. *** modbus_register(3304,ID) *** <------Change ID
        if Analog_Inputs.lower() == 'y':
            try:
                TempSensor1 = modbus_register(3304,24) / 100 * 1.8 + 32
            except AttributeError:
                TempSensor1 = "Sensor 1 Disconnected or Wrong Address"
                print("Analog Input Sensor 1 Disconnected or Wrong Address")

            try:
                TempSensor2 = modbus_register(3304,25) / 100 * 1.8 + 32
            except AttributeError:
                TempSensor2 = "Sensor 2 Disconnected or Wrong Address"
                print("Analog Input Sensor 2 Disconnected or Wrong Address")
            try:
                TempSensor3 = modbus_register(3304,26) / 100 * 1.8 + 32
            except AttributeError:
                TempSensor3 = "Sensor 3 Disconnected or Wrong Address"
                print("Analog Input Sensor 3 Disconnected or Wrong Address")

        if Analog_Inputs.lower() == 'y':
            self.Battery_Box_lcdNumber.display(str(f"{TempSensor1:.1f}"))
            self.Cabin_Int_lcdNumber.display(str(f"{TempSensor2:.1f}"))
            self.Cabin_Ext_lcdNumber.display(str(f"{TempSensor3:.1f}"))
        else:
            self.Battery_Box_lcdNumber.setHidden(True)
            self.Cabin_Int_lcdNumber.setHidden(True)
            self.Cabin_Ext_lcdNumber.setHidden(True)
            self.Battery_Box_label.setHidden(True)
            self.Cabin_Int_label.setHidden(True)
            self.Cabin_Ext_label.setHidden(True)

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


#====================================================================
# Mains LED
        #Mains = 3
        if Mains == 0: # Off
            self.Mains_LED.setStyleSheet("QLabel#Mains_LED{color: rgb(28, 28, 28);}");

        elif Mains == 1: # On
            self.Mains_LED.setStyleSheet("QLabel#Mains_LED{color: rgb(115, 210, 22);}");

        elif Mains >= 2: # Blink
            #self.qled.value=next(green_led)
            self.Mains_LED.setStyleSheet(f"QLabel#Mains_LED{{color: {next(blinkgreen_Mains)};}}");
#====================================================================
# Inverter LED

        if Inverter == 0: # Off
            self.Inverting_LED.setStyleSheet("QLabel#Inverting_LED{color: rgb(28, 28, 28);}");

        elif Inverter == 1: # On
            self.Inverting_LED.setStyleSheet("QLabel#Inverting_LED{color: rgb(115, 210, 22);}");

        elif Inverter >= 2: # Blink
            self.Inverting_LED.setStyleSheet(f"QLabel#Inverting_LED{{color: {next(blinkgreen_Inverter)};}}");
#====================================================================
# Bulk LED
        #Bulk = 2
        if Bulk == 0: # Off
            self.Bulk_LED.setStyleSheet("QLabel#Bulk_LED{color: rgb(28, 28, 28);}");

        elif Bulk == 1: # On
            self.Bulk_LED.setStyleSheet("QLabel#Bulk_LED{color: rgb(255, 255, 0);}");

        elif Bulk >= 2: # Blink
            self.Bulk_LED.setStyleSheet(f"QLabel#Bulk_LED{{color: {next(blinkyellow_Bulk)};}}");
#====================================================================
# Overload LED
        #Overload = 3
        if Overload == 0: # Off
            self.Overload_LED.setStyleSheet("QLabel#Overload_LED{color: rgb(28, 28, 28);}");

        elif Overload == 1: # On
            self.Overload_LED.setStyleSheet("QLabel#Overload_LED{color: rgb(255, 0, 0);}");

        elif Overload >= 2: # Blink
            self.Overload_LED.setStyleSheet(f"QLabel#Overload_LED{{color: {next(blinkred_OverLoad)};}}");
#====================================================================
# Absorption LED
        #Absorption = 3
        if Absorp == 0: # Off
            self.Absorption_LED.setStyleSheet("QLabel#Absorption_LED{color: rgb(28, 28, 28);}");

        elif Absorp == 1: # On
            self.Absorption_LED.setStyleSheet("QLabel#Absorption_LED{color: rgb(255, 255, 0);}");

        elif Absorp >= 2: # Blink
            self.Absorption_LED.setStyleSheet(f"QLabel#Absorption_LED{{color: {next(blinkyellow_Absorption)};}}");
#====================================================================
# Low Battery LED
        #Lowbatt = 3
        if Lowbatt == 0: # Off
            self.Low_Battery_LED.setStyleSheet("QLabel#Low_Battery_LED{color: rgb(28, 28, 28);}");

        elif Lowbatt == 1: # On
            self.Low_Battery_LED.setStyleSheet("QLabel#Low_Battery_LED{color: rgb(255, 0, 0);}");

        elif Lowbatt >= 2: # Blink
            self.Low_Battery_LED.setStyleSheet(f"QLabel#Low_Battery_LED{{color: {next(blinkred_LoBatt)};}}");
#====================================================================
# Float LED
        #Floatchg = 2
        if Floatchg == 0: # Off
            self.Float_LED.setStyleSheet("QLabel#Float_LED{color: rgb(28, 28, 28);}");

        elif Floatchg == 1: # On
            self.Float_LED.setStyleSheet("QLabel#Float_LED{color: rgb(0, 0, 255);}");

        elif Floatchg >= 2: # Blink
            self.Float_LED.setStyleSheet(f"QLabel#Float_LED{{color: {next(blinkblue_Float)};}}");
#====================================================================
# Temperature LED
        #Temperature = 3
        if Temperature == 0: # Off
            self.Temperature_LED.setStyleSheet("QLabel#Temperature_LED{color: rgb(28, 28, 28);}");

        elif Temperature == 1: # On
            self.Temperature_LED.setStyleSheet("QLabel#Temperature_LED{color: rgb(255, 0, 0);}");

        elif Temperature >= 2: # Blink
            self.Temperature_LED.setStyleSheet(f"QLabel#Temperature_LED{{color: {next(blinkred_Temp)};}}");

#====================================================================
#   VE.Bus Status
        if VEbusStatus == 2:
            self.System_State_Value.setText(str(VEbusStatusDict[VEbusStatus]))
            self.System_State_Value.setStyleSheet("QLabel#System_State_Value{font-weight: bold; color: red; background-color: black;}");

        else:
            self.System_State_Value.setText(str(VEbusStatusDict[VEbusStatus]))
            self.System_State_Value.setStyleSheet("QLabel#System_State_Value{font-weight: bold; color: rgb(0, 0, 0);}");
#====================================================================
#   VE.Bus Error
        if VEbusError > 0:
            self.VE_Bus_Error_Value.setText(str(VEbusErrorDict[VEbusError]))
            self.VE_Bus_Error_Value.setStyleSheet("QLabel#VE_Bus_Error_Value{font-weight: bold; color: red; background-color: black;}");

        else:
            self.VE_Bus_Error_Value.setText(str(VEbusErrorDict[VEbusError]))
            self.VE_Bus_Error_Value.setStyleSheet("QLabel#VE_Bus_Error_Value{font-weight: bold; color: rgb(0, 255, 0);}");

        # Battery Life Disabled
        if ESSbatteryLifeState >= 10:
            self.ESS_SOC_Dynamic_label.setHidden(True)
            self.ESS_SOC_Dynamic_Value.setHidden(True)
            self.ESS_SOC_User_Value.setText(str(ESSsocLimitUser))
            self.ESS_Mode_Value.setText(ESSbatteryLifeStateDict[ESSbatteryLifeState] + "           Optimized (BatteryLife Disabled)")
        # Battery Life Enabled
        elif ESSbatteryLifeState >= 1 and ESSbatteryLifeState <= 8:
            self.ESS_SOC_Dynamic_label.setHidden(False)
            self.ESS_SOC_Dynamic_Value.setHidden(False)
            self.ESS_SOC_User_label.setHidden(False)
            self.ESS_SOC_User_Value.setHidden(False)
            self.ESS_SOC_User_Value.setText(str(ESSsocLimitUser))
            self.ESS_SOC_Dynamic_Value.setText(str(ESSsocLimitDynamic))
            self.ESS_Mode_Value.setText(ESSbatteryLifeStateDict[ESSbatteryLifeState] + "           Optimized (BatteryLife Enabled)")
        # Keep Batteries Charged Mode
        elif ESSbatteryLifeState == 9:
            self.ESS_SOC_Dynamic_label.setHidden(True)
            self.ESS_SOC_Dynamic_Value.setHidden(True)
            self.ESS_SOC_User_label.setHidden(True)
            self.ESS_SOC_User_Value.setHidden(True)
            self.ESS_Mode_Value.setText(ESSbatteryLifeStateDict[ESSbatteryLifeState])


#====================================================================
#   Multiplus Switch
        if MPswitch == 1:
            MPswitch = "Charger Only"
        elif MPswitch == 2:
            MPswitch = "Inverter Only"
        elif MPswitch == 3:
            MPswitch = "ON"
        elif MPswitch == 4:
            MPswitch = "OFF"
#===========================================================================================
# Populate Screen with Variable Values
#===========================================================================================
        # Battery Section
        self.Batt_SOC_progressBar.setRange(0, 100)
        #self.Batt_SOC_progressBar.setMaximum(100 * 10)
        #self.Batt_SOC_progressBar.setFormat("%.1f %%" % BatterySOC)
        self.Batt_SOC_progressBar.setValue(round(BatterySOC))
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

        if SolarError1 > 0:
            self.Solar_Charger1_Error_Value.setText(SolarErrorDict[SolarError1])
            self.Solar_Charger1_Error_Value.setStyleSheet("QLabel#Solar_Charger1_Error_Value{font-weight: bold; color: red; background-color: black;}");

        else:
            self.Solar_Charger1_Error_Value.setText(SolarErrorDict[SolarError1])
            self.Solar_Charger1_Error_Value.setStyleSheet("QLabel#Solar_Charger1_Error_Value{color: rgb(0, 255, 0);}");

        if SolarError2 > 0:
            self.Solar_Charger2_Error_Value.setText(SolarErrorDict[SolarError2])
            self.Solar_Charger2_Error_Value.setStyleSheet("QLabel#Solar_Charger2_Error_Value{font-weight: bold; color: red; background-color: black;}");

        else:
            self.Solar_Charger2_Error_Value.setText(SolarErrorDict[SolarError2])
            self.Solar_Charger2_Error_Value.setStyleSheet("QLabel#Solar_Charger2_Error_Value{color: rgb(0, 255, 0);}");


        self.Multiplus_Mode_Value.setText(str(MPswitch))
        self.statusBar.showMessage(dt_string)

        # Chart
        timestamp = time.time()
        self.watts_connector.cb_append_data_point(SolarWatts, timestamp)
        self.bat_watts_connector.cb_append_data_point(BatteryWatts, timestamp)
        self.amps_connector.cb_append_data_point(BatteryAmps, timestamp)
        self.volts_connector.cb_append_data_point(BatteryVolts, timestamp)
        self.soc_connector.cb_append_data_point(BatterySOC, timestamp)
        self.grid_connector.cb_append_data_point(GridWatts, timestamp)
        self.Box_Temp_connector.cb_append_data_point(TempSensor1, timestamp)
        self.Interior_Temp_connector.cb_append_data_point(TempSensor2, timestamp)
        self.Exterior_Temp_connector.cb_append_data_point(TempSensor3, timestamp)



#===========================================================================================


# Initialize The App
app = QApplication(sys.argv)
UIWindow = UI()
app.exec_()
