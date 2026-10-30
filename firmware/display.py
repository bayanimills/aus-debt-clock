"""Open the display for config.BOARD and set the font up to match it.

Both drivers are framebuffers with show(), show_window(x0, x1) and contrast(),
so main.py does not care which panel it is driving.
"""
import config
import font


def open_display():
    if config.BOARD == "rp2350b_lcd":
        from st7789 import ST7789, color565
        d = ST7789(baudrate=config.LCD_SPI_BAUD)
        font.configure(config.LCD_SCALE, color565(*config.LCD_FG), 0)
        d.ink = color565(*config.LCD_FG)
        d.dim = color565(*config.LCD_DIM)
    else:
        from ssd1305 import SSD1305
        d = SSD1305(baudrate=config.SPI_BAUD)
        font.configure()
        d.ink = 1
    d.contrast(config.CONTRAST)
    return d
