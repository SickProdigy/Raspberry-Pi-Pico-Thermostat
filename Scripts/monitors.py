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
        self.last_alert_state = None  # T