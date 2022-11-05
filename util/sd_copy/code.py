import board
import busio
import digitalio
import adafruit_sdcard
import storage
from audiocore import WaveFile
import audiopwmio

# Init audio PWM out
print("Initializing audio PWM out...")
audio = audiopwmio.PWMAudioOut(board.GP0)

# LED for testing
print("Initializing LED...")
led = digitalio.DigitalInOut(board.GP25)
led.direction = digitalio.Direction.OUTPUT
led.value = True

# Initialize and mount the SD card.
print("Initializing SD card 1...")
spi = busio.SPI(board.GP10, MOSI=board.GP11, MISO=board.GP12)
cs = digitalio.DigitalInOut(board.GP13)
sdcard = adafruit_sdcard.SDCard(spi, cs)
vfs = storage.VfsFat(sdcard)
storage.mount(vfs, "/sd1")

print("Initializing SD card 2...")
cs2 = digitalio.DigitalInOut(board.GP9)
sdcard2 = adafruit_sdcard.SDCard(spi, cs2)
vfs2 = storage.VfsFat(sdcard2)
storage.mount(vfs2, "/sd2")

# Copy files from SD card 1 to SD card 2
print("Copying files from SD card 1 to SD card 2...")
cur_amt = 0
with open("/sd1/PINBALL.wav", "rb") as f1, open("/sd2/PINBALL.wav", "wb") as f2:
    while True:
        buf = f1.read(4096)
        if buf:
            f2.write(buf)
            cur_amt += len(buf)
            print(f"Read {cur_amt} bytes")
        else:
            break

wave_file = open("/sd2/PINBALL.WAV", "rb")
wave = WaveFile(wave_file)
audio.play(wave)

audio.play(wave) # Loop music forever
while audio.playing:
    pass
