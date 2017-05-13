#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys
reload(sys)
sys.setdefaultencoding('utf8')

import time
import datetime
import serial


"""
****************
geiger_gmc320.py
****************

Python script for communication with GQ GMC-320+ from GQ Electronics LLC
(https://www.gqelectronicsllc.com/comersus/store/comersus_viewItem.asp?idProduct=4579)

Features:

* Uses serial communication (via USB)
* Reads firmware information from geiger counter (model, serial number, ...)
* Reads temperature and voltage
* Reads CPM and converts to nSv/h (nSv/h = CPM * 6.5, see https://www.gqelectronicsllc.com/forum/topic.asp?TOPIC_ID=4226&SearchTerms=conversio)
* Prints continouse data to terminal
* Stores data in json format to text file (json_data_log = True)
* Stores data to dummy device in FHEM server (fhem_data_log = True)

ToDo:

* Command line paramters
* Handling of serial connection problems
* Set date and time of geiger counter on start
* Create FHEM device only if not present
* Implement WiFi connection
* Daemon mode
* Test with Python 3

Based on:

Protocol description http://www.gqelectronicsllc.com/download/GQ-RFC1201.txt
FHEM python api from https://github.com/domschl/python-fhem
geiger_basic.py from ftp://197.155.77.5/sourceforge/g/project/project/ge/geigerlog/old%20files/geiger_basic.py

"""

# Copyright (C) Christian C. Gruber
#
# The following terms apply to all files associated
# with the software unless explicitly disclaimed in individual files.
#
# The authors hereby grant permission to use, copy, modify, distribute,
# and license this software and its documentation for any purpose, provided
# that existing copyright notices are retained in all copies and that this
# notice is included verbatim in any distributions. No written agreement,
# license, or royalty fee is required for any of the authorized uses.
# Modifications to this software may be copyrighted by their authors
# and need not follow the licensing terms described here, provided that
# the new terms are clearly indicated on the first page of each file where
# they apply.
#
# IN NO EVENT SHALL THE AUTHORS OR DISTRIBUTORS BE LIABLE TO ANY PARTY
# FOR DIRECT, INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES
# ARISING OUT OF THE USE OF THIS SOFTWARE, ITS DOCUMENTATION, OR ANY
# DERIVATIVES THEREOF, EVEN IF THE AUTHORS HAVE BEEN ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# THE AUTHORS AND DISTRIBUTORS SPECIFICALLY DISCLAIM ANY WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.  THIS SOFTWARE
# IS PROVIDED ON AN "AS IS" BASIS, AND THE AUTHORS AND DISTRIBUTORS HAVE
# NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES, ENHANCEMENTS, OR
# MODIFICATIONS.

__author__      = "Christian C. Gruber"
__copyright__   = "Copyright 2017"
__credits__     = "Christian C. Gruber"
__license__     = "GPL"
__version__     = "0.1"
__maintainer__  = ""
__email__       = "cg@chilia.com"
__status__      = "Development"

# *** SETTINGS START ***

# Settings: General
json_data_log = True
fhem_data_log = True

# Settings: device
device = "GQ_GMC_320E_plus"     # name of your device
port = "/dev/ttyUSB0"
baud = 115200
dT = 5 # CPM read interval (in s)

# Settings: FHEM
FHEM_server = "127.0.0.1"
FHEM_port = "7072"

# Settings: json data log dir
json_data_logdir = "/var/data"

# *** SETTINGS END ***

json_log_file = json_data_logdir + "/geiger_" + device + ".json"

def getVER(ser):
    ser.write(b'<GETVER>>')
    rec = ser.read(14)   
    return rec

def getCPM(ser):
    ser.write(b'<GETCPM>>')
    rec = ser.read(2)
    return ord(rec[0])<< 8 | ord(rec[1])
    
def getVOLT(ser):
    ser.write(b'<GETVOLT>>')
    rec = ser.read(1)
    return ord(rec)/10.0 

def getCFG(ser):
    ser.write(b'<GETCFG>>')
    rec = ser.read(256)    
    cfg = []
    for i in range(0,256):
        cfg.append(ord(rec[i]))
    return cfg

def getSERIAL(ser):
    ser.write(b'<GETSERIAL>>')
    a = ser.read(7)
    hexlookup = "0123456789ABCDEF"    
    rec =""
    for i in range(0,7):    
        n1   = ((ord(a[i]) & 0xF0) >>4)
        n2   = ((ord(a[i]) & 0x0F))
        rec += hexlookup[n1] + hexlookup[n2]
    return rec

def getDATETIME(ser):
    ser.write(b'<GETDATETIME>>')
    dt = ser.read(7)
    idt = []
    for i in range(0,6):
        idt.append( ord(dt[i]))
    idt[0] += 2000
    return datetime.datetime(idt[0], idt[1], idt[2], idt[3],idt[4],idt[5])

def getTEMP(ser):
    ser.write(b'<GETTEMP>>')
    rec = ser.read(4)
    signe = "+"
    if ord(rec[2]) != 0:
        signe = "-"
    temp = signe + str(ord(rec[0])) + "." + str(ord(rec[1]))
    return temp
    
def getGYRO(ser):
    ser.write(b'<GETGYRO>>')
    rec = ser.read(7)
    return rec
    
def stime():
    """ return current time as YYYY-MM-DD HH:MM:SS"""
    return time.strftime("%Y-%m-%d %H:%M:%S")


# Serial port setup
ser = serial.Serial(port, baud)

# Device information dictionary
config = {  'settings_port' :               port,
            'settings_baud' :               baud,
            'settings_dT' :                 dT,
            'settings_json_data_log' :      str(json_data_log),
            'settings_json_log_file' :      json_log_file,
            'settings_fhem_data_log' :      str(fhem_data_log),
            'settings_baud' :               baud,
            'settings_FHEM_server' :        FHEM_server,
            'settings_FHEM_port' :          FHEM_port,
            'settings_json_data_logdir' :   json_data_logdir,
            'version' :                     getVER(ser),
            'serial' :                      getSERIAL(ser),
            'device' :                      device
          }
          
print "{:<30} {:<20}".format('Key','Label')
for key, value in config.iteritems():
    print "{:<30} {:<20}".format(key, value)
          
if fhem_data_log == True: 
    
    import fhem
    
    fh = fhem.Fhem(FHEM_server)
    fh.connect()

    if fh.connected():
    
        fh.send_cmd("define  " + device + " dummy")
        stateFormat = " stateFormat { sprintf('Radiation: %s nsV/h (%s CPM@%s °C)', ReadingsVal('GQ_GMC_320E_plus','rad_nsvh',''), ReadingsVal('GQ_GMC_320E_plus','rad_cpm',''), ReadingsVal('GQ_GMC_320E_plus','temperature_C',''), )}"
        fh.send_cmd("attr  " + device + stateFormat)
          
        for key, value in config.items():
            fh.send_cmd("setreading " + device + " " + str(key) + " " + str(value))
    
try:
    print "\n{:<25} {:<10} {:<10} {:<10} {:<10}".format('datetime','rad_cpm','rad_nsvh','voltage_V','temperature_T')
    
    while True:        

        cpm = getCPM(ser)

        data = { 
                    'rad_cpm' :       cpm, 
                    'rad_nsvh' :      cpm * 6.5,
                    'voltage_V' :     getVOLT(ser),
                    'datetime' :      getDATETIME(ser),
                    'temperature_C' : getTEMP(ser)
                }
                
        print "{:<25} {:<10} {:<10} {:<10} {:<10}".format(str(data['datetime']),data['rad_cpm'],data['rad_nsvh'],data['voltage_V'],data['temperature_C'])
                
        if json_data_log == True:
            with open(json_log_file, "a") as f:
                f.write(str(data))
                
        if fhem_data_log == True and fh.connected():        
            for key, value in data.items():
                fh.send_cmd("setreading " + device + " " + str(key) + " " + str(value))
        
        time.sleep(dT)
        
except KeyboardInterrupt:
    pass

ser.close()
exit()