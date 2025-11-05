# 🌱 Auto Garden

> Automated garden monitoring and control system using Raspberry Pi Pico W

## Overview

This project automates garden monitoring using a Raspberry Pi Pico W with temperature sensors, Discord notifications, and planned expansion for humidity, soil moisture, and environmental controls.

## Features

- ✅ WiFi connectivity with auto-reconnect
- ✅ Inside/Outside temperature monitoring (DS18B20 sensors)
- ✅ Discord notifications for temperature readings
- ✅ Separate alert channel for critical temperatures
- ✅ Temperature logging to CSV file
- ✅ Configurable alert thresholds
- 🚧 Humidity monitoring (planned)
- 🚧 Soil moisture monitoring (planned)
- 🚧 Relay control for fans, AC, heaters (planned)

## Quick Start

### 1. Hardware Setup

**Required Components:**

- Raspberry Pi Pico W
- DS18B20 temperature sensors (waterproof recommended)
- 4.7kΩ resistor (pull-up for 1-Wire bus)
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

**Configure sensors in `scripts/temperature_sensor.py`:**

```python
SENSOR_CONFIG = {
    'inside': {
        'pin': 10,
        'label': 'Inside',
        'alert_high': 85.0,
        'alert_low': 32.0
    },
    'outside': {
        'pin': 11,
        'label': 'Outside',
        'alert_high': 100.0,
        'alert_low': 20.0
    }
}
```

### 5. Upload & Run

Upload all files to your Pico:

```text
/
├── main.py
├── secrets.py
└── scripts/
    ├── discord_webhook.py
    ├── monitors.py
    ├── networking.py
    └── temperature_sensor.py
```

The Pico will auto-start `main.py` on boot.

## Project Structure

```text
Auto-Garden/
├── main.py                      # Entry point, sets up monitors
├── secrets.py                   # WiFi & Discord credentials (gitignored)
├── secrets.example.py           # Template for secrets.py
└── scripts/
    ├── discord_webhook.py       # Discord notification handling
    ├── monitors.py              # Monitor base class & implementations
    ├── networking.py            # WiFi connection management
    └── temperature_sensor.py    # DS18B20 sensor interface & config
```

## Monitoring Behavior

- **Every 10 seconds:** Check temperatures, send alerts if out of range
- **Every 30 seconds:** Regular temperature reports to Discord + log to file
- **Every 5 seconds:** WiFi connection check with auto-reconnect

**Discord Channels:**

- `discord_webhook_url`: Regular temperature updates, connection status
- `discord_alert_webhook_url`: Critical temperature alerts (Inside sensor only)

## Temperature Logs

Logs are saved to `/temp_logs.csv` on the Pico:

```csv
2025-11-05 14:30:00,Inside,28000012,72.50
2025-11-05 14:30:00,Outside,28000034,45.30
```

Format: `timestamp,location,sensor_id,temperature_f`

## Future Expansion

### Planned Features

- **Humidity Sensors:** DHT22 or SHT31 for air humidity monitoring
- **Soil Moisture:** Capacitive sensors for plant watering automation
- **Relay Control:** 3V-32VDC SSR relays for switching AC, fans, heaters
- **Smart Ventilation:** Auto-open windows when outside air is optimal
- **Light Monitoring:** LDR or BH1750 for grow light automation

### Relay Wiring (Future)

```text
Pico 3.3V output → SSR relay input → High voltage device (120V/240V)
```

Use solid-state relays (SSR) rated for your voltage/current needs.

## Troubleshooting

**No temperature readings:**

- Check 4.7kΩ pull-up resistor is connected
- Verify sensor wiring (VDD to 3.3V, not 5V)
- Check GPIO pin numbers in `SENSOR_CONFIG`

**WiFi not connecting:**

- Verify SSID/password in `secrets.py`
- Check 2.4GHz WiFi (Pico W doesn't support 5GHz)
- Look for connection messages in serial console

**Discord messages not sending:**

- Verify webhook URLs are correct
- Test webhooks with curl/Postman first
- Check Pico has internet access (ping test)

## Contributing

Feel free to open issues or submit pull requests for improvements!

## License

MIT License - See LICENSE file for details

## Resources

- [Raspberry Pi Pico W Documentation](https://www.raspberrypi.com/documentation/microcontrollers/raspberry-pi-pico.html)
- [MicroPython Documentation](https://docs.micropython.org/)
- [DS18B20 Datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/DS18B20.pdf)
- [Discord Webhooks Guide](https://discord.com/developers/docs/resources/webhook)

---

**Note:** Always ensure proper electrical safety when working with high-voltage relays and AC power. Consult a licensed electrician if unsure.