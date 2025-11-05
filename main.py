from machine import Pin
import time
from scripts.networking import connect_wifi
from scripts.discord_webhook import send_discord_message
from scripts.monitors import TemperatureMonitor, WiFiMonitor, run_monitors
from scripts.temperature_sensor import TemperatureSensor

# Initialize pins (LED light onboard)
led = Pin("LED", Pin.OUT)
led.low()

# Connect to WiFi
wifi = connect_wifi(led)

# Send startup message if connected
if wifi and wifi.isconnected():
    send_discord_message("Pico W online and connected ✅")

# Initialize temperature sensors
inside_sensor = TemperatureSensor(pin=10, label="Inside")
outside_sensor = TemperatureSensor(pin=11, label="Outside")

# Set up monitors
monitors = [
    WiFiMonitor(wifi, led, interval=5, reconnect_cooldown=60),
    TemperatureMonitor(
        sensor=inside_sensor,
        label="Inside",
        interval=300,  # 5 minutes
        alert_high=85.0,
        alert_low=32.0,
        log_file="/temp_logs.csv"
    ),
    TemperatureMonitor(
        sensor=outside_sensor,
        label="Outside",
        interval=300,  # 5 minutes
        alert_high=100.0,
        alert_low=20.0,
        log_file="/temp_logs.csv"
    ),
    # Add more monitors here later:
    # SoilMoistureMonitor(pin=26, interval=600),
    # LightLevelMonitor(pin=27, interval=900),
]

# Main monitoring loop
while True:
    run_monitors(monitors)
    time.sleep(0.1)