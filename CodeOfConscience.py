import multiprocessing
import time
from decimal import *
from functools import partial

import geopandas as gpd
from cellulariot import cellulariot
from joblib import Parallel, delayed
from shapely.geometry import Point, Polygon

import RPi.GPIO as GPIO

# Information
num_mobile = "XXXXXXXXXX"
id_machine = "CoC1"
allow_SMS = True

# Initializing Sixfab CellularIoT App. Shield
node = cellulariot.CellularIoTApp()
node.setupGPIO()
node.disable()
time.sleep(1)
node.enable()
time.sleep(1)
node.powerUp()

# LTE connection Check
node.getResponse("RDY")
node.sendATComm("ATE1", "OK\r\n")
time.sleep(0.5)

# Connecting GPS
node.turnOnGNSS()
time.sleep(60)
fixed = node.getFixedLocation()
time.sleep(1)
node.sendSMS(num_mobile, "GPS location has been fixed.")
print("GPS location has been fixed. Reading the current position../")
time.sleep(1)
longitude = node.getLongitude()
time.sleep(1)
latitude = node.getLatitude()
time.sleep(1)
node.sendSMS(num_mobile, "The current location - Latitude: {}, Longtitude: {}".format(latitude, longitude))
print("The current location - Latitude: {}, Longtitude: {}".format(latitude, longitude))


# Loading protected area map file
print("Loading protected area...")
shapefile = "organ-pipes-shapefile-polygons.shp"
df = gpd.read_file(shapefile)
machineLocation = Point(longitude, latitude)
print("Ready to check...")


def processInput(i, point):
    return point.within(df.loc[i].geometry)


def isInProtectedArea(machineLocation):
    num_cores = multiprocessing.cpu_count()
    process = partial(processInput, point=machineLocation)
    with multiprocessing.Pool(num_cores) as p:
        result = p.map(process, range(len(df)))
    if sum(result):
        print(" ")
        print("[!] The machine is inside a protected area")
        if allow_SMS:
            node.sendSMS(num_mobile, "The machine: " + id_machine + " is inside a protected area")
        allow_SMS = False
        node.turnOnRelay()
    else:
        print(" ")
        print("[√] The machine is not inside a protected area")
        node.turnOffRelay()
        allow_SMS = True


print("Monitoring in progress! Press CTRL+C to exit")
try:
    while 1:
        time.sleep(0.5)
        longitude = node.getLongitude()
        time.sleep(0.5)
        latitude = node.getLatitude()
        machineLocation = Point(longitude, latitude)
        if (longitude is not 0) & (latitude is not 0):
            isInProtectedArea(machineLocation)
        else:
            print('GPS data is missing')
except KeyboardInterrupt:  # If CTRL+C is pressed, exit cleanly:
    GPIO.cleanup()  # cleanup all GPIO
