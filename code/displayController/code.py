import board
import terminalio
import displayio
import busio
from digitalio import DigitalInOut, Direction, Pull
from adafruit_display_text import label
from adafruit_st7789 import ST7789
# import adafruit_ili9341
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
DROP_TARGET_RESET_SOUND = 11
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

DROP_TARGET_RESET_SOUNDS = [DROP_TARGET_RESET_SOUND, DROP_TARGET_RESET_SOUND_2, DROP_TARGET_RESET_SOUND_3]

# Other constants
SERVO_TIMEOUT = 1.0

# Release any resources currently in use for the displays
displayio.release_displays()

# LED for testing
print("Initializing LED...")
led = DigitalInOut(board.GP25)
led.direction = Direction.OUTPUT
led.value = True


def increase_score(add):
    """Update the score on the screen."""
    global score
    global text_area_score
    score += add
    # Reverse because RTL idk what I'm doing
    # TODO: Make this only update once per frame maximum
    text_area_score.text = ''.join(reversed(f"{score}"))


def play_sound(sound_idx):
    """Send a sound play request on the UART bus."""
    global uart_sound
    snd_str = f"SND {sound_idx}\r\n"
    uart_sound.write(bytearray(snd_str, "utf-8"))


def send_uart(uart, str):
    """Send a message out on a UART bus."""
    write_str = f"{str}\r\n"
    uart.write(bytearray(write_str, "utf-8"))

sound_controller_initialized = False
solenoid_driver_initialized = False
startup_anim = True

def readline(uart_bus):
    """Read a line from the UART bus and print it to console."""
    global hyperspace_sound_list
    global cur_hyperspace_sound
    global uart_sound
    global solenoid_driver_initialized
    global sound_controller_initialized
    global startup_anim
    data = uart_bus.readline()
    if data is not None:
        # convert bytearray to string
        data_string = ''.join([chr(b) for b in data])
        # Parse command
        command_list = data_string.split()
        command = command_list[0]
        if command == 'HYP':
            # Hyperspace
            print(f"Hyperspace launched {cur_hyperspace_sound + 1}")
            # TODO: Decrease cur_hyperspace_sound after a delay & turn off lights
            increase_score((cur_hyperspace_sound + 1) * 100)
            play_sound(hyperspace_sound_list[cur_hyperspace_sound])
            cur_hyperspace_sound = (cur_hyperspace_sound + 1) % len(hyperspace_sound_list)
        elif command == 'DRN':
            # Ball drained
            print("Ball drained!")
            # Relay to sound board
            send_uart(uart_sound, command)
            # TODO: Prevent flippers and update score and such
        elif command == 'PNT':
            # Update score
            increase_score(int(command_list[1]))
            send_uart(uart_sound, command)  # In case there was an IR sensor skipover
        elif command == 'DTR':
            # Drop target reset
            print("Drop target reset!")
            # TODO: Delay before playing sound. Also remove the dumb sound from this list
            play_sound(random.choice(DROP_TARGET_RESET_SOUNDS))
            increase_score(1000)
        elif command == 'BTN':
            button_num = int(command_list[1])
            if button_num == 0:
                print("Select first mission")
                # TODO: Do something with this info
            elif button_num == 1:
                print("Select second mission")
            elif button_num == 2:
                print("Select third mission")
            increase_score(50)
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
                startup_anim = False
        else:
            print(data_string, end="")


def init_uart(tx_pin, rx_pin):
    """Initialize a UART bus."""
    uart = busio.UART(tx=tx_pin, rx=rx_pin, baudrate=9600, timeout=0.5)
    return uart


def rand_ship_time():
    """Return a random time for the servo to update next."""
    return time.monotonic() + random.uniform(5, 30)


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
tft_backlight = board.GP9

# Setup display
display_bus = displayio.FourWire(spi, command=tft_dc, chip_select=tft_cs, reset=tft_reset)
display = ST7789(display_bus, width=240, height=320,rotation=180, backlight_pin=tft_backlight)
# If using bigger display:
# display = adafruit_ili9341.ILI9341(display_bus, width=240, height=320, rotation=270, backlight_pin=tft_backlight)

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
text = "Hit the Attack\nBumpers 8\ntimes"
text_area_recommendation = label.Label(terminalio.FONT, text=text, color=0x727ACA, line_spacing=0.9)
text_group_recommendation.append(text_area_recommendation)  # Subgroup for text scaling
group.append(text_group_recommendation)

# UART bus for sound controller
uart_sound = init_uart(board.GP0, board.GP1)
# UART bus for solenoid controller
uart_solenoid = init_uart(board.GP4, board.GP5)

# IR Sensors
ir_sensors = [
    DigitalInOut(board.GP2),
    DigitalInOut(board.GP3),
    DigitalInOut(board.GP6),
    DigitalInOut(board.GP7),
]

for sensor in ir_sensors:
    sensor.direction = Direction.INPUT
    sensor.pull = Pull.UP

ir_sensor_states = [False, False, False, False]

# Ship servo
servo_pwm = pwmio.PWMOut(board.GP16, frequency=50)
ship_servo = servo.Servo(servo_pwm, min_pulse=500, max_pulse=2500)
cur_ship_angle = ship_servo.angle = 90
rand_servo_time = rand_ship_time()
servo_shutoff_time = time.monotonic() + SERVO_TIMEOUT

score = 0
ball = 1
n = 0
pins = [0, 11, 10, 9, 8, 1, 2, 3, 4, 5, 6, 7, 12, 13, 14, 15]  # The order of the pins on the I2C expander
NUM_PINS = len(pins)
PIN_DELAY = 750
TOTAL_CYCLE = NUM_PINS * PIN_DELAY
hyperspace_sound_list = [
    HYPERSPACE_LAUNCH_SOUND,
    HYPERSPACE_JACKPOT_SOUND,
    HYPERSPACE_LAUNCH_SOUND,
    HYPERSPACE_EXTRA_BALL_SOUND,
    HYPERSPACE_GRAVITY_WELL_SOUND
]
cur_hyperspace_sound = 0
startup_anim_timer = time.monotonic()
STARTUP_ANIM_LED_BLINK_TIME = 0.25
while True:

    # Read any data waiting on the UART lines
    while uart_sound.in_waiting > 0:
        readline(uart_sound)
    while uart_solenoid.in_waiting > 0:
        readline(uart_solenoid)

    # Update score and play sounds for IR sensor being triggered
    # TODO: Remove IR sensors from this board, add new game button
    for i in range(len(ir_sensors)):
        sensor = ir_sensors[i]
        sensor_state = ir_sensor_states[i]
        if not sensor.value and not sensor_state:
            ir_sensor_states[i] = True
            print("IR sensor triggered")
            increase_score(100)
            play_sound(RE_ENTRY_SOUND)
        elif sensor.value:
            ir_sensor_states[i] = False

    # Blink LEDs randomly during startup animation
    if startup_anim:
        if time.monotonic() > startup_anim_timer + STARTUP_ANIM_LED_BLINK_TIME:
            startup_anim_timer = time.monotonic()
            for aw_device in aw_devices:
                for pin in range(len(pins)):
                    aw_device.set_constant_current(pin, 255 if random.random() > 0.5 else 0)
    else:
        # LED blinky test
        # TODO: Remove
        for idx, pin_ in enumerate(pins):
            pin_val = 0
            if n > idx * PIN_DELAY and n < (idx + 1) * PIN_DELAY:
                # First ship laser diode is dim for some reason, so set second one dim too
                pin_val = 140 if idx == 0 else 255
            aw1.set_constant_current(pin_, pin_val)
            aw2.set_constant_current(pin_, 255 if pin_val > 0 else 0)
            aw3.set_constant_current(pin_, 255 if pin_val > 0 else 0)
        n = (n + 5) % TOTAL_CYCLE

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
