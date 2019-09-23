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
num_mobile = "+61449980417"
id_machine = "CoC1"
in_protected_area = False
entered_time = 0
grace_period = 120  # 2 minutes grace before the machine is shut down

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
time.sleep(2)
longitude = node.getLongitude()
time.sleep(2)
latitude = node.getLatitude()
time.sleep(2)
node.sendSMS(num_mobile, "The Code of Conscience system is active. The current location - Latitude: {}, Longtitude: {}".format(latitude, longitude))
print("The current location - Latitude: {}, Longtitude: {}".format(latitude, longitude))


# Loading protected area map file
print("Loading protected area...")
shapefile = "WDPA_May2019_protected_area_24787-shapefile-polygons.shp"
df = gpd.read_file(shapefile)
machineLocation = Point(longitude, latitude)
print("Ready to check...")


def processInput(i, point):
    return point.within(df.loc[i].geometry)


def isInProtectedArea(machineLocation):
    num_cores = multiprocessing.cpu_count()
    process = partial(processInput, point=machineLocation)
    global in_protected_area
    global entered_time
    with multiprocessing.Pool(num_cores) as p:
        result = p.map(process, range(len(df)))

    if sum(result):
        print(" ")
        print("[!] The machine is inside a protected area")

        if in_protected_area is False:
            node.sendSMS(num_mobile, "The machine: " + id_machine +
                         " is inside a protected area. You have 2 minutes to leave this area. After this time, your engine will shut down.")
            entered_time = time.time()
            in_protected_area = True
    else:
        print(" ")
        print("[√] The machine is not inside a protected area")

        node.turnOffRelay()
        in_protected_area = False


print("Monitoring in progress! Press CTRL+C to exit")
try:
    while 1:
        time.sleep(2)
        longitude = node.getLongitude()
        time.sleep(2)
        latitude = node.getLatitude()
        machineLocation = Point(longitude, latitude)

        # check position at every opportunity
        if (longitude is not 0) & (latitude is not 0):
            isInProtectedArea(machineLocation)

            # if vehicle lingers too long, shut it down
            if in_protected_area is True and ((time.time() - entered_time) > grace_period):
                grace_period += 300
                node.turnOnRelay()
                time.sleep(2)
                node.sendSMS(num_mobile, "The machine: " + id_machine +
                             " has been in the protected area too long and the engine shut down signal has been sent.")
                time.sleep(2)
                node.sendSMS(
                    num_mobile, "Call 13 13 13 to verify your purpose and remove this restriction.")
        else:
            print('GPS data is missing')

except KeyboardInterrupt:  # If CTRL+C is pressed, exit cleanly:
    GPIO.cleanup()  # cleanup all GPIO
