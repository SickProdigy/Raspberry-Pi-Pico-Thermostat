from machine import Pin
import time
import network
import json

# Initialize pins (LED light onboard)
led = Pin("LED", Pin.OUT)
led.low()

# Hard reset WiFi interface before connecting
print("Initializing WiFi...")
try:
    wlan = network.WLAN(network.STA_IF)
    wlan.deinit()
    time.sleep(2)
    print("WiFi interface reset complete")
except Exception as e:
    print(f"WiFi reset warning: {e}")

# Import after WiFi reset
from scripts.networking import connect_wifi
from scripts.discord_webhook import send_discord_message
from scripts.monitors import TemperatureMonitor, WiFiMonitor, ACMonitor, HeaterMonitor, run_monitors
from scripts.temperature_sensor import TemperatureSensor
from scripts.air_conditioning import ACController
from scripts.heating import HeaterController
from scripts.web_server import TempWebServer
from scripts.scheduler import ScheduleMonitor

# Load saved settings from file
def load_config():
    """Load configuration from config.json file."""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            print("Loaded saved settings from config.json")
            return config
    except:
        print("No saved config found, using defaults")
        return {
            'ac_target': 77.0,
            'ac_swing': 1.0,
            'heater_target': 80.0,
            'heater_swing': 2.0,
            'schedules': [],
            'schedule_enabled': False
        }

# Load configuration
config = load_config()

# Connect to WiFi
wifi = connect_wifi(led)

# Set static IP and print WiFi details
if wifi and wifi.isconnected():
    # Configure static IP
    static_ip = '192.168.86.43'
    subnet = '255.255.255.0'
    gateway = '192.168.86.1'
    dns = '192.168.86.1'
    
    wifi.ifconfig((static_ip, subnet, gateway, dns))
    time.sleep(1)
    
    # Print WiFi details
    ifconfig = wifi.ifconfig()
    print("\n" + "="*50)
    print("WiFi Connected Successfully!")
    print("="*50)
    print(f"IP Address:     {ifconfig[0]}")
    print(f"Subnet Mask:    {ifconfig[1]}")
    print(f"Gateway:        {ifconfig[2]}")
    print(f"DNS Server:     {ifconfig[3]}")
    print(f"Web Interface:  http://{ifconfig[0]}")
    print("="*50 + "\n")
    
    # Send startup message with IP
    send_discord_message(f"Pico W online at http://{ifconfig[0]} ✅")
else:
    print("\n" + "="*50)
    print("WiFi Connection Failed!")
    print("="*50 + "\n")

# Start web server
web_server = TempWebServer(port=80)
web_server.start()

# Sensor configuration registry
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
def get_configured_sensors():
    """Return dictionary of configured sensor instances."""
    sensors = {}
    for key, config in SENSOR_CONFIG.items():
        sensors[key] = TemperatureSensor(pin=config['pin'], label=config['label'])
    return sensors

# Get configured sensors
sensors = get_configured_sensors()

# AC Controller options
ac_controller = ACController(
    relay_pin=15,
    min_run_time=30,
    min_off_time=5
)

# Use loaded config values for AC monitor
ac_monitor = ACMonitor(
    ac_controller=ac_controller,
    temp_sensor=sensors['inside'],
    target_temp=config['ac_target'],
    temp_swing=config['ac_swing'],
    interval=30
)

# Heater Controller options
heater_controller = HeaterController(
    relay_pin=16,
    min_run_time=30,
    min_off_time=5
)

# Use loaded config values for heater monitor
heater_monitor = HeaterMonitor(
    heater_controller=heater_controller,
    temp_sensor=sensors['inside'],
    target_temp=config['heater_target'],
    temp_swing=config['heater_swing'],
    interval=30
)

# Create schedule monitor
schedule_monitor = ScheduleMonitor(
    ac_monitor=ac_monitor,
    heater_monitor=heater_monitor,
    config=config,
    interval=60  # Check schedule every 60 seconds
)

# Print loaded settings
print("\n" + "="*50)
print("Current Climate Control Settings:")
print("="*50)
print(f"AC Target:      {config['ac_target']}°F ± {config['ac_swing']}°F")
print(f"Heater Target:  {config['heater_target']}°F ± {config['heater_swing']}°F")
print(f"Schedule:       {'Enabled' if config.get('schedule_enabled') else 'Disabled'}")
if config.get('schedules'):
    print(f"Schedules:      {len(config.get('schedules', []))} configured")
print("="*50 + "\n")

# Set up monitors
monitors = [
    WiFiMonitor(wifi, led, interval=5, reconnect_cooldown=60),
    schedule_monitor,  # Add schedule monitor
    ac_monitor,
    heater_monitor,
    TemperatureMonitor(
        sensor=sensors['inside'],
        label=SENSOR_CONFIG['inside']['label'],
        check_interval=10,
        report_interval=30,
        alert_high=SENSOR_CONFIG['inside']['alert_high'],
        alert_low=SENSOR_CONFIG['inside']['alert_low'],
        log_file="/temp_logs.csv",
        send_alerts_to_separate_channel=True
    ),
    TemperatureMonitor(
        sensor=sensors['outside'],
        label=SENSOR_CONFIG['outside']['label'],
        check_interval=10,
        report_interval=30,
        alert_high=SENSOR_CONFIG['outside']['alert_high'],
        alert_low=SENSOR_CONFIG['outside']['alert_low'],
        log_file="/temp_logs.csv",
        send_alerts_to_separate_channel=False
    ),
]

print("Starting monitoring loop...")
print("Press Ctrl+C to stop\n")

# Main monitoring loop
while True:
    run_monitors(monitors)
    web_server.check_requests(sensors, ac_monitor, heater_monitor)
    time.sleep(0.1)