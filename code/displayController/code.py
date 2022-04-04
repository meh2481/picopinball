import board
import terminalio
import displayio
import busio
from analogio import AnalogIn
from digitalio import DigitalInOut, Direction, Pull
from adafruit_display_text import label
from adafruit_st7789 import ST7789
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

# Other constants
SERVO_TIMEOUT = 1.0

# Release any resources currently in use for the displays
displayio.release_displays()

def increase_score(text_area, add):
    """Update the score on the screen."""
    global score
    score += add
    text_area.text = ''.join(reversed(f"{score}"))    # Reverse because RTL idk what I'm doing

def play_sound(sound_idx):
    """Send a sound play request on the UART bus."""
    global uart_sound
    snd_str = f"SND {sound_idx}\r\n"
    uart_sound.write(bytearray(snd_str, "utf-8"))

def readline(uart_bus):
    """Read a line from the UART bus and print it to console."""
    data = uart_bus.readline()
    if data is not None:
        # convert bytearray to string
        data_string = ''.join([chr(b) for b in data])
        # TODO: Command parsing
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
pins = [0, 11, 10, 9, 8]
i2c = busio.I2C(scl=board.GP21, sda=board.GP20)
aw = adafruit_aw9523.AW9523(i2c)
print("Found AW9523")

# Set all pins to outputs and LED (const current) mode
aw.LED_modes = 0xFFFF
aw.directions = 0xFFFF

# Setup SPI bus
spi = busio.SPI(board.GP14, MOSI=board.GP15, MISO=board.GP12)
tft_cs = board.GP13
tft_dc = board.GP10
tft_reset = board.GP11
tft_backlight = board.GP9

# Setup display
display_bus = displayio.FourWire(
    spi, command=tft_dc, chip_select=tft_cs, reset=tft_reset
)
display = ST7789(display_bus, width=240, height=320, rotation=180, backlight_pin=tft_backlight)

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

# Init spinner
pin = AnalogIn(board.GP26)
debounced_spinner = Debouncer(lambda: pin.value > 35000, interval=0.002)

# TEMP: Test button on GPIO17
button = DigitalInOut(board.GP17)
button.direction = Direction.INPUT
button.pull = Pull.UP
debounced_button = Debouncer(button)

# UART bus for sound controller
uart_sound = init_uart(board.GP0, board.GP1)

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
ship_servo = servo.Servo(servo_pwm, min_pulse = 500, max_pulse = 2500)
cur_ship_angle = ship_servo.angle = 90
rand_servo_time = rand_ship_time()
servo_shutoff_time = time.monotonic() + SERVO_TIMEOUT

score = 0
ball = 1
n = 0
NUM_PINS = len(pins)
PIN_DELAY = 1000
TOTAL_CYCLE = NUM_PINS * PIN_DELAY
while True:
    # Update debouncers
    debounced_spinner.update()
    debounced_button.update()

    # Read any data waiting on the UART line
    while uart_sound.in_waiting > 0:
        readline(uart_sound)

    # TEMP: Test button on GP17 to play sound & increase score
    if debounced_button.fell:
        print("Test button pressed")
        increase_score(text_area_score, 100)
        play_sound(HYPERSPACE_LAUNCH_SOUND)
    
    # Update score and play sounds for IR sensor being triggered
    for i in range(len(ir_sensors)):
        sensor = ir_sensors[i]
        sensor_state = ir_sensor_states[i]
        if not sensor.value and not sensor_state:
            ir_sensor_states[i] = True
            print("IR sensor triggered")
            increase_score(text_area_score, 100)
            play_sound(RE_ENTRY_SOUND)
        elif sensor.value:
            ir_sensor_states[i] = False

    # Spinner
    if debounced_spinner.rose or debounced_spinner.fell:
        increase_score(text_area_score, 10)

    # LED blinky test
    for idx, pin_ in enumerate(pins):
        pin_val = 0
        if n > idx * PIN_DELAY and n < (idx + 1) * PIN_DELAY:
            pin_val = 140 if idx == 0 else 255
        aw.set_constant_current(pin_, pin_val)
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
    
