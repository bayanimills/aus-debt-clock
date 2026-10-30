"""SSD1305 128x32 SPI driver for the Waveshare Pico-OLED-2.23.

Framebuffer-backed (MONO_VLSB). The SSD1305 has 132 columns of GDDRAM; the
128-wide panel sits at column offset 4, hence the 0x04 low-column command on
every page write. show() pushes the whole frame (512 bytes); show_window()
pushes only a column span, which is what the clock uses so a tick that
changes three digits does not rewrite the whole panel.
"""
import framebuf
from machine import Pin, SPI
from time import sleep_ms

WIDTH = 128
HEIGHT = 32
PAGES = HEIGHT // 8
COL_OFFSET = 4


class SSD1305(framebuf.FrameBuffer):
    def __init__(self, spi_id=1, sck=10, mosi=11, cs=9, dc=8, rst=12, baudrate=10_000_000):
        self.cs = Pin(cs, Pin.OUT, value=1)
        self.dc = Pin(dc, Pin.OUT, value=0)
        self.rst = Pin(rst, Pin.OUT, value=1)
        # miso=None matters: SPI1's default MISO is GP12, the panel's RST line.
        # Without it the SPI init re-muxes GP12 as an input and the panel
        # sits in reset while every write looks successful.
        self.spi = SPI(spi_id, baudrate=baudrate, polarity=0, phase=0,
                       sck=Pin(sck), mosi=Pin(mosi), miso=None)
        self.buffer = bytearray(WIDTH * PAGES)
        super().__init__(self.buffer, WIDTH, HEIGHT, framebuf.MONO_VLSB)
        self.width = WIDTH
        self.height = HEIGHT
        self.reset()
        self.init_display()

    def reset(self):
        self.rst(1)
        sleep_ms(10)
        self.rst(0)
        sleep_ms(10)
        self.rst(1)
        sleep_ms(10)

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

    def init_display(self):
        for c in (
            0xAE,        # display off
            0x04, 0x10,  # column address low / high nibble
            0x40,        # display start line 0
            0x81, 0x80,  # contrast
            0xA1,        # segment remap (column 127 -> SEG0)
            0xA6,        # normal (not inverted)
            0xA8, 0x1F,  # multiplex ratio 1/32
            0xC8,        # COM scan direction remapped
            0xD3, 0x00,  # display offset
            0xD5, 0xF0,  # clock divide / oscillator
            0xD8, 0x05,  # area colour mode off, low power
            0xD9, 0xC2,  # pre-charge period
            0xDA, 0x12,  # COM pins hardware config
            0xDB, 0x08,  # VCOMH deselect level
        ):
            self.write_cmd(c)
        self.fill(0)
        self.show()
        self.write_cmd(0xAF)  # display on

    def poweroff(self):
        self.write_cmd(0xAE)

    def poweron(self):
        self.write_cmd(0xAF)

    def contrast(self, level):
        self.write_cmd(0x81)
        self.write_cmd(level & 0xFF)

    def invert(self, on):
        self.write_cmd(0xA7 if on else 0xA6)

    def show(self):
        self.show_window(0, WIDTH - 1)

    def show_window(self, x0, x1, y0=0, y1=HEIGHT - 1):
        """Push columns x0..x1 inclusive for every page. y0/y1 are accepted for
        parity with the LCD driver; a page write is 8 rows anyway."""
        if x0 < 0:
            x0 = 0
        if x1 >= WIDTH:
            x1 = WIDTH - 1
        if x1 < x0:
            return
        col = x0 + COL_OFFSET
        lo = 0x00 | (col & 0x0F)
        hi = 0x10 | (col >> 4)
        n = x1 - x0 + 1
        mv = memoryview(self.buffer)
        for page in range(PAGES):
            self.write_cmd(0xB0 | page)
            self.write_cmd(lo)
            self.write_cmd(hi)
            start = page * WIDTH + x0
            self.write_data(mv[start:start + n])
