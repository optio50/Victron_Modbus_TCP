# Victron_Modbus_TCP
Victron Modbus TCP & MQTT Example

Indeed I was mistaken about the Cerbo Keep-Alive. I had installed the Grafana Docker over a year ago and it has its own keep alive in it.  
I had stopped using grafana and forgot all about it. Its since been removed.   
I have an alternate way to run the keep-alive on the cerbo (or Pi) its self.  

The file's are provided above, named Keep-Alive.py and Forever.py  
The Keep-Alive.py is run via a kind of pseudo monitoring script (forever.py).  
Place both files in the cerbo /data directory and make sure they are set executable.
edit the /data/rc.local file (nano rc.local) and make an entry that looks like this  
```
#!/bin/bash   
sleep 30   
/data/forever.py /data/keep-alive.py &
```   
ctrl+o to write the file to disk and ctrl+x to exit   
reboot the cerbo and the keep-alive should do its job.  
the sleep command is to ensure the cerbo has had time to accomplish a full startup routine.

You can still incororate the keep-alive into the different scripts provided here if you prefer that method.


~~For whatever reason the Cerbo GX does not appear to require a MQTT keep-alive request where the raspberry pi does.~~
The only one of these files that incorporates such a request is the stand alone system with no Multiplus.
PyQT5-No-Multiplus-Single-Charger.py

If you want to run the keep-alive in the script instead of the standalone keep-alive you will need the MQTT request in the update_value function with a counter.
See PyQT5-No-Multiplus-Single-Charger.py for an example.

If you find that the Cerbo-GX DOES need a MQTT keep-alive you will need to implement this into the various scripts.
See PyQT5-No-Multiplus-Single-Charger.py for an example.
(Maybe my situation is unique in not needing a Cerbo-GX MQTT keep-alive)


These file's are based on a system that has victron equipment in an "ESS" system. Multiplus, Solar charger, BMV

Be advised.  
Running the Example2.py file and pressing the arrow key's will change values on the GX device.  
(↑) or (↓) Arrows To change grid set point.  
(←) or (→) Arrows To Change ESS SOC limit.  
Pressing the Page-Up button toggles the ESS mode. "Keep batteries charged and Optimized (with battery life)"  
  
Example.py has no ability to control. Only monitor  


An example of the Victron TCP Modbus.  
If you intend to use this example for yourself it will require tweaking a few things. 

For starters you should download the victron xlsx register file from https://github.com/victronenergy/dbus_modbustcp/blob/master/CCGX-Modbus-TCP-register-list.xlsx  
Check the tabs for the relevant information. Especially tab #2 Unit ID Mapping  

Change the GX device IP address. Port is standard 502  

Check Instance #'s from Cerbo GX and cross referenced to the unit ID in the Victron TCP-MODbus register xls file.  

Change the the instance #'s to their correct values  

You likely dont have the 3 temperature sensors included. Change the variable to turn them on and off.  

  
If you use Example2.py you also need to adjust the portal id value. read the comment on how to find your portal id.  
This number is needed even with no internet access as its the name of your venus device.  
  
Examply.py should work on a very basic system such as running on the venus GX device itself. Minimal requirements.  
Example2.py has some additional requirements and should be run on your local nix* machine.

Example.py requires modbus enabled on the GX device  
Example2.py requires modbus & Mqtt enabled on the GX device.  
  
Example.py
![alt text](https://github.com/optio50/Victron_Modbus_TCP/blob/main/Modbus_2022-02-13_19-40-40.png?raw=true) 
  
Example2.py      
![alt text](https://github.com/optio50/Victron_Modbus_TCP/blob/main/Peek_2022-02-19_14-30.apng?raw=true)
  
PyQT5-Dual-Charger.py    
PyQT5-Dual-Charger.ui    
![alt text](https://github.com/optio50/Victron_Modbus_TCP/blob/main/Screenshot_2022-05-28_16-02-08.png?raw=true)    


TK-VictronSolar.py    
![alt text](https://github.com/optio50/Victron_Modbus_TCP/blob/main/VictronSolar-SingleMPPT.apng?raw=true)    

PyQT5-No-Multiplus-Single-Charger-JBD-BMS.py    
This file is for a Raspi and a single Victron SmartSolar Charger. Also includes a Serial UART BMS (JBD in my case).    
I have no idea if this works with the other compatiable BMS's. I only have a JBD.    
Venus OS Serial BMS info    
https://github.com/Louisvdw/dbus-serialbattery    
USB Serial interface https://overkillsolar.com/product/usb-module-for-bms/    
The connector included did not fit my BMS, YMMV. I cut the BMS BlueTooth cable in half and soldered the UART wire's to the connector wire's    
![alt text](https://github.com/optio50/Victron_Modbus_TCP/blob/main/PyQT5-No-Multiplus-Single-Charger-JBD-BMS.png?raw=true)    
    
To install  
git clone https://github.com/optio50/Victron_Modbus_TCP  
cd Victron_Modbus_TCP  
chmod +x Example.py  
pip3 install paho-mqtt  
pip3 install pymodbus  
./Example.py  
or  
./Example2.py    
 
 
To use the PyQt files you will need to.    

```pip install pymodbus paho-mqtt pglive```    
install PyQT5 with your package manager.     
such as ```sudo apt install python3-pyqt5```

The PyQT5-Dual-Charger.py and PyQT5-Dual-Charger.ui are PYQT5 files that are used together.    
Same with PyQT5-Single-Charger.py and PyQT5-Single-Charger.ui    
Just run the .py file and the .ui file will auto load.    
execute in the cloned directory as the icon file is in that location.    
Your system theme / font will dictate the style and appearence of the Pyqt program.

You must have the correct Victron equipment. such as Multiplus, BMV, Solar charger, Venus GX device.    


 
