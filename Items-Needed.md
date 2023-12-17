# Items Needed for the Project

<p> There are quite a few items needed to get this project going, for instance, in order to get accurate time and data logs another item would be easiest integrate into the system. Adafruit DS3231 is designed to keep track of RTC data using a battery so in case of power outage, it won't reset. If we integrate through pi pico alone, everytime the pico resets the log would reset to jan 1, 2021 12:01 etc.. </p>

<p> So here we are, along with contactors, step ups, and few other miscaleneous stuff to get high voltage things going, here is the list. </p>

Components Needed:
- [ ] [Adafruit DS3231 (Precision RTC Breakout)](https://www.adafruit.com/product/3013)
- [x] [3vdc input 24-380vac output relay](https://amzn.to/41h5ESE) [Picked up 4]
- [ ] Temp Probe
- [ ] Humidity Probe

Things needed to cut on and off:
- Cooling
- Heating
- Humidifier
- Dehumidifier
- Lights

Later:
- Water


Components Wanted:
- Adafruit DS3231 (Precision RTC Breakout)
- 3vdc to 24v step ups
- 3vdc contactor?
- 24vac contactor
- 24vdc contactor
- Voltage converter

<p> It seems there are 8 channel relay modules on amazon with a pinout for elegoo pi boards. Would be good for staging fans and/or lights. Although the lights can take 12 amps per 2 led boards I have. So would be more preferred to go with low voltage coil relay with high voltage output. Trying to think what else it could be useful for. Small switches and open/close sides on 8 channels.</p>