"""Renders docs/images/icons.png: every Geography icon on the minimap's dark tone.
Pure Python, no dependencies.

    py tools/make_icons.py      # regenerate Media/*.tga first
    py tools/preview_icons.py

Rows: terrain, each terrain's zone tones (two rows), ground, water + wildness,
and last a strip at real size (16 px icons), enlarged 3x.
"""
import os
import struct
import zlib

ROOT = os.path.join(os.path.dirname(__file__), "..")
MEDIA = os.path.join(ROOT, "Media")
OUT = os.path.join(ROOT, "docs", "images", "icons.png")
BG = (0.15, 0.13, 0.10)
S, PAD = 96, 8

ROWS = [
    ["land_terrain_" + v for v in ("forest", "grassland", "hills", "mountains", "desert", "badlands", "swamp",
                                   "jungle", "tundra", "coast", "volcanic", "blighted", "underground", "city")],
    ["land_terrain_" + v for v in ("forest_dusk", "forest_pine", "forest_dead", "forest_violet", "grassland_gold",
                                   "hills_red", "hills_dry", "mountains_snow", "mountains_brown", "mountains_dark",
                                   "badlands_tan", "badlands_grey")],
    ["land_terrain_" + v for v in ("blighted_plague", "coast_grey", "city_iron", "city_horde", "city_crypt",
                                   "city_elven", "city_bluff")],
    ["land_ground_" + v for v in ("soil", "mud", "sand", "rock", "snow", "ash", "stone")],
    ["land_water_" + v for v in ("river", "lake", "sea", "marsh", "none")] + [None]
    + ["land_wild_" + v for v in ("settled", "frontier", "wild")],
]
MINI = ("land_terrain_grassland", "land_terrain_grassland_gold", "land_terrain_forest", "land_terrain_mountains_snow",
        "land_terrain_city", "land_ground_rock", "land_water_river", "land_wild_frontier")

_cache = {}


def load(name):
    if name not in _cache:
        d = open(os.path.join(MEDIA, name + ".tga"), "rb").read()
        n = struct.unpack("<H", d[12:14])[0]
        px = d[18:]
        img = [[None] * n for _ in range(n)]
        for row in range(n):
            for col in range(n):
                b, g, r, a = px[(row * n + col) * 4:(row * n + col) * 4 + 4]
                img[n - 1 - row][col] = (r / 255, g / 255, b / 255, a / 255)
        _cache[name] = (img, n)
    return _cache[name]


def sample_box(tex, x0, y0, x1, y1):
    """Average of the texels under a destination pixel (box filter, like a GPU mip)."""
    img, n = tex
    acc, cnt = [0.0, 0.0, 0.0, 0.0], 0
    for y in range(int(y0 * n), max(int(y0 * n) + 1, int(y1 * n))):
        for x in range(int(x0 * n), max(int(x0 * n) + 1, int(x1 * n))):
            if 0 <= x < n and 0 <= y < n:
                r, g, b, a = img[y][x]
                acc[0] += r * a; acc[1] += g * a; acc[2] += b * a; acc[3] += a
                cnt += 1
    if not cnt or acc[3] <= 0:
        return (0, 0, 0, 0)
    return (acc[0] / acc[3], acc[1] / acc[3], acc[2] / acc[3], acc[3] / cnt)


def paste(canvas, name, ox, oy, size, crop=0.0, round_=False):
    tex = load(name)
    k = 1.0 - 2 * crop
    for y in range(size):
        for x in range(size):
            if round_ and (x + .5 - size / 2) ** 2 + (y + .5 - size / 2) ** 2 > (size / 2) ** 2:
                continue
            p = sample_box(tex, crop + x / size * k, crop + y / size * k, crop + (x + 1) / size * k, crop + (y + 1) / size * k)
            if p[3] > 0:
                d = canvas[oy + y][ox + x]
                canvas[oy + y][ox + x] = tuple(p[i] * p[3] + d[i] * (1 - p[3]) for i in range(3))


def write_png(rows, path):
    h, w = len(rows), len(rows[0])
    raw = b"".join(b"\x00" + bytes(int(max(0, min(1, c)) * 255 + .5) for p in r for c in p) for r in rows)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main():
    cols = max(len(r) for r in ROWS)
    small, scale = 16, 3
    width = PAD + cols * (S + PAD)
    height = PAD + len(ROWS) * (S + PAD) + (small + PAD) * scale
    canvas = [[BG] * width for _ in range(height)]
    for ri, row in enumerate(ROWS):
        for ci, name in enumerate(row):
            if name:
                paste(canvas, name, PAD + ci * (S + PAD), PAD + ri * (S + PAD), S)
    # the same icons at the size the game draws them, enlarged: first as the minimap orb shows
    # the terrain (cut round, its square border cropped away), then square as in the tooltip
    mini = [[BG] * ((small + 4) * len(MINI)) for _ in range(small)]
    for i, name in enumerate(MINI):
        if name.startswith("land_terrain_"):
            paste(mini, name, i * (small + 4), 0, small, crop=0.09, round_=True)
        else:
            paste(mini, name, i * (small + 4), 0, small)
    top = PAD + len(ROWS) * (S + PAD)
    for y, r in enumerate(mini):
        for x, p in enumerate(r):
            for dy in range(scale):
                for dx in range(scale):
                    canvas[top + y * scale + dy][PAD + x * scale + dx] = p
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    write_png(canvas, OUT)
    print("wrote", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
