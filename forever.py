#!/usr/bin/python3
from subprocess import Popen
from datetime import datetime
import time
import sys

filename = sys.argv[1]
while True:
#    print("\nStarting " + filename)
    p = Popen("python3 " + filename, shell=True)
    
    # Datetime object containing current date and time
    nowStart = datetime.now()
    # Fri 21 Jan 2022     09:06:57 PM
    dt_stringStart = nowStart.strftime("%a %d %b %Y     %r")
    
    f = open("/data/MQTT.log", "a")
    f.write("Keep-Alive Started " + dt_stringStart + "\n")
    f.close()
    time.sleep(5) # If process did die, Wait 5 seconds before trying again.
    p.wait()
