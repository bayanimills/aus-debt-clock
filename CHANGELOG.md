# Changelog

## 0.2.0 (2026-10-31)

- Support for the Spotpear RP2350B 2.25inch LCD board (ST7789P3, 284x76), selected with
  `BOARD` in `firmware/config.py`.
- Odometer roll for readable digits and wheel motion blur for fast ones, 50 frames a second.
- USB refresh for boards without a radio: `tools/deploy.py --refresh` copies the baseline and
  stamps the time.
- The newest of the synced and bundled baselines wins at boot; state is saved at boot and
  every minute.

## 0.1.0 (2026-09-14)

- Pico 2 W + Waveshare Pico-OLED-2.23 debt clock: SSD1305 driver, hand-drawn 7x20 digits.
- Model anchored on AOFM's weekly face-value print, accruing at the Budget gross-debt path.
- Integer micro-dollar arithmetic throughout (RP2 floats are 32-bit).
- Daily WiFi sync with the RTC set from the HTTP Date header; weekly baseline refresh script.
