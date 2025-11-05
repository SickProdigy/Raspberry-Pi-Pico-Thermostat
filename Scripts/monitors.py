import time
from scripts.discord_webhook import send_discord_message
from scripts.temperature_sensor import TemperatureSensor

class Monitor:
    """Base class for all monitoring tasks."""
    def __init__(self, interval=300):
        """
        interval: seconds between checks
        """
        self.interval = interval
        self.last_check_ms = 0
    
    def should_run(self):
        """Check if enough time has passed to run again."""
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_check_ms) >= (self.interval * 1000):
            self.last_check_ms = now
            return True
        return False
    
    def run(self):
        """Override this in subclasses to implement monitoring logic."""
        pass

class TemperatureMonitor(Monitor):
    """Monitor temperature sensors and report to Discord."""
    def __init__(self, sensor, label="Temp", interval=300, alert_high=None, alert_low=None, log_file=None, send_alerts_to_separate_channel=False):
        super().__init__(interval)
        self.sensor = sensor
        self.label = label  # e.g., "Inside" or "Outside"
        self.alert_high = alert_high
        self.alert_low = alert_low
        self.log_file = log_file
        self.send_alerts_to_separate_channel = send_alerts_to_separate_channel
    
    def run(self):
        """Read all sensors and report temperatures."""
        temps = self.sensor.read_all_temps(unit='F')
        if not temps:
            # print(f"No temperature readings available for {self.label}")
            return
        
        for rom, temp in temps.items():
            sensor_id = rom.hex()[:8]
            
            # Build message with alert on same line if present
            temp_msg = f"🌡️ {self.label} Temperature: {temp:.1f}°F"
            has_alert = False
            
            if self.alert_high and temp > self.alert_high:
                temp_msg += f" ⚠️ HIGH (threshold: {self.alert_high}°F)"
                has_alert = True
            elif self.alert_low and temp < self.alert_low:
                temp_msg += f" ⚠️ LOW (threshold: {self.alert_low}°F)"
                has_alert = True
            
            # Send to alert channel if out of range and configured to do so
            if has_alert and self.send_alerts_to_separate_channel:
                send_discord_message(temp_msg, is_alert=True)
            else:
                send_discord_message(temp_msg, is_alert=False)
            
            # Log to file if enabled
            if self.log_file:
                self._log_temp(sensor_id, temp)
    
    def _log_temp(self, sensor_id, temp):
        """Log temperature reading to file."""
        try:
            import time
            timestamp = time.localtime()
            log_entry = f"{timestamp[0]}-{timestamp[1]:02d}-{timestamp[2]:02d} {timestamp[3]:02d}:{timestamp[4]:02d}:{timestamp[5]:02d},{self.label},{sensor_id},{temp:.2f}\n"
            
            with open(self.log_file, 'a') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"Error logging temperature: {e}")

class WiFiMonitor(Monitor):
    """Monitor WiFi connection and handle reconnection."""
    def __init__(self, wifi, led, interval=5, reconnect_cooldown=60):
        super().__init__(interval)
        self.wifi = wifi
        self.led = led
        self.reconnect_cooldown = reconnect_cooldown
        self.last_reconnect_attempt = 0
        self.was_connected = wifi.isconnected() if wifi else False
    
    def run(self):
        """Check WiFi status, blink LED, attempt reconnect if needed."""
        import network
        from scripts.networking import connect_wifi
        
        is_connected = self.wifi.isconnected() if self.wifi else False
        
        if not is_connected:
            # Fast blink when disconnected
            self.led.on()
            time.sleep(0.2)
            self.led.off()
            
            # Try reconnect if cooldown passed
            now = time.ticks_ms()
            if time.ticks_diff(now, self.last_reconnect_attempt) >= (self.reconnect_cooldown * 1000):
                self.last_reconnect_attempt = now
                # print("Attempting WiFi reconnect...")
                self.wifi = connect_wifi(self.led)
                
                if self.wifi and self.wifi.isconnected():
                    send_discord_message("WiFi connection restored 🔄")
                    self.was_connected = True
        else:
            # Slow blink when connected
            self.led.on()
            time.sleep(1)
            self.led.off()
            
            # Notify if connection was just restored
            if not self.was_connected:
                send_discord_message("WiFi connection restored 🔄")
                self.was_connected = True

def run_monitors(monitors):
    """
    Run all monitors in the list, checking if each should run based on interval.
    Call this in your main loop.
    """
    for monitor in monitors:
        if monitor.should_run():
            try:
                monitor.run()
            except Exception as e:
                print(f"Error running monitor {monitor.__class__.__name__}: {e}")