import board
import terminalio
import displayio
import busio
from digitalio import DigitalInOut, Direction, Pull
from adafruit_display_text import label
# from adafruit_st7789 import ST7789
import adafruit_ili9341
import adafruit_imageload
import time
from adafruit_debouncer import Debouncer
import adafruit_aw9523
import pwmio
from adafruit_motor import servo
import random

# Sound fx keys
STARTUP_SOUND = 0
HIGH_SCORE_SOUND = 1
BALL_DEPLOY_SOUND = 2
FLIPPER_SOUND = 3
WIND_DOWN_SOUND = 4
FUEL_LIGHT_SOUND = 5
MISSION_COMPLETE_SOUND = 6
SLINGSHOT_SOUND = 7
LIGHT_GROUP_LIT_SOUND = 8
CENTER_POST_GONE_SOUND = 9
FLIPPER_SOUND_2 = 10
DROP_TARGET_RESET_SOUND_DUMB = 11
WOOP_UP_SOUND = 12
WOOP_DOWN_SOUND = 13
DROP_TARGET_RESET_SOUND_2 = 14
PLUNGER_LAUNCH_SOUND = 15
MISSION_ACCEPTED_SOUND = 16
SHIP_REFUELED_SOUND = 17
RE_ENTRY_SOUND = 18
BALL_DRAINED_SOUND = 19
EXTRA_BALL_GAINED_SOUND = 20
HIGH_PITCHED_JACKPOT_SOUND = 21
LAUNCHED_NO_MISSION_SOUND = 22
CENTERPOST_BUMP_SOUND = 23
HYPERSPACE_LAUNCH_SOUND = 24
HYPERSPACE_JACKPOT_SOUND = 25
HYPERSPACE_EXTRA_BALL_SOUND = 26
HYPERSPACE_GRAVITY_WELL_SOUND = 27
GRAVITY_WELL_CANCELLED_SOUND = 28
WORMHOLE_SOUND = 29
DROP_TARGET_RESET_SOUND_3 = 30
SHOOT_SOUND = 31
SHOOT_SOUND_2 = 32
BONUS_AWARDED_SOUND = 33
SECRET_MISSION_SELECTED_SOUND = 34
MISSION_COMPLETE_PROMOTION_SOUND = 35
WORMHOLE_OPEN_LIGHT_SOUND = 36
BLACK_HOLE_RELEASE_SOUND = 37
SHOOT_SOUND_3 = 38
FLIPPER_SOUND_3 = 39
FLIPPER_SOUND_4 = 40
TILT_SOUND = 41
SPINNER_SOUND = 42

DROP_TARGET_RESET_SOUNDS = [DROP_TARGET_RESET_SOUND_2, DROP_TARGET_RESET_SOUND_3]

# Overall modes for the game
MODE_STARTUP = 0
MODE_BALL_LAUNCH = 1
MODE_PLAYING = 2
MODE_BALL_DRAIN = 3
MODE_GAME_OVER = 4
game_mode = MODE_STARTUP

# Modes for mission progression
MISSION_STATUS_NONE = 0
MISSION_STATUS_SELECTED = 1
MISSION_STATUS_ACTIVE = 2
mission_status = MISSION_STATUS_NONE
cur_mission = None
num_missions_completed = 0
cur_rank = 0
mission_hits_left = 0
DEFAULT_CRASH_BONUS = 1000
crash_bonus = DEFAULT_CRASH_BONUS
message_timer = None
MESSAGE_DELAY = 5.0
MESSAGE_DELAY_LONGER = 8.0
next_message = ''
WAITING_MISSION_SELECT_TEXT = "Hit Mission Select Targets"
current_status_text = WAITING_MISSION_SELECT_TEXT
MISSION_NAMES = [
    'Engine Maintenance',
    'Thruster Tests',
    'Orbital Refueling',
]
MISSION_HIT_COUNTS = [5, 6, 3]
MISSION_TARGETS = ['PB', 'SLG', 'HYP']
MISSION_STATUS_TEXT_PLURAL = [
    '{} Engine Bumper Hits Left',
    '{} Slingshot Thruster Hits Left',
    '{} Hyperspace Launches Left',
]
MISSION_STATUS_TEXT_SINGULAR = [
    '1 Engine Bumper Hit Left',
    '1 Slingshot Thruster Hit Left',
    '1 Hyperspace Launch Left',
]
MISSION_REWARDS = [50_000, 30_000, 25_000]
MISSIONS_PER_RANK = 3
RANK_NAMES = [
    'Cadet',
    'Ensign',
    'Lieutenant',
    'Captain',
    'Lieutenant Commander',
    'Commander',
    'Commodore',
    'Admiral',
    'Fleet Admiral',
]

# Servo constants
SERVO_TIMEOUT = 1.0

# Lights constants
pins = [0, 11, 10, 9, 8, 1, 2, 3, 4, 5, 6, 7, 12, 13, 14, 15]  # The physical order of the pins on the I2C expanders
LIGHT_SPACESHIP_LASERS = [
    [0, pins[0]],
    [0, pins[1]],
]
LIGHT_NEW_GAME_BUTTON = [0, pins[2]]
LIGHT_LEFT_FLIPPER = [0, pins[3]]
LIGHT_RIGHT_FLIPPER = [0, pins[4]]
LIGHT_DROP_TARGET = [
    [0, pins[5]], # Far
    [0, pins[6]], # Middle
    [0, pins[7]] # Close
]
LIGHT_BALL_DEPLOY = [0, pins[8]] # First device, ninth pin

light_state = [[False for _ in range(len(pins))] for _ in range(3)]
def set_light(arr, state):
    """Set the light state."""
    global aw_devices
    global light_state
    value = 255 if state else 0
    print(f'Setting light {arr[0]},{arr[1]} to {state}')
    aw_devices[arr[0]].set_constant_current(arr[1], value)
    light_state[arr[0]][arr[1]] = state

light_blink_anims = []
def blink_light(arr, num_blinks, period, stay_off_on_complete):
    """Blink a light."""
    global light_blink_anims
    light_blink_anims.append(
        (arr, num_blinks, period, stay_off_on_complete, time.monotonic())
    )

def update_blink_anims():
    """Update the blink animations."""
    # TODO: We could feasibly fade with constant current instead of just on/off
    global light_blink_anims, aw_devices, light_state
    # Iterate backwards so we can delete from the list as we go
    for i in reversed(range(len(light_blink_anims))):
        arr, num_blinks, period, stay_off_on_complete, start_time = light_blink_anims[i]
        if num_blinks == 0:
            set_light(arr, stay_off_on_complete)
            del light_blink_anims[i]
        else:
            elapsed = time.monotonic() - start_time
            if elapsed > period:
                light_blink_anims[i] = (arr, num_blinks - 1, period, stay_off_on_complete, time.monotonic())
                set_light(arr, not light_state[arr[0]][arr[1]])

# Release any resources currently in use for the displays
displayio.release_displays()

# LED for testing
print("Initializing LED...")
led = DigitalInOut(board.GP25)
led.direction = Direction.OUTPUT
led.value = True

def set_status_text(str):
    """Set the status text on the screen."""
    global text_area_recommendation
    global message_timer
    global next_message
    global current_status_text
    # Split the string into lines of maximum length 14
    final_str = ""
    cur_len = 0
    for s in str.split(" "):
        if s == "":
            continue
        s_len = len(s)
        if cur_len + s_len > 14:
            final_str += "\n" + s
            cur_len = s_len
        else:
            final_str += " " + s if cur_len > 0 else s
            cur_len += s_len + 1
    text_area_recommendation.text = final_str
    message_timer = None
    next_message = ''
    print("Set status text: " + final_str)
    current_status_text = str


def init_uart(tx_pin, rx_pin):
    """Initialize a UART bus."""
    uart = busio.UART(tx=tx_pin, rx=rx_pin, baudrate=9600, timeout=0.5)
    return uart

score_multiplier = 1

def increase_score(add):
    """Update the score on the screen."""
    global score
    global score_multiplier
    global text_area_score
    global uart_sound
    global game_mode
    score += add * score_multiplier
    # Reverse because RTL idk what I'm doing
    text_area_score.text = ''.join(reversed(f"{score}"))
    if game_mode == MODE_BALL_LAUNCH: # In case there was an IR sensor skipover
        game_mode = MODE_PLAYING
        if mission_status == MISSION_STATUS_NONE:
            set_status_text(WAITING_MISSION_SELECT_TEXT)
        send_uart(uart_sound, 'PNT')
        # Turn off ball deploy light
        set_light(LIGHT_BALL_DEPLOY, False)


def play_sound(sound_idx):
    """Send a sound play request on the UART bus."""
    global uart_sound
    snd_str = f"SND {sound_idx}\r\n"
    uart_sound.write(bytearray(snd_str, "utf-8"))


def send_uart(uart, str):
    """Send a message out on a UART bus."""
    print(f'UART send: {str}')
    write_str = f"{str}\r\n"
    uart.write(bytearray(write_str, "utf-8"))

sound_controller_initialized = False
solenoid_driver_initialized = False
drop_target_reset_sound_timer = None
DROP_TARGET_RESET_SOUND_DELAY = 0.75
HYPERSPACE_DECREASE_TIMER = 60  # Delay to decrease the hyperspace bonus
cur_hyperspace_trigger_timer = 0
ball_drained_timer = None
BALL_DRAIN_DELAY = 2.5

def readline(uart_bus):
    """Read a line from the UART bus and print it to console."""
    global NUM_HYP_BLINKS
    global HYPERSPACE_SOUND_LIST
    global cur_hyperspace_value
    global uart_sound
    global solenoid_driver_initialized
    global sound_controller_initialized
    global drop_target_reset_sound_timer
    global cur_hyperspace_trigger_timer
    global ball_drained_timer
    global ir_scores
    global pins
    global aw_devices
    global game_mode
    global score_multiplier
    global cur_mission
    global mission_hits_left
    global mission_status
    global crash_bonus
    global num_missions_completed
    global cur_rank
    global message_timer
    global next_message
    global light_blink_anims
    data = uart_bus.readline()
    mission_accepted_this_frame = False
    if data is not None:
        # convert bytearray to string
        data_string = ''.join([chr(b) for b in data])
        # Parse command
        command_list = data_string.split()
        if len(command_list) > 0:
            command = command_list[0]
            if command == 'HYP':
                # Hyperspace
                print(f"Hyperspace launched {cur_hyperspace_value + 1}")
                increase_score((cur_hyperspace_value + 1) * 100)
                if mission_status != MISSION_STATUS_SELECTED:
                    if mission_status != MISSION_STATUS_ACTIVE or command != MISSION_TARGETS[cur_mission] or mission_hits_left != 1:
                        play_sound(HYPERSPACE_SOUND_LIST[cur_hyperspace_value])
                        # Blink ship lights
                        for arr in LIGHT_SPACESHIP_LASERS:
                            blink_light(arr, NUM_HYP_BLINKS[cur_hyperspace_value], 0.125, False)
                cur_hyperspace_trigger_timer = time.monotonic()
                if mission_status == MISSION_STATUS_SELECTED:
                    set_status_text('Mission Accepted')
                    mission_accepted_this_frame = True
                    mission_status = MISSION_STATUS_ACTIVE
                    mission_hits_left = MISSION_HIT_COUNTS[cur_mission]
                    send_uart(uart_sound, 'ACC')
                    # Blink ship lights
                    for arr in LIGHT_SPACESHIP_LASERS:
                        blink_light(arr, 10, 0.125, False)
                    # TODO: Start blinking relevant mission light(s)
                    # TODO: Also need a way to stop blinking these light(s) when the mission is complete
                    # Update message after a delay
                    message_timer = MESSAGE_DELAY + time.monotonic()
                    next_message = MISSION_STATUS_TEXT_PLURAL[cur_mission].format(mission_hits_left)
                elif cur_hyperspace_value == 4:
                    if mission_status != MISSION_STATUS_ACTIVE or command != MISSION_TARGETS[cur_mission]:
                        next_message_to_set = current_status_text
                        if message_timer:
                            next_message_to_set = next_message
                        set_status_text('Jackpot Awarded')
                        next_message = next_message_to_set
                        message_timer = MESSAGE_DELAY + time.monotonic()
                    increase_score(1500)
                elif mission_status != MISSION_STATUS_ACTIVE or command != MISSION_TARGETS[cur_mission]:
                    next_message_to_set = current_status_text
                    if message_timer:
                        next_message_to_set = next_message
                    set_status_text('Hyperspace Bonus')
                    next_message = next_message_to_set
                    message_timer = MESSAGE_DELAY + time.monotonic()
                cur_hyperspace_value = (cur_hyperspace_value + 1) % len(HYPERSPACE_SOUND_LIST)
                # TODO: Blink new hyperspace light
            elif command == 'DRN':
                # Ball drained
                print("Ball drained!")
                game_mode = MODE_BALL_DRAIN
                # TODO: Handle replay/redeploy
                set_status_text(f"Crash Bonus {crash_bonus * score_multiplier}")
                increase_score(crash_bonus)
                # Relay to sound board
                send_uart(uart_sound, command)
                # Wait for a bit before reloading
                ball_drained_timer = time.monotonic()
                cur_mission = None
                mission_status = MISSION_STATUS_NONE
                # TODO: Turn off any mission lights
                light_blink_anims = []
            elif command == 'DTR':
                # Drop target reset
                print("Drop target reset!")
                # Delay before playing sound
                drop_target_reset_sound_timer = time.monotonic() + DROP_TARGET_RESET_SOUND_DELAY
                increase_score(1000)
                crash_bonus += 1000
                score_multiplier = min(score_multiplier + 1, 5)
                next_message_to_set = current_status_text
                if message_timer:
                    next_message_to_set = next_message
                set_status_text(f"Score Multiplier {score_multiplier}x")
                message_timer = MESSAGE_DELAY + time.monotonic()
                # Blink all 3 drop target lights
                for i in range(3):
                    blink_light(LIGHT_DROP_TARGET[i], 10, 0.125, True)
                next_message = next_message_to_set
            elif command == 'BTN':
                if mission_status == MISSION_STATUS_NONE or mission_status == MISSION_STATUS_SELECTED:
                    button_num = int(command_list[1])
                    set_status_text(f"Launch to Perform {MISSION_NAMES[button_num]}")
                    cur_mission = button_num
                    mission_status = MISSION_STATUS_SELECTED
                increase_score(50)
                crash_bonus += 25
            elif command == 'INI':
                board_initialized = command_list[1]
                if board_initialized == 'solenoidDriver':
                    print("Solenoid driver initialized")
                    solenoid_driver_initialized = True
                elif board_initialized == 'soundController':
                    print("Sound controller initialized")
                    sound_controller_initialized = True
                if solenoid_driver_initialized and sound_controller_initialized:
                    print("All boards initialized")
                    # Stop animation
                    for aw_device in range(len(aw_devices)):
                        for pin in range(len(pins)):
                            set_light([aw_device, pin], False)
                    # Turn on relevant lamps
                    for i in range(len(LIGHT_DROP_TARGET)):
                        set_light(LIGHT_DROP_TARGET[i], True)
                    # Reload the ball
                    send_uart(uart_solenoid, "RLD")
                    game_mode = MODE_BALL_LAUNCH
                    crash_bonus = DEFAULT_CRASH_BONUS
                    set_status_text("Launch Ball")
                    # Turn on ball deploy light
                    set_light(LIGHT_BALL_DEPLOY, True)
            elif command == 'IR':
                print("IR sensor triggered")
                increase_score(ir_scores[int(command_list[1])])
                if game_mode != MODE_BALL_LAUNCH:
                    crash_bonus += 100
                game_mode = MODE_PLAYING
                set_status_text(WAITING_MISSION_SELECT_TEXT)
                # Turn off ball deploy light
                set_light(LIGHT_BALL_DEPLOY, False)
            elif command == 'DT':
                print("Drop target triggered")
                dt_pin = int(command_list[1])
                set_light(LIGHT_DROP_TARGET[dt_pin], False)
                increase_score(1000)
            elif command == 'PB':
                print("Pop Bumper Triggered")
                increase_score(200)
            elif command == 'SLG':
                print("Slingshot Triggered")
                increase_score(100)
            elif command == 'FLU':
                print("Left flipper Up")
                set_light(LIGHT_LEFT_FLIPPER, True)
            elif command == 'FLD':
                print("Left flipper Down")
                set_light(LIGHT_LEFT_FLIPPER, False)
            elif command == 'FRU':
                print("Right flipper Up")
                set_light(LIGHT_RIGHT_FLIPPER, True)
            elif command == 'FRD':
                print("Right flipper Down")
                set_light(LIGHT_RIGHT_FLIPPER, False)
            else:
                print(data_string, end="")
            
            # Test for mission update
            if mission_status == MISSION_STATUS_ACTIVE and command == MISSION_TARGETS[cur_mission] and not mission_accepted_this_frame:
                mission_hits_left -= 1
                if mission_hits_left == 0:
                    mission_status = MISSION_STATUS_NONE
                    increase_score(MISSION_REWARDS[cur_mission] * cur_rank)
                    num_missions_completed += 1
                    cur_mission = None
                    if num_missions_completed == MISSIONS_PER_RANK:
                        crash_bonus += 1000 * cur_rank
                        num_missions_completed = 0
                        cur_rank += 1
                        cur_rank = min(cur_rank, len(RANK_NAMES) - 1)
                        set_status_text(f"Promotion to {RANK_NAMES[cur_rank]}")
                        next_message = WAITING_MISSION_SELECT_TEXT
                        message_timer = MESSAGE_DELAY_LONGER + time.monotonic()
                        send_uart(uart_sound, f'RNK {cur_rank}')
                        if command == 'HYP':
                            # Blink ship lights
                            for arr in LIGHT_SPACESHIP_LASERS:
                                blink_light(arr, 14, 0.125, False)
                        # TODO: Blink other lights around the board in celebration, too?
                    else:
                        set_status_text("Mission Completed")
                        next_message = WAITING_MISSION_SELECT_TEXT
                        message_timer = MESSAGE_DELAY_LONGER + time.monotonic()
                        crash_bonus += 550 * cur_rank
                        send_uart(uart_sound, f'MSN {num_missions_completed}')
                        if command == 'HYP':
                            # Blink ship lights
                            for arr in LIGHT_SPACESHIP_LASERS:
                                blink_light(arr, 16, 0.125, False)
                elif mission_hits_left == 1:
                    set_status_text(MISSION_STATUS_TEXT_SINGULAR[cur_mission])
                else:
                    set_status_text(MISSION_STATUS_TEXT_PLURAL[cur_mission].format(mission_hits_left))

def rand_ship_time():
    """Return a random time for the servo to update next."""
    return time.monotonic() + random.uniform(10, 30)


def rand_ship_angle(cur_angle):
    """Return a random angle for the ship servo to update to."""
    min_angle = max(cur_angle - 30, 50)
    max_angle = min(cur_angle + 30, 130)
    return random.randint(min_angle, max_angle)


# Setup I2C for the I/O expander
i2c = busio.I2C(scl=board.GP21, sda=board.GP20)
# First one has neither jumper bridged
aw1 = adafruit_aw9523.AW9523(i2c)
print("Found AW9523 1")
# Second one has A0 jumper bridged
aw2 = adafruit_aw9523.AW9523(i2c, address=0x59)
print("Found AW9523 2")
# Third one has A1 jumper bridged
aw3 = adafruit_aw9523.AW9523(i2c, address=0x5A)
print("Found AW9523 3")
aw_devices = [aw1, aw2, aw3]

# Set all pins to outputs and LED (const current) mode
aw1.LED_modes = 0xFFFF
aw1.directions = 0xFFFF
aw2.LED_modes = 0xFFFF
aw2.directions = 0xFFFF
aw3.LED_modes = 0xFFFF
aw3.directions = 0xFFFF

# Setup SPI bus
spi = busio.SPI(board.GP14, MOSI=board.GP15, MISO=board.GP12)
tft_cs = board.GP13
tft_dc = board.GP10
tft_reset = board.GP11
tft_backlight = board.GP8

# Setup display
display_bus = displayio.FourWire(spi, command=tft_dc, chip_select=tft_cs, reset=tft_reset)
# display = ST7789(display_bus, width=240, height=320,rotation=180, backlight_pin=tft_backlight)
# If using bigger display:
display = adafruit_ili9341.ILI9341(display_bus, width=240, height=320, rotation=270, backlight_pin=tft_backlight, backlight_on_high=True, brightness=1.0)

# Load score background
bitmap, palette = adafruit_imageload.load(
    "/images/score_display_vert.bmp",
    bitmap=displayio.Bitmap,
    palette=displayio.Palette,
)
# make the color at 0 index transparent.
palette.make_transparent(0)

# Make the display context
bitmap = displayio.TileGrid(bitmap, pixel_shader=palette, x=18, y=0)
group = displayio.Group()
group.append(bitmap)
display.show(group)

# Draw the score label
text_group = displayio.Group(scale=3, x=210, y=193)
text = "0"
text_area_score = label.Label(terminalio.FONT, text=text, color=0x727ACA, label_direction="RTL")
text_group.append(text_area_score)  # Subgroup for text scaling
group.append(text_group)

# Draw the ball label
text_group_ball = displayio.Group(scale=2, x=187, y=150)
text = "1"
text_area_ball = label.Label(terminalio.FONT, text=text, color=0x727ACA)
text_group_ball.append(text_area_ball)  # Subgroup for text scaling
group.append(text_group_ball)

# Draw the recommendation text
text_group_recommendation = displayio.Group(scale=2, x=31, y=232)
text = "Starting Up..."
text_area_recommendation = label.Label(terminalio.FONT, text=text, color=0x727ACA, line_spacing=0.9)
text_group_recommendation.append(text_area_recommendation)  # Subgroup for text scaling
group.append(text_group_recommendation)

# New game button
new_game_button = DigitalInOut(board.GP7)
new_game_button.direction = Direction.INPUT
new_game_button.pull = Pull.UP
new_game_button_debouncer = Debouncer(new_game_button)

# Ship servo
servo_pwm = pwmio.PWMOut(board.GP16, frequency=50)
ship_servo = servo.Servo(servo_pwm, min_pulse=500, max_pulse=2500)
cur_ship_angle = ship_servo.angle = 90
rand_servo_time = rand_ship_time()
servo_shutoff_time = time.monotonic() + SERVO_TIMEOUT

# UART bus for sound controller
uart_sound = init_uart(board.GP0, board.GP1)
# UART bus for solenoid controller
uart_solenoid = init_uart(board.GP4, board.GP5)

score = 0
ball = 1
n = 0
ir_scores = [100, 500, 200]  # Score values for each IR sensor
NUM_PINS = len(pins)
PIN_DELAY = 750
TOTAL_CYCLE = NUM_PINS * PIN_DELAY
HYPERSPACE_SOUND_LIST = [
    HYPERSPACE_LAUNCH_SOUND,
    HYPERSPACE_JACKPOT_SOUND,
    HYPERSPACE_LAUNCH_SOUND,
    HYPERSPACE_EXTRA_BALL_SOUND,
    HYPERSPACE_GRAVITY_WELL_SOUND
]
NUM_HYP_BLINKS = [
    14,
    24,
    14,
    10,
    18
]
cur_hyperspace_value = 0
gameover_anim_timer = time.monotonic()
GAMEOVER_ANIM_LED_BLINK_TIME = 0.75
NUM_BALLS = 5
while True:

    # Read any data waiting on the UART lines
    while uart_sound.in_waiting > 0:
        readline(uart_sound)
    while uart_solenoid.in_waiting > 0:
        readline(uart_solenoid)

    # Update blinking light animations
    update_blink_anims()

    # Blink LEDs randomly during gameover
    if game_mode == MODE_GAME_OVER:
        if time.monotonic() > gameover_anim_timer + GAMEOVER_ANIM_LED_BLINK_TIME:
            gameover_anim_timer = time.monotonic()
            for aw_device in aw_devices:
                for pin in range(len(pins)):
                    aw_device.set_constant_current(pin, 255 if random.random() > 0.5 else 0)

    # Update ship servo
    cur_time = time.monotonic()
    if cur_time > rand_servo_time:
        print("Move ship servo")
        rand_servo_time = rand_ship_time()
        cur_ship_angle = rand_ship_angle(cur_ship_angle)
        ship_servo.angle = cur_ship_angle
    elif cur_time > servo_shutoff_time:
        # Turn off ship servo motor if we're not using it
        print("Turn off ship servo")
        ship_servo.angle = None
        servo_shutoff_time = rand_servo_time + SERVO_TIMEOUT

    if drop_target_reset_sound_timer and cur_time > drop_target_reset_sound_timer:
        drop_target_reset_sound_timer = None
        play_sound(random.choice(DROP_TARGET_RESET_SOUNDS))
        # Reset drop target lights
        # TODO: Blinking lights should handle this already
        for i in range(len(LIGHT_DROP_TARGET)):
            set_light(LIGHT_DROP_TARGET[i], True)

    # Decrease cur_hyperspace_value after a delay & turn off lights
    if cur_time > cur_hyperspace_trigger_timer + HYPERSPACE_DECREASE_TIMER:
        cur_hyperspace_value -= 1
        cur_hyperspace_trigger_timer = cur_time
        if cur_hyperspace_value < 0:
            cur_hyperspace_value = 0
        # TODO: Something here about decreasing lights and such
        #     hyperspace_lights_off()
        # else:
        #     hyperspace_lights_on(cur_hyperspace_value)

    # Reload the ball if we should
    if ball_drained_timer and cur_time > ball_drained_timer + BALL_DRAIN_DELAY:
        # TODO: Handle replay/extra balls
        ball_drained_timer = None
        cur_hyperspace_value = 0
        ball += 1
        if ball > NUM_BALLS:
            game_mode = MODE_GAME_OVER
            set_status_text("Game Over")
            message_timer = cur_time + MESSAGE_DELAY_LONGER
            next_message = "Press New Game Button"
            send_uart(uart_sound, "GOV")
        else:
            text_area_ball.text = str(ball)
            send_uart(uart_solenoid, "RLD")
            game_mode = MODE_BALL_LAUNCH
            crash_bonus = DEFAULT_CRASH_BONUS
            set_status_text("Launch Ball")
            mission_status = MISSION_STATUS_NONE
            cur_mission = None
            # Turn on ball deploy light
            set_light(LIGHT_BALL_DEPLOY, True)

    # Start new game and such
    new_game_button_debouncer.update()
    if new_game_button_debouncer.fell:
        set_light(LIGHT_NEW_GAME_BUTTON, True)
        if game_mode == MODE_GAME_OVER:
            # Start a new game
            print("Start new game")
            game_mode = MODE_BALL_LAUNCH
            crash_bonus = DEFAULT_CRASH_BONUS
            # Turn on ball deploy light
            set_light(LIGHT_BALL_DEPLOY, True)
            score = 0
            ball = 1
            text_area_score.text = str(score)
            text_area_ball.text = str(ball)
            set_status_text("Launch Ball")
            cur_hyperspace_value = 0
            score_multiplier = 1
            mission_status = MISSION_STATUS_NONE
            cur_mission = None
            num_missions_completed = 0
            # Turn off all lights
            for aw_device in range(len(aw_devices)):
                for pin in range(len(pins)):
                    set_light([aw_device, pin], False)
            # Turn on drop target lights
            for i in range(len(LIGHT_DROP_TARGET)):
                set_light(LIGHT_DROP_TARGET[i], True)
            send_uart(uart_solenoid, "RST")
            send_uart(uart_sound, "RST")
        elif game_mode == MODE_PLAYING:
            print("New game button pressed; manual reload")
        send_uart(uart_solenoid, "RLD")
    elif new_game_button_debouncer.rose:
        print("New game button released")
        set_light(LIGHT_NEW_GAME_BUTTON, False)

    # Update message area
    if message_timer and next_message and cur_time > message_timer:
        set_status_text(next_message)
        message_timer = None
        next_message = None
