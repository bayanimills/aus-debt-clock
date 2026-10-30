# Hardware notes

## `rp2350b_lcd`: Spotpear RP2350B 2.25inch LCD

RP2350B (QFN80, 48 GPIO), 16 MB flash, no radio, with a 2.25in 76x284 IPS LCD (panel
ZJY225KP-PG01, ST7789P3 driver), a QMI8658 IMU, a microSD slot and a WS2812 RGB LED. The
vendor's demo code and pinout are at
[Spotpear/RP2350B-2.25inch-LCD](https://github.com/Spotpear/RP2350B-2.25inch-LCD). The board
ships with that demo, an SD-card slideshow with an IMU viewer fallback; the pins and LCD init
used here were checked against it on the bench. Back up the factory image with
`picotool save -a` before flashing if you want to return to it.

| Function | Pins |
|---|---|
| LCD, ST7789P3 on SPI1 | SCK GP30, MOSI GP31, CS GP29, DC GP28, RST GP10 |
| LCD backlight | PWM on GP23 |
| IMU, QMI8658 at 0x6B on I2C0 | SDA GP36, SCL GP37, INT1 GP39, INT2 GP38 |
| microSD on SPI0 | MISO GP32, CS GP33, SCK GP34, MOSI GP35 |
| WS2812 RGB LED | GP25 |
| UART0 | TX GP0, RX GP1 |

LCD notes:

- The 76x284 panel is a window in the controller's 240x320 RAM, at column 82 / row 18 in
  portrait. The driver runs it landscape (MADCTL 0x60), offsets 18 / 82, readable with the
  USB port on the right.
- Display inversion must be **off** (0x20). With 0x21, as in many ST7789 examples, every
  colour shows as its complement.
- SPI runs at 31.25 MHz; a full frame takes 17.5 ms, a 14x40 digit cell about 2 ms.

No radio: the factory image has no wireless driver, and driving each unused GPIO high (as a
radio's power-enable would be) woke nothing on any other pin.

Getting to BOOTSEL: `picotool reboot -u -f`, a 1200-baud touch on the serial port, or hold
BOOT while plugging in. The last is the only one that works if the USB serial has hung.

## `pico2w_oled`: Pico 2 W + Pico-OLED-2.23

### Bill of materials (v1)

| Item | Note |
|---|---|
| Raspberry Pi Pico 2 W | RP2350 + CYW43439. Male headers soldered. |
| Waveshare Pico-OLED-2.23 | 128x32 SSD1305, SPI, plugs over the header. USB marker toward the Pico's USB end. |
| LiPo 3.7 V 500 to 1000 mAh | Single cell, JST-PH. |
| TP4056 charge module (with protection) | Or a Pico LiPo SHIM / Pico LiPo board with charging on board. |
| Schottky diode (if using TP4056 into VSYS) | Feed VSYS through a diode so USB and battery never back-feed each other, per the Pico datasheet. |
| Wrist strap mount | TBD: 3D print or an off-the-shelf watch case adapted. |

### Wiring

The OLED uses only these header pins:

| OLED | Pico | Function |
|---|---|---|
| VCC | VSYS | Power |
| GND | GND | |
| DIN | GP11 | SPI1 TX |
| CLK | GP10 | SPI1 SCK |
| CS | GP9 | Chip select, active low |
| DC | GP8 | Data/command |
| RST | GP12 | Reset, active low. Also SPI1's default MISO, hence `miso=None` in the driver. |

The board is SPI by default; a backside resistor selects I2C (SDA GP6, SCL GP7). Not used.

### Battery into VSYS

Pico datasheet section on powering: VSYS accepts 1.8 to 5.5 V. With a TP4056 output on
VSYS and USB also possible, put a Schottky diode from the battery output into VSYS so
USB's own diode and the battery path do not fight. A Pico LiPo SHIM does this for you
and adds a fuel gauge-free battery voltage read on VSYS/3.

Reading battery voltage on a Pico W/2 W: ADC3 (GP29) reads VSYS/3 but shares the pin
with the wireless SPI, so drive GP25 high before sampling and expect noise while the
radio is active. Not implemented in v1.

### Power budget

To be measured with a USB current meter or a shunt on the battery lead:

1. Radio off, panel mostly black, 4 ticks/s: baseline current.
2. Same with `config.LIGHTSLEEP = True`.
3. One sync burst: duration and average current.
4. Runtime from a full 500 mAh charge.
