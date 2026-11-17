"""Generates the art for ImmerseMe: Geography as 32-bit TGA files.

Pure Python 3, no dependencies. Re-run after tweaking:

    py tools/make_icons.py
    py tools/preview_icons.py      # docs/images/icons.png

Files (Media/):
  land_<facet>_<value>.tga             128x128 painted icons, one per value in Data.lua ns.Facets
  land_terrain_<terrain>_<tone>.tga    the same terrain in a zone's own colours (Data.lua ns.TerrainTones)
  icon.tga                   128x128 addon-list icon in the shared ImmerseMe frame

The canvas, shape helpers and suite_icon() are copied from ImmerseMe_Weather/tools/make_icons.py.
"""
import math
import os
import struct

OUT = os.path.join(os.path.dirname(__file__), "..", "Media")
N = 128          # layer size
K = N / 64.0     # shapes below are designed on a 64 grid and scaled by K
SS = 3           # supersampling for hard-edged shapes


def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def smoothstep(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


class Canvas:
    def __init__(self, size=N):
        self.n = size
        self.px = [[0.0, 0.0, 0.0, 0.0] for _ in range(size * size)]

    def _blend(self, px, py, c, a):
        if a <= 0:
            return
        d = self.px[py * self.n + px]
        da = d[3]
        oa = a + da * (1 - a)
        for i in range(3):
            d[i] = (c[i] * a + d[i] * da * (1 - a)) / oa
        d[3] = oa

    def _box(self, bbox, pad=1):
        x0, y0, x1, y1 = bbox
        return (max(0, int(x0) - pad), max(0, int(y0) - pad),
                min(self.n, int(x1) + pad + 1), min(self.n, int(y1) + pad + 1))

    def fill(self, shape, color, alpha=1.0):
        """Hard-edged shape: shape = (inside(x,y) -> bool, bbox). Supersampled."""
        inside, bbox = shape
        x0, y0, x1, y1 = self._box(bbox)
        st = 1.0 / SS
        for py in range(y0, y1):
            for px in range(x0, x1):
                hits = 0
                for sy in range(SS):
                    for sx in range(SS):
                        if inside(px + (sx + .5) * st, py + (sy + .5) * st):
                            hits += 1
                if hits:
                    c = color(px + .5, py + .5) if callable(color) else color
                    self._blend(px, py, c, alpha * hits / (SS * SS))

    def glow(self, sdf, bbox, color, alpha, soft):
        """Soft shape: sdf(x,y) = signed distance (negative inside); fades over `soft` px."""
        x0, y0, x1, y1 = self._box(bbox, int(soft) + 2)
        for py in range(y0, y1):
            for px in range(x0, x1):
                d = sdf(px + .5, py + .5)
                a = 1.0 if d <= 0 else 1.0 - smoothstep(0, soft, d)
                if a > 0.003:
                    c = color(px + .5, py + .5) if callable(color) else color
                    self._blend(px, py, c, alpha * a)

    def save(self, name):
        n = self.n
        data = bytearray(struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, n, n, 32, 8))
        for row in range(n - 1, -1, -1):  # bottom-left origin
            for col in range(n):
                r, g, b, a = self.px[row * n + col]
                data += bytes((b8(b), b8(g), b8(r), b8(a)))
        with open(os.path.join(OUT, name + ".tga"), "wb") as f:
            f.write(data)


def b8(v):
    return int(clamp(v) * 255 + 0.5)


# ---------------------------------------------------------------- shapes (64-grid coords, scaled by K)
def circle(cx, cy, r):
    cx, cy, r = cx * K, cy * K, r * K
    return (lambda x, y: (x - cx) ** 2 + (y - cy) ** 2 <= r * r), (cx - r, cy - r, cx + r, cy + r)


def circle_sdf(cx, cy, r):
    cx, cy, r = cx * K, cy * K, r * K
    return (lambda x, y: math.hypot(x - cx, y - cy) - r), (cx - r, cy - r, cx + r, cy + r)


def seg_dist(x, y, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = clamp(((x - ax) * dx + (y - ay) * dy) / ((dx * dx + dy * dy) or 1e-9))
    return math.hypot(x - ax - t * dx, y - ay - t * dy)


def capsule_sdf(ax, ay, bx, by, r):
    ax, ay, bx, by, r = ax * K, ay * K, bx * K, by * K, r * K
    return (lambda x, y: seg_dist(x, y, ax, ay, bx, by) - r), \
           (min(ax, bx) - r, min(ay, by) - r, max(ax, bx) + r, max(ay, by) + r)


def capsule(ax, ay, bx, by, r):
    f, bb = capsule_sdf(ax, ay, bx, by, r)
    return (lambda x, y: f(x, y) <= 0), bb


def polygon_px(pts):
    """pts already in pixel space."""
    def inside(x, y):
        c = False
        j = len(pts) - 1
        for i in range(len(pts)):
            xi, yi = pts[i]
            xj, yj = pts[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                c = not c
            j = i
        return c
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return inside, (min(xs), min(ys), max(xs), max(ys))


def polygon(pts):
    return polygon_px([(x * K, y * K) for x, y in pts])


def union_sdf(*shapes):
    fns = [s[0] for s in shapes]
    bb = (min(s[1][0] for s in shapes), min(s[1][1] for s in shapes),
          max(s[1][2] for s in shapes), max(s[1][3] for s in shapes))
    return (lambda x, y: min(f(x, y) for f in fns)), bb


def hard(sdf_shape, grow=0.0):
    f, bb = sdf_shape
    g = grow * K
    return (lambda x, y: f(x, y) <= g), (bb[0] - g, bb[1] - g, bb[2] + g, bb[3] + g)


def vgrad(top, bottom, y0, y1):
    y0, y1 = y0 * K, y1 * K
    return lambda x, y: mix(top, bottom, clamp((y - y0) / (y1 - y0)))


def rgrad(inner, outer, cx, cy, r):
    cx, cy, r = cx * K, cy * K, r * K
    return lambda x, y: mix(inner, outer, clamp(math.hypot(x - cx, y - cy) / r))


# ---------------------------------------------------------------- sky + stars

# Every ImmerseMe module shares this frame: a dark carved-stone square with a
# gold bevelled edge (like Blizzard's ability icons) holding a round sky
# medallion in a gold ring (like the minimap's day/night icon). Only the
# medallion's sky colours and the emblem inside it change per module.
# Copy suite_icon() into a new module's tools/ and give it its own emblem.

def rounded_rect_sdf(x0, y0, x1, y1, r):
    X0, Y0, X1, Y1, R = x0 * K, y0 * K, x1 * K, y1 * K, r * K
    cx, cy, hx, hy = (X0 + X1) / 2, (Y0 + Y1) / 2, (X1 - X0) / 2 - R, (Y1 - Y0) / 2 - R

    def f(x, y):
        dx, dy = abs(x - cx) - hx, abs(y - cy) - hy
        return math.hypot(max(dx, 0), max(dy, 0)) + min(max(dx, dy), 0) - R
    return f, (X0, Y0, X1, Y1)


def blit(dst, src, cx, cy, size):
    """Draws canvas `src` scaled to `size` (64 grid) centred at (cx, cy), bilinear."""
    n = src.n
    x0, y0, s = (cx - size / 2) * K, (cy - size / 2) * K, size * K
    for py in range(max(0, int(y0)), min(dst.n, int(y0 + s) + 1)):
        for px in range(max(0, int(x0)), min(dst.n, int(x0 + s) + 1)):
            u, v = (px + .5 - x0) / s * n - .5, (py + .5 - y0) / s * n - .5
            iu, iv = int(math.floor(u)), int(math.floor(v))
            fu, fv = u - iu, v - iv
            acc = [0.0, 0.0, 0.0, 0.0]
            for (ox, oy, w) in ((0, 0, (1 - fu) * (1 - fv)), (1, 0, fu * (1 - fv)), (0, 1, (1 - fu) * fv), (1, 1, fu * fv)):
                qx, qy = iu + ox, iv + oy
                if 0 <= qx < n and 0 <= qy < n:
                    r, g, b, a = src.px[qy * n + qx]
                    acc[0] += r * a * w; acc[1] += g * a * w; acc[2] += b * a * w; acc[3] += a * w
            if acc[3] > 0.003:
                dst._blend(px, py, (acc[0] / acc[3], acc[1] / acc[3], acc[2] / acc[3]), acc[3])


def suite_icon(name, sky_top, sky_bottom, emblem):
    c = Canvas()
    gold_light, gold_dark = (1.0, 0.86, 0.48), (0.55, 0.35, 0.12)
    # gold bevelled square
    c.fill(hard(rounded_rect_sdf(0.5, 0.5, 63.5, 63.5, 7)), (0.10, 0.06, 0.03))
    c.fill(hard(rounded_rect_sdf(1.6, 1.6, 62.4, 62.4, 6)),
           lambda x, y: mix(gold_light, gold_dark, clamp((x + y) / (2 * N))))
    c.fill(hard(rounded_rect_sdf(4.2, 4.2, 59.8, 59.8, 4)), (0.12, 0.08, 0.04))
    # carved stone, lit from the top-left
    c.fill(hard(rounded_rect_sdf(5.2, 5.2, 58.8, 58.8, 3.4)),
           rgrad((0.30, 0.24, 0.18), (0.10, 0.07, 0.05), 20, 18, 52))
    # sky medallion in a gold ring
    c.glow(*circle_sdf(32, 33, 24), (0.0, 0.0, 0.0), 0.5, 3 * K)          # drop shadow
    c.fill(circle(32, 32, 25.5), (0.12, 0.07, 0.02))
    c.fill(circle(32, 32, 24.4), lambda x, y: mix(gold_light, gold_dark, clamp((x * 0.4 + y) / (1.4 * N))))
    c.fill(circle(32, 32, 21.6), (0.10, 0.06, 0.02))
    c.fill(circle(32, 32, 20.8), vgrad(sky_top, sky_bottom, 11, 53))
    inner = Canvas()                                                    # emblem, clipped to the medallion
    emblem(inner)
    clip = circle(32, 32, 20.8)[0]
    for i, p in enumerate(inner.px):
        if p[3] and not clip((i % N) + .5, (i // N) + .5):
            p[3] = 0.0
    blit(c, inner, 32, 32, 64)
    c.glow(*circle_sdf(26, 22, 6), (1.0, 1.0, 1.0), 0.10, 10 * K)     # glassy highlight
    c.save(name)



# ================================================================ Geography icons (128x128)
# Small painted scenes in the manner of the game's own ability and item icons: a square
# picture that fills its frame, lit from the upper left, with deep shadows, a rough painted
# surface and a thin dark metal border. Each icon is built in three steps:
#   backdrop()  the sky, the haze on the horizon and the ground the subject stands on
#   t_* / g_* / w_* / wl_*   the subject itself, shapes with a thin dark contour
#   finish()    grading, brushwork, vignette and the border
#
# Everything below is drawn in 64-grid coordinates on an Icon canvas, which maps
# them onto its own pixel size.

INK = (0.05, 0.035, 0.03)
OUTLINE = 2.2
CONTOUR = 0.5        # how much of each drawing's outline width is kept: a painted contour, not a cartoon line
ICON = 128

GREEN = (0.42, 0.68, 0.26)
GREEN_DARK = (0.18, 0.38, 0.12)
BROWN = (0.55, 0.36, 0.18)
BROWN_DARK = (0.32, 0.20, 0.09)
GREY = (0.66, 0.66, 0.68)
GREY_DARK = (0.36, 0.36, 0.40)
SNOW = (0.94, 0.97, 1.0)
SNOW_LO = (0.70, 0.80, 0.94)
BLUE = (0.36, 0.64, 0.95)
BLUE_HI = (0.56, 0.80, 1.0)
BLUE_DARK = (0.14, 0.32, 0.62)
FOAM = (0.92, 0.97, 1.0)
SAND = (0.93, 0.78, 0.48)
SAND_HI = (0.99, 0.90, 0.64)
SAND_DARK = (0.72, 0.52, 0.26)
RED = (0.82, 0.40, 0.20)
RED_DARK = (0.50, 0.20, 0.10)
LAVA = (1.0, 0.55, 0.12)
LAVA_HI = (1.0, 0.88, 0.40)
ASH = (0.45, 0.43, 0.42)
FEL = (0.55, 0.85, 0.30)
DARK = (0.08, 0.05, 0.03)


class Icon(Canvas):
    """A canvas drawn in 64-grid coordinates whatever its pixel size."""

    def __init__(self, size=ICON):
        Canvas.__init__(self, size)
        self.s = size / 64.0

    def fill(self, shape, color, alpha=1.0):
        inside, bbox = shape
        s = self.s
        x0, y0, x1, y1 = self._box(tuple(v * s for v in bbox))
        st = 1.0 / SS
        for py in range(y0, y1):
            for px in range(x0, x1):
                hits = 0
                for sy in range(SS):
                    for sx in range(SS):
                        if inside((px + (sx + .5) * st) / s, (py + (sy + .5) * st) / s):
                            hits += 1
                if hits:
                    c = color((px + .5) / s, (py + .5) / s) if callable(color) else color
                    self._blend(px, py, c, alpha * hits / (SS * SS))

    def glow(self, sdf, bbox, color, alpha, soft):
        s = self.s
        x0, y0, x1, y1 = self._box(tuple(v * s for v in bbox), int(soft * s) + 2)
        for py in range(y0, y1):
            for px in range(x0, x1):
                d = sdf((px + .5) / s, (py + .5) / s)
                a = 1.0 if d <= 0 else 1.0 - smoothstep(0, soft, d)
                if a > 0.003:
                    c = color((px + .5) / s, (py + .5) / s) if callable(color) else color
                    self._blend(px, py, c, alpha * a)


def small_canvas():
    global K
    K = 1.0
    return Icon()


def lit(light, dark, x0=8, y0=8, x1=56, y1=56):
    """Diagonal light-to-dark gradient over a box (top-left lit)."""
    return lambda x, y: mix(light, dark, clamp(((x - x0) + (y - y0)) / ((x1 - x0) + (y1 - y0))))


def shade(col, f):
    return tuple(clamp(v * f) for v in col)


def ink(c, shapes, outline=OUTLINE):
    """shapes = [(shape_factory(dx, dy) -> (inside, bbox), color)].
    Paints the shapes, with one ink outline around their joint silhouette."""
    layer = Icon(c.n)
    for factory, color in shapes:
        layer.fill(factory(0, 0), color)
    n = c.n
    al = [p[3] for p in layer.px]
    drawn = [i for i, a in enumerate(al) if a > 0]
    if not drawn:
        return
    r = max(1.0, outline * CONTOUR * c.s)
    R = int(math.ceil(r))
    offs = sorted(((dx, dy) for dy in range(-R, R + 1) for dx in range(-R, R + 1) if dx * dx + dy * dy <= r * r),
                  key=lambda o: o[0] * o[0] + o[1] * o[1])
    xs, ys = [i % n for i in drawn], [i // n for i in drawn]
    for py in range(max(0, min(ys) - R), min(n, max(ys) + R + 1)):
        for px in range(max(0, min(xs) - R), min(n, max(xs) + R + 1)):
            m = 0.0
            for dx, dy in offs:
                qx, qy = px + dx, py + dy
                if 0 <= qx < n and 0 <= qy < n:
                    a = al[qy * n + qx]
                    if a > m:
                        m = a
                        if m >= 1.0:
                            break
            if m > 0:
                c._blend(px, py, INK, 0.85 * m)
    for i in drawn:
        p = layer.px[i]
        c._blend(i % n, i // n, (p[0], p[1], p[2]), p[3])


# ---- shape factories for ink(): each returns f(dx, dy) -> (inside, bbox)
def poly(pts):
    return lambda dx, dy: polygon([(x + dx, y + dy) for x, y in pts])


def circ(cx, cy, r):
    return lambda dx, dy: circle(cx + dx, cy + dy, r)


def caps(ax, ay, bx, by, r):
    return lambda dx, dy: capsule(ax + dx, ay + dy, bx + dx, by + dy, r)


def oval0(cx, cy, rx, ry):
    return (lambda x, y: ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1), (cx - rx, cy - ry, cx + rx, cy + ry)


def oval(cx, cy, rx, ry):
    return lambda dx, dy: oval0(cx + dx, cy + dy, rx, ry)


def clipped(factory, keep):
    """Limit a shape to where keep(x, y) is true (e.g. above a ground line)."""
    def f(dx, dy):
        inside, bb = factory(dx, dy)
        return (lambda x, y: inside(x, y) and keep(x, y)), bb
    return f


def rect(x0, y0, x1, y1):
    return poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def rect0(*a):
    return rect(*a)(0, 0)


def caps0(*a):
    return caps(*a)(0, 0)


def wave_band(y, amp, period, half, x0=6, x1=58, phase=0.0):
    def f(dx, dy):
        def inside(x, yy):
            if x < x0 + dx or x > x1 + dx:
                return False
            mid = y + dy + amp * math.sin((x - dx) / period * 2 * math.pi + phase)
            return abs(yy - mid) <= half
        return inside, (x0 + dx, y + dy - amp - half, x1 + dx, y + dy + amp + half)
    return f


# ---- details painted on top of the inked silhouette (no outline of their own)
def paint(c, shape, color, alpha=1.0, clip=None):
    inside, bb = shape
    if clip:
        keep, f = clip[0], inside
        inside = lambda x, y: f(x, y) and keep(x, y)
        bb = bb or clip[1]
    c.fill((inside, bb or (0, 0, 64, 64)), color, alpha)


def stroke(c, pts, r, color, alpha=1.0, clip=None):
    """A polyline of thickness 2r, painted as one shape (joints don't double up)."""
    segs = [capsule(a[0], a[1], b[0], b[1], r) for a, b in zip(pts, pts[1:])]
    fns = [s[0] for s in segs]
    bb = (min(s[1][0] for s in segs), min(s[1][1] for s in segs), max(s[1][2] for s in segs), max(s[1][3] for s in segs))
    paint(c, ((lambda x, y: any(f(x, y) for f in fns)), bb), color, alpha, clip)


def crescent(cx, cy, r, ox=1.6, oy=2.4):
    """The lit rim of a round form: the circle minus the same circle pushed down-right."""
    a, bb = circle(cx, cy, r)
    b, _ = circle(cx + ox, cy + oy, r)
    return (lambda x, y: a(x, y) and not b(x, y)), bb


def dot(c, x, y, r, color, rim=None):
    if rim:
        c.fill(circle(x, y, r + 0.7), rim, 0.9)
    c.fill(circle(x, y, r), color)


def pine(cx, base, h, w, color):
    trunk = (rect(cx - w * 0.16, base - 4, cx + w * 0.16, base + 3), BROWN)
    tiers = []
    for i in range(3):
        top = base - h + i * h * 0.26
        bot = base - h * 0.42 + i * h * 0.21
        ww = w * (0.55 + i * 0.22)
        tiers.append((poly([(cx, top), (cx + ww, bot), (cx - ww, bot)]), color))
    return [trunk] + tiers


def pine_detail(c, cx, base, h, w, dark, light=None, snow=None):
    """Shade the right half of each tier, catch the light on the left edge, and (snow) cap them."""
    for i in range(3):
        top = base - h + i * h * 0.26
        bot = base - h * 0.42 + i * h * 0.21
        ww = w * (0.55 + i * 0.22)
        c.fill(polygon([(cx, top), (cx + ww, bot), (cx + ww * 0.15, bot)]), dark, 0.45)
        if light:
            c.fill(polygon([(cx, top + 1.5), (cx - ww * 0.55, bot - 1.2), (cx - ww * 0.80, bot - 1.2)]), light, 0.45)
        if snow:
            c.fill(polygon([(cx, top), (cx + ww * 0.42, top + (bot - top) * 0.55), (cx + ww * 0.12, top + (bot - top) * 0.42),
                            (cx - ww * 0.14, top + (bot - top) * 0.62), (cx - ww * 0.46, top + (bot - top) * 0.50)]), snow)


# ---------------------------------------------------------------- the painted frame
def _hash(ix, iy, seed):
    v = math.sin(ix * 127.1 + iy * 311.7 + seed * 74.7) * 43758.5453
    return v - math.floor(v)


def noise(x, y, seed=0):
    """Smooth value noise in 0..1, one new value per unit."""
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _hash(ix, iy, seed), _hash(ix + 1, iy, seed)
    cc, d = _hash(ix, iy + 1, seed), _hash(ix + 1, iy + 1, seed)
    return a + (b - a) * fx + (cc - a) * fy + (a - b - cc + d) * fx * fy


def brush(x, y, seed=0):
    """Brushwork: streaks laid diagonally, broad strokes with finer ones over them. -1..1."""
    u, v = x * 0.90 + y * 0.42, y * 0.90 - x * 0.42
    return (noise(u / 9.0, v / 3.2, seed) - 0.5) * 1.3 + (noise(u / 3.6, v / 1.4, seed + 7) - 0.5) * 0.7


def backdrop(c, sky, haze, floor=None, horizon=51.0, seed=0):
    """The scene behind the subject: sky deepening upwards, haze on the horizon, light pooling in
    the upper left, and (floor) the ground it stands on, darkening towards the viewer."""
    n, s = c.n, c.s
    for py in range(n):
        y = (py + .5) / s
        for px in range(n):
            x = (px + .5) / s
            col = mix(sky, haze, smoothstep(0.0, 1.0, y / horizon) ** 1.3)
            cloud = noise(x / 13.0 + 3.1, y / 5.0 + seed, seed + 3)               # long soft streaks of cloud
            col = mix(col, haze, 0.30 * smoothstep(0.52, 0.85, cloud) * smoothstep(horizon, horizon - 22, y))
            glow = math.exp(-((x - 15) ** 2 + (y - 13) ** 2) / (2 * 20.0 ** 2))
            col = mix(col, mix(haze, (1.0, 1.0, 0.94), 0.5), 0.28 * glow)
            if floor:
                f = smoothstep(horizon - 2.5, horizon + 3.5, y + 1.6 * math.sin(x * 0.21 + seed))
                col = mix(col, mix(floor, shade(floor, 0.55), smoothstep(horizon, 64, y)), f)
            c.px[py * n + px] = [col[0], col[1], col[2], 1.0]


FRAME_DARK, FRAME_LIGHT = (0.035, 0.03, 0.03), (0.50, 0.47, 0.42)


def finish(c, seed=0):
    """Grade the picture like the game's icons (rich, dark in the shadows, lit from the upper
    left), roughen it with brushwork, close it in with a vignette and set the border round it."""
    n, s = c.n, c.s
    for py in range(n):
        y = (py + .5) / s
        for px in range(n):
            x = (px + .5) / s
            p = c.px[py * n + px]
            r, g, b = p[0], p[1], p[2]
            lum = r * 0.30 + g * 0.59 + b * 0.11
            k = 1.0 + 0.11 * brush(x, y, seed)                                    # the painted surface
            k *= 1.10 - 0.30 * clamp((x + y) / 128.0)                             # light falls from the upper left
            edge = max(abs(x - 32), abs(y - 32)) / 32.0
            k *= 1.0 - 0.42 * smoothstep(0.62, 1.0, edge)                         # vignette
            col = []
            for v in (r, g, b):
                v = lum + (v - lum) * 1.12                                        # a little richer
                v = 0.5 + (v - 0.5) * 1.16                                        # a little harder
                v = clamp(v * k * 0.94)
                col.append(v * v * (3 - 2 * v) * 0.35 + v * 0.65)                 # deepen the shadows
            d = min(x, y, 64 - x, 64 - y)                                         # the border
            if d < 3.3:
                lit_side = (x < 3.3 and x <= y and x <= 64 - y) or (y < 3.3 and y < x and y < 64 - x)
                if d < 1.3 or d >= 2.5:
                    col = list(FRAME_DARK)
                else:
                    col = list(mix(FRAME_DARK, FRAME_LIGHT, (0.85 if lit_side else 0.22) * (1.0 - abs(d - 1.9) / 0.6 * 0.5)))
            elif d < 6.0:
                f = 1.0 - 0.45 * (1.0 - (d - 3.3) / 2.7) ** 2                       # the shadow the border casts
                col = [v * f for v in col]
            p[0], p[1], p[2], p[3] = col[0], col[1], col[2], 1.0


# ---------------------------------------------------------------- terrain
# Each terrain is drawn from a palette, so one drawing serves every tone a zone can have
# (TERRAIN_TONES below): Westfall's grassland is gold, Elwynn's would be green.

def t_forest(c, p):
    crown = lit(p["leaf"], p["leaf_lo"], 22, 12, 58, 46)
    ink(c, [(oval(32, 57, 25, 3.6), lit(p["ground"], shade(p["ground"], 0.6), 6, 52, 58, 60))] +
        pine(17, 53, 36, 12, lit(p["pine"], p["pine_lo"], 5, 17, 29, 53)))
    pine_detail(c, 17, 53, 36, 12, p["pine_lo"], p["leaf_hi"])
    ink(c, [(poly([(36, 56), (45, 56), (43, 40), (38, 40)]), lit(p["trunk"], shade(p["trunk"], 0.5), 36, 40, 45, 56)),
            (circ(40, 25, 13), crown), (circ(30, 31, 9.5), crown), (circ(51, 31, 9.5), crown), (circ(40, 36, 10), crown)])
    # the crown: light on the upper-left of each mass, shadow gathering underneath
    for x, y, r, a in ((35, 20, 6.0, 0.50), (47, 24, 3.6, 0.40), (27, 28, 3.4, 0.45), (38, 31, 2.6, 0.30)):
        c.fill(circle(x, y, r), p["leaf_hi"], a)
    for x, y, r in ((46, 37, 6.0), (33, 39, 4.2), (54, 34, 3.6)):
        c.fill(circle(x, y, r), shade(p["leaf_lo"], 0.75), 0.42)
    stroke(c, [(40.5, 41), (37, 35)], 0.9, shade(p["trunk"], 0.5), 0.8)
    stroke(c, [(40.5, 41), (45, 35.5)], 0.9, shade(p["trunk"], 0.5), 0.8)
    stroke(c, [(38.4, 44), (38.0, 54)], 0.7, shade(p["trunk"], 1.35), 0.55)


def blade(x, b, h, lean, w=1.7):
    return poly([(x - w, b), (x + w, b), (x + lean * 0.6 + w * 0.62, b - h * 0.6), (x + lean, b - h),
                 (x + lean * 0.6 - w * 0.62, b - h * 0.6)])


def t_grassland(c, p):
    keep = lambda x, y: 5 <= x <= 59 and y <= 57
    parts = [(clipped(circ(46, 82, 40), lambda x, y: 5 <= x <= 59 and y <= 54), lit(p["far"], p["field"], 6, 40, 58, 56)),
             (clipped(circ(28, 98, 53), keep), lit(p["field"], p["field_lo"], 6, 44, 58, 58))]
    tips = []
    for cx, base, k in ((13, 51, 1.15), (33, 50, 1.62), (52, 52, 1.25)):
        for i, (lean, h) in enumerate(((-7, 13), (-3.5, 19), (0.5, 23), (4, 18), (7.5, 12))):
            col = (p["blade_lo"], p["blade"], p["blade_hi"], p["blade"], p["blade_lo"])[i]
            parts.append((blade(cx + lean * 0.35, base, h * k, lean * k, 1.9), col))
            if abs(lean) < 5:
                tips.append((cx + lean * 0.35 + lean * k, base - h * k))
    if p.get("head"):                                   # ripe seed heads: tall dry grass, wheat
        for x, y in tips:
            parts.append((oval(x, y - 1.6, 1.7, 3.6), lit(p["head"], shade(p["head"], 0.6), x - 2, y - 5, x + 2, y + 2)))
    ink(c, parts)
    for a, b in (((9, 55.2), (22, 53.8)), ((38, 56), (55, 54.6)), ((24, 57), (33, 56.4))):   # wind in the field
        stroke(c, [a, b], 0.6, p["far"], 0.6)
    for cx, base, k in ((13, 51, 1.15), (33, 50, 1.62), (52, 52, 1.25)):          # a lit edge on the tall blades
        stroke(c, [(cx - 0.5, base - 2), (cx + 0.1, base - 15 * k)], 0.5, p["blade_hi"], 0.7)
    if p.get("flower"):
        for x, y in ((23, 55), (44, 56.4), (7.5, 55.5)):
            dot(c, x, y, 1.25, p["flower"], shade(p["field_lo"], 0.6))


def t_hills(c, p):
    keep = lambda x, y: y <= 57
    ink(c, [(clipped(circ(45, 51, 18), keep), lit(p["far"], p["lo"], 27, 33, 63, 57))])
    c.fill(crescent(45, 51, 18, 2.2, 3.0), p["hi"], 0.40)
    ink(c, [(clipped(circ(18, 57, 19), keep), lit(p["mid"], p["lo"], 0, 38, 37, 60))])
    paint(c, crescent(18, 57, 19, 2.2, 3.0), p["hi"], 0.45, clip=(keep, None))
    for x, y, h in ((41, 39, 6.5), (51, 42, 5.5), (12, 45, 6.5), (23, 47, 5)):                   # a few trees on the slopes
        c.fill(polygon([(x, y - h - 0.9), (x + h * 0.52 + 0.8, y + 0.7), (x - h * 0.52 - 0.8, y + 0.7)]), shade(p["bush"], 0.4))
        c.fill(polygon([(x, y - h), (x + h * 0.52, y), (x - h * 0.52, y)]), p["bush"])
        c.fill(polygon([(x, y - h), (x + h * 0.52, y), (x + h * 0.1, y)]), shade(p["bush"], 0.6), 0.6)
    front = oval0(41, 62, 27, 14)
    ink(c, [(clipped(oval(41, 62, 27, 14), keep), lit(p["front"], p["lo"], 14, 48, 68, 64))])
    paint(c, (lambda x, y: ((x - 43) / 27) ** 2 + ((y - 64.6) / 14) ** 2 > 1 and y <= 57, None), p["hi"], 0.5, clip=front)
    stroke(c, [(34, 57), (38.6, 54.4), (36.6, 52), (39.6, 49.8)], 0.8, p["path"], 0.8)        # a track over the rise


def t_mountains(c, p):
    k = p["cap"]

    def cap(apex, pts):
        ax, ay = apex
        return polygon([(ax + (x - ax) * k, ay + (y - ay) * k) for x, y in pts])

    def peak(pts, gullies):
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        ink(c, [(poly(pts), lit(p["hi"], p["rock"], min(xs), min(ys), max(xs), max(ys)))])
        apex, right = pts[0], pts[1]
        c.fill(polygon([apex, right, (apex[0] + (right[0] - apex[0]) * 0.18, right[1])]), p["lo"], 0.55)   # the face out of the light
        for a, b in gullies:
            stroke(c, [a, b], 0.6, p["lo"], 0.5)

    ink(c, [(clipped(oval(32, 58, 28, 5), lambda x, y: y <= 58.5), lit(p["foot"], shade(p["foot"], 0.6), 4, 52, 60, 60))])
    peak([(44, 11), (61, 55), (25, 55)], [((40, 28), (36, 37))])
    if k:
        c.fill(cap((44, 11), [(44, 11), (49.2, 24.5), (46.6, 22.4), (44.4, 26.4), (41.4, 22.6), (38.6, 24.6)]), p["snow"])
        c.fill(cap((44, 11), [(44, 11), (49.2, 24.5), (46.6, 22.4), (44.4, 26.4)]), p["snow_lo"], 0.75)
    peak([(37, 35), (50, 55), (25, 55)], [((41, 45), (40, 51))])
    if k > 1.2:
        c.fill(polygon([(37, 35), (41, 41.2), (38.6, 40), (37, 42.4), (35.2, 40), (33.2, 41)]), p["snow"])
    peak([(21, 22), (40, 55), (3, 55)], [((15, 38), (11, 48)), ((19, 34), (17, 44))])
    if k:
        c.fill(cap((21, 22), [(21, 22), (26.2, 31), (23.6, 29.2), (21.2, 32.6), (18.6, 29.2), (15.9, 31)]), p["snow"])
        c.fill(cap((21, 22), [(21, 22), (26.2, 31), (23.6, 29.2), (21.2, 32.6)]), p["snow_lo"], 0.75)
    if p.get("trees"):
        for x, y, h in ((8, 57.4, 6), (13, 58.2, 5), (52, 58.2, 5.5), (57, 57.4, 6)):
            c.fill(polygon([(x, y - h), (x + 2.4, y), (x - 2.4, y)]), p["tree"])


def t_desert(c, p):
    keep = lambda x, y: y <= 57
    c.glow(*circle_sdf(21, 16, 8), (1.0, 0.86, 0.40), 0.45, 9)
    cactus = lit((0.52, 0.72, 0.34), (0.20, 0.40, 0.18), 38, 26, 54, 48)
    ink(c, [(circ(21, 16, 7.5), lit((1.0, 0.95, 0.62), (0.96, 0.66, 0.22), 13, 8, 29, 24))])
    c.fill(circle(18.6, 13.6, 3.2), (1.0, 1.0, 0.86), 0.6)
    back = (lambda x, y: (x - 44) ** 2 + (y - 72) ** 2 <= 31 * 31 and y <= 57, (13, 41, 64, 57))
    ink(c, [(clipped(circ(44, 72, 31), keep), lit(SAND, SAND_DARK, 16, 40, 72, 58))])
    paint(c, crescent(44, 72, 31, 1.6, 3.0), SAND_HI, 0.55, clip=back)                       # the crest in the sun
    paint(c, (lambda x, y: (x - 37) ** 2 + (y - 67) ** 2 > 31 * 31, None), shade(SAND_DARK, 0.75), 0.40, clip=back)   # its lee side
    c.fill(oval0(50, 47.4, 4.6, 1.1), shade(SAND_DARK, 0.6), 0.5)                              # the shadow the cactus throws
    ink(c, [(caps(46, 47, 46, 30, 2.7), cactus),
            (caps(46, 40, 40.6, 40, 1.8), cactus), (caps(40.6, 40, 40.6, 35, 1.8), cactus),
            (caps(46, 37, 51, 37, 1.7), cactus), (caps(51, 37, 51, 32.5, 1.7), cactus)])
    stroke(c, [(45.2, 46), (45.2, 30.5)], 0.6, (0.74, 0.90, 0.50), 0.7)
    for y in (33, 37.5, 42):
        stroke(c, [(47.4, y), (48.2, y + 1.2)], 0.45, (0.16, 0.30, 0.14), 0.8)
    front = (lambda x, y: (x - 13) ** 2 + (y - 70) ** 2 <= 26 * 26 and y <= 57, (0, 44, 40, 57))
    ink(c, [(clipped(circ(13, 70, 26), keep), lit(SAND_HI, SAND, -10, 44, 40, 58))])
    paint(c, crescent(13, 70, 26, 1.6, 3.0), (1.0, 0.97, 0.80), 0.6, clip=front)
    for a, m, b in (((5, 52.5), (13, 50.6), (22, 52)), ((8, 56), (18, 54), (30, 55.6)), ((42, 55), (50, 53.4), (58, 55))):
        stroke(c, [a, m, b], 0.5, SAND_DARK, 0.6)                                             # wind ripples


def t_badlands(c, p):
    mesa = [(12, 20), (36, 20), (38, 26), (42, 55), (6, 55), (10, 26)]
    butte = [(46, 32), (54, 32), (55.5, 37), (59, 55), (41, 55), (44.5, 37)]
    ink(c, [(oval(32, 57, 27, 3.8), lit(p["ground"], shade(p["ground"], 0.6), 5, 52, 59, 61)),
            (poly(mesa), lit(p["mid"], p["lo"], 0, 14, 44, 62)),
            (poly(butte), lit(p["mid"], p["lo"], 36, 28, 62, 62))])
    for shape, top, x0, x1 in ((polygon(mesa), 20, 6, 42), (polygon(butte), 32, 41, 59)):
        h = 55 - top
        paint(c, rect0(x0, top, x1, top + 2.6), p["hi"], 0.85, clip=shape)                 # the sunlit cap rock
        for f, col, a in ((0.24, p["lo"], 0.55), (0.42, p["strata"], 0.60), (0.50, p["lo"], 0.35),
                          (0.68, p["strata"], 0.45), (0.80, p["lo"], 0.40)):                  # strata
            paint(c, rect0(x0, top + h * f, x1, top + h * f + 1.5), col, a, clip=shape)
    paint(c, polygon([(31, 20), (36, 20), (38, 26), (42, 55), (35, 55)]), shade(p["lo"], 0.8), 0.40)
    paint(c, polygon([(51.5, 32), (54, 32), (55.5, 37), (59, 55), (54, 55)]), shade(p["lo"], 0.8), 0.40)
    for a, b in (((18, 23), (17, 34)), ((26, 23), (27.5, 40)), ((49, 34.5), (48.4, 44))):       # weathered clefts
        stroke(c, [a, b], 0.5, shade(p["lo"], 0.8), 0.6)
    for x, y, r in ((44.5, 56.6, 1.5), (20, 57.6, 1.3), (9, 57, 1.1)):
        dot(c, x, y, r, p["mid"], shade(p["lo"], 0.6))
    for dx, dy in ((-2.6, -4.2), (0, -5.4), (2.6, -4.0)):                                      # a dry shrub
        stroke(c, [(33, 58.4), (33 + dx, 58.4 + dy)], 0.5, p["scrub"], 0.95)


def t_swamp(c, p):
    leaf = lit(p["leaf"], p["leaf_lo"], 10, 8, 52, 32)
    trunk = lit(p["trunk"], shade(p["trunk"], 0.5), 20, 22, 40, 54)
    parts = [(wave_band(53, 1.1, 18, 5.2), lit(p["water"], p["water_lo"], 6, 46, 58, 60))]
    for x, top in ((53, 33), (57.5, 38)):                                           # cattails
        parts.append((caps(x, 50, x, top + 5, 0.9), GREEN))
        parts.append((caps(x, top + 5, x, top, 2.2), BROWN))
    parts += [(caps(27, 50, 20.5, 53.6, 1.7), trunk), (caps(33, 50, 39.5, 53.6, 1.7), trunk),       # stilt roots
              (poly([(26, 51), (34, 51), (31.5, 35), (37, 25), (31, 22), (27, 33)]), trunk)]
    for x, y0, y1 in ((15.5, 24, 35), (22.5, 27, 34), (40.5, 27, 37), (47, 24, 32)):     # hanging moss
        parts.append((caps(x, y0, x, y1, 1.35), p["moss"]))
    parts += [(circ(30, 18, 10.5), leaf), (circ(42, 20, 8.2), leaf), (circ(19.5, 22, 7.2), leaf)]
    ink(c, parts)
    for x, y, r, a in ((26, 13.5, 4.6, 0.5), (39.5, 16, 3.0, 0.4), (16.5, 19, 2.6, 0.4)):
        c.fill(circle(x, y, r), p["leaf_hi"], a)
    for x, y, r in ((35, 24, 5.0), (45, 24, 3.4), (22, 26.5, 3.4)):
        c.fill(circle(x, y, r), shade(p["leaf_lo"], 0.7), 0.42)
    stroke(c, [(28.6, 49), (29.6, 36)], 0.7, shade(p["trunk"], 1.4), 0.5)
    for a, b in (((8, 51.6), (17, 51.6)), ((40, 55.6), (49, 55.6)), ((20, 57), (27, 57))):   # still water
        stroke(c, [a, b], 0.5, p["water_hi"], 0.75)
    for x, y in ((12, 55.4), (45.5, 52.4)):                                          # lily pads
        c.fill(oval0(x, y, 3.3, 1.5), shade(p["pad"], 0.5))
        c.fill(oval0(x, y - 0.3, 2.7, 1.1), p["pad"])
    c.fill(caps0(53, 37.5, 53, 34, 0.6), shade(BROWN, 1.5), 0.6)


def t_jungle(c, p):
    frond = lit(p["leaf"], p["leaf_lo"], 12, 8, 58, 40)
    under = lit(p["leaf_hi"], p["leaf"], 4, 40, 60, 60)
    crown = (36, 23)
    ends = ((14, 24), (19, 36), (28, 11), (46, 10), (57, 23), (53, 36))
    parts = [(caps(30, 57, 32, 41, 2.7), lit(p["trunk"], shade(p["trunk"], 0.55), 26, 22, 40, 58)),
             (caps(32, 41, 36, 24, 2.5), lit(p["trunk"], shade(p["trunk"], 0.55), 26, 22, 40, 58))]
    for ex, ey in ends:
        mx, my = (crown[0] + ex) / 2, (crown[1] + ey) / 2 - 3.5                       # fronds arch, then droop
        parts.append((caps(crown[0], crown[1], mx, my, 3.3), frond))
        parts.append((caps(mx, my, ex, ey, 2.4), frond))
    parts += [(caps(15, 57, 8, 44, 3.7), under), (caps(19, 57, 21, 42.5, 3.3), lit(p["leaf"], p["leaf_lo"], 14, 40, 26, 58)),
              (caps(47, 57, 55, 44.5, 3.8), under), (caps(51, 58, 44.5, 46, 3.2), lit(p["leaf"], p["leaf_lo"], 40, 44, 56, 60)),
              (circ(34, 26.6, 2.3), BROWN), (circ(38.6, 27.4, 2.3), BROWN)]
    ink(c, parts)
    for ex, ey in ends:                                                               # frond midribs
        mx, my = (crown[0] + ex) / 2, (crown[1] + ey) / 2 - 3.5
        stroke(c, [crown, (mx, my), (ex, ey)], 0.5, shade(p["leaf_lo"], 0.7), 0.6)
        stroke(c, [(crown[0] - 0.6, crown[1] - 1.4), (mx - 0.6, my - 1.6)], 0.5, p["leaf_hi"], 0.55)
    for y in (52, 47, 42, 36.5, 31):                                                 # the trunk's rings
        x = 30 + (57 - y) / 16 * 2 if y > 41 else 32 + (41 - y) / 17 * 4
        stroke(c, [(x - 2.2, y + 0.4), (x + 2.2, y - 0.4)], 0.45, shade(p["trunk"], 0.45), 0.7)
    for a, b in (((15, 56), (9.2, 45.5)), ((19.2, 56), (20.8, 44)), ((47, 56), (54, 45.6)), ((50.6, 57), (45.2, 47.2))):
        stroke(c, [a, b], 0.45, shade(p["leaf_lo"], 0.7), 0.6)
    for x, y in ((33.3, 25.9), (37.9, 26.7)):
        c.fill(circle(x, y, 0.8), shade(BROWN, 1.6), 0.7)
    dot(c, 27, 55.5, 1.9, p["flower"], shade(p["leaf_lo"], 0.5))
    c.fill(circle(27, 55.5, 0.7), (1.0, 0.9, 0.4))


def t_tundra(c, p):
    keep = lambda x, y: 5 <= x <= 59 and y <= 58
    needles = lit((0.40, 0.60, 0.48), (0.14, 0.30, 0.26), 26, 12, 54, 48)
    ink(c, [(clipped(circ(32, 94, 49), keep), lit(SNOW, SNOW_LO, 6, 44, 58, 60))] +
        pine(15, 50, 20, 8, lit((0.36, 0.56, 0.46), (0.14, 0.30, 0.26), 7, 30, 23, 50)) +
        pine(39, 49, 36, 14, needles) +
        [(circ(55, 51.5, 4.2), lit(GREY, GREY_DARK, 50, 46, 60, 56))])
    pine_detail(c, 39, 49, 36, 14, (0.08, 0.20, 0.18), snow=SNOW)
    pine_detail(c, 15, 50, 20, 8, (0.08, 0.20, 0.18), snow=SNOW)
    paint(c, crescent(55, 51.5, 4.2, 0.6, 2.6), SNOW, 1.0)                           # snow on the boulder
    for a, m, b in (((7, 53), (16, 51.6), (27, 53.4)), ((30, 56.6), (42, 54.8), (56, 56.4))):   # drifts
        stroke(c, [a, m, b], 0.6, SNOW_LO, 0.9)
    stroke(c, [(33, 50.5), (46, 50.5)], 0.9, (0.56, 0.68, 0.88), 0.55)               # the tree's shadow on the snow
    for x, y, r in ((10, 16, 1.2), (24, 9, 1.0), (55, 14, 1.2), (57, 30, 0.9), (6, 34, 0.9), (26, 22, 0.8)):
        dot(c, x, y, r, SNOW, (0.20, 0.30, 0.50))                                    # falling snow


def t_coast(c, p):
    def sea(dx, dy):
        def inside(x, y):
            return 14 + dx <= x <= 59 + dx and 29 + dy + 1.8 * math.sin((x - dx) / 15 * 2 * math.pi) <= y <= 57 + dy
        return inside, (14 + dx, 26 + dy, 59 + dx, 57 + dy)
    keep = lambda x, y: y <= 57 and x >= 4
    ink(c, [(sea, lit(p["sea_hi"], p["sea_lo"], 14, 26, 60, 60)),
            (clipped(circ(8, 68, 33), keep), lit(p["sand_hi"], p["sand_lo"], 0, 34, 42, 60))])
    ink(c, [(circ(49, 37, 4.4), lit(p["rock"], shade(p["rock"], 0.5), 44, 32, 54, 42))], 1.6)
    beach = circle(8, 68, 33)[0]
    wet = lambda r: (lambda x, y: not beach(x, y) and (x - 8) ** 2 + (y - 68) ** 2 <= r * r and y <= 57, (4, 30, 46, 58))
    paint(c, wet(37.5), p["sea_hi"], 0.55, clip=sea(0, 0))                           # shallows
    paint(c, wet(35.0), FOAM, 0.95, clip=sea(0, 0))                                  # surf on the sand
    for y, x0, x1, ph in ((36, 28, 43, 0.5), (43.5, 36, 58, 2.0), (50.5, 44, 58, 0.0)):
        c.fill(wave_band(y, 1.1, 13, 0.6, x0, x1, ph)(0, 0), FOAM, 0.8)              # wave crests
    stroke(c, [(45, 40.6), (53.5, 40.6)], 0.6, FOAM, 0.85)                           # foam round the rock
    c.fill(circle(47.6, 35.6, 1.5), shade(p["rock"], 1.4), 0.6)
    for x, y in ((12, 46), (20, 50), (9, 53), (26, 54.6), (17, 55.6), (7, 42)):
        c.fill(circle(x, y, 0.8), p["sand_lo"], 0.8)
    dot(c, 15, 51.5, 1.5, (0.98, 0.80, 0.74), shade(p["sand_lo"], 0.6))              # a shell


def t_volcanic(c, p):
    c.glow(*circle_sdf(32, 19, 9), LAVA, 0.65, 10)
    smoke = lit((0.50, 0.46, 0.46), (0.22, 0.20, 0.22), 20, 0, 46, 16)
    cone = [(25, 22), (39, 22), (60, 56), (4, 56)]
    ink(c, [(circ(29, 12, 5.2), smoke), (circ(37, 8.5, 4.4), smoke), (circ(26, 5.6, 3.4), smoke),
            (poly(cone), lit((0.52, 0.48, 0.46), (0.14, 0.12, 0.12), 4, 22, 60, 56)),
            (poly([(25, 22), (39, 22), (36.4, 27.4), (32.4, 24.4), (28.4, 28.6)]), LAVA)])
    c.fill(polygon([(35, 22), (39, 22), (60, 56), (44, 56)]), (0.06, 0.05, 0.05), 0.45)
    c.fill(polygon([(27, 22.6), (37, 22.6), (35, 25), (32.4, 23.4), (29.6, 25.6)]), LAVA_HI, 0.9)
    for pts in ([(29.4, 27), (26.6, 36), (28.6, 44), (25.4, 52)], [(36, 26.4), (40.4, 34), (38.4, 41), (42, 47)],
                [(32.6, 25), (33.4, 33)]):                                             # lava running down
        stroke(c, pts, 1.5, LAVA)
        stroke(c, pts, 0.55, LAVA_HI)
    for a, m, b in (((12, 52), (15, 48.6), (19, 50)), ((47, 52), (50, 49), (54, 51.6))):  # glowing cracks
        stroke(c, [a, m, b], 0.5, LAVA, 0.85)
    for x, y, r in ((9, 55.6, 1.8), (51, 55.8, 1.6), (33, 56.4, 1.4)):
        dot(c, x, y, r, (0.30, 0.28, 0.28), (0.05, 0.04, 0.04))
    for x, y, r, a in ((27.4, 10.4, 2.4, 0.4), (36, 7.2, 1.9, 0.35)):
        c.fill(circle(x, y, r), (0.72, 0.68, 0.68), a)
    for x, y in ((22, 15), (42, 14.6), (33, 13.6)):                                   # sparks
        c.fill(circle(x, y, 0.9), LAVA_HI)


def t_blighted(c, p):
    c.glow(*circle_sdf(32, 51, 15), p["glow"], 0.45, 10)
    bark = lit(p["bark"], p["bark_lo"], 14, 10, 52, 58)
    cap = lit(p["cap"], shade(p["cap"], 0.55), 8, 44, 56, 56)
    stem = (0.86, 0.82, 0.70)
    ink(c, [(oval(32, 57.4, 23, 3.4), lit(p["ground"], shade(p["ground"], 0.5), 9, 54, 55, 61)),
            (rect(14.4, 50, 17.6, 56), stem), (clipped(oval(16, 50.4, 5.4, 4.4), lambda x, y: y <= 51), cap),
            (rect(47.2, 52, 49.6, 56.6), stem), (clipped(oval(48.4, 52.4, 4.2, 3.4), lambda x, y: y <= 53), cap),
            (poly([(28, 57), (36, 57), (34.6, 40), (33.6, 24), (30.4, 24), (29.4, 40)]), bark),
            (caps(32, 35, 18, 18, 2.4), bark), (caps(32, 30, 46, 14, 2.4), bark),
            (caps(24, 25.4, 15.5, 27.6, 1.7), bark), (caps(40, 21.6, 49.5, 23.6, 1.7), bark),
            (caps(32, 26, 31, 11, 1.9), bark), (caps(20.6, 21, 21.6, 12.6, 1.4), bark),
            (caps(43.4, 17, 41.4, 8.6, 1.4), bark)])
    stroke(c, [(30.6, 55), (31.2, 28)], 0.7, p["bark_hi"], 0.55)
    stroke(c, [(30.4, 33.4), (19.4, 19.6)], 0.5, p["bark_hi"], 0.5)
    stroke(c, [(34.4, 54), (34.0, 36)], 0.8, shade(p["bark_lo"], 0.6), 0.5)
    c.fill(oval0(32.2, 43, 1.7, 2.5), shade(p["bark_lo"], 0.4))                      # a hollow
    for x, y, r in ((14.4, 48.4, 0.9), (18, 49.2, 0.7), (47.4, 51, 0.7), (49.8, 51.6, 0.6)):
        c.fill(circle(x, y, r), (1.0, 0.98, 0.86), 0.9)                              # spots on the caps
    for x, y, r in ((18, 23.4, 1.2), (46, 19.4, 1.2), (15.6, 31, 0.9), (49.4, 27.4, 0.9), (26, 47, 0.8), (39, 50, 0.8)):
        c.glow(*circle_sdf(x, y, r * 0.5), p["glow"], 1.0, r * 1.8)                   # what drips from it


def t_underground(c, p):
    keep = lambda x, y: y <= 57
    wood = lit((0.70, 0.50, 0.28), BROWN_DARK, 16, 38, 48, 58)
    ink(c, [(circ(10, 55, 3.6), lit(GREY, GREY_DARK, 5, 50, 15, 59)), (circ(54.5, 55.4, 3.2), lit(GREY, GREY_DARK, 50, 51, 59, 59)),
            (clipped(circ(32, 57, 27), keep), lit((0.74, 0.73, 0.74), (0.30, 0.30, 0.34), 5, 30, 59, 60)),
            (clipped(circ(32, 59, 15), keep), DARK)])
    rockface = (lambda x, y: (x - 32) ** 2 + (y - 57) ** 2 <= 27 * 27 and y <= 57 and (x - 32) ** 2 + (y - 59) ** 2 > 15 * 15, None)
    paint(c, crescent(32, 57, 27, 2.4, 3.4), (0.90, 0.90, 0.92), 0.5, clip=rockface)
    for pts in ([(12, 44), (17, 40), (16, 34)], [(44, 34), (48, 39), (53, 41)], [(26, 33), (29, 37)], [(9, 51), (14, 49)],
                [(50, 49), (55, 47)]):                                                # cracks in the rock
        stroke(c, pts, 0.5, (0.20, 0.20, 0.24), 0.75, clip=rockface)
    c.glow(*circle_sdf(32, 49, 2.5), LAVA, 0.75, 12)                                  # lantern light in the dark
    ink(c, [(rect(18.4, 43, 22, 57), wood), (rect(42, 43, 45.6, 57), wood), (rect(16.4, 39.6, 47.6, 43.6), wood)], 1.4)
    for a, b in (((19.4, 45), (19.4, 56)), ((43, 45), (43, 56)), ((18, 40.8), (46, 40.8))):
        stroke(c, [a, b], 0.4, (0.90, 0.70, 0.42), 0.6)
    stroke(c, [(32, 43.6), (32, 46.6)], 0.4, (0.30, 0.24, 0.16))
    dot(c, 32, 48.4, 1.7, LAVA_HI, (0.36, 0.20, 0.06))
    stroke(c, [(24, 56.4), (40, 56.4)], 0.5, (0.50, 0.36, 0.18), 0.7)                 # the track into the mine
    stroke(c, [(26, 54), (38, 54)], 0.4, (0.40, 0.28, 0.14), 0.6)


def t_city(c, p):
    wall = lambda x0, y0, x1, y1: lit(p["wall_hi"], p["wall"], x0, y0, x1, y1)
    roof = lit(p["roof"], p["roof_lo"], 20, 4, 44, 22)
    parts = [(caps(32, 7, 32, 2.4, 0.6), DARK), (poly([(32.4, 1.6), (39.6, 3.6), (32.4, 5.8)]), p["flag"]),
             (rect(9, 38, 55, 57), wall(9, 38, 55, 57)),
             (rect(5, 29, 16, 57), wall(5, 29, 16, 57)), (rect(48, 29, 59, 57), wall(48, 29, 59, 57)),
             (rect(24, 20, 40, 57), wall(24, 20, 40, 57)), (poly([(21.6, 21), (42.4, 21), (32, 6.4)]), roof)]
    for x in (5, 9.2, 13.4, 48, 52.2, 56.4):
        parts.append((rect(x, 25.4, x + 2.6, 30), wall(x, 25, x + 3, 30)))
    for x in (18, 43.4):
        parts.append((rect(x, 34.6, x + 2.8, 39), wall(x, 34, x + 3, 39)))
    ink(c, parts)
    for x0, x1, y0 in ((36, 40, 21), (13, 16, 29), (56, 59, 29)):                    # the walls' shaded sides
        c.fill(rect0(x0, y0, x1, 57), p["wall_lo"], 0.45)
    c.fill(polygon([(32, 6.4), (42.4, 21), (33.4, 21)]), p["roof_lo"], 0.55)
    c.fill(polygon([(32, 8.4), (27.6, 16), (25.6, 18.4)]), shade(p["roof"], 1.5), 0.45)
    for y, x0, x1 in ((44, 16.6, 23.4), (50, 16.6, 23.4), (44, 40.6, 47.4), (50, 40.6, 47.4), (36, 25, 39), (42, 25, 39)):
        stroke(c, [(x0, y), (x1, y)], 0.3, p["wall_lo"], 0.55)                        # courses of stone
    for x, y in ((19, 47), (21.6, 53), (43, 47), (45.4, 53), (28, 39), (36, 39), (31, 45)):
        stroke(c, [(x, y - 3), (x, y)], 0.3, p["wall_lo"], 0.5)
    c.fill(caps0(32, 49.4, 32, 57, 4.4), DARK)                                       # the gate and its portcullis
    c.fill(rect0(27.6, 53, 36.4, 57.2), DARK)
    for x in (29.6, 32, 34.4):
        stroke(c, [(x, 46.4), (x, 57)], 0.35, shade(p["wall_lo"], 0.9), 0.85)
    stroke(c, [(28, 51.4), (36, 51.4)], 0.35, shade(p["wall_lo"], 0.9), 0.85)
    c.fill(caps0(32, 28.6, 32, 32.6, 1.7), DARK)                                     # windows, one of them lit
    c.fill(caps0(32, 29, 32, 32.4, 0.9), (1.0, 0.84, 0.42))
    for x in (10.4, 53.6):
        c.fill(caps0(x, 36.4, x, 41.4, 0.9), DARK)


TERRAIN = {"forest": t_forest, "grassland": t_grassland, "hills": t_hills, "mountains": t_mountains,
           "desert": t_desert, "badlands": t_badlands, "swamp": t_swamp, "jungle": t_jungle,
           "tundra": t_tundra, "coast": t_coast, "volcanic": t_volcanic, "blighted": t_blighted,
           "underground": t_underground, "city": t_city}

# terrain -> { tone: palette }. "" is the terrain's own look (land_terrain_<terrain>.tga); every
# other tone is a zone colouring (land_terrain_<terrain>_<tone>.tga), named in Data.lua
# ns.TerrainTones and chosen per zone with `tone = "..."`. A tone only lists what it changes.
TERRAIN_TONES = {
    "forest": {
        "": dict(bg=((0.20, 0.40, 0.62), (0.72, 0.84, 0.72), (0.15, 0.30, 0.11)),
             leaf_hi=(0.62, 0.84, 0.36), leaf=(0.36, 0.64, 0.24), leaf_lo=(0.16, 0.38, 0.14), pine=(0.26, 0.52, 0.30),
                 pine_lo=(0.10, 0.28, 0.18), trunk=(0.56, 0.38, 0.20), ground=(0.28, 0.48, 0.18)),
        "dusk": dict(bg=((0.04, 0.06, 0.13), (0.22, 0.27, 0.38), (0.05, 0.09, 0.09)),
             leaf_hi=(0.38, 0.52, 0.56), leaf=(0.20, 0.32, 0.38), leaf_lo=(0.07, 0.14, 0.20), pine=(0.16, 0.28, 0.34),
                     pine_lo=(0.05, 0.11, 0.16), trunk=(0.36, 0.32, 0.36), ground=(0.14, 0.20, 0.20)),
        "pine": dict(bg=((0.17, 0.28, 0.42), (0.62, 0.75, 0.78), (0.09, 0.21, 0.21)),
             leaf_hi=(0.56, 0.78, 0.70), leaf=(0.28, 0.52, 0.50), leaf_lo=(0.11, 0.28, 0.33), pine=(0.22, 0.44, 0.46),
                     pine_lo=(0.08, 0.21, 0.27), trunk=(0.44, 0.36, 0.30), ground=(0.20, 0.36, 0.32)),
        "dead": dict(bg=((0.32, 0.34, 0.32), (0.68, 0.65, 0.48), (0.19, 0.19, 0.09)),
             leaf_hi=(0.70, 0.68, 0.38), leaf=(0.48, 0.47, 0.24), leaf_lo=(0.24, 0.25, 0.13), pine=(0.36, 0.40, 0.25),
                     pine_lo=(0.16, 0.20, 0.12), trunk=(0.42, 0.36, 0.30), ground=(0.32, 0.31, 0.18)),
        "violet": dict(bg=((0.13, 0.10, 0.33), (0.52, 0.45, 0.72), (0.09, 0.17, 0.23)),
             leaf_hi=(0.78, 0.60, 0.90), leaf=(0.50, 0.34, 0.68), leaf_lo=(0.25, 0.15, 0.42), pine=(0.20, 0.46, 0.50),
                       pine_lo=(0.07, 0.23, 0.30), trunk=(0.44, 0.32, 0.38), ground=(0.20, 0.36, 0.38)),
    },
    "grassland": {
        "": dict(bg=((0.20, 0.44, 0.80), (0.82, 0.92, 0.88), (0.24, 0.42, 0.13)),
             far=(0.64, 0.82, 0.42), field=(0.46, 0.68, 0.26), field_lo=(0.22, 0.42, 0.14), blade_hi=(0.76, 0.92, 0.42),
                 blade=(0.48, 0.74, 0.28), blade_lo=(0.24, 0.46, 0.14), flower=(1.0, 0.96, 0.62)),
        "gold": dict(bg=((0.26, 0.46, 0.76), (1.0, 0.89, 0.66), (0.56, 0.38, 0.13)),
             far=(0.98, 0.86, 0.52), field=(0.90, 0.71, 0.32), field_lo=(0.60, 0.41, 0.15), blade_hi=(1.0, 0.93, 0.58),
                     blade=(0.94, 0.77, 0.34), blade_lo=(0.66, 0.46, 0.17), flower=None, head=(0.80, 0.52, 0.16)),
    },
    "hills": {
        "": dict(bg=((0.22, 0.46, 0.80), (0.84, 0.92, 0.86), (0.17, 0.33, 0.11)),
             far=(0.36, 0.58, 0.30), mid=(0.46, 0.70, 0.28), front=(0.58, 0.80, 0.34), lo=(0.20, 0.40, 0.14),
                 hi=(0.82, 0.95, 0.54), bush=(0.20, 0.44, 0.16), path=(0.84, 0.72, 0.46)),
        "red": dict(bg=((0.27, 0.42, 0.68), (0.98, 0.80, 0.62), (0.38, 0.15, 0.08)),
             far=(0.62, 0.30, 0.20), mid=(0.78, 0.40, 0.24), front=(0.88, 0.52, 0.30), lo=(0.46, 0.18, 0.10),
                    hi=(1.0, 0.76, 0.52), bush=(0.40, 0.50, 0.20), path=(0.96, 0.82, 0.60)),
        "dry": dict(bg=((0.30, 0.48, 0.72), (0.96, 0.91, 0.70), (0.34, 0.34, 0.13)),
             far=(0.56, 0.58, 0.30), mid=(0.70, 0.70, 0.34), front=(0.82, 0.80, 0.42), lo=(0.40, 0.40, 0.18),
                    hi=(0.97, 0.95, 0.64), bush=(0.32, 0.44, 0.18), path=(0.88, 0.76, 0.52)),
    },
    "mountains": {
        "": dict(bg=((0.17, 0.34, 0.64), (0.80, 0.88, 0.94), (0.19, 0.31, 0.15)),
             hi=(0.82, 0.82, 0.85), rock=(0.60, 0.60, 0.64), lo=(0.30, 0.30, 0.37), snow=SNOW, snow_lo=SNOW_LO,
                 foot=(0.32, 0.50, 0.24), cap=1.0, trees=True, tree=(0.14, 0.32, 0.16)),
        "snow": dict(bg=((0.10, 0.24, 0.54), (0.62, 0.76, 0.94), (0.72, 0.81, 0.92)),
             hi=(0.95, 0.98, 1.0), rock=(0.74, 0.83, 0.94), lo=(0.42, 0.53, 0.74), foot=(0.92, 0.96, 1.0),
                     cap=1.7, tree=(0.16, 0.34, 0.30)),
        "brown": dict(bg=((0.25, 0.41, 0.64), (0.94, 0.83, 0.66), (0.29, 0.33, 0.13)),
             hi=(0.86, 0.70, 0.52), rock=(0.66, 0.48, 0.32), lo=(0.36, 0.22, 0.13), foot=(0.42, 0.52, 0.24), cap=0),
        "dark": dict(bg=((0.08, 0.06, 0.14), (0.38, 0.31, 0.42), (0.11, 0.09, 0.13)),
             hi=(0.60, 0.58, 0.66), rock=(0.40, 0.38, 0.47), lo=(0.17, 0.15, 0.23), foot=(0.27, 0.25, 0.30),
                     cap=0, trees=False),
    },
    "desert": {"": dict(bg=((0.22, 0.48, 0.86), (1.0, 0.90, 0.66), (0.72, 0.52, 0.25)))},
    "badlands": {
        "": dict(bg=((0.27, 0.44, 0.72), (1.0, 0.80, 0.56), (0.48, 0.23, 0.10)),
             hi=(1.0, 0.68, 0.42), mid=(0.84, 0.42, 0.22), lo=(0.50, 0.20, 0.10), strata=(0.97, 0.60, 0.34),
                 ground=(0.72, 0.38, 0.19), scrub=(0.50, 0.46, 0.20)),
        "tan": dict(bg=((0.27, 0.46, 0.74), (1.0, 0.90, 0.68), (0.54, 0.38, 0.17)),
             hi=(1.0, 0.88, 0.60), mid=(0.87, 0.65, 0.37), lo=(0.54, 0.36, 0.16), strata=(0.97, 0.78, 0.48),
                    ground=(0.76, 0.56, 0.29)),
        "grey": dict(bg=((0.31, 0.33, 0.40), (0.74, 0.71, 0.68), (0.29, 0.27, 0.27)),
             hi=(0.82, 0.80, 0.78), mid=(0.58, 0.56, 0.56), lo=(0.29, 0.27, 0.30), strata=(0.71, 0.69, 0.67),
                     ground=(0.46, 0.44, 0.45), scrub=(0.36, 0.36, 0.30)),
    },
    "swamp": {"": dict(bg=((0.13, 0.21, 0.18), (0.52, 0.62, 0.44), (0.09, 0.17, 0.13)),
             water_hi=(0.62, 0.76, 0.62), water=(0.36, 0.52, 0.38), water_lo=(0.14, 0.26, 0.20),
                       leaf_hi=(0.56, 0.68, 0.34), leaf=(0.34, 0.48, 0.22), leaf_lo=(0.14, 0.26, 0.12), moss=(0.46, 0.56, 0.30),
                       trunk=(0.44, 0.34, 0.24), pad=(0.44, 0.70, 0.30))},
    "jungle": {"": dict(bg=((0.11, 0.36, 0.44), (0.74, 0.90, 0.62), (0.07, 0.25, 0.09)),
             leaf_hi=(0.56, 0.88, 0.36), leaf=(0.34, 0.72, 0.26), leaf_lo=(0.12, 0.40, 0.14),
                        trunk=(0.62, 0.44, 0.24), flower=(0.95, 0.30, 0.36))},
    "tundra": {"": dict(bg=((0.12, 0.24, 0.50), (0.64, 0.76, 0.94), (0.68, 0.79, 0.92)))},
    "coast": {
        "": dict(bg=((0.22, 0.50, 0.86), (0.88, 0.95, 0.99), (0.11, 0.29, 0.55)),
             sand_hi=SAND_HI, sand_lo=SAND_DARK, sea_hi=BLUE_HI, sea_lo=BLUE_DARK, rock=(0.56, 0.54, 0.54)),
        "grey": dict(bg=((0.27, 0.33, 0.42), (0.72, 0.78, 0.82), (0.13, 0.21, 0.31)),
             sand_hi=(0.84, 0.84, 0.82), sand_lo=(0.44, 0.45, 0.48), sea_hi=(0.58, 0.70, 0.78),
                     sea_lo=(0.15, 0.25, 0.36), rock=(0.42, 0.42, 0.46)),
    },
    "volcanic": {"": dict(bg=((0.10, 0.05, 0.05), (0.60, 0.21, 0.08), (0.09, 0.05, 0.05)))},
    "blighted": {
        "": dict(bg=((0.08, 0.06, 0.14), (0.31, 0.38, 0.22), (0.07, 0.09, 0.05)),
             glow=FEL, bark_hi=(0.72, 0.64, 0.74), bark=(0.50, 0.42, 0.52), bark_lo=(0.24, 0.18, 0.26),
                 cap=(0.62, 0.86, 0.34), ground=(0.22, 0.26, 0.15)),
        "plague": dict(bg=((0.14, 0.07, 0.05), (0.56, 0.31, 0.14), (0.13, 0.07, 0.04)),
             glow=(0.96, 0.60, 0.20), bark_hi=(0.72, 0.64, 0.56), bark=(0.50, 0.42, 0.36), bark_lo=(0.24, 0.18, 0.14),
                       cap=(0.92, 0.50, 0.18), ground=(0.36, 0.25, 0.14)),
    },
    "underground": {"": dict(bg=((0.05, 0.04, 0.04), (0.22, 0.16, 0.11), (0.09, 0.07, 0.05)))},
    "city": {
        "": dict(bg=((0.22, 0.44, 0.80), (0.86, 0.91, 0.95), (0.32, 0.35, 0.28)),
             wall_hi=(0.96, 0.94, 0.88), wall=(0.78, 0.75, 0.68), wall_lo=(0.46, 0.43, 0.39), roof=(0.32, 0.48, 0.80),
                 roof_lo=(0.13, 0.23, 0.50), flag=(0.32, 0.52, 0.92)),
        "iron": dict(bg=((0.09, 0.07, 0.07), (0.48, 0.27, 0.12), (0.15, 0.13, 0.13)),
             wall_hi=(0.76, 0.76, 0.80), wall=(0.54, 0.54, 0.59), wall_lo=(0.27, 0.27, 0.32), roof=(0.76, 0.58, 0.24),
                     roof_lo=(0.44, 0.30, 0.10), flag=(0.92, 0.74, 0.30)),
        "horde": dict(bg=((0.31, 0.42, 0.64), (1.0, 0.78, 0.52), (0.42, 0.23, 0.11)),
             wall_hi=(0.88, 0.62, 0.42), wall=(0.66, 0.42, 0.28), wall_lo=(0.34, 0.19, 0.11), roof=(0.36, 0.32, 0.32),
                      roof_lo=(0.15, 0.13, 0.13), flag=(0.84, 0.16, 0.12)),
        "crypt": dict(bg=((0.05, 0.07, 0.07), (0.23, 0.36, 0.20), (0.07, 0.09, 0.09)),
             wall_hi=(0.66, 0.70, 0.64), wall=(0.46, 0.48, 0.46), wall_lo=(0.21, 0.23, 0.23), roof=(0.40, 0.28, 0.50),
                      roof_lo=(0.18, 0.11, 0.26), flag=(0.52, 0.88, 0.36)),
        "elven": dict(bg=((0.11, 0.08, 0.31), (0.54, 0.45, 0.74), (0.11, 0.21, 0.25)),
             wall_hi=(0.97, 0.96, 1.0), wall=(0.80, 0.78, 0.90), wall_lo=(0.48, 0.46, 0.64), roof=(0.56, 0.36, 0.76),
                      roof_lo=(0.27, 0.15, 0.44), flag=(0.40, 0.86, 0.82)),
        "bluff": dict(bg=((0.26, 0.48, 0.82), (0.94, 0.91, 0.74), (0.32, 0.42, 0.15)),
             wall_hi=(0.95, 0.82, 0.60), wall=(0.78, 0.62, 0.42), wall_lo=(0.44, 0.31, 0.17), roof=(0.72, 0.30, 0.20),
                      roof_lo=(0.40, 0.14, 0.08), flag=(0.94, 0.86, 0.62)),
    },
}


def terrain_palette(terrain, tone):
    p = dict(TERRAIN_TONES[terrain][""])
    p.update(TERRAIN_TONES[terrain][tone])
    return p


# ---------------------------------------------------------------- ground underfoot
def mound(color_light, color_dark):
    keep = lambda x, y: y <= 52
    return (clipped(circ(32, 62, 28), keep), lit(color_light, color_dark, 4, 34, 60, 52))


MOUND = (lambda x, y: (x - 32) ** 2 + (y - 62) ** 2 <= 28 * 28 and y <= 52, (4, 34, 60, 52))


def g_soil(c):
    ink(c, [mound((0.70, 0.49, 0.28), BROWN_DARK)])
    paint(c, crescent(32, 62, 28, 2.0, 3.0), (0.90, 0.70, 0.46), 0.45, clip=MOUND)
    for x, y in ((14, 46), (24, 41.5), (34, 39.5), (44, 41.5), (52, 46)):            # furrows
        stroke(c, [(x - 2.6, y + 5), (x + 2.6, y - 1.5)], 1.1, (0.26, 0.15, 0.07), 0.9, clip=MOUND)
        stroke(c, [(x - 1.2, y + 5.4), (x + 4.0, y - 1.1)], 0.5, (0.86, 0.64, 0.40), 0.6, clip=MOUND)
    for x, y, r in ((20, 49.6, 1.0), (39, 49, 1.2), (30, 47, 0.8)):
        c.fill(circle(x, y, r), (0.26, 0.15, 0.07), 0.9)
    ink(c, [(caps(32, 36.4, 32, 29.6, 0.8), GREEN), (oval(28.6, 29.4, 3.6, 1.9), GREEN),
            (oval(35.4, 28.4, 3.6, 1.9), lit((0.60, 0.84, 0.36), GREEN, 31, 26, 39, 31))], 1.5)    # a seedling


def g_mud(c):
    puddle = oval0(32, 44, 26, 11)
    ink(c, [(oval(32, 44, 26, 11), lit((0.52, 0.38, 0.22), (0.20, 0.13, 0.07), 6, 33, 58, 55))])
    paint(c, (lambda x, y: ((x - 33.5) / 25) ** 2 + ((y - 46) / 10) ** 2 > 1, None), (0.72, 0.56, 0.36), 0.55, clip=puddle)
    c.fill(oval0(34, 46, 17, 6), (0.24, 0.16, 0.09), 0.75)                            # standing water in the middle
    c.fill(oval0(31, 44.6, 11, 3.2), (0.40, 0.30, 0.20), 0.6)
    stroke(c, [(24, 43.6), (33, 42.8)], 0.6, (0.86, 0.80, 0.70), 0.7)
    for cx, cy, r in ((16, 42, 2.2), (48, 41, 2.6), (44, 50, 1.6), (21, 50, 1.4)):    # bubbles and clods
        c.fill(circle(cx, cy, r), (0.18, 0.11, 0.06))
        c.fill(circle(cx - r * 0.3, cy - r * 0.35, r * 0.4), (0.74, 0.60, 0.42), 0.8)
    ink(c, [(oval(46, 30.4, 2.2, 3.0), lit((0.52, 0.38, 0.22), (0.20, 0.13, 0.07), 43, 27, 49, 34)),
            (circ(20, 31.4, 1.6), (0.40, 0.28, 0.16))], 1.5)                           # spatter


def g_sand(c):
    ink(c, [mound(SAND_HI, SAND_DARK)])
    paint(c, crescent(32, 62, 28, 2.0, 3.0), (1.0, 0.96, 0.78), 0.5, clip=MOUND)
    for y, amp in ((41, 1.2), (45.4, 1.4), (49.6, 1.2)):                              # wind ripples
        paint(c, wave_band(y, amp, 12, 0.55, 6, 58, y)(0, 0), SAND_DARK, 0.75, clip=MOUND)
        paint(c, wave_band(y + 1.1, amp, 12, 0.4, 6, 58, y)(0, 0), (1.0, 0.95, 0.74), 0.6, clip=MOUND)
    for cx, cy in ((20, 38.4), (40, 37.6), (50, 43.4), (28, 36.6)):
        c.fill(circle(cx, cy, 0.8), SAND_DARK, 0.9)
    ink(c, [(clipped(oval(44, 34.6, 4.4, 3.8), lambda x, y: y <= 35.4), lit((1.0, 0.86, 0.80), (0.86, 0.56, 0.50), 39, 30, 49, 36))], 1.5)
    for dx in (-2.2, 0, 2.2):                                                         # a scallop shell
        stroke(c, [(44, 35), (44 + dx, 31.6)], 0.3, (0.70, 0.40, 0.36), 0.8)


def g_rock(c):
    for cx, cy, r, light, dark in ((32, 29, 11, (0.84, 0.84, 0.86), GREY_DARK), (21, 45, 12, (0.74, 0.74, 0.76), GREY_DARK),
                                   (43, 47, 10, (0.66, 0.66, 0.70), (0.28, 0.28, 0.33))):
        ink(c, [(circ(cx, cy, r), lit(light, dark, cx - r, cy - r, cx + r, cy + r))])
        c.fill(crescent(cx, cy, r, 1.8, 2.6), (0.96, 0.96, 0.98), 0.5)
        c.fill(crescent(cx, cy, r, -2.2, -3.0), (0.16, 0.16, 0.22), 0.40)
    for pts in ([(28, 22), (31, 27), (29.4, 32)], [(15, 40), (19, 44), (17.4, 50)], [(41, 41), (44, 46.4), (47.4, 48)],
                [(36, 31), (38.6, 34)]):                                               # cracks
        stroke(c, pts, 0.5, (0.18, 0.18, 0.24), 0.8)
    for x, y, r in ((33, 54.6, 2.0), (9, 55, 1.5)):                                    # chips fallen from them
        dot(c, x, y, r, GREY, (0.10, 0.10, 0.14))
    for x, y, r in ((24, 37, 1.6), (36, 24, 1.2)):                                    # moss
        c.fill(circle(x, y, r), (0.42, 0.60, 0.30), 0.75)


def g_snow(c):
    c.glow(*circle_sdf(32, 32, 10), (0.6, 0.85, 1.0), 0.35, 14)
    arms = []
    for i in range(6):
        a = i * math.pi / 3 + math.pi / 2
        ca, sa = math.cos(a), math.sin(a)
        arms.append((32, 32, 32 + ca * 25, 32 + sa * 25, 1.0))
        for d, ln in ((11, 6.5), (18, 5.0)):                                          # two pairs of barbs per arm
            bx, by = 32 + ca * d, 32 + sa * d
            for s in (-1, 1):
                b = a + s * math.pi / 3.4
                arms.append((bx, by, bx + math.cos(b) * ln, by + math.sin(b) * ln, 0.8))
    for grow, col, al in ((2.3, (0.05, 0.12, 0.32), 0.95), (0.0, (0.82, 0.94, 1.0), 1.0)):
        for ax, ay, bx, by, k in arms:
            c.fill(capsule(ax, ay, bx, by, 2.2 * k + grow * 0.95), col, al)
    for ax, ay, bx, by, k in arms:                                                    # the ice catching the light
        c.fill(capsule(ax, ay, bx, by, 0.6 * k), (1.0, 1.0, 1.0), 0.9)
    c.fill(polygon([(32 + math.cos(i * math.pi / 3) * 5.4, 32 + math.sin(i * math.pi / 3) * 5.4) for i in range(6)]),
           (0.05, 0.12, 0.32), 0.95)
    c.fill(polygon([(32 + math.cos(i * math.pi / 3) * 3.6, 32 + math.sin(i * math.pi / 3) * 3.6) for i in range(6)]),
           (0.90, 0.97, 1.0))


def g_ash(c):
    smoke = (0.60, 0.58, 0.58)
    for pts in ([(24, 34), (22, 27), (26, 21), (23, 14)], [(41, 32), (43.4, 25), (40, 19)]):   # smoke still rising
        stroke(c, pts, 1.7, DARK, 0.75)
        stroke(c, pts, 0.9, smoke, 0.9)
    ink(c, [mound((0.60, 0.58, 0.56), (0.20, 0.18, 0.18))])
    paint(c, crescent(32, 62, 28, 2.0, 3.0), (0.82, 0.80, 0.78), 0.45, clip=MOUND)
    for pts in ([(14, 47), (20, 44), (24, 48.4)], [(36, 39), (40, 43), (46, 41.6)], [(26, 38.6), (30, 42)],
                [(44, 48), (50, 46.4)]):                                               # cracks where the embers show
        stroke(c, pts, 1.0, (0.50, 0.14, 0.04), 0.9, clip=MOUND)
        stroke(c, pts, 0.45, LAVA, 1.0, clip=MOUND)
    for cx, cy, r in ((24, 43, 2.0), (37, 46.4, 1.7), (43, 44.4, 2.2), (31, 48.6, 1.4), (17, 49.6, 1.2)):
        c.glow(*circle_sdf(cx, cy, r * 0.5), LAVA, 0.95, r * 1.7)
        c.fill(circle(cx, cy, r * 0.42), LAVA_HI)
    for x, y in ((30, 30), (36, 26.4), (33, 20)):                                     # sparks
        c.fill(circle(x, y, 0.8), LAVA, 0.9)


def g_stone(c):
    parts, blocks = [], []
    for row, y in enumerate((14, 28, 42)):
        off = 0 if row % 2 == 0 else 9
        for x in range(6 - off, 58, 18):
            x0, x1 = max(6, x), min(58, x + 16)
            if x1 - x0 > 4:
                tint = 1.0 - 0.10 * ((x // 18 + row) % 3)
                parts.append((rect(x0, y, x1, y + 12), lit(shade((0.84, 0.80, 0.74), tint), shade((0.44, 0.42, 0.40), tint), x0, y, x1, y + 12)))
                blocks.append((x0, y, x1, y + 12))
    ink(c, parts)
    for x0, y0, x1, y1 in blocks:                                                     # each block bevelled
        c.fill(rect0(x0, y0, x1, y0 + 1.3), (1.0, 0.98, 0.92), 0.55)
        c.fill(rect0(x0, y0, x0 + 1.3, y1), (1.0, 0.98, 0.92), 0.35)
        c.fill(rect0(x0, y1 - 1.5, x1, y1), (0.14, 0.12, 0.12), 0.40)
        c.fill(rect0(x1 - 1.3, y0, x1, y1), (0.14, 0.12, 0.12), 0.28)
    for pts in ([(12, 17), (15, 20.6), (13.6, 24)], [(47, 31), (50, 35), (53.6, 36)], [(30, 45), (33, 49.6)]):
        stroke(c, pts, 0.45, (0.22, 0.20, 0.20), 0.75)                                # cracks
    c.fill(polygon([(40, 14), (45, 14), (42, 17.4)]), (0.20, 0.18, 0.18), 0.7)        # a chipped corner
    for x, y, r in ((9, 52.6, 1.6), (26, 39.4, 1.3), (55, 25.4, 1.2)):                # moss in the joints
        c.fill(circle(x, y, r), (0.40, 0.58, 0.28), 0.8)


# ---------------------------------------------------------------- water
def river_band(grow=0.0, shift=0.0):
    def band(dx, dy):
        def inside(x, y):
            mid = 32 + dy + shift + 10 * math.sin((x - dx) / 52 * 2 * math.pi)
            half = 5 + (x - 6) / 52 * 4 + grow
            return 6 + dx <= x <= 58 + dx and abs(y - mid) <= half
        return inside, (6 + dx, 12 + dy, 58 + dx, 52 + dy)
    return band


def w_river(c):
    bank = lit((0.56, 0.78, 0.34), (0.22, 0.42, 0.16), 6, 12, 58, 52)
    ink(c, [(river_band(3.4), bank), (river_band(), lit(BLUE_HI, BLUE_DARK, 6, 14, 58, 50))])
    water = river_band()(0, 0)
    lower = river_band(0, 2.2)(0, 0)[0]
    paint(c, water, BLUE_DARK, 0.40, clip=((lambda x, y: not lower(x, y)), None))    # the far bank's shadow on the water
    mid = lambda x: 32 + 10 * math.sin(x / 52 * 2 * math.pi)
    for x0, x1, off in ((9, 19, -1.6), (24, 36, 1.8), (40, 54, -2.0), (14, 24, 2.4), (44, 52, 3.2)):   # the current
        pts = [(x, mid(x) + off) for x in range(x0, x1 + 1, 2)]
        stroke(c, pts, 0.5, FOAM, 0.8, clip=water)
    for x, off, r in ((30, -1.4, 2.0), (47, 0.6, 1.7)):                               # stones breaking it
        dot(c, x, mid(x) + off, r, (0.62, 0.62, 0.66), (0.16, 0.18, 0.26))
        stroke(c, [(x + r, mid(x) + off + 0.8), (x + r + 3, mid(x + 3) + off + 1.2)], 0.4, FOAM, 0.85)
    for x, off in ((12, -8.6), (26, 10.6), (44, 9.4), (52, -10.6)):                   # tufts on the banks
        y = mid(x) + off
        for d in (-1.2, 0, 1.2):
            stroke(c, [(x, y), (x + d, y - 2.6)], 0.4, (0.16, 0.34, 0.12), 0.9)


def w_lake(c):
    ink(c, [(oval(32, 37, 27, 16), lit((0.62, 0.82, 0.38), (0.24, 0.44, 0.16), 5, 21, 59, 53)),
            (oval(32, 37.4, 23, 12.4), lit(BLUE_HI, BLUE_DARK, 9, 25, 55, 50))])
    water = oval0(32, 37.4, 23, 12.4)
    paint(c, (lambda x, y: ((x - 33) / 21.6) ** 2 + ((y - 38.8) / 11) ** 2 > 1, None), (0.78, 0.92, 1.0), 0.45, clip=water)
    c.fill(oval0(35, 40, 14, 6), BLUE_DARK, 0.35)                                     # the deep middle
    for a, b in (((16, 34), (27, 32.4)), ((33, 42), (43, 41)), ((24, 44.4), (30, 44)), ((38, 33), (46, 32.4))):
        stroke(c, [a, b], 0.6, FOAM, 0.8, clip=water)
    ink(c, [(caps(50, 33, 50, 22, 0.8), GREEN), (caps(50, 23, 50, 18.6, 1.9), BROWN),
            (caps(54, 35, 54.6, 26, 0.8), GREEN), (caps(54.6, 27, 54.8, 23.4, 1.7), BROWN),
            (caps(47, 34, 45, 27, 0.8), (0.50, 0.76, 0.32))], 1.5)                    # reeds on the shore
    for x, y in ((14, 41), (19, 44.6)):                                              # lily pads
        c.fill(oval0(x, y, 2.8, 1.4), (0.16, 0.36, 0.14))
        c.fill(oval0(x, y - 0.3, 2.2, 1.0), (0.50, 0.76, 0.32))
    dot(c, 18.6, 43.6, 0.8, (1.0, 0.80, 0.90))


def w_sea(c):
    ink(c, [(wave_band(20, 4, 20, 4.6), lit(BLUE_HI, BLUE, 6, 12, 58, 28)),
            (wave_band(34, 4, 20, 4.6, 6, 58, 1.2), lit((0.44, 0.70, 0.98), (0.20, 0.42, 0.76), 6, 26, 58, 42)),
            (wave_band(48, 4, 20, 4.6, 6, 58, 2.4), lit(BLUE, BLUE_DARK, 6, 40, 58, 56))])
    for y, ph in ((20, 0.0), (34, 1.2), (48, 2.4)):
        band = wave_band(y, 4, 20, 4.6, 6, 58, ph)(0, 0)
        paint(c, wave_band(y - 3.5, 4, 20, 1.1, 6, 58, ph)(0, 0), FOAM, 0.9, clip=band)        # foam on each crest
        paint(c, wave_band(y + 3.4, 4, 20, 1.2, 6, 58, ph)(0, 0), (0.06, 0.16, 0.40), 0.35, clip=band)   # and its trough


def w_marsh(c):
    parts = [(wave_band(48, 1.2, 16, 6), lit((0.46, 0.66, 0.72), (0.14, 0.28, 0.34), 6, 40, 58, 56))]
    for x, top, lean in ((16, 26, -2), (24, 20, 0), (33, 13, 1), (42, 22, 2), (50, 28, 3)):
        parts.append((caps(x, 46, x + lean, top, 1.2), lit((0.56, 0.80, 0.34), GREEN_DARK, x - 4, top, x + 6, 46)))
    for x, top in ((24, 20), (33, 13), (42.4, 22)):
        parts.append((caps(x, top + 7, x + (0.6 if x > 30 else 0), top, 2.6), lit((0.66, 0.44, 0.22), BROWN_DARK, x - 3, top, x + 3, top + 8)))
    parts += [(poly([(28, 46), (30, 46), (36, 32), (33, 36)]), GREEN), (poly([(38, 46), (40, 46), (37, 30), (36.6, 36)]), GREEN_DARK)]
    ink(c, parts)
    band = wave_band(48, 1.2, 16, 6)(0, 0)
    for x, top in ((24, 20), (33, 13), (42.4, 22)):
        stroke(c, [(x - 0.8, top + 6), (x - 0.8, top + 1)], 0.5, (0.90, 0.68, 0.40), 0.7)
        stroke(c, [(x, top - 1), (x, top - 4)], 0.4, (0.30, 0.20, 0.10))
    for a, b in (((8, 45.6), (17, 45.6)), ((44, 50), (55, 50)), ((20, 52), (30, 52))):   # still, weedy water
        stroke(c, [a, b], 0.5, (0.80, 0.94, 0.96), 0.75, clip=band)
    for x, y in ((12, 50.4), (38, 51), (52, 46.4)):
        c.fill(oval0(x, y, 3.0, 1.4), (0.14, 0.32, 0.14))
        c.fill(oval0(x, y - 0.3, 2.4, 1.0), (0.48, 0.74, 0.32))
    for x, y in ((27, 48), (46, 53), (17, 53.4)):                                     # duckweed
        c.fill(circle(x, y, 0.8), (0.56, 0.80, 0.36), 0.9)


def w_none(c):
    keep = lambda x, y: y >= 34
    bowl = (lambda x, y: (x - 32) ** 2 + (y - 30) ** 2 <= 24 * 24 and y >= 34, (8, 34, 56, 54))
    ink(c, [(clipped(circ(32, 30, 24), keep), lit(SAND, SAND_DARK, 8, 34, 56, 54)),
            (rect(8, 31, 56, 36), lit((0.86, 0.70, 0.44), SAND_DARK))])
    c.fill(rect0(8, 31, 56, 32.4), SAND_HI, 0.7)
    paint(c, crescent(32, 30, 24, -2.4, -2.6), shade(SAND_DARK, 0.7), 0.4, clip=bowl)
    cracks = ([(14, 37), (20, 40.4), (26, 44), (24, 49.6)], [(20, 40.4), (16, 44.6)], [(40, 36.6), (37, 41), (41, 46), (38, 51)],
              [(26, 44), (32, 45.4), (37, 41)], [(41, 46), (47, 44.4), (50, 39)], [(32, 45.4), (31, 52)], [(47, 44.4), (48, 48.6)])
    for pts in cracks:                                                                # cracked, dried mud
        stroke(c, pts, 0.9, (0.30, 0.18, 0.08), 0.95, clip=bowl)
    for pts in cracks:
        stroke(c, [(x + 0.9, y + 0.9) for x, y in pts], 0.35, SAND_HI, 0.7, clip=bowl)
    ink(c, [(caps(22, 31, 20, 20, 0.9), (0.52, 0.40, 0.26)), (caps(21, 25.4, 16, 21, 0.7), (0.52, 0.40, 0.26)),
            (caps(21.4, 27.6, 25.6, 23, 0.7), (0.52, 0.40, 0.26))], 1.5)             # a dead twig
    ink(c, [(oval(42, 28.4, 3.6, 3.0), (0.94, 0.92, 0.84)), (rect(40.4, 30, 43.6, 32.4), (0.94, 0.92, 0.84))], 1.5)   # and a skull
    for x in (40.6, 43.4):
        c.fill(circle(x, 28.4, 0.9), DARK)


# ---------------------------------------------------------------- wildness
def wl_settled(c):
    wall = lit((0.96, 0.90, 0.74), (0.60, 0.52, 0.40), 14, 30, 50, 55)
    stroke(c, [(43, 11), (45.4, 6.4), (42.6, 2.4)], 1.7, DARK, 0.7)                   # smoke from the chimney
    stroke(c, [(43, 11), (45.4, 6.4), (42.6, 2.4)], 0.9, (0.78, 0.78, 0.80), 0.9)
    ink(c, [(rect(40, 13, 46, 27), lit(GREY, GREY_DARK, 40, 13, 46, 27)), (rect(14, 30, 50, 55), wall),
            (poly([(32, 10), (57, 33), (7, 33)]), lit((0.90, 0.46, 0.24), RED_DARK, 7, 10, 57, 33))])
    c.fill(rect0(39.4, 13, 46.6, 15), (0.80, 0.80, 0.82))
    for y in (17, 22, 27):                                                            # rows of tiles
        half = (y - 10) * 25 / 23 - 2
        stroke(c, [(32 - half, y), (32 + half, y)], 0.4, RED_DARK, 0.7)
    c.fill(polygon([(32, 10), (57, 33), (38, 33)]), RED_DARK, 0.35)
    c.fill(rect0(14, 33, 50, 35.4), (0.36, 0.28, 0.20), 0.45)                         # the eaves' shadow
    for x in (14, 31.4, 48.4):                                                        # timber framing
        c.fill(rect0(x, 33, x + 1.6, 55), (0.42, 0.28, 0.14))
    c.fill(rect0(14, 43.4, 50, 44.8), (0.42, 0.28, 0.14))
    c.fill(rect0(35.6, 44, 43.6, 55), DARK)                                           # door
    c.fill(rect0(36.6, 45, 42.6, 55), lit((0.66, 0.44, 0.22), BROWN_DARK, 36, 45, 43, 55))
    c.fill(circle(41.2, 50.4, 0.7), (1.0, 0.86, 0.40))
    c.fill(rect0(18.4, 36.4, 27.6, 42.4), DARK)                                       # a lit window
    c.fill(rect0(19.4, 37.4, 26.6, 41.4), (1.0, 0.86, 0.42))
    c.fill(rect0(22.6, 37.4, 23.4, 41.4), DARK); c.fill(rect0(19.4, 39, 26.6, 39.8), DARK)
    ink(c, [(rect(52, 48, 53.6, 57), BROWN), (rect(57, 48, 58.6, 57), BROWN), (rect(50.6, 50.4, 60, 52), BROWN),
            (rect(5.4, 48, 7, 57), BROWN), (rect(10.4, 48, 12, 57), BROWN), (rect(4, 50.4, 13.4, 52), BROWN)], 1.3)   # fence


def wl_frontier(c):
    wood = lambda x: lit((0.80, 0.58, 0.32), BROWN_DARK, x - 5, 14, x + 5, 56)
    parts, stakes = [], []
    parts += [(caps(31.6, 16, 31.6, 4, 0.7), DARK), (poly([(32.2, 4), (43, 6.6), (32.2, 10)]), (0.84, 0.20, 0.14))]
    for i, x in enumerate((10, 20.6, 31.2, 41.8, 52.4)):
        h = (22, 17, 14, 18, 23)[i]
        stakes.append((x, h))
        parts.append((poly([(x - 4.7, 56), (x + 4.7, 56), (x + 4.7, h + 7), (x, h), (x - 4.7, h + 7)]), wood(x)))
    parts.append((rect(4, 33, 58.4, 37.6), lit((0.66, 0.44, 0.22), BROWN_DARK, 4, 33, 58, 38)))
    parts.append((rect(4, 46.4, 58.4, 50.4), lit((0.62, 0.42, 0.20), BROWN_DARK, 4, 46, 58, 50)))
    ink(c, parts)
    c.fill(polygon([(32.2, 7), (43, 6.6), (32.2, 10)]), (0.50, 0.08, 0.06), 0.5)
    for x, h in stakes:
        c.fill(polygon([(x, h), (x + 4.7, h + 7), (x + 4.7, 56), (x + 2.0, 56), (x + 2.0, h + 3)]), (0.20, 0.11, 0.04), 0.35)
        stroke(c, [(x - 3.0, h + 8), (x - 3.0, 32)], 0.45, (0.96, 0.78, 0.50), 0.6)   # the lit edge of each stake
        for y0, y1 in ((39.6, 45), (52, 55)):                                         # grain
            stroke(c, [(x - 0.6, y0), (x - 0.2, y1)], 0.35, (0.26, 0.15, 0.06), 0.65)
        for y in (35.3, 48.4):                                                        # nails
            c.fill(circle(x, y, 0.8), (0.20, 0.18, 0.18))
            c.fill(circle(x - 0.25, y - 0.25, 0.3), (0.80, 0.80, 0.84))
    c.fill(rect0(4, 33, 58.4, 34), (0.96, 0.78, 0.50), 0.5)
    c.fill(rect0(4, 46.4, 58.4, 47.3), (0.96, 0.78, 0.50), 0.45)


def wl_wild(c):
    paw = lit((0.86, 0.74, 0.56), BROWN_DARK, 8, 8, 56, 60)
    toes = ((15.4, 30, 5.4, 6.6), (25.6, 19.4, 5.6, 6.8), (38.4, 19.4, 5.6, 6.8), (48.6, 30, 5.4, 6.6))
    claws = []
    for x, y, rx, ry in toes:                                                         # claws
        tx = x + (x - 32) * 0.16
        claws.append((poly([(x - 1.9, y - ry + 1.4), (x + 1.9, y - ry + 1.4), (tx, y - ry - 5.6)]), (0.94, 0.92, 0.84)))
    pad = lambda dx, dy: ((lambda x, y: ((x - 32 - dx) / 13.4) ** 2 + ((y - 44 - dy) / 10.6) ** 2 <= 1
                           or (x - 23.4 - dx) ** 2 + (y - 49 - dy) ** 2 <= 36 or (x - 40.6 - dx) ** 2 + (y - 49 - dy) ** 2 <= 36),
                          (17, 32, 47, 56))
    ink(c, claws + [(pad, paw)] + [(oval(x, y, rx, ry), paw) for x, y, rx, ry in toes])
    for x, y, rx, ry in toes:
        c.fill(oval0(x - rx * 0.28, y - ry * 0.34, rx * 0.42, ry * 0.36), (1.0, 0.92, 0.76), 0.6)
        paint(c, (lambda px, py, x=x, y=y, rx=rx, ry=ry: ((px - x + 1.2) / rx) ** 2 + ((py - y + 1.6) / ry) ** 2 > 1, None),
              (0.22, 0.12, 0.05), 0.40, clip=oval0(x, y, rx, ry))
    c.fill(oval0(28, 39.6, 6.4, 3.6), (1.0, 0.92, 0.76), 0.5)
    paint(c, (lambda x, y: ((x - 30.4) / 13.4) ** 2 + ((y - 42) / 10.6) ** 2 > 1, None), (0.22, 0.12, 0.05), 0.38, clip=pad(0, 0))
    for pts in ([(26, 45), (32, 47), (38, 45)],):                                     # the crease in the pad
        stroke(c, pts, 0.5, (0.30, 0.18, 0.08), 0.55)


# sky, haze, ground (or None) behind each of the other icons: close views, so mostly dark
OTHER_BG = {
    ("ground", "soil"): ((0.20, 0.38, 0.62), (0.70, 0.78, 0.66), (0.22, 0.14, 0.07)),
    ("ground", "mud"): ((0.12, 0.10, 0.08), (0.36, 0.28, 0.18), (0.16, 0.11, 0.06)),
    ("ground", "sand"): ((0.24, 0.48, 0.82), (1.0, 0.90, 0.68), (0.74, 0.56, 0.28)),
    ("ground", "rock"): ((0.17, 0.22, 0.30), (0.54, 0.58, 0.62), (0.20, 0.20, 0.22)),
    ("ground", "snow"): ((0.07, 0.14, 0.32), (0.30, 0.48, 0.74), None),
    ("ground", "ash"): ((0.09, 0.05, 0.05), (0.44, 0.17, 0.08), (0.11, 0.09, 0.09)),
    ("ground", "stone"): ((0.13, 0.12, 0.11), (0.30, 0.28, 0.25), None),
    ("water", "river"): ((0.15, 0.32, 0.14), (0.40, 0.58, 0.26), None),
    ("water", "lake"): ((0.14, 0.30, 0.13), (0.38, 0.56, 0.25), None),
    ("water", "sea"): ((0.05, 0.13, 0.33), (0.15, 0.33, 0.62), None),
    ("water", "marsh"): ((0.13, 0.21, 0.18), (0.50, 0.60, 0.44), (0.08, 0.17, 0.18)),
    ("water", "none"): ((0.30, 0.46, 0.72), (1.0, 0.88, 0.64), (0.60, 0.42, 0.21)),
    ("wild", "settled"): ((0.22, 0.44, 0.80), (0.92, 0.91, 0.78), (0.24, 0.40, 0.13)),
    ("wild", "frontier"): ((0.27, 0.36, 0.54), (0.96, 0.78, 0.56), (0.32, 0.25, 0.11)),
    ("wild", "wild"): ((0.06, 0.12, 0.07), (0.24, 0.34, 0.16), None),
}

OTHER = {
    "ground": {"soil": g_soil, "mud": g_mud, "sand": g_sand, "rock": g_rock, "snow": g_snow,
               "ash": g_ash, "stone": g_stone},
    "water": {"river": w_river, "lake": w_lake, "sea": w_sea, "marsh": w_marsh, "none": w_none},
    "wild": {"settled": wl_settled, "frontier": wl_frontier, "wild": wl_wild},
}


# ---------------------------------------------------------------- addon-list icon
def geography_emblem(c):
    """Mountains over a winding river, in the suite medallion."""
    global K
    K = N / 64.0
    c.fill(polygon([(30, 18), (50, 46), (10, 46)]), lit(GREY, GREY_DARK, 10 * K, 18 * K, 50 * K, 46 * K))
    c.fill(polygon([(30, 18), (35, 25), (30, 23), (25, 26)]), SNOW)
    c.fill(polygon([(44, 26), (58, 46), (30, 46)]), lit((0.58, 0.58, 0.62), GREY_DARK, 30 * K, 26 * K, 58 * K, 46 * K))
    c.fill(polygon([(44, 26), (48, 31), (44, 30), (40, 32)]), SNOW)
    c.fill(polygon([(4, 44), (60, 44), (60, 60), (4, 60)]), (0.36, 0.58, 0.24))
    for y in range(44 * 8, 60 * 8):
        yy = y / 8.0
        mid = 32 + 6 * math.sin((yy - 44) / 16 * math.pi * 1.2)
        half = 1.5 + (yy - 44) / 16 * 4
        c.fill(capsule(mid - half, yy, mid + half, yy, 0.3), (0.45, 0.72, 0.98))


def main():
    global K
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith(".tga"):
            os.remove(os.path.join(OUT, f))
    K = N / 64.0
    suite_icon("icon", (0.22, 0.42, 0.66), (0.70, 0.78, 0.52), geography_emblem)
    seed = 0
    for terrain, draw in TERRAIN.items():
        for tone in TERRAIN_TONES[terrain]:
            seed += 1
            pal = terrain_palette(terrain, tone)
            c = small_canvas()
            backdrop(c, *pal["bg"], seed=seed)
            draw(c, pal)
            finish(c, seed)
            c.save("land_terrain_" + terrain + ("_" + tone if tone else ""))
    for facet, values in OTHER.items():
        for value, draw in values.items():
            seed += 1
            c = small_canvas()
            backdrop(c, *OTHER_BG[(facet, value)], seed=seed)
            draw(c)
            finish(c, seed)
            c.save("land_%s_%s" % (facet, value))
    print("wrote", len(os.listdir(OUT)), "files to", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
