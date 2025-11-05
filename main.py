from machine import Pin
import time
from scripts.networking import connect_wifi
from scripts.discord_webhook import send_discord_message
from scripts.monitors import TemperatureMonitor, WiFiMonitor, ACMonitor, run_monitors
from scripts.temperature_sensor import TemperatureSensor, get_configured_sensors
from scripts.air_conditioning import ACController

# Initialize pins (LED light onboard)
led = Pin("LED", Pin.OUT)
led.low()

# Connect to WiFi
wifi = connect_wifi(led)

# Send startup message if connected
if wifi and wifi.isconnected():
    send_discord_message("Pico W online and connected ✅")

# Sensor configuration registry (moved from temperature_sensor.py)
SENSOR_CONFIG = {
    'inside': {
        'pin': 10,
        'label': 'Inside',
        'alert_high': 80.0,
        'alert_low': 70.0
    },
    'outside': {
        'pin': 11,
        'label': 'Outside',
        'alert_high': 85.0,
        'alert_low': 68.0
    }
}
# Initialize sensors based on configuration
def get_configured_sensors():  # define the function here
    """Return dictionary of configured sensor instances."""
    sensors = {}
    for key, config in SENSOR_CONFIG.items():
        sensors[key] = TemperatureSensor(pin=config['pin'], label=config['label'])
    return sensors

# Get configured sensors
sensors = get_configured_sensors()  # Call the function here

# AC Controller options
ac_controller = ACController(
    relay_pin=15,
    min_run_time=30,   # min run time in seconds
    min_off_time=5     # min off time in seconds
    )

ac_monitor = ACMonitor(
    ac_controller=ac_controller,
    temp_sensor=sensors['inside'],  # <-- This is your inside temperature sensor
    target_temp=77.0,   # target temperature in Fahrenheit
    temp_swing=1.0,      # temp swing target_temp-temp_swing to target_temp+temp_swing
    interval=30         # check temp every x seconds
)

# Set up monitors
monitors = [
    WiFiMonitor(wifi, led, interval=5, reconnect_cooldown=60), # Wifi monitor, Check WiFi every 5s
    ac_monitor, # AC monitor
    TemperatureMonitor( # Inside temperature monitor
        sensor=sensors['inside'],
        label=SENSOR_CONFIG['inside']['label'],
        check_interval=10,      # Check temp every 10 seconds
        report_interval=30,     # Report/log every 30 seconds
        alert_high=SENSOR_CONFIG['inside']['alert_high'],
        alert_low=SENSOR_CONFIG['inside']['alert_low'],
        log_file="/temp_logs.csv",
        send_alerts_to_separate_channel=True
    ),
    TemperatureMonitor( # Outside temperature monitor
        sensor=sensors['outside'],
        label=SENSOR_CONFIG['outside']['label'],
        check_interval=10,      # Check temp every 10 seconds
        report_interval=30,     # Report/log every 30 seconds
        alert_high=SENSOR_CONFIG['outside']['alert_high'],
        alert_low=SENSOR_CONFIG['outside']['alert_low'],
        log_file="/temp_logs.csv",
        send_alerts_to_separate_channel=False
    ),
]

# Main monitoring loop
while True:
    run_monitors(monitors)
    time.sleep(0.1)