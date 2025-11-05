# 🌱 Auto Garden

> Automated garden monitoring and control system using Raspberry Pi Pico W

## Overview

This project automates garden monitoring using a Raspberry Pi Pico W with temperature sensors, Discord notifications, and AC control for climate management.

## Features

- ✅ WiFi connectivity with auto-reconnect
- ✅ Inside/Outside temperature monitoring (DS18B20 sensors)
- ✅ Discord notifications for temperature readings
- ✅ Separate alert channel for critical temperatures
- ✅ Temperature logging to CSV file
- ✅ Configurable alert thresholds
- ✅ Automated AC control with temperature swing logic
- ✅ Relay control via opto-coupler for 110V AC
- 🚧 Humidity monitoring (planned)
- 🚧 Soil moisture monitoring (planned)
- 🚧 Additional relay control for fans, heaters (planned)

## Quick Start

### 1. Hardware Setup

**Required Components:**

- Raspberry Pi Pico W
- DS18B20 temperature sensors (waterproof recommended)
- 4.7kΩ resistor (pull-up for 1-Wire bus)
- Opto-coupler relay module (3.3V logic, 110V AC rated)
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

**⚠️ Important:** The 4.7kΩ pull-up resistor is **required** for reliable 1-Wire communication. While it may work without it occasionally, you'll experience intermittent failures, communication errors, and unreliable readings.

**Opto-Coupler Relay Module:**

```text
Low Voltage Side (Pico):
GP15 (Pin 20)  →  IN (Signal)
3.3V (Pin 36)  →  VCC
GND            →  GND

High Voltage Side (AC Unit):
NO (Normally Open)  →  AC Control Wire 1
COM (Common)        →  AC Control Wire 2
```

**Note:** Most opto-coupler modules work with standard logic:

- `relay.on()` = relay energized (NO closes) = AC ON
- `relay.off()` = relay de-energized (NC closes) = AC OFF

If your AC behavior is inverted (turns on when it should be off), your module may be active LOW—see troubleshooting section.

**Optional Reset Button:**

```text
RUN pin  →  Button  →  GND
```

Pressing button grounds RUN and resets the Pico.

### 3. Software Setup

**Install MicroPython:**

1. Download [MicroPython firmware](https://micropython.org/download/rp2-pico-w/)
2. Hold BOOTSEL button while plugging in Pico
3. Copy `.uf2` file to the Pico drive

**IDE Setup:**

- Recommended: VS Code with [MicroPico extension](https://marketplace.visualstudio.com/items?itemName=paulober.pico-w-go) by paulober
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

**Configure sensors and AC in `main.py`:**

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

# AC Controller options
relay_pin = 15
min_run_time = 300      # Minimum 5 minutes run time
min_off_time = 180      # Minimum 3 minutes off time

# AC Monitor options
target_temp = 75.0      # Target temperature in °F
temp_swing = 2.0        # ±2°F swing (AC on at 77°F, off at 73°F)
```

### 5. Upload & Run

Upload all files to your Pico:

```text
/
├── main.py
├── secrets.py
└── scripts/
    ├── air_conditioning.py
    ├── discord_webhook.py
    ├── monitors.py
    ├── networking.py
    └── temperature_sensor.py
```

The Pico will auto-start `main.py` on boot.

## Project Structure

```text
Auto-Garden/
├── main.py                      # Entry point, configuration, monitor setup
├── secrets.py                   # WiFi & Discord credentials (gitignored)
├── secrets.example.py           # Template for secrets.py
└── scripts/
    ├── air_conditioning.py      # AC controller with short-cycle protection
    ├── discord_webhook.py       # Discord notification handling
    ├── monitors.py              # Monitor base class & implementations
    ├── networking.py            # WiFi connection management
    └── temperature_sensor.py    # DS18B20 sensor interface
```

## How It Works

### Temperature Monitoring

- **Every 10 seconds:** Check temperatures, send alerts if out of range
- **Every 30 seconds:** Regular temperature reports to Discord + log to file

**Discord Channels:**

- `discord_webhook_url`: Regular temperature updates, connection status
- `discord_alert_webhook_url`: Critical temperature alerts (Inside sensor only)

### AC Control Logic

- **Every 30 seconds:** Check inside temperature and decide AC state
- **Temperature swing:** Creates a "dead band" to prevent rapid cycling
  - Example: Target 75°F with 2°F swing
  - AC turns **ON** when temp > 77°F
  - AC turns **OFF** when temp < 73°F
  - Between 73-77°F: maintains current state

**Short-Cycle Protection:**

- Minimum run time (default 5 min) prevents AC from turning off too quickly
- Minimum off time (default 3 min) protects compressor from rapid restarts

### WiFi Monitoring

- **Every 5 seconds:** Check WiFi connection status
- **LED Indicator:**
  - Slow blink (1 sec on/off): Connected
  - Fast blink (0.2 sec): Disconnected
- **Auto-reconnect:** Attempts reconnection every 60 seconds if disconnected

## Temperature Logs

Logs are saved to `/temp_logs.csv` on the Pico:

```csv
2025-11-05 14:30:00,Inside,28000012,72.50
2025-11-05 14:30:00,Outside,28000034,45.30
```

Format: `timestamp,location,sensor_id,temperature_f`

## Customization

All configuration is centralized in `main.py`:

**Sensor Settings:**

- Pin assignments
- Alert thresholds (high/low)
- Labels

**AC Settings:**

- Relay pin
- Target temperature
- Temperature swing (dead band)
- Minimum run/off times

**Monitor Intervals:**

- Temperature check/report intervals
- WiFi check interval
- AC control interval

## Safety Notes

⚠️ **High Voltage Warning:**

- Opto-couplers isolate the Pico from AC voltage
- Never connect GPIO pins directly to 110V AC
- Ensure your opto-coupler module is rated for your voltage
- Test relay switching with a multimeter before connecting AC
- Consider hiring a licensed electrician if uncomfortable with AC wiring

**Compressor Protection:**

- Always use minimum run/off times (defaults are safe)
- Minimum 3 minutes off time protects compressor bearings
- Minimum 5 minutes run time prevents short cycling

## Future Expansion

### Planned Features

- **Humidity Sensors:** DHT22 or SHT31 for air humidity monitoring
- **Soil Moisture:** Capacitive sensors for plant watering automation
- **Additional Relays:** Control for fans, heaters, grow lights
- **Smart Ventilation:** Auto-open windows when outside air is optimal
- **Light Monitoring:** LDR or BH1750 for day/night cycles

### Adding More Sensors

To add a new temperature sensor:

First Add to `SENSOR_CONFIG` in `main.py`:

```python
'greenhouse': {
    'pin': 12,
    'label': 'Greenhouse',
    'alert_high': 90.0,
    'alert_low': 50.0
}
```

Second Add a `TemperatureMonitor` to the monitors list:

```python
TemperatureMonitor(
    sensor=sensors['greenhouse'],
    label=SENSOR_CONFIG['greenhouse']['label'],
    check_interval=10,
    report_interval=30,
    alert_high=SENSOR_CONFIG['greenhouse']['alert_high'],
    alert_low=SENSOR_CONFIG['greenhouse']['alert_low'],
    log_file="/temp_logs.csv",
    send_alerts_to_separate_channel=False
)
```

## Troubleshooting

**No temperature readings:**

- Check 4.7kΩ pull-up resistor is connected between data line and 3.3V
- Verify sensor wiring (VDD to 3.3V, not 5V)
- Check GPIO pin numbers in `SENSOR_CONFIG`
- Run `sensor.scan_sensors()` to detect connected sensors

**WiFi not connecting:**

- Verify SSID/password in `secrets.py`
- Check 2.4GHz WiFi (Pico W doesn't support 5GHz)
- Look for connection messages in serial console
- LED should blink slowly when connected

**Discord messages not sending:**

- Verify webhook URLs are correct
- Test webhooks with curl/Postman first
- Check Pico has internet access

**AC not switching:**

- Verify relay pin number (default GP15)
- Test relay manually: `Pin(15, Pin.OUT).off()` should activate it
- Check if module is active LOW or active HIGH
- Ensure opto-coupler has 3.3V power
- Look for LED on relay module (should light when active)
- Verify minimum run/off times haven't locked out switching

**AC behavior inverted:**

- Your opto-coupler is likely active LOW
- In `air_conditioning.py`, swap `relay.on()` and `relay.off()` calls

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
