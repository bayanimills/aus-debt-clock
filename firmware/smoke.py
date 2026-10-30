# Smoke test: border, label, a wide number, then a partial-window rewrite.
from ssd1305 import SSD1305
from time import sleep_ms
o = SSD1305()
o.fill(0)
o.rect(0, 0, 128, 32, 1)
o.text("AUD GOVT DEBT", 2, 2, 1)
o.text("1002841620000", 2, 12, 1)
o.text("SSD1305 OK", 2, 22, 1)
o.show()
sleep_ms(1500)
# partial update: overwrite the right half of row 2 only
o.fill_rect(64, 12, 60, 8, 0)
o.text("PART", 66, 12, 1)
o.show_window(64, 123)
print("smoke drawn")
