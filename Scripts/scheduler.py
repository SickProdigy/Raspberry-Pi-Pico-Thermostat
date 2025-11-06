import time

class ScheduleMonitor:
    """Monitor that checks and applies temperature schedules."""
    
    def __init__(self, ac_monitor, heater_monitor, config, interval=60):
        """
        Initialize schedule monitor.
        
        Args:
            ac_monitor: ACMonitor instance
            heater_monitor: HeaterMonitor instance
            config: Configuration dict with schedules
            interval: How often to check schedule (seconds)
        """
        self.ac_monitor = ac_monitor
        self.heater_monitor = heater_monitor
        self.config = config
        self.interval = interval
        self.last_check = 0
        self.current_schedule = None
        self.last_applied_schedule = None
    
    def should_run(self):
        """Check if it's time to run this monitor."""
        current_time = time.time()
        if current_time - self.last_check >= self.interval:
            self.last_check = current_time
            return True
        return False
        
    def _parse_time(self, time_str):
        """Convert time string 'HH:MM' to minutes since midnight."""
        try:
            parts = time_str.split(':')
            hours = int(parts[0])
            minutes = int(parts[1])
            return hours * 60 + minutes
        except:
            return None
    
    def _get_current_minutes(self):
        """Get current time in minutes since midnight."""
        t = time.localtime()
        return t[3] * 60 + t[4]  # hours * 60 + minutes
    
    def _find_active_schedule(self):
        """Find which schedule should be active right now."""
        if not self.config.get('schedule_enabled', False):
            # Schedule is disabled (HOLD mode)
            return None
        
        schedules = self.config.get('schedules', [])
        if not schedules:
            return None
        
        current_minutes = self._get_current_minutes()
        
        # Sort schedules by time
        sorted_schedules = []
        for schedule in schedules:
            schedule_minutes = self._parse_time(schedule['time'])
            if schedule_minutes is not None:
                sorted_schedules.append((schedule_minutes, schedule))
        
        sorted_schedules.sort()
        
        # Find the most recent schedule that has passed
        active_schedule = None
        for schedule_minutes, schedule in sorted_schedules:
            if current_minutes >= schedule_minutes:
                active_schedule = schedule
            else:
                break
        
        # If no schedule found (before first schedule), use last schedule from yesterday
        if active_schedule is None and sorted_schedules:
            active_schedule = sorted_schedules[-1][1]
        
        return active_schedule
    
    def _apply_schedule(self, schedule):
        """Apply a schedule's settings to the monitors."""
        if not schedule:
            return
        
        # Check if this is a different schedule than last applied
        schedule_id = schedule.get('time', '') + schedule.get('name', '')
        if schedule_id == self.last_applied_schedule:
            return  # Already applied
        
        try:
            # Update AC settings if provided
            if 'ac_target' in schedule:
                self.ac_monitor.target_temp = float(schedule['ac_target'])
            
            if 'ac_swing' in schedule:
                self.ac_monitor.temp_swing = float(schedule['ac_swing'])
            
            # Update heater settings if provided
            if 'heater_target' in schedule:
                self.heater_monitor.target_temp = float(schedule['heater_target'])
            
            if 'heater_swing' in schedule:
                self.heater_monitor.temp_swing = float(schedule['heater_swing'])
            
            # Log the change
            schedule_name = schedule.get('name', 'Unnamed')
            print("\n" + "="*50)
            print("Schedule Applied: {}".format(schedule_name))
            print("="*50)
            print("AC Target:      {}°F".format(self.ac_monitor.target_temp))
            print("Heater Target:  {}°F".format(self.heater_monitor.target_temp))
            print("="*50 + "\n")
            
            # Send Discord notification
            try:
                from scripts.discord_webhook import send_discord_message
                message = "🕐 Schedule '{}' applied - AC: {}°F | Heater: {}°F".format(
                    schedule_name,
                    self.ac_monitor.target_temp,
                    self.heater_monitor.target_temp
                )
                send_discord_message(message)
            except:
                pass
            
            self.last_applied_schedule = schedule_id
            
        except Exception as e:
            print("Error applying schedule: {}".format(e))
    
    def run(self):
        """Check if schedule needs to be updated."""
        # Find and apply active schedule
        active_schedule = self._find_active_schedule()
        if active_schedule:
            self._apply_schedule(active_schedule)
    
    def reload_config(self, new_config):
        """Reload configuration (called when settings are updated via web)."""
        self.config = new_config
        self.last_applied_schedule = None  # Force re-application
        print("Schedule configuration reloaded")