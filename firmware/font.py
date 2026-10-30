"""Hand-drawn 7x20 digits with 2 px strokes for the number row, plus a 2 px
comma and a 7 px dollar sign. Variable advance: "$1,002,841,620,000" is
7 + 13*7 + 4*2 glyph pixels + 17 gaps = 123 px, so it fits the 128 px panel.

Glyphs are pre-rendered into FrameBuffers once (MONO_HLSB, one byte per row)
so a redraw is one blit per character.
"""
import framebuf

GAP = 1
HEIGHT = 20

_ART = {
    "0": (
        ".XXXXX.",
        "XXXXXXX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XXXXXXX",
        ".XXXXX.",
    ),
    "1": (
        "...XX..",
        "..XXX..",
        ".XXXX..",
        "XX.XX..",
        "...XX..",
        "...XX..",
        "...XX..",
        "...XX..",
        "...XX..",
        "...XX..",
        "...XX..",
        "...XX..",
        "...XX..",
        "...XX..",
        "...XX..",
        "...XX..",
        "...XX..",
        "...XX..",
        "...XX..",
        "...XX..",
    ),
    "2": (
        ".XXXXX.",
        "XXXXXXX",
        "XX...XX",
        ".....XX",
        ".....XX",
        ".....XX",
        ".....XX",
        "....XX.",
        "....XX.",
        "...XX..",
        "...XX..",
        "..XX...",
        "..XX...",
        ".XX....",
        ".XX....",
        "XX.....",
        "XX.....",
        "XX.....",
        "XXXXXXX",
        "XXXXXXX",
    ),
    "3": (
        ".XXXXX.",
        "XXXXXXX",
        "XX...XX",
        ".....XX",
        ".....XX",
        ".....XX",
        ".....XX",
        "....XX.",
        "..XXXX.",
        "..XXXX.",
        "....XX.",
        ".....XX",
        ".....XX",
        ".....XX",
        ".....XX",
        ".....XX",
        ".....XX",
        "XX...XX",
        "XXXXXXX",
        ".XXXXX.",
    ),
    "4": (
        "....XX.",
        "...XXX.",
        "...XXX.",
        "..XXXX.",
        "..XXXX.",
        ".XX.XX.",
        ".XX.XX.",
        "XX..XX.",
        "XX..XX.",
        "XX..XX.",
        "XX..XX.",
        "XXXXXXX",
        "XXXXXXX",
        "....XX.",
        "....XX.",
        "....XX.",
        "....XX.",
        "....XX.",
        "....XX.",
        "....XX.",
    ),
    "5": (
        "XXXXXXX",
        "XXXXXXX",
        "XX.....",
        "XX.....",
        "XX.....",
        "XX.....",
        "XX.....",
        "XXXXXX.",
        "XXXXXXX",
        ".....XX",
        ".....XX",
        ".....XX",
        ".....XX",
        ".....XX",
        ".....XX",
        ".....XX",
        ".....XX",
        "XX...XX",
        "XXXXXXX",
        ".XXXXX.",
    ),
    "6": (
        ".XXXXX.",
        "XXXXXXX",
        "XX...XX",
        "XX.....",
        "XX.....",
        "XX.....",
        "XX.....",
        "XXXXXX.",
        "XXXXXXX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XXXXXXX",
        ".XXXXX.",
    ),
    "7": (
        "XXXXXXX",
        "XXXXXXX",
        ".....XX",
        ".....XX",
        ".....XX",
        "....XX.",
        "....XX.",
        "....XX.",
        "...XX..",
        "...XX..",
        "...XX..",
        "..XX...",
        "..XX...",
        "..XX...",
        "..XX...",
        "..XX...",
        "..XX...",
        "..XX...",
        "..XX...",
        "..XX...",
    ),
    "8": (
        ".XXXXX.",
        "XXXXXXX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        ".XXXXX.",
        ".XXXXX.",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XXXXXXX",
        ".XXXXX.",
    ),
    "9": (
        ".XXXXX.",
        "XXXXXXX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XX...XX",
        "XXXXXXX",
        ".XXXXXX",
        ".....XX",
        ".....XX",
        ".....XX",
        ".....XX",
        ".....XX",
        "XX...XX",
        "XXXXXXX",
        ".XXXXX.",
    ),
    "$": (
        "...X...",
        ".XXXXX.",
        "XXXXXXX",
        "XX.X.XX",
        "XX.X...",
        "XX.X...",
        "XX.X...",
        "XXXX...",
        ".XXXX..",
        "..XXX..",
        "..XXX..",
        "..XXXX.",
        "...XXXX",
        "...X.XX",
        "...X.XX",
        "...X.XX",
        "XX.X.XX",
        "XXXXXXX",
        ".XXXXX.",
        "...X...",
    ),
    ",": (
        "..", "..", "..", "..", "..", "..", "..", "..", "..", "..",
        "..", "..", "..", "..", "..", "..", "XX", "XX", ".X", "X.",
    ),
    " ": ("...",) * 20,
    "?": (
        ".XXXXX.",
        "XXXXXXX",
        "XX...XX",
        ".....XX",
        ".....XX",
        "....XX.",
        "...XX..",
        "...XX..",
        "...XX..",
        "...XX..",
        "...XX..",
        ".......",
        ".......",
        "...XX..",
        "...XX..",
        ".......",
        ".......",
        ".......",
        ".......",
        ".......",
    ),
}

_cache = {}
_scale = 1
_fg = None      # None: 1-bit glyphs for the mono OLED; else RGB565 colour
_bg = 0


def configure(scale=1, fg=None, bg=0):
    """Scale glyphs by an integer factor and, with fg set, pre-render them as
    RGB565 in fg on bg (colours already byte-swapped by the display driver)."""
    global _scale, _fg, _bg
    _scale, _fg, _bg = scale, fg, bg
    _cache.clear()


def _glyph(ch, fg=None):
    if fg is None:
        fg = _fg
    g = _cache.get((ch, fg))
    if g is None:
        art = _ART.get(ch) or _ART["?"]
        w = len(art[0])
        if fg is None and _scale == 1:
            buf = bytearray(HEIGHT)
            for i, row in enumerate(art):
                b = 0
                for j, px in enumerate(row):
                    if px == "X":
                        b |= 0x80 >> j
                buf[i] = b
            g = (w, framebuf.FrameBuffer(buf, w, HEIGHT, framebuf.MONO_HLSB))
        else:
            k = _scale
            sw, sh = w * k, HEIGHT * k
            fb = framebuf.FrameBuffer(bytearray(sw * sh * 2), sw, sh, framebuf.RGB565)
            fb.fill(_bg)
            for i, row in enumerate(art):
                for j, px in enumerate(row):
                    if px == "X":
                        fb.fill_rect(j * k, i * k, k, k, fg)
            g = (sw, fb)
        _cache[(ch, fg)] = g
    return g


def height():
    return HEIGHT * _scale


def advance(ch):
    return _glyph(ch)[0] + GAP * _scale


def width(s):
    return sum(advance(ch) for ch in s) - GAP * _scale if s else 0


def x_of(s, i):
    """Pixel offset of character i within s."""
    return sum(advance(ch) for ch in s[:i])


def draw(fb, s, x, y, color=1, fg=None):
    """Draw s at (x, y). Clears each cell first so overdraw is safe. fg picks
    a colour other than the configured one (colour glyphs only)."""
    h = HEIGHT * _scale
    gap = GAP * _scale
    for ch in s:
        w, g = _glyph(ch, fg)
        fb.fill_rect(x, y, w + gap, h, _bg)
        if color:
            fb.blit(g, x, y)
        x += w + gap
    return x
