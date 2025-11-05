import network
import time
from secrets import secrets

RECONNECT_COOLDOWN_MS = 60000  # 60 seconds

def connect_wifi(led=None, timeout=10):
    """
    Connect to WiFi using secrets['ssid'] / secrets['password'].
    If `led` (machine.Pin) is provided, pulse it once on successful connect.
    Returns the WLAN object or None on failure.
    """
    wifi = network.WLAN(network.STA_IF)
    wifi.active(True)
    
    # print("Connecting to WiFi...", end="")
    wifi.connect(secrets['ssid'], secrets['password'])
    
    # Wait for connection with timeout
    max_wait = timeout
    while max_wait > 0:
        if wifi.status() < 0 or wifi.status() >= 3:
            break
        max_wait -= 1
        # print(".", end="")
        time.sleep(1)
        
    if wifi.isconnected():
        # print("\nConnected! Network config:", wifi.ifconfig())
        if led:
            led.on()
            time.sleep(1)
            led.off()
        return wifi
    else:
        # print("\nConnection failed!")
        return None