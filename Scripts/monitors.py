import time # type: ignore
import scripts.discord_webhook as discord_webhook
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
    """Monitor for tracking temperature readings and alerts."""
    
    def __init__(self, sensor, label, check_interval=10, report_interval=60, 
                 alert_high=None, alert_low=None, log_file="/temp_logs.csv",
                 send_alerts_to_separate_channel=False):
        """
        Initialize temperature monitor.
        
        Args:
            sensor: TemperatureSensor instance
            label: Label for this sensor
            check_interval: How often to check temp (seconds)
            report_interval: How often to report/log temp (seconds)
            alert_high: High temp threshold for alerts
            alert_low: Low temp threshold for alerts
            log_file: Path to CSV log file
            send_alerts_to_separate_channel: Use separate Discord channel for alerts
        """
        self.sensor = sensor
        self.label = label
        self.check_interval = check_interval
        self.report_interval = report_interval
        self.alert_high = alert_high
        self.alert_low = alert_low
        self.log_file = log_file
        self.send_alerts_to_separate_channel = send_alerts_to_separate_channel
        
        self.last_check = 0
        self.last_report = 0
        self.alert_sent = False
        self.alert_start_time = None  # Track when alert started
        self.last_temp = None    # Cached Last temperature reading
        self.last_read_time = 0     # Timestamp of last reading
    
    def should_run(self):
        """Check if it's time to run this monitor."""
        current_time = time.time()
        if current_time - self.last_check >= self.check_interval:
            self.last_check = current_time
            return True
        return False
    
    def run(self):
        """Check temperature and handle alerts/logging."""
        current_time = time.time()
        
        # Read temperature
        temps = self.sensor.read_all_temps(unit='F')
        if not temps:
            return
        
        temp = list(temps.values())[0]  # Get first temp reading
        
        # ===== ADD THIS: Validate temperature is reasonable =====
        if temp < -50 or temp > 150:  # Sanity check (outside normal range)
            print("⚠️ Warning: {} sensor returned invalid temp: {:.1f}°F".format(self.label, temp))
            return  # Don't cache invalid reading
        # ===== END: Validation =====
        
        # Cache the reading for web server (avoid blocking reads)
        self.last_temp = temp
        self.last_read_time = current_time
        
        # Check for alerts
        alert_condition = False
        alert_message = ""
        
        if self.alert_high and temp > self.alert_high:
            alert_condition = True
            alert_message = "⚠️ {} temperature HIGH: {:.1f}°F (threshold: {:.1f}°F)".format(
                self.label, temp, self.alert_high
            )
        elif self.alert_low and temp < self.alert_low:
            alert_condition = True
            alert_message = "⚠️ {} temperature LOW: {:.1f}°F (threshold: {:.1f}°F)".format(
                self.label, temp, self.alert_low
            )
        
        # Handle alert state changes
        if alert_condition and not self.alert_sent:
            # Alert triggered
            self.alert_start_time = current_time
            print(alert_message)
            
            # send alert (use module-level discord_webhook; set_config must be called in main)
            if self.send_alerts_to_separate_channel:
                discord_webhook.send_discord_message(alert_message, is_alert=True)
            else:
                discord_webhook.send_discord_message(alert_message)
            
            self.alert_sent = True
            
        elif not alert_condition and self.alert_sent:
            # Alert resolved
            duration = current_time - self.alert_start_time if self.alert_start_time else 0
            
            # Format duration
            if duration >= 3600:
                hours = int(duration / 3600)
                minutes = int((duration % 3600) / 60)
                duration_str = "{}h {}m".format(hours, minutes)
            elif duration >= 60:
                minutes = int(duration / 60)
                seconds = int(duration % 60)
                duration_str = "{}m {}s".format(minutes, seconds)
            else:
                duration_str = "{}s".format(int(duration))
            
            recovery_message = "✅ {} temperature back to normal: {:.1f}°F (was out of range for {})".format(
                self.label, temp, duration_str
            )
            print(recovery_message)
            
            # send recovery message
            if self.send_alerts_to_separate_channel:
                discord_webhook.send_discord_message(recovery_message, is_alert=True)
            else:
                discord_webhook.send_discord_message(recovery_message)
            
            self.alert_sent = False
            self.alert_start_time = None
        
        # Log temperature at report interval
        if current_time - self.last_report >= self.report_interval:
            self.last_report = current_time
            self._log_temperature(temp)
    
    def _log_temperature(self, temp):
        """Log temperature to CSV file."""
        try:
            # Get timestamp
            t = time.localtime()
            timestamp = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                t[0], t[1], t[2], t[3], t[4], t[5]
            )
            
            # Append to log file
            with open(self.log_file, 'a') as f:
                f.write("{},{},{:.2f}\n".format(
                    timestamp, self.label, temp
                ))
        except Exception as e:
            print("Error logging temperature: {}".format(e))

class ACMonitor(Monitor):
    def __init__(self, ac_controller, temp_sensor, target_temp=75.0, temp_swing=2.0, interval=30):
        super().__init__(interval)
        self.ac = ac_controller
        self.sensor = temp_sensor  # <-- This is set from main.py
        self.target_temp = target_temp
        self.temp_swing = temp_swing
        self.last_notified_state = None
    
    def run(self):
        """Check temperature and control AC."""
        temps = self.sensor.read_all_temps(unit='F')
        if not temps:
            return
        
        # Use first sensor reading (assuming single inside sensor)
        current_temp = list(temps.values())[0]
        
        # Cooling logic with temperature swing
        # Turn ON if: temp > target + temp_swing
        # Turn OFF if: temp < target - temp_swing
        
        if current_temp > (self.target_temp + self.temp_swing):
            # Too hot, turn AC on
            if self.ac.turn_on():
                if not self.last_notified_state:
                    discord_webhook.send_discord_message(f"❄️ AC turned ON - Current: {current_temp:.1f}°F, Target: {self.target_temp:.1f}°F")
                    self.last_notified_state = True
        
        elif current_temp < (self.target_temp - self.temp_swing):
            # Cool enough, turn AC off
            if self.ac.turn_off():
                if self.last_notified_state:
                    discord_webhook.send_discord_message(f"✅ AC turned OFF - Current: {current_temp:.1f}°F, Target: {self.target_temp:.1f}°F")
                    self.last_notified_state = False
        
        # Else: within temp_swing range, maintain current state

class HeaterMonitor(Monitor):
    """Monitor temperature and control heater automatically."""
    def __init__(self, heater_controller, temp_sensor, target_temp=70.0, temp_swing=2.0, interval=30):
        """
        heater_controller: HeaterController instance
        temp_sensor: TemperatureSensor instance (inside temp)
        target_temp: Target temperature in °F
        temp_swing: Temperature swing allowed (prevents rapid cycling)
        interval: Seconds between checks
        """
        super().__init__(interval)
        self.heater = heater_controller
        self.sensor = temp_sensor
        self.target_temp = target_temp
        self.temp_swing = temp_swing
        self.last_notified_state = None
    
    def run(self):
        """Check temperature and control heater."""
        temps = self.sensor.read_all_temps(unit='F')
        if not temps:
            return
        
        # Use first sensor reading (assuming single inside sensor)
        current_temp = list(temps.values())[0]
        
        # Heating logic with temperature swing
        # Turn ON if: temp < target - temp_swing
        # Turn OFF if: temp > target + temp_swing
        
        if current_temp < (self.target_temp - self.temp_swing):
            # Too cold, turn heater on
            if self.heater.turn_on():
                if not self.last_notified_state:
                    discord_webhook.send_discord_message(f"🔥 Heater turned ON - Current: {current_temp:.1f}°F, Target: {self.target_temp:.1f}°F")
                    self.last_notified_state = True
        
        elif current_temp > (self.target_temp + self.temp_swing):
            # Warm enough, turn heater off
            if self.heater.turn_off():
                if self.last_notified_state:
                    discord_webhook.send_discord_message(f"✅ Heater turned OFF - Current: {current_temp:.1f}°F, Target: {self.target_temp:.1f}°F")
                    self.last_notified_state = False
        
        # Else: within temp_swing range, maintain current state

class WiFiMonitor(Monitor):
    """Monitor WiFi connection and handle reconnection."""
    def __init__(self, wifi, led, interval=5, reconnect_cooldown=60, config=None):
        super().__init__(interval)
        self.wifi = wifi
        self.led = led
        self.reconnect_cooldown = reconnect_cooldown
        self.last_reconnect_attempt = 0
        self.was_connected = wifi.isconnected() if wifi else False
        self.config = config
    
    def run(self):
        """Check WiFi status, blink LED, attempt reconnect if needed."""
        import network # type: ignore
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
                self.wifi = connect_wifi(self.led, config=self.config)
                
                if self.wifi and self.wifi.isconnected():
                    discord_webhook.send_discord_message("WiFi connection restored 🔄")
                    self.was_connected = True
        else:
            # Slow blink when connected
            self.led.on()
            time.sleep(1)
            self.led.off()
            
            # Notify if connection was just restored
            if not self.was_connected:
                discord_webhook.send_discord_message("WiFi connection restored 🔄")
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