import board
import busio
import digitalio
import adafruit_sdcard
import storage
import audiomp3
import audiopwmio
import time
import countio
from audiocore import WaveFile
from adafruit_debouncer import Debouncer
import random
import neopixel
from adafruit_led_animation.animation.rainbowcomet import RainbowComet
from adafruit_led_animation.animation.comet import Comet
from adafruit_led_animation.animation.chase import Chase
from adafruit_led_animation.animation.pulse import Pulse
from adafruit_led_animation.animation.blink import Blink
from adafruit_led_animation.animation.rainbowsparkle import RainbowSparkle
from adafruit_led_animation.animation.sparkle import Sparkle
from adafruit_led_animation import helper

# Constants
RE_ENTRY_SOUND = 18
PLAY_STOP_TIMER_AMOUNT = 5
SHOOT_SOUND = 31
SHOOT_SOUND_2 = 32
SHOOT_SOUND_3 = 38
SHOOT_SOUNDS = [SHOOT_SOUND, SHOOT_SOUND_2, SHOOT_SOUND_3]
BALL_DRAINED_SOUND = 19
STARTUP_SOUND = 0
GAME_OVER_SOUND = 28
MISSION_COMPLETE_PROMOTION_SOUND = 35
MISSION_ACCEPTED_SOUND = 16
MISSION_COMPLETE_SOUND = 6

# Init audio PWM out
print("Initializing audio PWM out...")
audio = audiopwmio.PWMAudioOut(board.GP0)

# First things first, play startup sound
wave_file = open("sfx/SOUND1.WAV", "rb")
wave = WaveFile(wave_file)
audio.play(wave)

ANIM_STATE_LAUNCHING = 0
ANIM_STATE_DRAINED = 1
ANIM_STATE_GAME_OVER = 2
ANIM_STATE_PLAYING = 3
ANIM_STATE_STARTUP = 4
ANIM_STATE_MISSION_IN_PROGRESS = 5
ANIM_STATE_RANKUP_IN_PROGRESS = 6
ANIM_STATE_MISSION_COMPLETE = 7
ANIM_STATE_RANKUP_COMPLETE = 8
anim_flash_time = 0
MISSION_COMPLETE_FLASH_TIME = 2.0
led_anim_state = ANIM_STATE_LAUNCHING

# Next, init board perimeter neopixels to light up the board
print("Initializing neopixel perimeter...")
drained_time = 0
DRAINED_SOUND_LEN = 2.5
pixel_pin = board.GP1
num_pixels = 39
ORDER = neopixel.GRB
pixels_perimeter = neopixel.NeoPixel(
    # Tell it there's one more pixel than there actually is so the animations line up properly
    pixel_pin, num_pixels+1, brightness=0.25, auto_write=False, pixel_order=ORDER
)
pixels_perimeter.fill((0, 136, 255))  # Init neopixel color is a dark blue
pixels_perimeter.show()

# Initialize neopixel ring
print("Initializing neopixel ring...")
pixels_ring = neopixel.NeoPixel(
    board.GP2, 24+12+1, brightness=0.2, auto_write=False, pixel_order=ORDER
)
pixels_ring.fill((0, 136, 255))
pixels_ring.show()

# Create neopixel animations
print("Setting up neopixel animations...")
OUTER_RING_COLOR = (255, 0, 255)
INNER_RING_COLOR = (0, 0, 255)
PULSE_COLOR = (200, 0, 0)
INNERMOST_CENTER_COLOR = (255, 0, 0)
CENTERMOST_PIXEL = 24+12
# For perimeter neopixels
perimeter_pixel_grid = helper.PixelMap.vertical_lines(
    # Pretend the perimeter pixels are a grid so we get lines up both sides for this anim
    pixels_perimeter, 20, 2, helper.horizontal_strip_gridmap(20, alternating=True)
)
perimeter_rainbow_comet_anim = RainbowComet(perimeter_pixel_grid, speed=.035, tail_length=7, bounce=False)
perimeter_red_pulse_anim = Pulse(pixels_perimeter, speed=.035, color=PULSE_COLOR, period=1.0)
# For center ring
ring_twinkle_anim = RainbowSparkle(pixels_ring, speed=0.11, period=1.0, step=5)
ring_red_pulse_anim = Pulse(pixels_ring, speed=.035, color=PULSE_COLOR, period=1.0)
# For outer center ring
ring_outer_sparkle_anim = Sparkle(pixels_ring, speed=0.025, color=OUTER_RING_COLOR, num_sparkles=8, num_pixels=24)
ring_outer_spin_anim = Chase(pixels_ring, color=OUTER_RING_COLOR, speed=0.035, size=0, spacing=24, num_pixels=24, pixel_start=0)
ring_outer_blink_anim = Blink(pixels_ring, speed=0.125, color=OUTER_RING_COLOR, num_pixels=24, pixel_start=0)
# For inner center ring
ring_inner_spin_anim = Chase(pixels_ring, color=INNER_RING_COLOR, speed=0.035, reverse=True, size=1, spacing=11, num_pixels=12, pixel_start=24)
ring_inner_blink_anim = Blink(pixels_ring, speed=0.125, color=INNER_RING_COLOR, num_pixels=12, pixel_start=24)
# For centermost single LED
ring_center_blink_anim = Blink(pixels_ring, speed=0.5, color=INNERMOST_CENTER_COLOR, num_pixels=1, pixel_start=CENTERMOST_PIXEL)

# Setup globals
playing = False
playing_stop_timer = 0
uart = None
num_complete_missions = 0
cur_rank = 0

# LED for testing
print("Initializing LED...")
led = digitalio.DigitalInOut(board.GP25)
led.direction = digitalio.Direction.OUTPUT
led.value = True

def readline(uart_bus):
    """Read a line from the UART bus and print it to console."""
    global playing
    global playing_stop_timer
    data = uart_bus.readline()
    if data is not None:
        # convert bytearray to string
        data_string = ''.join([chr(b) for b in data])
        if "done" in data_string and playing_stop_timer <= 0:
            playing = False
        print(data_string, end="")


def readline_comm(uart_recv):
    """Read a line from the UART bus and print it to console."""
    global uart
    global audio
    global decoder
    global led_anim_state
    global ring_twinkle_anim
    global perimeter_red_pulse_anim
    global ring_red_pulse_anim
    global pixels_perimeter
    global pixels_ring
    global drained_time
    global num_complete_missions
    global cur_rank
    global ring_outer_spin_anim
    global ring_inner_spin_anim
    global anim_flash_time
    data = uart_recv.readline()
    if data is not None:
        # convert bytearray to string
        data_string = ''.join([chr(b) for b in data])
        command_list = data_string.split()
        if len(command_list) > 0:
            command = command_list[0]
            if command == 'SND':
                # SND <sound_num> - Play specified sound
                sound_num = command_list[1]
                print("Got sound to play: ", sound_num, end="")
                play_sound(uart, int(sound_num))
            elif command == 'RST':
                # RST - Reset and start new game
                print("Got reset command")
                play_sound(uart, STARTUP_SOUND)
                led_anim_state = ANIM_STATE_LAUNCHING
                drained_time = 0
                pixels_perimeter.fill((0, 0, 0))
                pixels_perimeter.show()
                pixels_ring.fill((15, 255, 120))
                pixels_ring.show()
            elif command == 'MUS':
                # MUS <on/off> - Turn music on/off
                on_off = command_list[1]
                if on_off.upper() == 'ON':
                    print("Turning music on")
                    audio.play(decoder)
                elif on_off.upper() == 'OFF':
                    print("Turning music off")
                    audio.stop()
                else:
                    print("Invalid MUS command")
            elif command == 'DRN':
                play_sound(uart, BALL_DRAINED_SOUND)
                led_anim_state = ANIM_STATE_DRAINED
                pixels_perimeter.fill((176, 13, 0))  # Drain neopixel color is a dark red
                pixels_perimeter.show()
                pixels_ring.fill((176, 13, 0))
                pixels_ring.show()
                # Delay and then reset animation
                drained_time = time.monotonic()
            elif command == 'PNT':
                # In case IR sensors don't trigger, cancel the launching animation as soon as anything else happens
                if led_anim_state == ANIM_STATE_LAUNCHING:
                    # Cancel ball launching animation
                    led_anim_state = ANIM_STATE_PLAYING
                    pixels_perimeter.fill((255, 255, 255))
                    pixels_perimeter.show()
                    # Show center lights for current state
                    for i in range(24):
                        if i < num_complete_missions * 8:
                            pixels_ring[i] = OUTER_RING_COLOR
                        else:
                            pixels_ring[i] = (0, 0, 0)
                    for i in range(12):
                        if i < cur_rank + 1:
                            pixels_ring[i+24] = INNER_RING_COLOR
                        else:
                            pixels_ring[i+24] = (0, 0, 0)
                    pixels_ring[CENTERMOST_PIXEL] = (0, 0, 0)
                    pixels_ring.show()
            elif command == 'GOV':
                # Game over
                play_sound(uart, GAME_OVER_SOUND)
                led_anim_state = ANIM_STATE_GAME_OVER
                pixels_perimeter.fill((0, 0, 0))
                pixels_perimeter.show()
                pixels_ring.fill((0, 0, 0))
                pixels_ring.show()
                ring_twinkle_anim.reset()
                perimeter_red_pulse_anim.reset()
                ring_red_pulse_anim.reset()
                num_complete_missions = 0
                cur_rank = 0
                # Update spin anims length
                ring_inner_spin_anim._size = 1
                ring_inner_spin_anim._spacing = 11
                ring_outer_spin_anim._size = 0
                ring_outer_spin_anim._spacing = 24
            elif command == 'ACC':
                play_sound(uart, MISSION_ACCEPTED_SOUND)
                ring_outer_spin_anim.reset()
                if num_complete_missions == 2:
                    led_anim_state = ANIM_STATE_RANKUP_IN_PROGRESS
                    ring_inner_spin_anim.reset()
                else:
                    led_anim_state = ANIM_STATE_MISSION_IN_PROGRESS
            elif command == 'MSN':
                # Mission completed
                play_sound(uart, MISSION_COMPLETE_SOUND)
                led_anim_state = ANIM_STATE_MISSION_COMPLETE
                for i in range(24):
                    pixels_ring[i] = (0, 0, 0)
                pixels_ring.show()
                # Update anims length
                num_complete_missions = int(command_list[1])
                ring_outer_spin_anim._size = 8 * num_complete_missions
                ring_outer_spin_anim._spacing = 24 - ring_outer_spin_anim._size
                ring_outer_blink_anim._num_pixels = 8 * num_complete_missions
                ring_outer_blink_anim.reset()
                anim_flash_time = time.monotonic()
            elif command == 'RNK':
                # Rank changed
                play_sound(uart, MISSION_COMPLETE_PROMOTION_SOUND)
                led_anim_state = ANIM_STATE_RANKUP_COMPLETE
                ring_inner_blink_anim.reset()
                ring_outer_blink_anim.reset()
                anim_flash_time = time.monotonic()
                # Flashing anim for new rank
                for i in range(24+12):
                    pixels_ring[i] = (0, 0, 0)
                pixels_ring.show()
                cur_rank = int(command_list[1])
                num_complete_missions = 0
                ring_inner_blink_anim._num_pixels = cur_rank + 1
                ring_inner_blink_anim.reset()
                # Update spin anims length
                ring_inner_spin_anim._size = cur_rank + 1
                ring_inner_spin_anim._spacing = 12 - ring_inner_spin_anim._size
                ring_outer_spin_anim._size = 0
                ring_outer_spin_anim._spacing = 24
            else:
                print(f'Unknown command: {command}')


def init_uart():
    """Initialize the UART bus for the audio FX board."""
    # Init UART serial for audio fx board
    uart = busio.UART(board.GP16, board.GP17, baudrate=9600, timeout=0.5)
    rst = digitalio.DigitalInOut(board.GP18)
    rst.direction = digitalio.Direction.OUTPUT
    rst.value = False
    time.sleep(0.01)
    rst.value = True
    rst.direction = digitalio.Direction.INPUT
    time.sleep(1.0)  # wait for board to boot

    # Print version info
    readline(uart)  # eat newline
    readline(uart)  # Adafruit FX Sound Board 11/6/14
    time.sleep(0.25)
    readline(uart)  # FAT type
    readline(uart)  # File count

    # DEBUG: List tracks
    # Leaving this in because the FX board swallows the first sound play command otherwise, it seems
    uart.write(b"L\r\n")
    return uart


def init_uart_comm():
    """Initialize the UART bus for communicating with the other pico."""
    uart = busio.UART(board.GP8, board.GP9, baudrate=9600, timeout=0.5)
    return uart

def kill_sound():
    """Write a line to the UART bus."""
    global playing
    global playing_stop_timer
    if playing:  # Sound still playing
        # Kill current sound
        uart.write(b"q\r\n")
        playing_stop_timer = PLAY_STOP_TIMER_AMOUNT
        time.sleep(0.1)
    playing = False

def play_sound(uart, sound_num):
    """Write a line to the UART bus."""
    print("playing sound: ", sound_num)
    global playing
    if playing:
        kill_sound()
    # Play sound
    sound_str = f'#{sound_num}\r\n'
    uart.write(sound_str.encode())
    playing = True

# Initialize and mount the SD card.
print("Initializing SD card...")
spi = busio.SPI(board.GP10, MOSI=board.GP11, MISO=board.GP12)
cs = digitalio.DigitalInOut(board.GP13)
sdcard = adafruit_sdcard.SDCard(spi, cs)
vfs = storage.VfsFat(sdcard)
storage.mount(vfs, "/sd")

# Init the audio board
print("Initializing audio board...")
uart = init_uart()

# UART for communicating with the other pico
print("Initializing UART for other pico...")
uart_comm = init_uart_comm()

def send_uart(str):
    """Send a message out on the comm UART bus."""
    global uart_comm
    print(f'UART send: {str}')
    write_str = f"{str}\r\n"
    uart_comm.write(bytearray(write_str, "utf-8"))

# Init Wav decoder for music
# decoder = WaveFile(open("/sd/PINBALL.WAV", "rb"), bytearray(1024))
# Init MP3 decoder for music
decoder = audiomp3.MP3Decoder(open("/sd/PINBALL.mp3", "rb"))

# Init switches for mission select buttons
mission_select_1 = digitalio.DigitalInOut(board.GP21)
mission_select_1.direction = digitalio.Direction.INPUT
mission_select_1.pull = digitalio.Pull.UP
mission_select_2 = digitalio.DigitalInOut(board.GP20)
mission_select_2.direction = digitalio.Direction.INPUT
mission_select_2.pull = digitalio.Pull.UP
mission_select_3 = digitalio.DigitalInOut(board.GP19)
mission_select_3.direction = digitalio.Direction.INPUT
mission_select_3.pull = digitalio.Pull.UP

debounced_mission_buttons = [
    Debouncer(mission_select_1),
    Debouncer(mission_select_2),
    Debouncer(mission_select_3),
]

print("Wait for startup sound done...")
while audio.playing:
    while uart.in_waiting > 0:
        readline(uart)
    while uart_comm.in_waiting > 0:
        readline_comm(uart_comm)
print("Startup sound done")
wave.deinit()
send_uart("INI soundController")
# Clear out perimeter neopixels
pixels_perimeter.fill((0, 0, 0))
pixels_perimeter.show()
print("Setting up IR Sensors...")
# GP27 = left IR sensor
# GP3 = middle IR sensor
# GP5 = right IR sensor
with countio.Counter(board.GP27, pull=digitalio.Pull.UP) as ir1, countio.Counter(board.GP3, pull=digitalio.Pull.UP) as ir2, countio.Counter(board.GP5, pull=digitalio.Pull.UP) as ir3:
    ir_sensors = [ir1, ir2, ir3]
    print("Start main loop...")
    while True:
        audio.play(decoder) # Loop music forever
        while audio.playing:
            cur_time = time.monotonic()

            # Update pixel animations
            if led_anim_state == ANIM_STATE_GAME_OVER:
                perimeter_red_pulse_anim.animate()
                ring_red_pulse_anim.animate()
            elif led_anim_state == ANIM_STATE_LAUNCHING:
                perimeter_rainbow_comet_anim.animate()
                ring_twinkle_anim.animate()
            elif led_anim_state == ANIM_STATE_RANKUP_IN_PROGRESS:
                ring_outer_spin_anim.animate(show=False)
                ring_inner_spin_anim.animate(show=False)
                ring_center_blink_anim.animate(show=False)
                pixels_ring.show()
            elif led_anim_state == ANIM_STATE_MISSION_IN_PROGRESS:
                ring_outer_spin_anim.animate(show=False)
                ring_center_blink_anim.animate(show=False)
                pixels_ring.show()
            elif led_anim_state == ANIM_STATE_DRAINED and cur_time - drained_time > DRAINED_SOUND_LEN:
                led_anim_state = ANIM_STATE_LAUNCHING
                pixels_perimeter.fill((0, 0, 0))
                pixels_perimeter.show()
                pixels_ring.fill((0, 0, 0))
                pixels_ring.show()
                perimeter_rainbow_comet_anim.reset()
            elif led_anim_state == ANIM_STATE_MISSION_COMPLETE:
                ring_outer_blink_anim.animate(show=False)
                ring_center_blink_anim.animate(show=False)
                if cur_time > anim_flash_time + MISSION_COMPLETE_FLASH_TIME:
                    # Light relevant LEDs for mission/rank completion progress
                    for i in range(0, num_complete_missions * 8):
                        pixels_ring[i] = OUTER_RING_COLOR
                    pixels_ring[CENTERMOST_PIXEL] = (0, 0, 0)
                    led_anim_state = ANIM_STATE_PLAYING
                pixels_ring.show()
            elif led_anim_state == ANIM_STATE_RANKUP_COMPLETE:
                ring_inner_blink_anim.animate(show=False)
                ring_outer_sparkle_anim.animate(show=False)
                ring_center_blink_anim.animate(show=False)
                if cur_time > anim_flash_time + MISSION_COMPLETE_FLASH_TIME:
                    # Light relevant LEDs for mission/rank completion progress
                    for i in range(24):
                        pixels_ring[i] = (0, 0, 0)
                    for i in range(0, cur_rank + 1):
                        pixels_ring[i+24] = INNER_RING_COLOR
                    pixels_ring[CENTERMOST_PIXEL] = (0, 0, 0)
                    led_anim_state = ANIM_STATE_PLAYING
                pixels_ring.show()

            # Print any data on the UART line from the audio fx board
            while uart.in_waiting > 0:
                readline(uart)

            while uart_comm.in_waiting > 0:
                readline_comm(uart_comm)

            playing_stop_timer -= 1

            # Check IR sensors
            for i in range(len(ir_sensors)):
                if ir_sensors[i].count > 0:
                    print(f'IR sensor {i} triggered')
                    play_sound(uart, RE_ENTRY_SOUND)
                    ir_sensors[i].count = 0
                    send_uart(f'IR {i}')
                    # Cancel ball launching animation
                    if led_anim_state == ANIM_STATE_LAUNCHING:
                        led_anim_state = ANIM_STATE_PLAYING
                        pixels_perimeter.fill((255, 255, 255))
                        pixels_perimeter.show()
                        # Show center lights for current state
                        for i in range(24):
                            if i < num_complete_missions * 8:
                                pixels_ring[i] = OUTER_RING_COLOR
                            else:
                                pixels_ring[i] = (0, 0, 0)
                        for i in range(12):
                            if i < cur_rank + 1:
                                pixels_ring[i+24] = INNER_RING_COLOR
                            else:
                                pixels_ring[i+24] = (0, 0, 0)
                        pixels_ring[CENTERMOST_PIXEL] = (0, 0, 0)
                        pixels_ring.show()

            # Check mission select buttons
            for i in range(len(debounced_mission_buttons)):
                debounced_mission_buttons[i].update()
                if debounced_mission_buttons[i].fell:
                    print(f'Mission select button {i} pressed')
                    play_sound(uart, random.choice(SHOOT_SOUNDS))
                    send_uart(f"BTN {i}")  # Display controller handles the score update so we don't spam the UART bus
