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
from adafruit_led_animation import helper

# Constants
RE_ENTRY_SOUND = 18
PLAY_STOP_TIMER_AMOUNT = 5
SHOOT_SOUND = 31
SHOOT_SOUND_2 = 32
SHOOT_SOUND_3 = 38
SHOOT_SOUNDS = [SHOOT_SOUND, SHOOT_SOUND_2, SHOOT_SOUND_3]
BALL_DRAINED_SOUND = 19

# Init audio PWM out
print("Initializing audio PWM out...")
audio = audiopwmio.PWMAudioOut(board.GP0)

# First things first, play startup sound
wave_file = open("sfx/SOUND1.WAV", "rb")
wave = WaveFile(wave_file)
audio.play(wave)

# Next, init board outer ring neopixels to light up the board
print("Initializing neopixels...")
ball_launch_animation = True
drained_time = 0
currently_drained = False
DRAINED_SOUND_LEN = 2.5
pixel_pin = board.GP1
num_pixels = 39
ORDER = neopixel.GRB
pixels = neopixel.NeoPixel(
    pixel_pin, num_pixels+1, brightness=0.25, auto_write=False, pixel_order=ORDER
)
pixels.fill((0, 136, 255))  # Init neopixel color is a dark blue
pixels.show()

# Setup globals
playing = False
playing_stop_timer = 0
uart = None

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
    global ball_launch_animation
    global pixels
    global drained_time
    global currently_drained
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
                # RST - Reset and stop all currently-playing sounds
                print("Got reset command")
                kill_sound()
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
                pixels.fill((176, 13, 0))  # Drain neopixel color is a dark red
                pixels.show()
                # Delay and then reset animation
                drained_time = time.monotonic()
                currently_drained = True
            elif command == 'PNT':
                # In case IR sensors don't trigger, cancel the launching animation as soon as anything else happens
                if ball_launch_animation:
                    # Cancel ball launching animation
                    ball_launch_animation = False
                    pixels.fill((255, 255, 255))
                    pixels.show()
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

# Init MP3 decoder for music
# TODO: Swap this over to WAV for less decoding processor overhead
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
time.sleep(0.5)
send_uart("INI soundController")
# Clear out pixels
pixels.fill((0, 0, 0))
pixels.show()
print("Setting up IR Sensors...")
# GP27 = left IR sensor
# GP3 = middle IR sensor
# GP5 = right IR sensor
with countio.Counter(board.GP27, pull=digitalio.Pull.UP) as ir1, countio.Counter(board.GP3, pull=digitalio.Pull.UP) as ir2, countio.Counter(board.GP5, pull=digitalio.Pull.UP) as ir3:
    ir_sensors = [ir1, ir2, ir3]

    # Start neopixel animation
    print("Starting neopixel animation...")
    pixel_grid = helper.PixelMap.vertical_lines(
        pixels, 20, 2, helper.horizontal_strip_gridmap(20, alternating=True)
    )
    rainbow_comet_v = RainbowComet(
        pixel_grid, speed=.035, tail_length=7, bounce=False
    )
    print("Start main loop...")
    while True:
        audio.play(decoder) # Loop music forever
        while audio.playing:
            cur_time = time.monotonic()

            # Update pixel animations
            if ball_launch_animation:
                rainbow_comet_v.animate()
            if currently_drained and cur_time - drained_time > DRAINED_SOUND_LEN:
                currently_drained = False
                ball_launch_animation = True
                pixels.fill((0, 0, 0))
                pixels.show()
                rainbow_comet_v.reset()

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
                    if ball_launch_animation:
                        ball_launch_animation = False
                        pixels.fill((255, 255, 255))
                        pixels.show()

            # Check mission select buttons
            for i in range(len(debounced_mission_buttons)):
                debounced_mission_buttons[i].update()
                if debounced_mission_buttons[i].fell:
                    print(f'Mission select button {i} pressed')
                    play_sound(uart, random.choice(SHOOT_SOUNDS))
                    send_uart(f"BTN {i}")  # Display controller handles the score update so we don't spam the UART bus
