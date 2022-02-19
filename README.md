# Victron_Modbus_TCP
Victron Modbus TCP Example


An example of the Victron TCP Modbus.  
If you intend to use this example for yourself it will require tweaking a few things. 

For starters you should download the victron xlsx register file from https://github.com/victronenergy/dbus_modbustcp/blob/master/CCGX-Modbus-TCP-register-list.xlsx  
Check the tabs for the relevant information. Especially tab #2 Unit ID Mapping  

Change the GX device IP address. Port is standard 502  

Check Instance #'s from Cerbo GX and cross referenced to the unit ID in the Victron TCP-MODbus register xls file.  

Change the the instance #'s to their correct values  

You likely dont have the 3 temperature sensors included. Change the variable to turn them on and off.  

This file is based on a system that has victron equipment in an ESS system. Multiplus, Solar charger, BMV  
If you dont have ESS enabled change the variable to turn it on and off.  

If you use Example2.py you also need to adjust the portal id value. read the comment on how to find your portal id.  
This number is needed even with no internet access as its the name of your venus device.  
  
Examply.py should work on a very basic system such as running on the venus GX device itself. Minimal requirements.  
Example2.py has some additional requirements and should be run on your local nix* machine.

Example.py requires modbus enabled on the GX device  
Example2.py requires modbus & Mqtt enabled on the GX device.  
  
Example.py
![alt text](https://github.com/optio50/Victron_Modbus_TCP/blob/main/Modbus_2022-02-13_19-40-40.png?raw=true) 
  
Example2.py      
![alt text](https://github.com/optio50/Victron_Modbus_TCP/blob/main/Modbus_2022-02-18_13-50-13.png?raw=true)
  
    
    
To install  
git clone https://github.com/optio50/Victron_Modbus_TCP  
cd Victron_Modbus_TCP  
chmod +x Example.py  
pip3 install paho-mqtt  
pip3 install pymodbus  
./Example.py  
or  
./Example2.py
