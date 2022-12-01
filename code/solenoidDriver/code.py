import time
import board
import busio
import pwmio
from adafruit_motor import servo
from analogio import AnalogIn
from digitalio import DigitalInOut, Direction, Pull
from adafruit_debouncer import Debouncer

# Sensitivity jumper
sensitivity_pin = DigitalInOut(board.GP15)
sensitivity_pin.direction = Direction.INPUT
sensitivity_pin.pull = Pull.UP

# Constants
SLING_TRIGGER_TIME = 0.11
POP_BUMPER_TRIGGER_TIME = 0.125
POP_BUMPER_DEBOUNCE_TIME = 0.125
NUM_POP_BUMPER_SAMPLES = 20
POP_BUMPER_SENSITIVITY = -35
POP_BUMPER_DEBOUNCE_COUNT = 8
if sensitivity_pin.value:
    print("Sensitivity jumper is set to HIGH, decreasing sensitivity")
    POP_BUMPER_SENSITIVITY = 20
    POP_BUMPER_DEBOUNCE_COUNT = 20
else:
    print("Sensitivity jumper is set to LOW, increasing sensitivity")
POP_BUMPER_CALIBRATE_COUNT = 10000
POP_BUMPER_DEBOUNCE_DECREMENT = 10
DROP_TARGET_WAIT_TIME = 1.0
DROP_TARGET_UP_ANGLE = 95
DROP_TARGET_UP_TIME = 0.5
DROP_TARGET_DOWN_ANGLE = 15
DROP_TARGET_DOWN_TIME = 0.25

DRAIN_DELAY_TIME = 2.5
DRAIN_TRIGGER_TIME = 0.125
HYPERSPACE_DELAY_TIME = 0.75
HYPERSPACE_TRIGGER_TIME = 0.125
DRAIN_SIGNAL_DEBOUNCE_TIME = 5.0
PWM_MAX_DUTY_CYCLE = 65535
PWM_FLIPPER_SUSTAIN = PWM_MAX_DUTY_CYCLE // 3
FLIPPER_PWM_DELAY = 1.0

def send_uart(str):
    global uart
    print(f'UART send: {str}')
    uart.write(bytearray(f"{str}\r\n", "utf-8"))

reload_solenoid_timer = None
game_over = False

def readline():
    """Read a line from the UART bus and print it to console."""
    global uart
    global reload_solenoid
    global reload_solenoid_timer
    global drop_target_state
    global drop_target_start_time
    global game_over
    global solenoid_l
    global solenoid_r
    global sol_l_rose_time
    global sol_r_rose_time
    data = uart.readline()
    if data is not None:
        # convert bytearray to string
        data_string = ''.join([chr(b) for b in data])
        command_list = data_string.split()
        if len(command_list) > 0:
            command = command_list[0]
            if command == 'RLD':
                # Fire the reload solenoid
                reload_solenoid.value = True
                reload_solenoid_timer = time.monotonic()
            elif command == 'RST':
                game_over = False
                # Reset the drop targets
                drop_target_state = DROP_TARGET_STATE_WAIT
                drop_target_start_time = time.monotonic()
                # Recalibrate the pop bumpers
                calibrate_pop_bumpers()
                # Fire the reload solenoid
                reload_solenoid.value = True
                reload_solenoid_timer = time.monotonic()
            elif command == 'GOV':
                # Game over
                game_over = True
                solenoid_l.duty_cycle = 0
                solenoid_r.duty_cycle = 0
                sol_l_rose_time = None
                sol_r_rose_time = None
            else:
                print(f'Unknown command: {command}')

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
avg_val = 0

# Calibrate pop bumpers
def calibrate_pop_bumpers():
    global pop_bumper_vals
    global avg_val
    global max_pb_val
    print("Calibrating pop bumper sensors...")
    calibration_counter = POP_BUMPER_CALIBRATE_COUNT
    status_led.value = False    # Turn off status LED while calibrating and setting up
    while calibration_counter > 0:
        for i in range(3):
            val = pop_bumper_pins[i].value
            pop_bumper_vals[i].append(val)
            pop_bumper_vals[i].pop(0)
            avg_val = sum(pop_bumper_vals[i]) / len(pop_bumper_vals[i])
            calibration_counter -= 1
            if avg_val > max_pb_val[i]:
                max_pb_val[i] = avg_val
    print("Pop bumper calibration complete.")

    # Add a bit of margin above which the pop bumper will trigger
    for i in range(3):
        max_pb_val[i] = max_pb_val[i] + POP_BUMPER_SENSITIVITY
        print("Pop bumper {} max value: {}".format(i, max_pb_val[i]))

calibrate_pop_bumpers()

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
pop_bumper_signals = [False, False, False]
pop_bumper_signals_debounced = [
    Debouncer(lambda : pop_bumper_signals[0], interval=POP_BUMPER_DEBOUNCE_TIME),
    Debouncer(lambda : pop_bumper_signals[1], interval=POP_BUMPER_DEBOUNCE_TIME),
    Debouncer(lambda : pop_bumper_signals[2], interval=POP_BUMPER_DEBOUNCE_TIME),
]

# Init L/R flipper buttons
button_r = DigitalInOut(board.GP18)
button_r.direction = Direction.INPUT
button_r.pull = Pull.DOWN
button_l = DigitalInOut(board.GP19)
button_l.direction = Direction.INPUT
button_l.pull = Pull.DOWN
button_l_debouncer = Debouncer(button_l)
button_r_debouncer = Debouncer(button_r)

# Init L/R flipper solenoids
solenoid_l = pwmio.PWMOut(board.GP17)
solenoid_r = pwmio.PWMOut(board.GP16)

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

# Init drop target switch pins
drop_target_switch_1 = DigitalInOut(board.GP5)
drop_target_switch_1.direction = Direction.INPUT
drop_target_switch_1.pull = Pull.UP
drop_target_switch_2 = DigitalInOut(board.GP6)
drop_target_switch_2.direction = Direction.INPUT
drop_target_switch_2.pull = Pull.UP
drop_target_switch_3 = DigitalInOut(board.GP7)
drop_target_switch_3.direction = Direction.INPUT
drop_target_switch_3.pull = Pull.UP
drop_target_debouncers = [
    Debouncer(drop_target_switch_1),
    Debouncer(drop_target_switch_2),
    Debouncer(drop_target_switch_3),
]

# Init IR sensors
ir_drain = DigitalInOut(board.GP10)
ir_drain.direction = Direction.INPUT
ir_drain.pull = Pull.UP

ir_hyperspace = DigitalInOut(board.GP12)
ir_hyperspace.direction = Direction.INPUT
ir_hyperspace.pull = Pull.UP

# Init IR solenoids
reload_solenoid = DigitalInOut(board.GP11)
reload_solenoid.direction = Direction.OUTPUT
reload_solenoid.value = False

hyperspace_solenoid = DigitalInOut(board.GP13)
hyperspace_solenoid.direction = Direction.OUTPUT
hyperspace_solenoid.value = False

# Drop target servo raise states
drop_target_start_time = 0
DROP_TARGET_STATE_NONE = 0
DROP_TARGET_STATE_WAIT = 1
DROP_TARGET_STATE_UP = 2
DROP_TARGET_STATE_DOWN = 3
drop_target_state = DROP_TARGET_STATE_NONE
# Init drop target PWM
drop_target_pwm = pwmio.PWMOut(board.GP4, frequency=50)
drop_target_servo = servo.Servo(drop_target_pwm, min_pulse=500, max_pulse=2500)

# Init variables
sling_l_trigger_time = 0
sling_r_trigger_time = 0
pop_bumper_fire_time = [0 for _ in range(3)]
sol_drain_trigger_time = 0
drain_debounce_time = 0
sol_hyperspace_trigger_time = 0
sol_l_rose_time = None
sol_r_rose_time = None

# Init UART
uart = busio.UART(board.GP8, board.GP9)

# Reset drop targets
drop_target_state = DROP_TARGET_STATE_WAIT
drop_target_start_time = time.monotonic()

time.sleep(2.0)
send_uart("INI solenoidDriver")  # Let the display controller know we're ready

# Main loop
status_led.value = True   # Turn on status LED again now that we're running for real
print("Starting main loop")
while True:
    cur_time = time.monotonic()

    # Update flippers
    button_l_debouncer.update()
    button_r_debouncer.update()

    if not game_over:
        # No flipper control during gameover
        if button_l_debouncer.rose:
            sol_l_rose_time = cur_time
            solenoid_l.duty_cycle = PWM_MAX_DUTY_CYCLE
            send_uart("FLU")
        elif button_l_debouncer.fell:
            solenoid_l.duty_cycle = 0
            sol_l_rose_time = None
            send_uart("FLD")
        elif sol_l_rose_time is not None and cur_time - sol_l_rose_time > FLIPPER_PWM_DELAY:
            # PWM the solenoids after a certain period of time to make them last longer
            solenoid_l.duty_cycle = PWM_FLIPPER_SUSTAIN
            sol_l_rose_time = None

        if button_r_debouncer.rose:
            sol_r_rose_time = cur_time
            solenoid_r.duty_cycle = PWM_MAX_DUTY_CYCLE
            send_uart("FRU")
        elif button_r_debouncer.fell:
            solenoid_r.duty_cycle = 0
            sol_r_rose_time = None
            send_uart("FRD")
        elif sol_r_rose_time is not None and cur_time - sol_r_rose_time > FLIPPER_PWM_DELAY:
            solenoid_r.duty_cycle = PWM_FLIPPER_SUSTAIN
            sol_r_rose_time = None

    # Update slingshots
    # Slingshots only launch after a delay since last launch, to avoid chatter
    if slingshot_switch_l.value and cur_time - sling_l_trigger_time > SLING_TRIGGER_TIME:
        sling_l_trigger_time = cur_time + SLING_TRIGGER_TIME
        sling_solenoid_l.value = True
        send_uart("SLG L")
    if sling_switch_r.value and cur_time > sling_r_trigger_time + SLING_TRIGGER_TIME:
        sling_r_trigger_time = cur_time + SLING_TRIGGER_TIME
        sling_solenoid_r.value = True
        send_uart("SLG R")

    # Turn off slingshots after a delay
    if cur_time > sling_l_trigger_time:
        sling_solenoid_l.value = False
    if cur_time > sling_r_trigger_time:
        sling_solenoid_r.value = False
    
    # Update drain solenoid
    if not ir_drain.value and cur_time - drain_debounce_time > DRAIN_SIGNAL_DEBOUNCE_TIME:
        # Only do this once per drain event, by waiting 5 secs after the last drain
        print("drain sensor")
        drain_debounce_time = cur_time
        send_uart("DRN")
    if reload_solenoid_timer and cur_time - reload_solenoid_timer > DRAIN_TRIGGER_TIME:
        reload_solenoid.value = False
        reload_solenoid_timer = None
    
    # Update hyperspace solenoid
    if not ir_hyperspace.value and sol_hyperspace_trigger_time + HYPERSPACE_TRIGGER_TIME * 3 < cur_time:
        send_uart("HYP")
        sol_hyperspace_trigger_time = cur_time + HYPERSPACE_DELAY_TIME
    if cur_time > sol_hyperspace_trigger_time and cur_time < sol_hyperspace_trigger_time + HYPERSPACE_TRIGGER_TIME:
        print("Firing hyperspace solenoid")
        hyperspace_solenoid.value = True
    else:
        hyperspace_solenoid.value = False

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
                pop_bumper_signals[i] = False
                pop_bumper_fire_time[i] = cur_time
        else:
            if POP_BUMPER_TRIGGER_TIME + pop_bumper_fire_time[i] < cur_time:
                pop_bumper_out_pins[i].value = False
                pop_bumper_signals[i] = True
            pb_debounce_counter[i] -= POP_BUMPER_DEBOUNCE_DECREMENT
            if pb_debounce_counter[i] < 0:
                pb_debounce_counter[i] = 0
        pop_bumper_signals_debounced[i].update()
        if pop_bumper_signals_debounced[i].fell:
            print("Firing pop bumper #", i)
            send_uart("PB " + str(i+1))

    # Update drop targets
    for i in range(len(drop_target_debouncers)):
        drop_target_debouncers[i].update()  # Update debouncers
        if drop_target_debouncers[i].rose:
            print("Drop target down")
            send_uart("DT " + str(i))
    if drop_target_switch_1.value and drop_target_switch_2.value and drop_target_switch_3.value and drop_target_state == DROP_TARGET_STATE_NONE:
        print("All switches down, raising servos")
        send_uart("DTR")
        drop_target_state = DROP_TARGET_STATE_WAIT
        drop_target_start_time = cur_time
    elif drop_target_state == DROP_TARGET_STATE_WAIT and cur_time > drop_target_start_time + DROP_TARGET_WAIT_TIME:
        drop_target_servo.angle = DROP_TARGET_UP_ANGLE
        drop_target_state = DROP_TARGET_STATE_UP
        drop_target_start_time = cur_time
    elif drop_target_state == DROP_TARGET_STATE_UP and cur_time > drop_target_start_time + DROP_TARGET_UP_TIME:
        drop_target_servo.angle = DROP_TARGET_DOWN_ANGLE
        drop_target_state = DROP_TARGET_STATE_DOWN
        drop_target_start_time = cur_time
    elif drop_target_state == DROP_TARGET_STATE_DOWN and cur_time > drop_target_start_time + DROP_TARGET_DOWN_TIME:
        drop_target_servo.angle = None
        drop_target_state = DROP_TARGET_STATE_NONE
    
    while uart.in_waiting > 0:
        readline()
