import time
import board
from digitalio import DigitalInOut, Direction, Pull

SLING_TRIGGER_TIME = 0.125

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

# Init L/R slingshot switches
slingshot_switch_l = DigitalInOut(board.GP0)
slingshot_switch_l.direction = Direction.INPUT
slingshot_switch_l.pull = Pull.DOWN

sling_switch_r = DigitalInOut(board.GP1)
sling_switch_r.direction = Direction.INPUT
sling_switch_r.pull = Pull.DOWN

# Init L/R slingshot solenoids
sling_solenoid_l = DigitalInOut(board.GP2)
sling_solenoid_l.direction = Direction.OUTPUT
sling_solenoid_l.value = False

sling_solenoid_r = DigitalInOut(board.GP3)
sling_solenoid_r.direction = Direction.OUTPUT
sling_solenoid_r.value = False

sling_l_trigger_time = 0
sling_r_trigger_time = 0

# Main loop
while True:
    cur_time = time.monotonic()

    # Update flippers
    if button_l.value:
        solenoid_l.value = True
    else:
        solenoid_l.value = False
    if button_r.value:
        solenoid_r.value = True
    else:
        solenoid_r.value = False

    # Update slingshots
    # Slingshots only launch after a delay since last launch, to avoid chatter
    if slingshot_switch_l.value and cur_time - sling_l_trigger_time > SLING_TRIGGER_TIME:
        sling_l_trigger_time = cur_time + SLING_TRIGGER_TIME
        sling_solenoid_l.value = True
    if sling_switch_r.value and cur_time > sling_r_trigger_time + SLING_TRIGGER_TIME:
        sling_r_trigger_time = cur_time + SLING_TRIGGER_TIME
        sling_solenoid_r.value = True

    # Turn off slingshots after a delay
    if cur_time > sling_l_trigger_time:
        sling_solenoid_l.value = False
    if cur_time > sling_r_trigger_time:
        sling_solenoid_r.value = False