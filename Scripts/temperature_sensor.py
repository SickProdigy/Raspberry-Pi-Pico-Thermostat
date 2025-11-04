import machine, onewire, ds18x20, time

ds_pin = machine.Pin(10)
ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))

roms = ds_sensor.scan()
print('Found DS devices: ', roms)

while True:
  ds_sensor.convert_temp()
  time.sleep_ms(750)
  for rom in roms:      # in a loop to get each sensor on the same pin since you can have multi sensors
    print(rom)
    tempC = ds_sensor.read_temp(rom)
    tempF = tempC * (9/5) +32    # convert to farenheit
    # print('temperature (ºC):', "{:.2f}".format(tempC))  # The result will have two decimal places {:.2f}
    print('temperature (ºF):', "{:.2f}".format(tempF))
    print()
  time.sleep(5) # the loop will repeat every 5 seconds