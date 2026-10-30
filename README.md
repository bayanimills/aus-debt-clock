# aus-debt-clock

A wearable Australian Government gross debt clock. It shows one number, the face value of
Commonwealth debt on issue, ticking up in real time from the official AOFM figure.

```
   $999,002,216,243
```

Nothing else is drawn. Sync state and the as-at date go to the console.

## How the number is made

There is no live feed for Commonwealth gross debt, so the device extrapolates:

    debt(t) = baseline + rate * (t - as_at)

| Term | Source | Cadence |
|---|---|---|
| `baseline` | AOFM home page, "Australian Government Securities on issue": face value of Treasury Bonds, Indexed Bonds and Notes. Fallback: the Data Hub "Executive Summary" XLSX (month end, dealt basis) | AOFM updates the print every Friday |
| `rate` | Budget Paper No. 1, Statement 3, Table 3.3: the gross-debt path for the current financial year, divided into seconds | Hand-updated at Budget (May) and MYEFO (December) in `data/budget.json` |

The rate follows the gross-debt path, not the underlying cash deficit, because the display
shows gross debt, which also carries off-budget financing. For 2026-27 the path is $982.0bn
to $1,051.0bn: $2,188 a second.

The model is smooth and linear by design. Real issuance is lumpy (tenders add debt, maturities
remove it in blocks), so the display drifts between prints and each new baseline re-anchors it.
In September 2026 the 0.50% 21 September 2026 Treasury Bond matured and the print fell below
$1 trillion; the clock follows the print, not the Budget's year-end figure.

The display never runs backwards within a run: if the extrapolation overshot, it ticks at a
quarter rate until the target catches up.

`tools/update_baseline.py` writes `data/baseline.json` from the weekly print. Devices read that
file (over WiFi, or copied over USB); they never parse AOFM pages themselves.

Other clocks will not agree, because every clock is an extrapolation from some anchor at some
rate. audebtclock.org anchors on the same weekly print but accrues about $4,373 a second
($138bn a year), close to AOFM's gross Treasury Bond issuance, which ignores the bonds that
mature during the year. The Budget's gross-debt path nets maturities out.

## Boards

`BOARD` in `firmware/config.py` picks the hardware. Pinouts and power notes are in
`hardware/README.md`.

| `BOARD` | Hardware | Display | Baseline |
|---|---|---|---|
| `rp2350b_lcd` | [Spotpear RP2350B 2.25inch LCD](https://github.com/Spotpear/RP2350B-2.25inch-LCD): RP2350B, 16 MB flash, no radio | ST7789P3, 284x76 colour | USB refresh |
| `pico2w_oled` | Raspberry Pi Pico 2 W + Waveshare Pico-OLED-2.23 | SSD1305, 128x32 mono | WiFi, daily |

Both run MicroPython 1.29: `WEACTSTUDIO_RP2350B_CORE` for the LCD board (there is no build of
its own; this RP2350B, 16 MB build fits it) and `RPI_PICO2_W` for the Pico.

## Display and motion

Digits are hand-drawn 7x20 pixel art with 2 px commas, so the full figure is 123 px wide. The
OLED draws them 1:1; the LCD draws them at 2x (14x40) in white.

On the LCD, digits are tiered by how often they change at the current rate:

- **Readable digits** (thousands and up, at most a few changes a second) roll up like odometer
  wheels. A roll eases out over 220 ms or half the digit's change interval, whichever is
  shorter. When a carry moves several places, each place to the left starts 40 ms later, so
  the carry ripples.
- **Fast digits** (ones, tens and hundreds, 22 to 2,188 changes a second) cannot be read at
  any frame rate. They are drawn as the wheel would photograph: the digit strip averaged in
  linear light over the distance it turns in a 10 ms exposure. The hundreds is a streaked
  digit racing upward, the tens a shimmer, the ones a steady blur.

It runs at 50 frames a second, pushing only the changed digit cells. `MOTION = False` gives
plain instant updates. The OLED updates instantly, 25 frames a second.

## Time and persistence

- With WiFi, the RTC is set from the HTTP `Date` header of the baseline fetch. Sync runs daily,
  retrying hourly, with the radio powered only inside a sync.
- Without WiFi, `tools/deploy.py --refresh` copies a new baseline and stamps the current UTC
  time into the device.
- The displayed value and time are saved to flash at boot and every minute. After a power loss
  the clock resumes from the last save and the time the device spent off is lost until the
  next sync or refresh. The clock is never set earlier than the baseline's as-at date.

## Use

```
pip install -r tools/requirements.txt

# once per board: hold BOOT while plugging in, copy the MicroPython UF2 to the drive
python tools/deploy.py COM9            # firmware + baseline + time, then reset
python tools/deploy.py COM9 --repl     # same, then watch the console

# keep the figure current
python tools/update_baseline.py        # fetch the latest AOFM print into data/baseline.json
python tools/deploy.py COM9 --refresh  # LCD board: copy it over with the time

python -m pytest tests                 # model and formatting
```

`firmware/secrets.py` (from `secrets.example.py`, git-ignored) holds the Pico's WiFi
credentials (and, for a private fork, a read token for `baseline.json`). It is never copied
to the LCD board.

## Firmware

| File | Role |
|---|---|
| `main.py` | Boot, cache, sync schedule, frame loop |
| `debtclock.py` | Model and clock arithmetic in integer micro-dollars, formatting. Unit-tested on CPython |
| `display.py` | Opens the display for `BOARD` and sets the font to match |
| `st7789.py` | LCD driver, RGB565 framebuffer with windowed pushes |
| `ssd1305.py` | OLED driver, mono framebuffer with column-window pushes |
| `font.py` | The 7x20 digits, scaled and coloured on demand |
| `motion.py` | LCD odometer roll and wheel motion blur |
| `net.py` | WiFi, baseline fetch, RTC set |
| `config.py` | Board, URLs, cadences, SPI speeds, colours, motion |
| `smoke.py` | OLED bench test |

Money and epoch maths are integers throughout: RP2 MicroPython floats are 32-bit and cannot
hold a trillion-dollar figure to the dollar.

## Open items

- `.github/workflows/baseline.yml` times out reaching aofm.gov.au from GitHub's runners, so the
  weekly print needs a run from elsewhere until that is fixed.
- Power: bench the current draw and decide on `LIGHTSLEEP` (off by default; it stops the USB
  REPL).
- Enclosure and strap.
- Update `data/budget.json` at MYEFO and each Budget.

## License

MIT. See `LICENSE`.

---
<sub><i>Vires in numeris.</i></sub>
