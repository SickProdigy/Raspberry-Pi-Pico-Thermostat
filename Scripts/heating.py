from machine import Pin # type: ignore
import time # type: ignore

class HeaterController:
    """Control heater via opto-coupler relay."""
    def __init__(self, relay_pin=16, min_run_time=300, min_off_time=180):
        """
        relay_pin: GPIO pin connected to opto-coupler input
        min_run_time: Minimum seconds heater must run before turning off (prevent short cycling)
        min_off_time: Minimum seconds heater must be off before turning on (element protection)
        """
        self.relay = Pin(relay_pin, Pin.OUT)
        self.relay.off()  # Start with heater off (relay normally open)
        
        self.min_run_time = min_run_time
        self.min_off_time = min_off_time
        
        self.is_on = False
        self.last_state_change = time.ticks_ms()
    
    def turn_on(self):
        """Turn heater on if minimum off time has elapsed."""
        if self.is_on:
            return True  # Already on
        
        now = time.ticks_ms()
        time_since_change = time.ticks_diff(now, self.last_state_change) / 1000
        
        if time_since_change < self.min_off_time:
            remaining = int(self.min_off_time - time_since_change)
            print(f"Heater cooldown: {remaining}s remaining before can turn on")
            return False
        
        self.relay.on()
        self.is_on = True
        self.last_state_change = now
        print("Heater turned ON")
        return True
    
    def turn_off(self):
        """Turn heater off if minimum run time has elapsed."""
        if not self.is_on:
            return True  # Already off
        
        now = time.ticks_ms()
        time_since_change = time.ticks_diff(now, self.last_state_change) / 1000
        
        if time_since_change < self.min_run_time:
            remaining = int(self.min_run_time - time_since_change)
            print(f"Heater minimum runtime: {remaining}s remaining before can turn off")
            return False
        
        self.relay.off()
        self.is_on = False
        self.last_state_change = now
        print("Heater turned OFF")
        return True
    
    def get_state(self):
        """Return current heater state."""
        return self.is_on
    
    def force_off(self):
        """Emergency shut off (bypasses timers)."""
        self.relay.off()
        self.is_on = False
        self.last_state_change = time.ticks_ms()
        print("Heater FORCE OFF")