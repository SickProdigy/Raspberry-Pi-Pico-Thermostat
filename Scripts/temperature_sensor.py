import machine
import onewire
import ds18x20
import time

class TemperatureSensor:
    def __init__(self, pin=10):
        """Initialize DS18X20 temperature sensor on the specified pin."""
        self.ds_pin = machine.Pin(pin)
        self.ds_sensor = ds18x20.DS18X20(onewire.OneWire(self.ds_pin))
        self.roms = []
        self.scan_sensors()
    
    def scan_sensors(self):
        """Scan for connected DS18X20 sensors."""
        try:
            # Convert bytearray to bytes so they can be used as dict keys
            self.roms = [bytes(rom) for rom in self.ds_sensor.scan()]
            # print(f'Found {len(self.roms)} DS18X20 sensor(s)')
            return self.roms
        except Exception as e:
            print(f'Error scanning sensors: {e}')
            return []
    
    def read_temp_c(self, rom=None):
        """Read temperature in Celsius. If rom=None, reads first sensor."""
        try:
            self.ds_sensor.convert_temp()
            time.sleep_ms(750)
            
            if rom is None and self.roms:
                rom = self.roms[0]
            
            if rom:
                return self.ds_sensor.read_temp(rom)
            return None
        except Exception as e:
            print(f'Error reading temperature: {e}')
            return None
    
    def read_temp_f(self, rom=None):
        """Read temperature in Fahrenheit."""
        temp_c = self.read_temp_c(rom)
        if temp_c is not None:
            return temp_c * (9/5) + 32
        return None
    
    def read_all_temps(self, unit='F'):
        """Read all connected sensors. Returns dict of {rom: temp}."""
        results = {}
        try:
            self.ds_sensor.convert_temp()
            time.sleep_ms(750)
            
            for rom in self.roms:
                temp_c = self.ds_sensor.read_temp(rom)
                if unit.upper() == 'F':
                    results[rom] = temp_c * (9/5) + 32
                else:
                    results[rom] = temp_c
        except Exception as e:
            print(f'Error reading temperatures: {e}')
        
        return results