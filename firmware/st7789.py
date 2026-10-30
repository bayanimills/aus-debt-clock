"""ST7789P3 76x284 SPI driver for the Spotpear RP2350B 2.25inch LCD board
(panel ZJY225KP-PG01).

Pins, SPI clock and the init sequence match the board's factory firmware: SPI1 SCK GP30, MOSI GP31, CS GP29, DC GP28, RST GP10, backlight PWM
on GP23. The panel is a 76x284 window inside the controller's 240x320 RAM, at
column 82 / row 18 in portrait. The driver runs it in landscape (284x76).

Framebuffer-backed RGB565 (43 KB). ST7789 wants big-endian pixels and
framebuf stores little-endian, so colours go through color565(), which
pre-swaps the bytes. show() pushes the whole frame; show_window() pushes a
column span, which is what the clock uses for a tick.
"""
import framebuf
from machine import Pin, PWM, SPI
from time import sleep_ms

WIDTH = 284
HEIGHT = 76
# Landscape RAM offsets (portrait x=82, y=18 swap under MV).
X_OFFSET = 18
Y_OFFSET = 82
MADCTL = 0x60          # MV | MX: landscape, USB on the right, text upright


def color565(r, g, b):
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c & 0xFF) << 8) | (c >> 8)


_INIT = (
    (0x11, None, 120),                      # sleep out
    (0x36, bytes([MADCTL]), 0),
    (0x3A, b"\x05", 0),                     # RGB565
    (0xB2, b"\x0c\x0c\x00\x33\x33", 0),     # porch
    (0xB0, b"\x00\xe0", 0),                 # RAM control
    (0xB7, b"\x45", 0),                     # gate control
    (0xBB, b"\x1d", 0),                     # VCOM
    (0xC0, b"\x2c", 0),
    (0xC2, b"\x01", 0),
    (0xC3, b"\x19", 0),
    (0xC4, b"\x20", 0),
    (0xC6, b"\x0f", 0),                     # frame rate
    (0xD0, b"\xa4\xa1", 0),                 # power control
    (0xD6, b"\xa1", 0),
    (0xE0, b"\xd0\x10\x21\x14\x15\x2d\x41\x44\x4f\x28\x0e\x0c\x1d\x1f", 0),
    (0xE1, b"\xd0\x0f\x1b\x0d\x0d\x26\x42\x54\x50\x3e\x1a\x18\x22\x25", 0),
    (0x20, None, 0),                        # inversion off: 0x21 inverts this panel
    (0x29, None, 20),                       # display on
)


class ST7789(framebuf.FrameBuffer):
    def __init__(self, spi_id=1, sck=30, mosi=31, cs=29, dc=28, rst=10, bl=23,
                 baudrate=31_250_000):
        self.cs = Pin(cs, Pin.OUT, value=1)
        self.dc = Pin(dc, Pin.OUT, value=0)
        self.rst = Pin(rst, Pin.OUT, value=1)
        self.bl = PWM(Pin(bl), freq=1000, duty_u16=0)
        self.spi = SPI(spi_id, baudrate=baudrate, polarity=0, phase=0,
                       sck=Pin(sck), mosi=Pin(mosi), miso=None)
        self.buffer = bytearray(WIDTH * HEIGHT * 2)
        super().__init__(self.buffer, WIDTH, HEIGHT, framebuf.RGB565)
        self.width = WIDTH
        self.height = HEIGHT
        self.reset()
        for cmd, data, delay in _INIT:
            self.write_cmd(cmd)
            if data:
                self.write_data(data)
            if delay:
                sleep_ms(delay)
        self.fill(0)
        self.show()
        self.contrast(0x80)

    def reset(self):
        self.rst(1)
        sleep_ms(10)
        self.rst(0)
        sleep_ms(10)
        self.rst(1)
        sleep_ms(120)

    def write_cmd(self, cmd):
        self.dc(0)
        self.cs(0)
        self.spi.write(bytes([cmd]))
        self.cs(1)

    def write_data(self, buf):
        self.dc(1)
        self.cs(0)
        self.spi.write(buf)
        self.cs(1)

    def _window(self, x0, y0, x1, y1):
        x0 += X_OFFSET
        x1 += X_OFFSET
        y0 += Y_OFFSET
        y1 += Y_OFFSET
        self.write_cmd(0x2A)
        self.write_data(bytes([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF]))
        self.write_cmd(0x2B)
        self.write_data(bytes([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF]))
        self.write_cmd(0x2C)

    def contrast(self, level):
        """0..255 backlight, kept as 'contrast' to match the OLED driver."""
        level &= 0xFF
        self.bl.duty_u16(level * 257)

    def poweroff(self):
        self.write_cmd(0x28)
        self.bl.duty_u16(0)

    def poweron(self):
        self.write_cmd(0x29)

    def show(self):
        self._window(0, 0, WIDTH - 1, HEIGHT - 1)
        self.write_data(self.buffer)

    def show_window(self, x0, x1, y0=0, y1=HEIGHT - 1):
        """Push columns x0..x1 inclusive over rows y0..y1."""
        if x0 < 0:
            x0 = 0
        if x1 >= WIDTH:
            x1 = WIDTH - 1
        if x1 < x0:
            return
        self._window(x0, y0, x1, y1)
        mv = memoryview(self.buffer)
        self.dc(1)
        self.cs(0)
        for y in range(y0, y1 + 1):
            s = (y * WIDTH + x0) * 2
            self.spi.write(mv[s:s + (x1 - x0 + 1) * 2])
        self.cs(1)
