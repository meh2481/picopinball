import board
import busio
import digitalio
import adafruit_sdcard
import storage
import audiomp3
import audiopwmio
import time
from audiocore import WaveFile

# Init audio PWM out
print("Initializing audio PWM out...")
audio = audiopwmio.PWMAudioOut(board.GP0)

# First things first, play startup sound
wave_file = open("sfx/SOUND1.WAV", "rb")
wave = WaveFile(wave_file)
audio.play(wave)

playing = False
playing_stop_timer = 0
uart = None
PLAY_STOP_TIMER_AMOUNT = 5

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
    data = uart_recv.readline()
    if data is not None:
        # convert bytearray to string
        data_string = ''.join([chr(b) for b in data])
        command_list = data_string.split()
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
            else:
                print("Turning music off")
                audio.stop()
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

# Init MP3 decoder for music
decoder = audiomp3.MP3Decoder(open("/sd/PINBALL.mp3", "rb"))

# Init the IR sensors
ir1 = digitalio.DigitalInOut(board.GP28)
ir1.direction = digitalio.Direction.INPUT
ir1.pull = digitalio.Pull.UP
ir2 = digitalio.DigitalInOut(board.GP3)
ir2.direction = digitalio.Direction.INPUT
ir2.pull = digitalio.Pull.UP
ir3 = digitalio.DigitalInOut(board.GP4)
ir3.direction = digitalio.Direction.INPUT
ir3.pull = digitalio.Pull.UP

ir_sensors = [ir1, ir2, ir3]
prev_ir_values = [False, False, False]
RE_ENTRY_SOUND = 18

print("Wait for startup sound done...")
while audio.playing:
    pass
print("Startup sound done")
wave.deinit()
# TODO: Send startup signal to display controller
print("Start main loop...")
while True:
    audio.play(decoder) # Loop music forever
    while audio.playing:
        # Print any data on the UART line from the audio fx board
        while uart.in_waiting > 0:
            readline(uart)

        while uart_comm.in_waiting > 0:
            readline_comm(uart_comm)
        
        playing_stop_timer -= 1

        # Check IR sensors
        for i, ir in enumerate(ir_sensors):
            if not ir.value:
                if not prev_ir_values[i]:
                    print(f"IR sensor {i} triggered")
                    play_sound(uart, RE_ENTRY_SOUND)
                    prev_ir_values[i] = True
            else:
                prev_ir_values[i] = False
