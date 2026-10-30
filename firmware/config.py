# Non-secret device configuration. WiFi credentials live in secrets.py.

# Which hardware this build drives:
#   "pico2w_oled"   Pico 2 W + Waveshare Pico-OLED-2.23 (SSD1305 128x32, WiFi sync)
#   "rp2350b_lcd"   Spotpear RP2350B 2.25inch LCD (ST7789P3 76x284, no radio)
BOARD = "rp2350b_lcd"
HAS_WIFI = BOARD == "pico2w_oled"

# Where the device fetches its baseline. A weekly GitHub Action regenerates
# data/baseline.json in this repo from the AOFM executive-summary XLSX.
BASELINE_URL = "https://raw.githubusercontent.com/bayanimills/aus-debt-clock/main/data/baseline.json"

SYNC_INTERVAL_S = 24 * 3600     # resync cadence when the last sync succeeded
SYNC_RETRY_S = 3600             # retry cadence after a failed sync
WIFI_TIMEOUT_S = 20
HTTP_TIMEOUT_S = 15

TICK_MS = 40                    # render period; 25 frames/s so the low digits flow at the rate
SAVE_INTERVAL_S = 60            # persist displayed value + clock to flash this often

# LCD board: SPI clock, digit colour (RGB) and glyph scale. 2x gives 14x40
# digits, 246 px for the full number on the 284 px panel.
LCD_SPI_BAUD = 31_250_000
LCD_FG = (255, 255, 255)
LCD_SCALE = 2

# LCD motion (see motion.py). Digits changing faster than FAST_HZ are drawn in
# LCD_DIM and update live; slower ones roll like an odometer wheel.
MOTION = True
LCD_TICK_MS = 20                # 50 frames/s so a roll has ~11 steps
FAST_HZ = 6
FAST_STYLE = "blur"             # "blur": wheel motion blur; "dim": plain digits in LCD_DIM
SHUTTER_MS = 10                 # blur length = distance the wheel turns in this exposure
LCD_DIM = (110, 110, 110)
ROLL_MS = 220                   # capped at half the digit's change interval
STAGGER_MS = 40                 # each place left in a carry starts this much later

# SSD1305 datasheet caps SCLK at 4 MHz. Bench-verified clean at 1, 4 and 10 MHz
# on this panel; 4 MHz keeps to spec and a full frame is still under 1.5 ms.
SPI_BAUD = 4_000_000
CONTRAST = 0x80                 # OLED contrast / LCD backlight, 0..255
# Push only the changed digit columns each tick (True) or the whole frame (False).
PARTIAL_UPDATE = True

# machine.lightsleep between ticks. Off until bench-measured; USB REPL dies in lightsleep.
LIGHTSLEEP = False
