import time
import board
from digitalio import DigitalInOut, Direction, Pull

# Leave the LED on when the pico is running
led = DigitalInOut(board.GP25)
led.direction = Direction.OUTPUT
led.value = True

# Init L/R flipper buttons
button_r = DigitalInOut(board.GP18)
button_r.direction = Direction.INPUT
button_r.pull = Pull.DOWN

button_l = DigitalInOut(board.GP19)
button_l.direction = Direction.INPUT
button_l.pull = Pull.DOWN

# Init L/R flipper solenoids
solenoid_l = DigitalInOut(board.GP17)
solenoid_l.direction = Direction.OUTPUT
solenoid_l.value = False

solenoid_r = DigitalInOut(board.GP16)
solenoid_r.direction = Direction.OUTPUT
solenoid_r.value = False

# Main loop
while True:
    if button_l.value:
        solenoid_l.value = True
    else:
        solenoid_l.value = False

    if button_r.value:
        solenoid_r.value = True
    else:
        solenoid_r.value = False