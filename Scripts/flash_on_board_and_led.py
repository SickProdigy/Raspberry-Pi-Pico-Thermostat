from machine import Pin, Timer

ledMachine = machine.Pin("LED", machine.Pin.OUT)
led = Pin(12, Pin.OUT)
timer = Timer()

def blink(timer):
    led.toggle()
    ledMachine.toggle()

timer.init(freq=2.5, mode=Timer.PERIODIC, callback=blink)