from manim import *
import numpy as np

config.background_color = "#000000"

INK = "#FFFFFF"
DOT = "#FFE600"
WIRE = 4
FONT = "Helvetica"

SPACING = 0.30
SPEED = 3.2
DOT_R = 0.075
HOLD = 4.5


OFFSET = np.array([-0.4, -0.1, 0.0])

TABLE_LEFT, TABLE_TOP = 4.3, 1.4
COLS, ROW_H = [0.72, 0.72, 1.1], 0.58


def P(x, y):
    return np.array([x, y, 0.0]) + OFFSET


def poly(*pts):
    m = VMobject(stroke_color=INK, stroke_width=WIRE)
    m.set_points_as_corners([P(*p) for p in pts])
    return m


def zigzag_pts(a, b, n=3, amp=0.17):
    a, b = np.array(a, float), np.array(b, float)
    d = b - a
    perp = np.array([-d[1], d[0]]) / np.linalg.norm(d)
    pts = [a, a + 0.1 * d]
    for i in range(2 * n):
        t = 0.1 + 0.8 * (i + 0.5) / (2 * n)
        pts.append(a + t * d + (amp if i % 2 == 0 else -amp) * perp)
    pts += [a + 0.9 * d, b]
    return [tuple(p) for p in pts]


def triangle(tip, direction, length=0.2, half_width=0.09):
    tip = P(*tip)
    u = np.array([*direction, 0.0], float)
    u /= np.linalg.norm(u)
    perp = np.array([-u[1], u[0], 0.0])
    base = tip - length * u
    return Polygon(tip, base + half_width * perp, base - half_width * perp,
                   stroke_color=INK, stroke_width=1, fill_color=INK, fill_opacity=1)


def label(s, size=30, **kw):
    return Text(s, font=FONT, font_size=size, color=INK, **kw)


def junction(x, y):
    return Dot(P(x, y), radius=0.065, color=INK)


def terminal(x, y):
    return Circle(radius=0.09, stroke_color=INK, stroke_width=3,
                  fill_color="#000000", fill_opacity=1).move_to(P(x, y))


def ground(x, y):
    return VGroup(*[
        Line(P(x - w, y - i * 0.1), P(x + w, y - i * 0.1), stroke_color=INK, stroke_width=WIRE)
        for i, w in enumerate([0.26, 0.16, 0.06])
    ])


def vcc(x, y_bottom, y_tip):
    return VGroup(
        Line(P(x, y_bottom), P(x, y_tip - 0.18), stroke_color=INK, stroke_width=WIRE),
        triangle((x, y_tip), (0, 1)),
        label("+Vcc", 28).move_to(P(x, y_tip + 0.25)),
    )


def transistor(tx, ty, r=0.5):
    k = dict(
        base_in=(tx - r, ty),
        bar_m=(tx - 0.2, ty),
        bar_c=(tx - 0.2, ty + 0.12),
        bar_e=(tx - 0.2, ty - 0.12),
        C=(tx + 0.25, ty + 0.43),
        E=(tx + 0.25, ty - 0.43),
    )
    be = np.array(k["bar_e"])
    ee = np.array(k["E"])
    tip = be + 0.8 * (ee - be)
    g = VGroup(
        Circle(radius=r, stroke_color=INK, stroke_width=WIRE).move_to(P(tx, ty)),
        poly(k["base_in"], k["bar_m"]),
        Line(P(tx - 0.2, ty - 0.28), P(tx - 0.2, ty + 0.28), stroke_color=INK, stroke_width=7),
        poly(k["bar_c"], k["C"]),
        poly(k["bar_e"], k["E"]),
        triangle(tuple(tip), tuple(ee - be), length=0.19, half_width=0.085),
    )
    return g, k


def input_branch(name, x_term, y, x_base):
    x0 = x_term + 0.09
    zig = zigzag_pts((-3.0, y), (-1.6, y))
    g = VGroup(
        terminal(x_term, y),
        poly((x0, y), (-3.0, y)),
        poly(*zig),
        poly((-1.6, y), (x_base, y)),
        label("R", 28).move_to(P(-2.3, y + 0.45)),
    )
    return g, [(x0, y), (-3.0, y), *zig, (-1.6, y), (x_base, y)]


class Flow(VGroup):
    def __init__(self, pts, clock, D=0.0, **kw):
        super().__init__(**kw)
        p = np.array([P(*q) for q in pts])
        keep = [0] + [i for i in range(1, len(p)) if np.linalg.norm(p[i] - p[i - 1]) > 1e-9]
        self.pts = p[keep]
        self.cum = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(self.pts, axis=0), axis=1))])
        self.L = self.cum[-1]
        self.D = D
        self.clock = clock
        self.born = clock.get_value()
        self.dying = None
        for _ in range(int(np.ceil(self.L / SPACING)) + 1):
            self.add(Dot(radius=DOT_R, color=DOT))
        self.add_updater(lambda m: m.refresh())
        self.refresh()

    def point_at(self, s):
        i = int(np.clip(np.searchsorted(self.cum, s, side="right") - 1, 0, len(self.pts) - 2))
        t = (s - self.cum[i]) / (self.cum[i + 1] - self.cum[i])
        return self.pts[i] + t * (self.pts[i + 1] - self.pts[i])

    def refresh(self):
        T = self.clock.get_value()
        op = min(1.0, (T - self.born) / 0.2)
        if self.dying is not None:
            op = min(op, max(0.0, 1 - (T - self.dying) / 0.2))
        base = (T * SPEED - self.D) % SPACING
        for i, d in enumerate(self.submobjects):
            x = base + i * SPACING
            if x <= self.L:
                d.move_to(self.point_at(x))
                d.set_opacity(op)
            else:
                d.set_opacity(0)


class RTLGate(Scene):
    title = ""

    def build(self):
        raise NotImplementedError

    def construct(self):
        self.clock = ValueTracker(0)
        self.clock.add_updater(lambda m, dt: m.increment_value(dt))
        self.add(self.clock)

        watermark = Text("PARTH", font=FONT, weight=BOLD, color=INK)
        watermark.scale_to_fit_width(11).rotate(20 * DEGREES).set_opacity(0.14).set_z_index(-1)
        self.add(watermark)

        circuit, texts, self.segs, combos = self.build()
        self.seg_len = {k: Flow(v, self.clock).L for k, v in self.segs.items()}

        title = label(self.title, 38, weight=BOLD).to_corner(UL, buff=0.45)
        table = self.empty_table()
        self.play(Create(circuit), Write(texts), Write(title), Create(table), run_time=2.5)

        state = None
        highlight = None
        flows = []
        for row, combo in enumerate(combos, start=1):
            new_state = self.state_labels(combo)
            new_highlight = Rectangle(width=sum(COLS), height=ROW_H, stroke_color=DOT, stroke_width=5)
            new_highlight.move_to([TABLE_LEFT + sum(COLS) / 2, self.cell(row, 0)[1], 0])
            if state is None:
                self.play(*[Write(m) for m in new_state], Create(new_highlight), run_time=0.5)
                state, highlight = new_state, new_highlight
            else:
                for f in flows:
                    f.dying = self.clock.get_value()
                self.play(*[Transform(o, n) for o, n in zip(state, new_state)],
                          Transform(highlight, new_highlight), run_time=0.4)
                self.remove(*flows)

            flows = self.make_flows(combo["chains"], combo.get("bases", {}))
            self.add(*flows)
            self.wait(HOLD - 1.0)

            a, b = combo["AB"]
            values = [label(str(v), 32).move_to(self.cell(row, col))
                      for col, v in enumerate([a, b, combo["Q"]])]
            self.play(*[Write(v) for v in values], run_time=0.5)
            self.wait(0.5)

        for f in flows:
            f.dying = self.clock.get_value()
        self.play(FadeOut(highlight), run_time=0.4)
        self.wait(1.5)

    def cell(self, row, col):
        return np.array([TABLE_LEFT + sum(COLS[:col]) + COLS[col] / 2, TABLE_TOP - (row + 0.5) * ROW_H, 0.0])

    def empty_table(self):
        x0, x1 = TABLE_LEFT, TABLE_LEFT + sum(COLS)
        y0, y1 = TABLE_TOP, TABLE_TOP - 5 * ROW_H
        lines = VGroup(Rectangle(width=x1 - x0, height=y0 - y1, stroke_color=INK, stroke_width=4)
                       .move_to([(x0 + x1) / 2, (y0 + y1) / 2, 0]))
        for r in range(1, 5):
            y = y0 - r * ROW_H
            lines.add(Line([x0, y, 0], [x1, y, 0], stroke_color=INK, stroke_width=4 if r == 1 else 2.5))
        for c in range(1, 3):
            x = x0 + sum(COLS[:c])
            lines.add(Line([x, y0, 0], [x, y1, 0], stroke_color=INK, stroke_width=4 if c == 2 else 2.5))
        headers = VGroup(*[label(h, 30, weight=BOLD).move_to(self.cell(0, c))
                           for c, h in enumerate(["A", "B", "OUT"])])
        return VGroup(lines, headers)

    def make_flows(self, chains, bases):
        D = {}
        for chain in chains:
            prev = None
            for k in chain:
                if k not in D:
                    D[k] = 0.0 if prev is None else D[prev] + self.seg_len[prev]
                prev = k
        for b, target in bases.items():
            D[b] = D[target] - self.seg_len[b]
        return [Flow(self.segs[k], self.clock, D[k]) for k in D]

    def state_labels(self, combo):
        a, b = combo["AB"]
        pos = self.pos
        mobs = [
            label(f"A = {a}", 32).next_to(P(*pos["A"]), LEFT, buff=0.25),
            label(f"B = {b}", 32).next_to(P(*pos["B"]), LEFT, buff=0.25),
            label(f"OUT = {combo['Q']}", 30).next_to(P(*pos["OUT"]), UP, buff=0.2),
            label(f"T1  {'ON' if a else 'OFF'}", 28),
            label(f"T2  {'ON' if b else 'OFF'}", 28),
        ]
        side, (x1, y1), (x2, y2) = pos["T"]
        if side == "left":
            mobs[3].move_to(P(x1, y1), aligned_edge=RIGHT)
            mobs[4].move_to(P(x2, y2), aligned_edge=RIGHT)
        else:
            mobs[3].move_to(P(x1, y1), aligned_edge=LEFT)
            mobs[4].move_to(P(x2, y2), aligned_edge=LEFT)
        return mobs


def overlined_q(expr):
    q = label("Q = ", 30)
    e = label(expr, 30)
    g = VGroup(q, e).arrange(RIGHT, buff=0.12)
    bar = Line(e.get_corner(UL) + UP * 0.08, e.get_corner(UR) + UP * 0.08, stroke_color=INK, stroke_width=3)
    return VGroup(q, e, bar)


class NORGate(RTLGate):
    title = "NOR using RTL"

    def build(self):
        ty1, ty2 = 0.1, -2.0
        xc, xg = 0.85, 1.5
        yN, yJ1, yb, ye1, ye2, yg = 1.6, 0.9, -1.2, -0.75, -2.75, -3.1
        hop = 0.13
        x_out = xc + 1.9

        t1, k1 = transistor(0, ty1)
        t2, k2 = transistor(0, ty2)
        inA, fA = input_branch("A", -4.0, ty1, k1["base_in"][0])
        inB, fB = input_branch("B", -4.0, ty2, k2["base_in"][0])
        r2 = zigzag_pts((xc, 3.1), (xc, 2.0))
        hop_pts = [(xc + hop * np.cos(t), ye1 + hop * np.sin(t)) for t in np.linspace(PI, 0, 14)]

        circuit = VGroup(
            vcc(xc, 3.1, 3.5),
            poly(*r2),
            poly((xc, 2.0), (xc, yN)),
            poly((xc, yN), (x_out, yN)),
            triangle((x_out + 0.2, yN), (1, 0)),
            t1, t2, inA, inB,
            poly(k1["C"], (0.25, yJ1), (xc, yJ1)),
            poly((xc, yN), (xc, yb), (0.25, yb), k2["C"]),
            poly(k1["E"], (0.25, ye1), (xc - hop, ye1)),
            Arc(radius=hop, start_angle=PI, angle=-PI, arc_center=P(xc, ye1),
                stroke_color=INK, stroke_width=WIRE),
            poly((xc + hop, ye1), (xg, ye1), (xg, yg)),
            poly(k2["E"], (0.25, ye2), (xg, ye2)),
            ground(xg, yg),
            junction(xc, yN), junction(xc, yJ1), junction(xg, ye2),
        )
        texts = VGroup(
            label("R2", 28).move_to(P(xc + 0.62, 2.55)),
            overlined_q("A+B").next_to(P(x_out, yN), DOWN, buff=0.25),
            label("Transistor\nSwitches", 28).move_to(P(3.4, -0.9)),
        )

        segs = {
            "vcc": [(xc, 3.3), *r2, (xc, yN)],
            "out": [(xc, yN), (x_out + 0.05, yN)],
            "bus1": [(xc, yN), (xc, yJ1)],
            "T1c": [(xc, yJ1), (0.25, yJ1), k1["C"], k1["bar_c"], k1["bar_m"]],
            "T1e": [k1["bar_m"], k1["bar_e"], k1["E"], (0.25, ye1), (xc - hop, ye1),
                    *hop_pts, (xc + hop, ye1), (xg, ye1)],
            "rail1": [(xg, ye1), (xg, ye2)],
            "bus2": [(xc, yJ1), (xc, yb), (0.25, yb), k2["C"], k2["bar_c"], k2["bar_m"]],
            "T2e": [k2["bar_m"], k2["bar_e"], k2["E"], (0.25, ye2), (xg, ye2)],
            "gnd": [(xg, ye2), (xg, yg)],
            "baseA": fA + [k1["bar_m"]],
            "baseB": fB + [k2["bar_m"]],
        }
        to_t1 = ["vcc", "bus1", "T1c", "T1e", "rail1", "gnd"]
        combos = [
            dict(AB=(0, 0), Q=1, chains=[["vcc", "out"]]),
            dict(AB=(0, 1), Q=0, chains=[["vcc", "bus1", "bus2", "T2e", "gnd"]], bases={"baseB": "T2e"}),
            dict(AB=(1, 0), Q=0, chains=[to_t1], bases={"baseA": "T1e"}),
            dict(AB=(1, 1), Q=0, chains=[to_t1, ["bus1", "bus2", "T2e"]],
                 bases={"baseA": "T1e", "baseB": "T2e"}),
        ]
        self.pos = dict(
            A=(-4.1, ty1), B=(-4.1, ty2), OUT=(x_out, yN),
            T=("left", (-0.2, ty1 + 0.75), (-0.2, ty2 - 0.75)),
        )
        return circuit, texts, segs, combos


class NANDGate(RTLGate):
    title = "NAND using RTL"

    def build(self):
        ty1, ty2 = 0.2, -1.9
        x = 0.25
        yN, yg = 1.4, -3.0
        x_out = 2.15

        t1, k1 = transistor(0, ty1)
        t2, k2 = transistor(0, ty2)
        inA, fA = input_branch("A", -4.0, ty1, k1["base_in"][0])
        inB, fB = input_branch("B", -4.0, ty2, k2["base_in"][0])
        r2 = zigzag_pts((x, 3.1), (x, 2.0))

        circuit = VGroup(
            vcc(x, 3.1, 3.5),
            poly(*r2),
            poly((x, 2.0), (x, yN), k1["C"]),
            poly((x, yN), (x_out, yN)),
            triangle((x_out + 0.2, yN), (1, 0)),
            t1, t2, inA, inB,
            poly(k1["E"], k2["C"]),
            poly(k2["E"], (x, yg)),
            ground(x, yg),
            junction(x, yN),
        )
        texts = VGroup(
            label("R2", 28).move_to(P(x + 0.62, 2.55)),
            overlined_q("A·B").next_to(P(x_out, yN), DOWN, buff=0.25),
            label("Transistor\nSwitches", 28).move_to(P(3.0, -0.85)),
        )

        segs = {
            "vcc": [(x, 3.3), *r2, (x, yN)],
            "out": [(x, yN), (x_out + 0.05, yN)],
            "T1c": [(x, yN), k1["C"], k1["bar_c"], k1["bar_m"]],
            "T1e": [k1["bar_m"], k1["bar_e"], k1["E"], k2["C"], k2["bar_c"], k2["bar_m"]],
            "T2e": [k2["bar_m"], k2["bar_e"], k2["E"], (x, yg)],
            "baseA": fA + [k1["bar_m"]],
            "baseB": fB + [k2["bar_m"]],
        }
        combos = [
            dict(AB=(0, 0), Q=1, chains=[["vcc", "out"]]),
            dict(AB=(0, 1), Q=1, chains=[["vcc", "out"], ["baseB", "T2e"]]),
            dict(AB=(1, 0), Q=1, chains=[["vcc", "out"]]),
            dict(AB=(1, 1), Q=0, chains=[["vcc", "T1c", "T1e", "T2e"]],
                 bases={"baseA": "T1e", "baseB": "T2e"}),
        ]
        self.pos = dict(
            A=(-4.1, ty1), B=(-4.1, ty2), OUT=(x_out, yN),
            T=("right", (0.75, ty1), (0.75, ty2)),
        )
        return circuit, texts, segs, combos
