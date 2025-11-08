# 🌱 Auto Garden

> Automated climate control system using Raspberry Pi Pico W with web interface and scheduling

## Overview

This project provides automated climate monitoring and control using a Raspberry Pi Pico W. Features dual-zone temperature monitoring, AC/heater control, time-based scheduling, and a web interface for easy management.

## Features

- **Core Features**
  - ✅ WiFi connectivity with auto-reconnect and static IP
  - ✅ Inside/Outside temperature monitoring (DS18B20 sensors)
  - ✅ Web interface for monitoring and configuration <http://192.168.x.x>
  - ✅ Discord notifications for all system events
  - ✅ Temperature logging to CSV file
  - ✅ Configurable alert thresholds
  - ✅ Exception recovery (system won't crash permanently)
  - ✅ Graceful shutdown with Ctrl+C

- **Climate Control**
  - ✅ Automated AC control with temperature swing logic
  - ✅ Automated heater control with separate swing settings
  - ✅ Short-cycle protection for both AC and heater
  - ✅ Dual relay control via opto-coupler for 110V AC
  - ✅ Mutual exclusion (AC and heater never run simultaneously)

- **Scheduling System**
  - ✅ 4 configurable time-based schedules per day
  - ✅ Each schedule sets different AC/heater targets
  - ✅ Automatic mode with schedule following
  - ✅ Temporary hold mode (auto-resumes after configurable time)
  - ✅ Permanent hold mode (manual control until restart)
  - ✅ Schedule configuration persists through reboots
  - ✅ Hold modes reset to Automatic on restart (safety feature)

- **Web Interface**
  - ✅ Real-time temperature display
  - ✅ AC/Heater status indicators
  - ✅ Manual temperature override
  - ✅ Schedule editor (4 time slots)
  - ✅ Mode control buttons (Automatic/Temp Hold/Perm Hold)
  - ✅ Countdown timer for temporary holds
  - ✅ Mobile-responsive design
  - ✅ Auto-refresh dashboard (30 seconds)

- **Planned Features**
  - 🚧 Humidity monitoring (DHT22/SHT31)
  - 🚧 Soil moisture monitoring
  - 🚧 Additional relay control for fans, grow lights

## Quick Start

### 1. Hardware Setup

**Required Components:**

- Raspberry Pi Pico W
- 2x DS18B20 temperature sensors (waterproof recommended)
- 4.7kΩ resistor (pull-up for 1-Wire bus)
- 2-channel opto-coupler relay module (3.3V logic, 110V AC rated)
- Momentary button (optional, for easy reset)

See the [Items Needed Wiki](https://gitea.rcs1.top/sickprodigy/Auto-Garden/wiki/Items-Needed-for-the-Project) for full parts list.

### 2. Wiring

**DS18B20 Temperature Sensors:**

```text
Sensor Wire    →  Pico Pin
─────────────────────────────
Red (VDD)      →  3V3 (OUT) - Pin 36
Black (GND)    →  GND - Any ground pin
Yellow (Data)  →  GP10 (Inside) - Pin 14
               →  GP11 (Outside) - Pin 15

Add 4.7kΩ resistor between Data line and 3.3V
```

**⚠️ Important:** The 4.7kΩ pull-up resistor is **required** for reliable 1-Wire communication.

**2-Channel Opto-Coupler Relay Module:**

```text
Low Voltage Side (Pico):
GP15 (Pin 20)  →  IN1 (AC Control Signal)
GP14 (Pin 19)  →  IN2 (Heater Control Signal)
3.3V (Pin 36)  →  VCC
GND            →  GND

High Voltage Side - Relay 1 (AC Unit):
NO (Normally Open)  →  AC Control Wire 1
COM (Common)        →  AC Control Wire 2

High Voltage Side - Relay 2 (Heater):
NO (Normally Open)  →  Heater Control Wire 1
COM (Common)        →  Heater Control Wire 2
```

**Note:** Most opto-coupler modules work with standard logic:

- `relay.on()` = relay energized (NO closes) = Device ON
- `relay.off()` = relay de-energized (NC closes) = Device OFF

If behavior is inverted, your module may be active LOW—see troubleshooting.

**Optional Reset Button:**

```text
RUN pin  →  Button  →  GND
```

### 3. Software Setup

**Install MicroPython:**

1. Download [MicroPython firmware](https://micropython.org/download/rp2-pico-w/)
2. Hold BOOTSEL button while plugging in Pico
3. Copy `.uf2` file to the Pico drive

**IDE Setup:**

- Recommended: VS Code with [MicroPico extension](https://marketplace.visualstudio.com/items?itemName=paulober.pico-w-go)
- Alternative: Thonny IDE

### 4. Configuration

**Create `secrets.py`** (copy from `secrets.example.py`):

```python
secrets = {
    'ssid': 'YOUR_WIFI_NAME',
    'password': 'YOUR_WIFI_PASSWORD',
    'discord_webhook_url': 'https://discord.com/api/webhooks/...',
    'discord_alert_webhook_url': 'https://discord.com/api/webhooks/...',
}
```

**Sensor Configuration in `main.py`:**

```python
# Sensor configuration
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
```

**Default Climate Settings (auto-saved to config.json):**

```python
# Default config (created on first boot)
{
    "ac_target": 77.0,           # AC target temperature (°F)
    "ac_swing": 1.0,             # AC turns on at 78°F, off at 76°F
    "heater_target": 72.0,       # Heater target temperature (°F)
    "heater_swing": 2.0,         # Heater turns on at 70°F, off at 74°F
    "temp_hold_duration": 3600,  # Temporary hold lasts 1 hour (3600 seconds)
    "schedule_enabled": true,    # Schedules active by default
    "schedules": [               # 4 time-based schedules
        {
            "time": "06:00",
            "name": "Morning",
            "ac_target": 75.0,
            "heater_target": 72.0
        },
        # ... 3 more schedules
    ]
}
```

All settings can be changed via the web interface and persist through reboots.

### 5. Upload & Run

Upload all files to your Pico:

```text
/
├── main.py
├── secrets.py
├── config.json              # Auto-generated on first boot
└── scripts/
    ├── air_conditioning.py   # AC/Heater controller classes
    ├── discord_webhook.py
    ├── monitors.py
    ├── networking.py
    ├── scheduler.py          # Schedule system with hold timer
    ├── temperature_sensor.py
    └── web_server.py         # Web interface
```

The Pico will auto-start `main.py` on boot and be accessible at **<http://192.168.x.x>**

## Project Structure

```text
Auto-Garden/
├── main.py                      # Entry point, configuration, system initialization
├── secrets.py                   # WiFi & Discord credentials (gitignored)
├── secrets.example.py           # Template for secrets.py
├── config.json                  # Persistent configuration (auto-generated)
└── scripts/
    ├── air_conditioning.py      # AC & Heater controllers with short-cycle protection
    ├── discord_webhook.py       # Discord notification handling
    ├── monitors.py              # Monitor base class & implementations
    ├── networking.py            # WiFi connection management
    ├── scheduler.py             # Schedule system with temporary/permanent hold modes
    ├── temperature_sensor.py    # DS18B20 sensor interface
    └── web_server.py            # Web interface for monitoring and control
```

## How It Works

### Temperature Monitoring

- **Every 10 seconds:** Check temperatures
- **Every 30 seconds:** Send temperature reports to Discord + log to CSV
- **Instant alerts:** High/low temperature warnings to separate Discord channel

**Discord Notifications:**

- `discord_webhook_url`: Regular updates, status changes, system events
- `discord_alert_webhook_url`: Critical temperature alerts (Inside sensor only)

**Example Discord Messages:**

```text
📊 Inside: 75.2°F | AC: OFF | Heater: OFF
📊 Outside: 68.5°F | AC: OFF | Heater: OFF
🔥 Inside temp HIGH: 81.0°F
Schedule 'Morning' applied - AC: 75°F, Heater: 72°F
⏸️ HOLD Mode - Manual override: AC: 77F +/- 1F | Heater: 72F +/- 2F
⏰ Temporary hold expired - Automatic mode resumed
```

### Climate Control Logic

**AC Control:**

- Target: 77°F with 1°F swing
- AC turns **ON** when temp > 78°F (77 + 1)
- AC turns **OFF** when temp < 76°F (77 - 1)
- Between 76-78°F: maintains current state (dead band prevents cycling)

**Heater Control:**

- Target: 72°F with 2°F swing
- Heater turns **ON** when temp < 70°F (72 - 2)
- Heater turns **OFF** when temp > 74°F (72 + 2)
- Between 70-74°F: maintains current state

**Short-Cycle Protection:**

- Minimum run time: 30 seconds (prevents rapid off)
- Minimum off time: 5 seconds (protects compressor/heater elements)
- AC and heater never run simultaneously (mutual exclusion)

### Scheduling System

**Automatic Mode (Default):**

- Schedules apply at configured times (e.g., 06:00, 12:00, 18:00, 22:00)
- AC and heater targets update automatically
- System follows the most recent schedule until next one applies

**Temporary Hold Mode:**

- Activated by manual temperature changes or "⏸️ Temp Hold" button
- Pauses schedules for configurable duration (default: 1 hour)
- Web UI shows countdown timer: "45 min remaining"
- Auto-resumes to Automatic mode when timer expires
- Can be manually resumed with "▶️ Resume" button

**Permanent Hold Mode:**

- Activated by "🛑 Perm Hold" button
- Completely disables schedules (manual control only)
- Stays disabled until "▶️ Enable Schedules" clicked or Pico reboots
- No countdown timer

**Hold Reset on Boot:**

- All hold modes reset to Automatic on Pico restart/power cycle
- Safety feature ensures schedules always resume after power loss
- Temperature targets, swing values, and schedules persist

### Web Interface

Access at **<http://192.168.x.x>**

**Dashboard (auto-refreshes every 30s):**

- Current inside/outside temperatures
- AC/Heater status indicators
- Next scheduled temperature change
- Current mode banner with countdown (if in Temporary Hold)
- Manual temperature override form
- Mode control buttons

**Schedule Editor:**

- Configure 4 time-based schedules
- Set time (HH:MM format), name, AC target, heater target for each
- Form validation (prevents heater > AC, invalid times)
- No auto-refresh (prevents losing edits)

**Mode Control:**

- **✅ Automatic Mode:** Schedules active, temps adjust based on time
  - Buttons: [⏸️ Temp Hold] [🛑 Perm Hold]
- **⏸️ Temporary Hold:** Manual override with countdown timer
  - Buttons: [▶️ Resume] [🛑 Perm Hold]
- **🛑 Permanent Hold:** Manual control only, schedules disabled
  - Button: [▶️ Enable Schedules]

### WiFi Monitoring

- **Every 5 seconds:** Check WiFi connection
- **LED Indicator:**
  - Solid ON: Connected
  - Blinking: Reconnecting
- **Auto-reconnect:** Attempts every 60 seconds if disconnected
- **Static IP:** Always accessible at <http://192.168.x.x>

## Temperature Logs

Logs are saved to `/temp_logs.csv` on the Pico:

```csv
2025-11-08 14:30:00,Inside,28000012,72.50
2025-11-08 14:30:00,Outside,28000034,45.30
```

Format: `timestamp,location,sensor_id,temperature_f`

## Customization

### Via Web Interface (Recommended)

- Navigate to <http://192.168.x.x>
- Adjust AC/Heater targets and swing values
- Edit schedules (times, names, targets)
- Settings persist through reboots

### Via config.json

```json
{
    "ac_target": 77.0,
    "ac_swing": 1.5,              // Change swing range
    "heater_target": 72.0,
    "heater_swing": 2.5,
    "temp_hold_duration": 7200,   // 2 hours (in seconds)
    "schedules": [ /* ... */ ]
}
```

### Via main.py (Advanced)

```python
# Relay pins
ac_relay_pin = 15
heater_relay_pin = 14

# Sensor pins
SENSOR_CONFIG = {
    'inside': {'pin': 10, ...},
    'outside': {'pin': 11, ...}
}

# Monitor intervals
check_interval=10      # Temperature check frequency
report_interval=30     # Discord report frequency
```

## Safety Notes

⚠️ **High Voltage Warning:**

- Opto-couplers isolate Pico from AC voltage
- Never connect GPIO directly to 110V AC
- Ensure relay module is rated for your voltage
- Test with multimeter before connecting AC loads
- Consider hiring licensed electrician if uncomfortable

**Compressor/Heater Protection:**

- Always use minimum run/off times
- Minimum 5s off time protects compressor bearings
- Minimum 30s run time prevents short cycling
- AC and heater mutual exclusion prevents simultaneous operation

**System Reliability:**

- Exception recovery prevents permanent crashes
- Graceful shutdown (Ctrl+C) safely turns off AC/heater
- Hold modes reset on reboot (schedules always resume)
- Static IP ensures web interface always accessible

## Troubleshooting

**Web interface not loading:**

- Verify Pico is connected to WiFi (LED should be solid)
- Check static IP is <http://192.168.x.x>
- Look for "Web Interface: <http://192.168.x.x>" in serial console
- Try accessing from same WiFi network

**No temperature readings:**

- Check 4.7kΩ pull-up resistor between data line and 3.3V
- Verify sensor wiring (VDD to 3.3V, not 5V)
- Check GPIO pin numbers in `SENSOR_CONFIG`
- Run `sensor.scan_sensors()` in REPL to detect sensors

**WiFi not connecting:**

- Verify SSID/password in `secrets.py`
- Check 2.4GHz WiFi (Pico W doesn't support 5GHz)
- LED should be solid when connected
- Check serial console for connection status

**Discord messages not sending:**

- Verify webhook URLs in `secrets.py`
- Test webhooks with curl/Postman first
- Check Pico has internet access (ping test)
- Look for error messages in serial console

**AC/Heater not switching:**

- Verify relay pin numbers (default GP15/GP14)
- Test relay manually in REPL: `Pin(15, Pin.OUT).on()`
- Check if module is active LOW or active HIGH
- Ensure opto-coupler has 3.3V power
- Look for LED on relay module (should light when active)
- Check minimum run/off times haven't locked out switching

**AC/Heater behavior inverted:**

- Your opto-coupler is active LOW
- In `air_conditioning.py`, swap `relay.on()` and `relay.off()` calls in both ACController and HeaterController classes

**Schedules not applying:**

- Check NTP time sync: "Time synced with NTP server" in serial
- Verify schedule times in HH:MM format (24-hour)
- Ensure "✅ Automatic Mode" is active (not in hold)
- Check serial console for "Schedule Applied: [name]" messages

**Temporary hold not auto-resuming:**

- Check `temp_hold_duration` in config.json (in seconds)
- Look for "⏰ Temporary hold expired" in serial console
- ScheduleMonitor runs every 60 seconds, may take up to 1 min extra
- Verify timer countdown appears in web UI banner

**System keeps crashing:**

- Check for recent code changes
- Look for exception messages in serial console
- System should auto-recover from most errors (5s pause, then retry)
- If persistent, check memory usage with `gc.mem_free()`

**Config changes not saving:**

- Verify web form submissions redirect to dashboard/schedule page
- Check for "Settings persisted to disk" in serial console
- Ensure config.json has write permissions
- Try manual edit of config.json and reboot

## Contributing

Feel free to open issues or submit pull requests for improvements!

## License

MIT License - See LICENSE file for details

## Resources

- [Raspberry Pi Pico W Documentation](https://www.raspberrypi.com/documentation/microcontrollers/raspberry-pi-pico.html)
- [MicroPython Documentation](https://docs.micropython.org/)
- [DS18B20 Datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/DS18B20.pdf)
- [Discord Webhooks Guide](https://discord.com/developers/docs/resources/webhook)
- [1-Wire Protocol Guide](https://www.analog.com/en/technical-articles/guide-to-1wire-communication.html)

---

**Note:** Always ensure proper electrical safety when working with high-voltage relays and AC power. Test thoroughly before leaving unattended.
