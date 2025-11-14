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
import scripts.discord_webhook as discord_webhook
from scripts.monitors import TemperatureMonitor, WiFiMonitor, ACMonitor, HeaterMonitor, run_monitors
from scripts.temperature_sensor import TemperatureSensor
from scripts.air_conditioning import ACController
from scripts.heating import HeaterController
from scripts.web_server import TempWebServer
from scripts.scheduler import ScheduleMonitor  # NEW: Import scheduler for time-based temp changes
from scripts.memory_check import check_memory_once  # Just the function

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

# Load configuration from file
config = load_config()
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
# Connect to WiFi using credentials from secrets.py
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
    
    # Send startup notification to Discord (with timeout, non-blocking)
    try:
        success = discord_webhook.send_discord_message(f"Pico W online at http://{ifconfig[0]} ✅")
        if success:
            print("Discord startup notification sent")
        else:
            print("Discord startup notification failed (continuing anyway)")
    except Exception as e:
        print("Discord notification error: {}".format(e))
    
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

# ===== START: Monitor Setup =====
# Set up all monitoring systems (run in order during main loop)
monitors = [
    # WiFi monitor: Checks connection, reconnects if needed, blinks LED
    WiFiMonitor(wifi, led, interval=5, reconnect_cooldown=60, config=config),
    
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

# Add NTP retry flags (before main loop)
retry_ntp_attempts = 0
max_ntp_attempts = 5  # Try up to 5 times after initial failure
last_ntp_sync = time.time()  # Track when we last synced

# ===== START: Main Loop =====
# Main monitoring loop (runs forever until Ctrl+C)
while True:
    try:
        # Run all monitors (each checks if it's time to run via should_run())
        run_monitors(monitors)

        # Web requests
        web_server.check_requests(sensors, ac_monitor, heater_monitor, schedule_monitor, config)

        # ===== PERIODIC RE-SYNC (every 24 hours) =====
        if ntp_synced and (time.time() - last_ntp_sync) > 86400:
            print("24-hour re-sync due...")
            if sync_ntp_time(TIMEZONE_OFFSET):
                last_ntp_sync = time.time()
                print("Daily NTP re-sync successful")
            else:
                print("Daily NTP re-sync failed (will retry tomorrow)")
        # ===== END: PERIODIC RE-SYNC =====
        
        # ===== ADD THIS: AGGRESSIVE GARBAGE COLLECTION =====
        current_time = time.time()
        if int(current_time) % 5 == 0:  # Every 5 seconds
            gc.collect()
            # Optional: Print memory stats occasionally
            if int(current_time) % 60 == 0:  # Every minute
                print("💾 Memory free: {} KB".format(gc.mem_free() // 1024))
        # ===== END: AGGRESSIVE GC =====
        time.sleep(0.1)
        
    except KeyboardInterrupt:
        # Graceful shutdown on Ctrl+C
        print("\n\n" + "="*50)
        print("Shutting down gracefully...")
        print("="*50)
        print("Turning off AC...")
        ac_controller.turn_off()
        print("Turning off heater...")
        heater_controller.turn_off()
        print("Turning off LED...")
        led.low()
        print("Shutdown complete!")
        print("="*50 + "\n")
        break
        
    except Exception as e:
        # If loop crashes, print error and keep running
        print("❌ Main loop error: {}".format(e))
        import sys
        sys.print_exception(e)
        time.sleep(5)  # Brief pause before retrying
# ===== END: Main Loop =====