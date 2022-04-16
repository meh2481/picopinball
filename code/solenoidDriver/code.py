import time
import board
from analogio import AnalogIn
from digitalio import DigitalInOut, Direction, Pull

# Constants
SLING_TRIGGER_TIME = 0.11
POP_BUMPER_TRIGGER_TIME = 0.125
NUM_POP_BUMPER_SAMPLES = 20
POP_BUMPER_SENSITIVITY = 30
POP_BUMPER_DEBOUNCE_COUNT = 20
POP_BUMPER_CALIBRATE_COUNT = 10000
POP_BUMPER_DEBOUNCE_DECREMENT = 10

# Leave the LED on while the pico is running
status_led = DigitalInOut(board.GP25)
status_led.direction = Direction.OUTPUT
status_led.value = True

# Init pop bumper pins
pop_bumper_pin_1 = AnalogIn(board.GP26)
pop_bumper_pin_2 = AnalogIn(board.GP27)
pop_bumper_pin_3 = AnalogIn(board.GP28)

pop_bumper_pins = [pop_bumper_pin_1, pop_bumper_pin_2, pop_bumper_pin_3]

pop_bumper_vals = [
    [0 for _ in range(NUM_POP_BUMPER_SAMPLES)],
    [0 for _ in range(NUM_POP_BUMPER_SAMPLES)],
    [0 for _ in range(NUM_POP_BUMPER_SAMPLES)],
]

pb_debounce_counter = [0 for _ in range(3)]

max_pb_val = [0, 0, 0]

# Calibrate pop bumpers
print("Calibrating pop bumper sensors...")
calibration_counter = POP_BUMPER_CALIBRATE_COUNT
status_led.value = False    # Turn off status LED while calibrating and setting up
while calibration_counter > 0:
    for i in range(3):
        val = pop_bumper_pin_1.value
        pop_bumper_vals[i].append(val)
        pop_bumper_vals[i].pop(0)
        avg_val = sum(pop_bumper_vals[i]) / len(pop_bumper_vals[i])
        calibration_counter -= 1
        if avg_val > max_pb_val[i]:
            max_pb_val[i] = avg_val

# Add a bit of margin above which the pop bumper will trigger
for i in range(3):
    max_pb_val[i] = max_pb_val[i] + POP_BUMPER_SENSITIVITY

# Init pop bumper output pins
pop_bumper_1_out = DigitalInOut(board.GP20)
pop_bumper_1_out.direction = Direction.OUTPUT
pop_bumper_1_out.value = False

pop_bumper_2_out = DigitalInOut(board.GP21)
pop_bumper_2_out.direction = Direction.OUTPUT
pop_bumper_2_out.value = False

pop_bumper_3_out = DigitalInOut(board.GP22)
pop_bumper_3_out.direction = Direction.OUTPUT
pop_bumper_3_out.value = False

pop_bumper_out_pins = [pop_bumper_1_out, pop_bumper_2_out, pop_bumper_3_out]

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
pop_bumper_fire_time = [0 for _ in range(3)]

# Main loop
status_led.value = True   # Turn on status LED again now that we're running for real
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

    # Update pop bumpers
    for i in range(3):
        val = pop_bumper_pins[i].value
        pop_bumper_vals[i].append(val)
        pop_bumper_vals[i].pop(0)
        avg_val = sum(pop_bumper_vals[i]) / len(pop_bumper_vals[i])
        if avg_val > max_pb_val[i]:
            pb_debounce_counter[i] += 1
            if pb_debounce_counter[i] > POP_BUMPER_DEBOUNCE_COUNT:
                pop_bumper_out_pins[i].value = True
                pop_bumper_fire_time[i] = cur_time + POP_BUMPER_TRIGGER_TIME
        else:
            if POP_BUMPER_TRIGGER_TIME + pop_bumper_fire_time[i] < cur_time:
                pop_bumper_out_pins[i].value = False
            pb_debounce_counter[i] -= POP_BUMPER_DEBOUNCE_DECREMENT
            if pb_debounce_counter[i] < 0:
                pb_debounce_counter[i] = 0
