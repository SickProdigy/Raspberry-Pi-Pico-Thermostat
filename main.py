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
from scripts.scheduler import ScheduleMonitor  # NEW: Import scheduler for time-based temp changes

# ===== START: Configuration Loading =====
# Load saved settings from config.json file on Pico
def load_config():
    """Load configuration from config.json file."""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            print("Loaded saved settings from config.json")
            return config
    except:
        # If file doesn't exist or is corrupted, use defaults
        print("No saved config found, using defaults")
        return {
            'ac_target': 77.0,         # Default AC target temp
            'ac_swing': 1.0,           # Default AC tolerance (+/- degrees)
            'heater_target': 80.0,     # Default heater target temp
            'heater_swing': 2.0,       # Default heater tolerance (+/- degrees)
            'schedules': [],           # No schedules by default
            'schedule_enabled': False  # Schedules disabled by default
        }

# Load configuration from file
config = load_config()
# ===== END: Configuration Loading =====

# ===== START: WiFi Connection =====
# Connect to WiFi using credentials from secrets.py
wifi = connect_wifi(led)

# Set static IP and print WiFi details
if wifi and wifi.isconnected():
    # Configure static IP (easier to bookmark web interface)
    static_ip = '192.168.86.43'  # Change this to match your network
    subnet = '255.255.255.0'
    gateway = '192.168.86.1'     # Usually your router IP
    dns = '192.168.86.1'         # Usually your router IP
    
    # Apply static IP configuration
    wifi.ifconfig((static_ip, subnet, gateway, dns))
    time.sleep(1)
    
    # Print WiFi details for debugging
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
    
    # Send startup notification to Discord
    send_discord_message(f"Pico W online at http://{ifconfig[0]} ✅")
    
    # ===== START: NTP Time Sync =====
    # Sync time with internet time server (required for schedules to work correctly)
    # Without this, the Pico's clock starts at 2021 on every reboot
    try:
        import ntptime
        ntptime.settime()  # Downloads current time from pool.ntp.org
        print("Time synced with NTP server")
    except Exception as e:
        print("Failed to sync time: {}".format(e))
    # ===== END: NTP Time Sync =====
    
else:
    # WiFi connection failed
    print("\n" + "="*50)
    print("WiFi Connection Failed!")
    print("="*50 + "\n")
# ===== END: WiFi Connection =====

# ===== START: Web Server Setup =====
# Start web server for monitoring and control (accessible at http://192.168.86.43)
web_server = TempWebServer(port=80)
web_server.start()
# ===== END: Web Server Setup =====

# ===== START: Sensor Configuration =====
# Define all temperature sensors and their alert thresholds
SENSOR_CONFIG = {
    'inside': {
        'pin': 10,              # GPIO pin for DS18B20 sensor
        'label': 'Inside',      # Display name
        'alert_high': 80.0,     # Send alert if temp > 80°F
        'alert_low': 70.0       # Send alert if temp < 70°F
    },
    'outside': {
        'pin': 11,              # GPIO pin for DS18B20 sensor
        'label': 'Outside',     # Display name
        'alert_high': 85.0,     # Send alert if temp > 85°F
        'alert_low': 68.0       # Send alert if temp < 68°F
    }
}

# Initialize sensors based on configuration
def get_configured_sensors():
    """Return dictionary of configured sensor instances."""
    sensors = {}
    for key, config in SENSOR_CONFIG.items():
        sensors[key] = TemperatureSensor(pin=config['pin'], label=config['label'])
    return sensors

# Create sensor instances
sensors = get_configured_sensors()
# ===== END: Sensor Configuration =====

# ===== START: AC Controller Setup =====
# Set up air conditioning relay controller
ac_controller = ACController(
    relay_pin=15,           # GPIO pin connected to AC relay
    min_run_time=30,        # Minimum seconds AC must run before turning off
    min_off_time=5          # Minimum seconds AC must be off before turning on again
)

# Create AC monitor (automatically controls AC based on temperature)
ac_monitor = ACMonitor(
    ac_controller=ac_controller,
    temp_sensor=sensors['inside'],      # Use inside sensor for AC control
    target_temp=config['ac_target'],    # Target temp from config.json
    temp_swing=config['ac_swing'],      # Tolerance (+/- degrees)
    interval=30                         # Check temperature every 30 seconds
)
# ===== END: AC Controller Setup =====

# ===== START: Heater Controller Setup =====
# Set up heating relay controller
heater_controller = HeaterController(
    relay_pin=16,           # GPIO pin connected to heater relay
    min_run_time=30,        # Minimum seconds heater must run before turning off
    min_off_time=5          # Minimum seconds heater must be off before turning on again
)

# Create heater monitor (automatically controls heater based on temperature)
heater_monitor = HeaterMonitor(
    heater_controller=heater_controller,
    temp_sensor=sensors['inside'],          # Use inside sensor for heater control
    target_temp=config['heater_target'],    # Target temp from config.json
    temp_swing=config['heater_swing'],      # Tolerance (+/- degrees)
    interval=30                             # Check temperature every 30 seconds
)
# ===== END: Heater Controller Setup =====

# ===== START: Schedule Monitor Setup =====
# Create schedule monitor (automatically changes temp targets based on time of day)
schedule_monitor = ScheduleMonitor(
    ac_monitor=ac_monitor,          # Pass AC monitor to control
    heater_monitor=heater_monitor,  # Pass heater monitor to control
    config=config,                  # Pass config with schedules
    interval=60                     # Check schedule every 60 seconds
)
# ===== END: Schedule Monitor Setup =====

# ===== START: Print Current Settings =====
# Display loaded configuration for debugging
print("\n" + "="*50)
print("Current Climate Control Settings:")
print("="*50)
print(f"AC Target:      {config['ac_target']}°F ± {config['ac_swing']}°F")
print(f"Heater Target:  {config['heater_target']}°F ± {config['heater_swing']}°F")
print(f"Schedule:       {'Enabled' if config.get('schedule_enabled') else 'Disabled'}")
if config.get('schedules'):
    print(f"Schedules:      {len(config.get('schedules', []))} configured")
print("="*50 + "\n")
# ===== END: Print Current Settings =====

# ===== START: Monitor Setup =====
# Set up all monitoring systems (run in order during main loop)
monitors = [
    # WiFi monitor: Checks connection, reconnects if needed, blinks LED
    WiFiMonitor(wifi, led, interval=5, reconnect_cooldown=60),
    
    # Schedule monitor: Changes temp targets based on time of day
    schedule_monitor,
    
    # AC monitor: Automatically turns AC on/off based on temperature
    ac_monitor,
    
    # Heater monitor: Automatically turns heater on/off based on temperature
    heater_monitor,
    
    # Inside temperature monitor: Logs temps, sends alerts if out of range
    TemperatureMonitor(
        sensor=sensors['inside'],
        label=SENSOR_CONFIG['inside']['label'],
        check_interval=10,                                  # Check temp every 10 seconds
        report_interval=30,                                 # Log to CSV every 30 seconds
        alert_high=SENSOR_CONFIG['inside']['alert_high'],  # High temp alert threshold
        alert_low=SENSOR_CONFIG['inside']['alert_low'],    # Low temp alert threshold
        log_file="/temp_logs.csv",                         # CSV file path
        send_alerts_to_separate_channel=True               # Use separate Discord channel
    ),
    
    # Outside temperature monitor: Logs temps, sends alerts if out of range
    TemperatureMonitor(
        sensor=sensors['outside'],
        label=SENSOR_CONFIG['outside']['label'],
        check_interval=10,                                   # Check temp every 10 seconds
        report_interval=30,                                  # Log to CSV every 30 seconds
        alert_high=SENSOR_CONFIG['outside']['alert_high'],  # High temp alert threshold
        alert_low=SENSOR_CONFIG['outside']['alert_low'],    # Low temp alert threshold
        log_file="/temp_logs.csv",                          # CSV file path
        send_alerts_to_separate_channel=False               # Use main Discord channel
    ),
]
# ===== END: Monitor Setup =====

print("Starting monitoring loop...")
print("Press Ctrl+C to stop\n")

# ===== START: Main Loop =====
# Main monitoring loop (runs forever until Ctrl+C)
while True:
    # Run all monitors (each checks if it's time to run via should_run())
    run_monitors(monitors)
    
    # Check for incoming web requests (non-blocking)
    # Pass schedule_monitor so web interface can reload config when schedules change
    web_server.check_requests(sensors, ac_monitor, heater_monitor, schedule_monitor)
    
    # Small delay to prevent CPU overload (0.1 seconds = 10 loops per second)
    time.sleep(0.1)
# ===== END: Main Loop =====