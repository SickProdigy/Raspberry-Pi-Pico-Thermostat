from machine import Pin, RTC # type: ignore
import time # type: ignore
import network # type: ignore
import json
import gc  # type: ignore # ADD THIS - for garbage collection
import sys

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

# ===== NEW: NTP Sync Function (imports locally) =====
def sync_ntp_time(timezone_offset):
    """
    Sync time with NTP server (imports modules locally to save RAM).
    Returns True if successful, False otherwise.
    """
    try:
        # Import ONLY when needed (freed by GC after function ends)
        import socket  # type: ignore
        import struct  # type: ignore
        
        NTP_DELTA = 2208988800
        host = "pool.ntp.org"
        NTP_QUERY = bytearray(48)
        NTP_QUERY[0] = 0x1B
        
        # Create socket with timeout
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(3.0)  # 3-second timeout
        
        try:
            addr = socket.getaddrinfo(host, 123)[0][-1]
            s.sendto(NTP_QUERY, addr)
            msg = s.recv(48)
            val = struct.unpack("!I", msg[40:44])[0]
            utc_timestamp = val - NTP_DELTA
            
            # Apply timezone offset
            local_timestamp = utc_timestamp + (timezone_offset * 3600)
            
            # Set RTC with local time
            tm = time.gmtime(local_timestamp)
            RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))
            
            return True
            
        finally:
            s.close()
            
    except Exception as e:
        print("NTP sync failed: {}".format(e))
        return False
    finally:
        # Force garbage collection to free socket/struct modules
        gc.collect()
# ===== END: NTP Sync Function =====

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
        # If file doesn't exist or is corrupted, create default config
        print("No saved config found, creating default config.json...")
        
        default_config = {
            'static_ip': '192.168.86.43',
            'subnet': '255.255.255.0',
            'gateway': '192.168.86.1',
            'dns': '192.168.86.1',
            'timezone_offset': -6,     # Timezone offset from UTC (CST=-6, EST=-5, MST=-7, PST=-8, add 1 for DST)
            'ac_target': 75.0,         # Default AC target temp
            'ac_swing': 1.0,           # Default AC tolerance (+/- degrees)
            'heater_target': 72.0,     # Default heater target temp
            'heater_swing': 2.0,       # Default heater tolerance (+/- degrees)
            'temp_hold_duration': 3600, # Default hold duration in seconds (1 hour)
            'temp_hold_start_time': None, # No hold active at startup
            'schedules': [             # Default 4 schedules
                {
                    'time': '06:00',
                    'name': 'Morning',
                    'ac_target': 75.0,
                    'heater_target': 72.0
                },
                {
                    'time': '12:00',
                    'name': 'Midday',
                    'ac_target': 75.0,
                    'heater_target': 72.0
                },
                {
                    'time': '18:00',
                    'name': 'Evening',
                    'ac_target': 75.0,
                    'heater_target': 72.0
                },
                {
                    'time': '22:00',
                    'name': 'Night',
                    'ac_target': 75.0,
                    'heater_target': 72.0
                }
            ],
            'schedule_enabled': True, # Schedules disabled by default (user can enable via web)
            'permanent_hold': False    # Permanent hold disabled by default
        }
        
        # ===== START: Save default config to file =====
        try:
            with open('config.json', 'w') as f:
                json.dump(default_config, f)
            print("✅ Default config.json created successfully with 4 sample schedules")
        except Exception as e:
            print("⚠️ Warning: Could not create config.json: {}".format(e))
            print("   (Program will continue with defaults in memory)")
        # ===== END: Save default config to file =====
        
        return default_config

# global variables for Discord webhook status
discord_sent = False
discord_send_attempts = 0
pending_discord_message = None

# Load configuration from file
config = load_config()
import scripts.discord_webhook as discord_webhook
# Initialize discord webhook module with loaded config (must be done BEFORE any send_discord_message calls)
discord_webhook.set_config(config)

# Get timezone offset from config (with fallback to -6 if not present)
TIMEZONE_OFFSET = config.get('timezone_offset', -6)

# ===== START: Reset hold modes on startup =====
# Always reset to automatic mode on boot (don't persist hold states)
if 'schedule_enabled' in config:
    config['schedule_enabled'] = True  # Always enable schedules on boot
if 'permanent_hold' in config:
    config['permanent_hold'] = False   # Always clear permanent hold on boot
if 'temp_hold_start_time' in config:
    config['temp_hold_start_time'] = None  # Clear temp hold start time

# Save the reset config immediately
try:
    with open('config.json', 'w') as f:
        json.dump(config, f)
    print("✅ Hold modes reset - Automatic mode active")
except Exception as e:
    print("⚠️ Warning: Could not save config reset: {}".format(e))
# ===== END: Reset hold modes on startup =====
# ===== END: Configuration Loading =====

# ===== START: WiFi Connection =====
# Connect to WiFi using credentials from config.json
wifi = connect_wifi(led, config=config)

# Set static IP and print WiFi details
if wifi and wifi.isconnected():
    # Get static IP settings from config
    static_ip = config.get('static_ip')
    subnet = config.get('subnet')
    gateway = config.get('gateway')
    dns = config.get('dns')
    
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
    
    # Try sending Discord webhook NOW, before creating other objects
    gc.collect()
    ram_free = gc.mem_free()
    print(f"DEBUG: Free RAM before Discord send: {ram_free // 1024} KB")
    mem_ok = ram_free > 105000
    if mem_ok:
        ok = discord_webhook.send_discord_message("Pico W online at http://{}".format(ifconfig[0]), debug=False)
        if ok:
            print("Discord startup notification sent")
            discord_sent = True
        else:
            print("Discord startup notification failed")
            pending_discord_message = "Pico W online at http://{}".format(ifconfig[0])
            discord_send_attempts = 1
    else:
        print("Not enough memory for Discord startup notification")
        pending_discord_message = "Pico W online at http://{}".format(ifconfig[0])
        discord_send_attempts = 1
    
    # ===== Moved to later so discord could fire off startup message hopefully =====
    from scripts.monitors import TemperatureMonitor, WiFiMonitor, ACMonitor, HeaterMonitor, run_monitors
    from scripts.temperature_sensor import TemperatureSensor
    from scripts.air_conditioning import ACController
    from scripts.heating import HeaterController
    from scripts.web_server import TempWebServer
    from scripts.scheduler import ScheduleMonitor
    from scripts.memory_check import check_memory_once
    
    # Start web server early so page can load even if time sync is slow
    web_server = TempWebServer(port=80)
    web_server.start()

    # ===== INITIAL NTP SYNC (using function) =====
    ntp_synced = False
    try:
        ntp_synced = sync_ntp_time(TIMEZONE_OFFSET)
        if ntp_synced:
            print("Time synced with NTP server (UTC{:+d})".format(TIMEZONE_OFFSET))
        else:
            print("Initial NTP sync failed, will retry in background...")
    except Exception as e:
        print("Initial NTP sync error: {}".format(e))
    # ===== END: INITIAL NTP SYNC =====
    
else:
    # WiFi connection failed
    print("\n" + "="*50)
    print("WiFi Connection Failed!")
    print("="*50 + "\n")
# ===== END: WiFi Connection =====



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

# ===== APPLY ACTIVE SCHEDULE IMMEDIATELY ON STARTUP =====
if config.get('schedule_enabled', False):
    try:
        # Find and apply the current active schedule
        active_schedule = schedule_monitor._find_active_schedule()
        if active_schedule:
            schedule_monitor._apply_schedule(active_schedule)
            print("✅ Active schedule applied on startup: {}".format(
                active_schedule.get('name', 'Unnamed')
            ))
        else:
            print("ℹ️ No active schedule found (using manual targets)")
    except Exception as e:
        print("⚠️ Warning: Could not apply startup schedule: {}".format(e))
else:
    print("ℹ️ Schedules disabled - using manual targets")
# ===== END: APPLY ACTIVE SCHEDULE ON STARTUP =====
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

# ===== START: Startup Memory Check =====
# Check memory usage after all imports and initialization
check_memory_once()
# ===== END: Startup Memory Check =====

print("Starting monitoring loop...")
print("Press Ctrl+C to stop\n")

# Add NTP retry flags (before main loop)
retry_ntp_attempts = 0
max_ntp_attempts = 5  # Try up to 5 times after initial failure
last_ntp_sync = time.time()  # Track when we last synced

# ===== START: Main Loop =====
# Main monitoring loop (runs forever until Ctrl+C)
last_monitor_run = {
    "wifi": 0,
    "schedule": 0,
    "ac": 0,
    "heater": 0,
    "inside_temp": 0,
    "outside_temp": 0,
}

while True:
    now = time.time()

    # WiFi monitor every 5 seconds (can be stateless)
    if now - last_monitor_run["wifi"] >= 5:
        from scripts.monitors import WiFiMonitor
        wifi_monitor = WiFiMonitor(wifi, led, interval=5, reconnect_cooldown=60, config=config)
        try:
            wifi_monitor.run()
        except Exception as e:
            print("WiFiMonitor error:", e)
        del wifi_monitor
        gc.collect()
        last_monitor_run["wifi"] = now

    # Schedule monitor every 60 seconds (persistent)
    if now - last_monitor_run["schedule"] >= 60:
        try:
            schedule_monitor.run()
        except Exception as e:
            print("ScheduleMonitor error:", e)
        last_monitor_run["schedule"] = now

    # AC monitor every 30 seconds (persistent)
    if now - last_monitor_run["ac"] >= 30:
        try:
            ac_monitor.run()
        except Exception as e:
            print("ACMonitor error:", e)
        last_monitor_run["ac"] = now

    # Heater monitor every 30 seconds (persistent)
    if now - last_monitor_run["heater"] >= 30:
        try:
            heater_monitor.run()
        except Exception as e:
            print("HeaterMonitor error:", e)
        last_monitor_run["heater"] = now

    # Inside temperature monitor every 10 seconds (can be stateless)
    if now - last_monitor_run["inside_temp"] >= 10:
        from scripts.monitors import TemperatureMonitor
        inside_monitor = TemperatureMonitor(
            sensor=sensors['inside'],
            label=SENSOR_CONFIG['inside']['label'],
            check_interval=10,
            report_interval=30,
            alert_high=SENSOR_CONFIG['inside']['alert_high'],
            alert_low=SENSOR_CONFIG['inside']['alert_low'],
            log_file="/temp_logs.csv",
            send_alerts_to_separate_channel=True
        )
        inside_monitor.run()
        del inside_monitor
        gc.collect()
        last_monitor_run["inside_temp"] = now

    # Outside temperature monitor every 10 seconds (can be stateless)
    if now - last_monitor_run["outside_temp"] >= 10:
        from scripts.monitors import TemperatureMonitor
        outside_monitor = TemperatureMonitor(
            sensor=sensors['outside'],
            label=SENSOR_CONFIG['outside']['label'],
            check_interval=10,
            report_interval=30,
            alert_high=SENSOR_CONFIG['outside']['alert_high'],
            alert_low=SENSOR_CONFIG['outside']['alert_low'],
            log_file="/temp_logs.csv",
            send_alerts_to_separate_channel=False
        )
        outside_monitor.run()
        del outside_monitor
        gc.collect()
        last_monitor_run["outside_temp"] = now

    # Web requests (keep web server loaded if needed)
    web_server.check_requests(sensors, ac_monitor, heater_monitor, schedule_monitor, config)

    gc.collect()
    time.sleep(0.1)
# ===== END: Main Loop =====