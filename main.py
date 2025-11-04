from machine import Pin
import time
import network
import urequests as requests
from secrets import secrets

# Initialize pins (LED light onboard)
led = Pin("LED", Pin.OUT)
# Initial state
led.low()

# Network connection
def connect_wifi():
    wifi = network.WLAN(network.STA_IF)
    wifi.active(True)
    
    print("Connecting to WiFi...", end="")
    wifi.connect(secrets['ssid'], secrets['password'])
    
    # Wait for connection with timeout
    max_wait = 10
    while max_wait > 0:
        if wifi.status() < 0 or wifi.status() >= 3:
            break
        max_wait -= 1
        print(".", end="")
        time.sleep(1)
        
    if wifi.isconnected():
        print("\nConnected! Network config:", wifi.ifconfig())
        led.on()
        time.sleep(1)
        led.off()
        return wifi
    else:
        print("\nConnection failed!")
        return None

# Connect to WiFi
wifi = connect_wifi()

# Connection monitoring loop
while True:
    if not wifi or not wifi.isconnected():
        # Fast blink when disconnected
        led.on()
        time.sleep(0.2)
        led.off()
        time.sleep(0.2)
        # Try to reconnect
        wifi = connect_wifi()
    else:
        # Slow blink when connected
        led.on()
        time.sleep(1)
        led.off()
        time.sleep(1)
    
    time.sleep(0.1)