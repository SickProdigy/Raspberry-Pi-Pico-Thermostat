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
    def __init__(self, sensor, label="Temp", check_interval=10, report_interval=30, alert_high=None, alert_low=None, log_file=None, send_alerts_to_separate_channel=False):
        super().__init__(check_interval)  # Check interval for temp reading
        self.sensor = sensor
        self.label = label
        self.check_interval = check_interval
        self.report_interval = report_interval
        self.alert_high = alert_high
        self.alert_low = alert_low
        self.log_file = log_file
        self.send_alerts_to_separate_channel = send_alerts_to_separate_channel
        self.last_report_ms = 0
        self.last_alert_state = None  # Track if we were in alert state
    
    def run(self):
        """Read sensors every check_interval, report/log every report_interval."""
        temps = self.sensor.read_all_temps(unit='F')
        if not temps:
            # print(f"No temperature readings available for {self.label}")
            return
        
        now = time.ticks_ms()
        should_report = time.ticks_diff(now, self.last_report_ms) >= (self.report_interval * 1000)
        
        for rom, temp in temps.items():
            sensor_id = rom.hex()[:8]
            
            # Check if in alert state
            has_alert = False
            alert_type = None
            
            if self.alert_high and temp > self.alert_high:
                has_alert = True
                alert_type = "HIGH"
            elif self.alert_low and temp < self.alert_low:
                has_alert = True
                alert_type = "LOW"
            
            # Send alert immediately to alert channel (every check_interval, only if configured)
            if has_alert and self.send_alerts_to_separate_channel:
                alert_msg = f"🚨 {self.label} Temperature: {temp:.1f}°F ⚠️ {alert_type} (threshold: {self.alert_high if alert_type == 'HIGH' else self.alert_low}°F)"
                send_discord_message(alert_msg, is_alert=True)
                self.last_alert_state = True
            
            # Send normal report at report_interval to regular channel (regardless of alert state)
            if should_report:
                temp_msg = f"🌡️ {self.label} Temperature: {temp:.1f}°F"
                
                # Add alert indicator to regular report if in alert
                if has_alert:
                    temp_msg += f" ⚠️ {alert_type}"
                
                send_discord_message(temp_msg, is_alert=False)
                
                # Send recovery message if we were in alert and now normal
                if not has_alert and self.last_alert_state:
                    recovery_msg = f"✅ {self.label} Temperature back to normal: {temp:.1f}°F"
                    send_discord_message(recovery_msg, is_alert=False)
                    self.last_alert_state = False
            
            # Log to file at report_interval
            if should_report and self.log_file:
                self._log_temp(sensor_id, temp)
        
        # Update last report time
        if should_report:
            self.last_report_ms = now
    
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
        