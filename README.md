# Victron_Modbus_TCP
Victron Modbus TCP Example


A rudimentary example of the Victron TCP Modbus.  
If you intend to use this example for yourself it will require tweaking a few things. 

For starters you should download the victron xlsx register file from https://github.com/victronenergy/dbus_modbustcp/blob/master/CCGX-Modbus-TCP-register-list.xlsx  
Check the tabs for the relevant information. Especially tab #2 Unit ID Mapping  

Change the GX device IP address. Port is standard 502  

Check Instance #'s from Cerbo GX and cross referenced to the unit ID in the Victron TCP-MODbus register xls file.  

Change the the instance #'s to their correct values  

You likely dont have the 3 temperature sensors included. Remove them or comment them out.  

This file is based on a system that has victron equipment in an ESS system. Multiplus, Solar charger, BMV  

![alt text](https://github.com/optio50/Victron_Modbus_TCP/blob/main/Modbus_2022-01-18_22-58-24.png?raw=true)  
  
    
    
To install  
git clone https://github.com/optio50/Victron_Modbus_TCP  
cd Victron_Modbus_TCP  
chmod +x Example.py  
make sure you have the correct dependencies installed (pymodbus)  
./Example.py  
