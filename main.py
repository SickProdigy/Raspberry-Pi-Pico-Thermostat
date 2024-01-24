from machine import Pin
import time
import network
import urequests as requests
from secrets import secrets

# Load login data from different file for security!
# ssid = secrets['ssid']
# pw = secrets['pw']

# Initialize pins
contactorLights = Pin(18, Pin.OUT)
led = machine.Pin("LED", machine.Pin.OUT)


led.low()
contactorLights.low() # sets to lowest setting 0 first. 

contactorLights.toggle() # Toggle contactor on for testing

# Network connection going through
wifi = network.WLAN(network.STA_IF)
wifi.active(True)   # must capitalize boolean statements!
wifi.connect(secrets['ssid'], secrets['password'])

print(wlan.ifconfig())

#Proof connected
led.on()
print('Connected to Wi-Fi network')
time.sleep(5)
led.off()

# If disconnect will flash light
while wifi.isconnected() == False:
  led.on()
  time.sleep(0.5)
  led.off()
  time.sleep(0.5)

# think the while loop will hold the next line from running, we will see

# while True:
#    led.toggle()
#    utime.sleep(0.2)

# Need to log time accurately. Connect to internet with wifi and set time. Start logging. Also need temp probes and how to pull temps