from machine import Pin
import time
import network
import urequests as requests
from secrets import secrets
from scripts.discord_webhook import send_discord_message


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

# Send startup message if connected
if wifi and wifi.isconnected():
    send_discord_message("Pico W online and connected ✅")


# Throttle reconnect attempts
RECONNECT_COOLDOWN_MS = 60000  # 60 seconds
last_attempt_ms = time.ticks_ms()


# Connection monitoring loop
while True:
    if not wifi or not wifi.isconnected():
        # Fast blink when disconnected
        led.on()
        time.sleep(0.2)
        led.off()
        time.sleep(0.2)

        # Only try to reconnect after cooldown
        if time.ticks_diff(time.ticks_ms(), last_attempt_ms) >= RECONNECT_COOLDOWN_MS:
            last_attempt_ms = time.ticks_ms()
            wifi = connect_wifi()
            # Notify only when connection is restored
            if wifi and wifi.isconnected():
                send_discord_message("WiFi connection restored 🔄")

    else:
        # Slow blink when connected
        led.on()
        time.sleep(1)
        led.off()
        time.sleep(1)
    
    time.sleep(0.1)