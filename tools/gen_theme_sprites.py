"""Draw a shared pixel-art sprite collection on integer grids."""

import argparse
import math
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PALETTE = {
    'canvas': '#0d0d10',
    'outline': '#1a1510',
    'soil': '#29241f',
    'wood_dark': '#493226',
    'wood': '#76513a',
    'wood_light': '#a57a4c',
    'stone_dark': '#414444',
    'stone': '#696e68',
    'stone_light': '#9ca38c',
    'moss_dark': '#344436',
    'moss': '#63744c',
    'ghost_shade': '#8daba0',
    'ghost': '#c6d2b4',
    'bone': '#eee1b5',
    'bone_dim': '#ccc19c',
    'wax': '#c9b381',
    'brass_dark': '#79532c',
    'brass': '#b68942',
    'gold': '#e9b85c',
    'flame': '#ffe09a',
    'rust': '#95452f',
    'ember': '#d97757',
    'teal_dark': '#24665f',
    'teal': '#2aa198',
    'teal_light': '#83c7ac',
    'sea': '#1d4e79',
    'night': '#000000',
    'teal_glint': '#bcebd8',
    'suit': '#f1f2e8',
}


# Transparent vial aperture, with inclusive pixel coordinates.
VIAL_INTERIOR = [(5, 5), (8, 5), (8, 17), (7, 19), (6, 19), (5, 17)]


class Grid:
    def __init__(self, width, height):
        self.image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.image)

    def rect(self, box, color):
        self.draw.rectangle(box, fill=PALETTE[color])

    def poly(self, points, color):
        self.draw.polygon(points, fill=PALETTE[color])

    def line(self, points, color, width=1):
        self.draw.line(points, fill=PALETTE[color], width=width)

    def hole(self, points):
        self.draw.polygon(points, fill=(0, 0, 0, 0))


def moon(g):
    # Paired integer spans keep the full moon and crater details symmetric.
    for box in ((11, 0, 18, 29), (8, 1, 21, 28), (6, 2, 23, 27),
                (4, 4, 25, 25), (2, 6, 27, 23), (1, 8, 28, 21),
                (0, 11, 29, 18)):
        g.rect(box, 'outline')
    face_spans = ((11, 2, 18, 27), (8, 3, 21, 26), (6, 4, 23, 25),
                  (4, 6, 25, 23), (3, 8, 26, 21), (2, 11, 27, 18))
    for box in face_spans:
        g.rect(box, 'wax')
    for x, y, right, bottom in face_spans:
        g.rect((x, y, right, bottom - 2), 'bone')
    g.poly([(13, 6), (16, 6), (17, 7), (17, 9), (16, 10),
            (13, 10), (12, 9), (12, 7)], 'wax')
    g.rect((13, 7, 16, 8), 'wood_light')
    for x in (6, 19):
        g.poly([(x + 1, 16), (x + 3, 16), (x + 4, 17),
                (x + 4, 19), (x + 3, 20), (x + 1, 20),
                (x, 19), (x, 17)], 'wax')
        g.rect((x + 1, 17, x + 3, 18), 'wood_light')


def crypt(g):
    # Stepped pediment, paired pillars and recessed arched doorway.
    g.poly([(0, 13), (3, 10), (7, 10), (7, 7), (12, 7), (12, 4),
            (18, 4), (18, 1), (25, 1), (25, 4), (31, 4), (31, 7),
            (36, 7), (36, 10), (40, 10), (43, 13), (43, 16),
            (40, 16), (40, 31), (43, 31), (43, 35), (0, 35),
            (0, 31), (3, 31), (3, 16), (0, 16)], 'outline')
    g.poly([(4, 12), (9, 12), (9, 9), (14, 9), (14, 6), (20, 6),
            (20, 4), (23, 4), (23, 6), (29, 6), (29, 9),
            (34, 9), (34, 12), (39, 12), (39, 14), (4, 14)], 'stone')
    g.line([(10, 11), (15, 8), (20, 6), (23, 6), (28, 8), (33, 11)], 'stone_light', 2)
    g.rect((5, 16, 38, 30), 'stone_dark')
    g.rect((6, 16, 11, 30), 'stone')
    g.rect((32, 16, 37, 30), 'stone')
    g.rect((6, 17, 7, 28), 'stone_light')
    g.rect((36, 17, 37, 28), 'stone_light')
    g.poly([(13, 30), (13, 20), (15, 20), (15, 17), (18, 15),
            (25, 15), (28, 17), (28, 20), (30, 20), (30, 30)], 'stone')
    g.poly([(16, 31), (16, 21), (18, 21), (18, 18), (20, 17),
            (23, 17), (25, 18), (25, 21), (27, 21), (27, 31)], 'outline')
    g.rect((19, 22, 24, 30), 'wood_dark')
    g.line([(21, 22), (21, 30)], 'outline')
    g.rect((23, 25, 24, 26), 'brass')
    g.rect((2, 32, 41, 33), 'stone')
    g.rect((4, 32, 13, 32), 'stone_light')
    g.rect((30, 32, 39, 32), 'stone_light')
    g.poly([(4, 28), (8, 28), (8, 30), (13, 30), (13, 33), (4, 33)], 'moss_dark')
    g.rect((5, 29, 7, 30), 'moss')
    g.rect((10, 31, 12, 32), 'moss')
    g.rect((33, 12, 37, 13), 'moss_dark')
    g.rect((34, 12, 35, 12), 'moss')


def tree(g):
    # A split trunk carries angular bare boughs and exposed roots.
    g.poly([(0, 8), (3, 8), (3, 14), (7, 16), (7, 8), (5, 5),
            (5, 1), (8, 1), (8, 5), (10, 7), (10, 18),
            (14, 22), (14, 11), (12, 8), (12, 4), (15, 4),
            (15, 9), (18, 12), (18, 19), (22, 15), (22, 8),
            (25, 5), (25, 1), (28, 1), (28, 7), (25, 10),
            (25, 13), (28, 11), (28, 8), (31, 8), (31, 14),
            (26, 18), (22, 19), (18, 25), (18, 35), (21, 39),
            (25, 41), (25, 43), (19, 43), (16, 40), (13, 40),
            (10, 43), (5, 43), (5, 41), (10, 38), (12, 34),
            (12, 27), (7, 21), (3, 19), (0, 15)], 'outline')
    g.line([(2, 10), (2, 15), (8, 19), (14, 26), (14, 35), (12, 39), (8, 41)], 'wood_dark', 2)
    g.line([(7, 3), (7, 5), (9, 8), (9, 17), (14, 23)], 'wood', 1)
    g.line([(14, 6), (14, 9), (16, 13), (16, 35), (19, 40), (22, 41)], 'wood', 2)
    g.line([(16, 24), (23, 17), (24, 10), (27, 6), (27, 3)], 'wood_dark', 2)
    g.line([(24, 16), (29, 12), (29, 10)], 'wood', 1)
    g.line([(15, 28), (15, 33)], 'wood_light', 1)
    g.rect((14, 37, 16, 38), 'wood_light')


def tomb_one(g):
    g.poly([(1, 19), (1, 6), (3, 6), (3, 3), (5, 3), (5, 1),
            (10, 1), (10, 3), (12, 3), (12, 6), (14, 6),
            (14, 19)], 'outline')
    g.poly([(3, 17), (3, 7), (5, 7), (5, 4), (6, 3), (9, 3),
            (10, 4), (10, 7), (12, 7), (12, 17)], 'stone')
    g.line([(4, 14), (4, 8), (6, 5), (9, 5)], 'stone_light', 1)
    g.line([(9, 3), (8, 7), (10, 9), (8, 12), (9, 14)], 'stone_dark', 1)
    g.rect((5, 16, 10, 17), 'moss_dark')
    g.rect((5, 16, 6, 16), 'moss')


def tomb_two(g):
    g.poly([(4, 0), (9, 0), (9, 5), (13, 5), (13, 11),
            (9, 11), (9, 17), (11, 17), (11, 19), (2, 19),
            (2, 17), (4, 17), (4, 11), (0, 11), (0, 5), (4, 5)], 'outline')
    g.rect((6, 2, 7, 17), 'stone')
    g.rect((2, 7, 11, 9), 'stone')
    g.rect((5, 12, 8, 17), 'stone_dark')
    g.rect((6, 12, 7, 17), 'stone')
    g.rect((6, 2, 7, 3), 'stone_light')
    g.rect((2, 7, 5, 7), 'stone_light')
    g.rect((4, 18, 9, 18), 'moss_dark')


def tomb_three(g):
    # A broad slab leans on a short, uneven footing.
    g.poly([(0, 5), (14, 1), (16, 3), (17, 10), (15, 12),
            (4, 13), (1, 11)], 'outline')
    g.poly([(2, 6), (13, 3), (14, 4), (15, 9), (4, 11)], 'stone')
    g.line([(3, 6), (12, 4)], 'stone_light', 1)
    g.line([(9, 5), (8, 7), (11, 9)], 'stone_dark', 1)
    g.rect((4, 10, 7, 11), 'moss_dark')


def ghost(g, teal=False):
    # The face sits high on a right-facing sheet with a scalloped hem.
    g.poly([(3, 31), (1, 28), (2, 23), (2, 12), (3, 7), (5, 3),
            (8, 1), (14, 0), (19, 2), (22, 6), (23, 12),
            (21, 18), (22, 23), (23, 27), (21, 30), (18, 28),
            (15, 31), (12, 28), (9, 31), (6, 28)], 'outline')
    g.poly([(4, 28), (4, 23), (4, 12), (5, 8), (7, 4), (10, 2),
            (14, 2), (18, 4), (20, 7), (21, 12), (19, 18),
            (20, 23), (21, 27), (18, 25), (15, 28), (12, 25),
            (9, 28), (6, 25)], 'teal' if teal else 'ghost')
    shade = 'teal_dark' if teal else 'ghost_shade'
    g.poly([(4, 15), (7, 17), (7, 23), (9, 28), (6, 25), (4, 28)], shade)
    g.rect((8, 5, 13, 6), 'teal_light' if teal else 'bone')
    g.rect((11, 9, 14, 13), 'outline')
    g.rect((18, 9, 20, 12), 'outline')
    g.rect((15, 16, 17, 18), shade)


def grave_candle(g, lit):
    # Both states share the same wax stub, rim, wick and base.
    if lit:
        g.poly([(3, 0), (5, 2), (6, 4), (5, 6), (2, 6), (1, 4)], 'outline')
        g.poly([(3, 1), (4, 3), (5, 4), (4, 5), (2, 4)], 'gold')
        g.rect((3, 3, 3, 4), 'flame')
    else:
        g.line([(3, 4), (4, 3), (4, 2), (3, 1)], 'stone', 1)
    g.rect((1, 6, 6, 10), 'outline')
    g.rect((2, 7, 5, 9), 'wax')
    g.rect((2, 7, 5, 7), 'bone')
    g.rect((3, 5, 4, 6), 'outline')
    g.rect((0, 10, 7, 11), 'outline')
    g.rect((2, 10, 5, 10), 'brass_dark')


def pumpkin(g):
    g.rect((6, 0, 8, 2), 'outline')
    g.rect((6, 0, 7, 1), 'moss')
    g.poly([(3, 2), (10, 2), (12, 4), (13, 6), (13, 9),
            (10, 11), (3, 11), (0, 9), (0, 6), (1, 4)], 'outline')
    g.poly([(3, 3), (10, 3), (11, 5), (12, 6), (12, 8),
            (9, 10), (4, 10), (1, 8), (1, 6), (2, 5)], 'rust')
    g.rect((3, 4, 10, 8), 'ember')
    g.rect((3, 4, 4, 5), 'gold')
    g.rect((9, 4, 10, 5), 'gold')
    g.line([(3, 7), (5, 8), (8, 8), (10, 7)], 'outline', 2)
    g.rect((5, 8, 8, 8), 'flame')


def vial(g):
    # The clear test tube sits within a wooden two-post stand.
    g.rect((0, 0, 13, 23), 'canvas')
    g.rect((0, 9, 2, 22), 'outline')
    g.rect((11, 9, 13, 22), 'outline')
    g.rect((1, 10, 1, 21), 'wood')
    g.rect((12, 10, 12, 21), 'wood')
    g.rect((0, 21, 13, 23), 'outline')
    g.rect((2, 22, 11, 22), 'wood_light')
    g.poly([(2, 1), (11, 1), (11, 4), (10, 4), (10, 18),
            (8, 21), (5, 21), (3, 18), (3, 4), (2, 4)], 'outline')
    g.poly([(4, 4), (9, 4), (9, 18), (7, 20), (6, 20), (4, 18)], 'ghost_shade')
    g.hole(VIAL_INTERIOR)
    g.rect((3, 2, 10, 2), 'stone_light')
    g.rect((4, 6, 4, 9), 'bone')


def skull(g):
    g.poly([(4, 0), (11, 0), (14, 3), (15, 8), (12, 10),
            (12, 13), (3, 13), (3, 10), (0, 8), (1, 3)], 'outline')
    g.poly([(4, 2), (11, 2), (12, 4), (13, 7), (10, 9),
            (10, 11), (5, 11), (5, 9), (2, 7), (3, 4)], 'wax')
    g.rect((4, 2, 10, 3), 'bone')
    g.rect((3, 5, 5, 7), 'outline')
    g.rect((10, 5, 12, 7), 'outline')
    g.poly([(7, 7), (8, 7), (9, 9), (6, 9)], 'outline')
    g.rect((6, 11, 6, 12), 'bone')
    g.rect((9, 11, 9, 12), 'bone')


def books(g):
    g.rect((2, 0, 18, 5), 'outline')
    g.rect((3, 1, 17, 2), 'rust')
    g.rect((5, 3, 17, 4), 'wax')
    g.rect((3, 3, 4, 4), 'ember')
    g.rect((13, 1, 14, 2), 'brass')
    g.rect((0, 6, 19, 11), 'outline')
    g.rect((1, 7, 18, 8), 'moss_dark')
    g.rect((3, 9, 17, 10), 'wax')
    g.rect((1, 9, 2, 10), 'moss')
    g.rect((5, 9, 12, 9), 'bone')


def alch_candle(g):
    g.poly([(4, 0), (6, 2), (7, 4), (6, 6), (3, 6), (2, 4)], 'outline')
    g.poly([(4, 1), (5, 3), (6, 4), (5, 5), (3, 4)], 'gold')
    g.rect((4, 3, 4, 4), 'flame')
    g.rect((3, 6, 6, 12), 'outline')
    g.rect((4, 7, 5, 12), 'wax')
    g.rect((4, 7, 5, 8), 'bone')
    g.poly([(0, 13), (9, 13), (8, 15), (1, 15)], 'outline')
    g.rect((2, 13, 7, 13), 'brass')
    g.rect((3, 14, 6, 14), 'brass_dark')


def mortar(g):
    g.poly([(8, 0), (11, 0), (12, 2), (9, 5), (13, 5),
            (12, 8), (10, 9), (3, 9), (1, 7), (0, 4),
            (5, 4)], 'outline')
    g.line([(9, 1), (6, 5)], 'stone_light', 2)
    g.poly([(2, 5), (11, 5), (10, 7), (9, 8), (4, 8), (3, 7)], 'stone')
    g.rect((3, 5, 10, 5), 'stone_light')
    g.rect((5, 7, 9, 8), 'stone_dark')


def holder(g):
    # The dish's raised side ring has a transparent center.
    g.poly([(20, 0), (25, 0), (27, 2), (27, 6), (25, 8),
            (22, 8), (22, 9), (4, 9), (1, 7), (0, 4),
            (18, 4), (18, 2)], 'outline')
    g.poly([(21, 1), (24, 1), (26, 3), (26, 5), (24, 7),
            (21, 7), (19, 5), (19, 3)], 'brass')
    g.hole([(21, 3), (24, 3), (24, 5), (21, 5)])
    g.poly([(2, 5), (21, 5), (20, 7), (18, 8), (5, 8), (3, 7)], 'brass_dark')
    g.rect((3, 5, 20, 5), 'gold')
    g.rect((5, 6, 17, 6), 'brass')
    g.rect((7, 7, 10, 7), 'gold')


def flame(g, bent, teal=False):
    # Two solid stepped flame silhouettes share the same bottom anchor.
    points = ([(7, 0), (8, 0), (8, 4), (7, 6), (9, 9), (9, 11),
               (7, 13), (2, 13), (0, 11), (0, 8), (2, 5), (5, 4)]
              if bent else
              [(4, 0), (5, 0), (5, 3), (7, 5), (7, 7), (9, 9),
               (9, 11), (7, 13), (2, 13), (0, 11), (0, 8), (2, 5), (3, 3)])
    g.poly(points, 'outline')
    g.poly(([(7, 2), (6, 5), (4, 6), (2, 8), (1, 10), (3, 12),
             (6, 12), (8, 10), (6, 7)] if bent else
            [(4, 2), (4, 4), (6, 6), (6, 8), (8, 10), (6, 12),
             (3, 12), (1, 10), (3, 6)]), 'teal_dark' if teal else 'ember')
    g.poly([(4, 6), (5, 8), (7, 10), (6, 12), (3, 12), (2, 10)],
           'teal' if teal else 'gold')
    g.poly([(4, 9), (5, 10), (5, 12), (3, 12)], 'teal_light' if teal else 'flame')


def horse(g, frame, teal=False):
    # The jockey leans over a right-facing horse; only the leg pose changes.
    coat, shade, light = ('teal', 'teal_dark', 'teal_light') if teal else ('ember', 'rust', 'gold')
    g.poly([(0, 7), (3, 5), (6, 6), (12, 6), (15, 4), (16, 1),
            (18, 3), (21, 3), (23, 5), (23, 7), (20, 8), (18, 6),
            (17, 10), (13, 11), (6, 11), (3, 9), (0, 10)], 'outline')
    g.poly([(2, 7), (5, 7), (7, 6), (12, 7), (16, 5), (17, 3),
            (19, 4), (21, 4), (22, 6), (20, 7), (18, 5),
            (16, 9), (12, 10), (6, 10), (4, 8), (1, 9)], coat)
    g.rect((6, 9, 12, 10), shade)
    g.rect((20, 4, 20, 4), 'outline')
    legs = ([(6, 10), (4, 13), (1, 15)], [(13, 10), (16, 13), (20, 15)]) if frame == 1 else (
        [(6, 10), (8, 12), (6, 15)], [(14, 10), (12, 13), (15, 15)])
    for points in legs:
        g.line(points, 'outline', 2)
        g.line(points, coat)
        x, y = points[-1]
        g.rect((x, y, min(23, x + 2), y), 'outline')
    g.rect((8, 6, 12, 7), 'outline')
    g.poly([(9, 1), (12, 1), (13, 3), (16, 5), (14, 6),
            (11, 4), (10, 6), (8, 5)], shade)
    g.rect((10, 0, 13, 1), coat)
    g.rect((11, 2, 12, 2), 'bone')
    g.line([(11, 3), (14, 4), (16, 4)], light)


def race_checker(g):
    for row in range(16):
        for column in range(2):
            color = 'bone' if (column + row) % 2 == 0 else 'outline'
            g.rect((column, row, column, row), color)


def train(g, teal=False):
    # A blunt right cab and three lit windows define one compact metro car.
    coat, shade, light = ('teal', 'teal_dark', 'teal_light') if teal else ('ember', 'rust', 'gold')
    g.poly([(2, 0), (21, 0), (23, 2), (25, 5), (25, 9),
            (23, 10), (22, 11), (19, 11), (18, 10), (7, 10),
            (6, 11), (3, 11), (2, 10), (0, 9), (0, 2)], 'outline')
    g.poly([(2, 1), (21, 1), (23, 3), (24, 5), (24, 8),
            (22, 9), (2, 9), (1, 8), (1, 3)], coat)
    g.rect((2, 7, 23, 8), shade)
    for x in (3, 9, 15):
        g.rect((x, 2, x + 3, 5), 'outline')
        g.rect((x + 1, 3, x + 2, 4), 'flame' if not teal else 'teal_light')
    g.poly([(21, 3), (22, 3), (24, 5), (21, 5)], 'ghost_shade')
    g.rect((24, 6, 24, 7), 'bone')
    g.rect((3, 1, 20, 1), light)
    for x in (4, 20):
        g.rect((x, 10, x + 1, 10), 'stone')


def wisp_head(g, teal=False):
    # A rounded right-facing head joins the body at its flat left edge.
    body, shade = ('teal', 'teal_dark') if teal else ('bone', 'ghost_shade')
    g.poly([(0, 2), (2, 0), (5, 0), (7, 2), (7, 5), (5, 7), (0, 7)], body)
    g.rect((0, 6, 4, 7), shade)
    g.rect((3, 2, 3, 3), 'outline')
    g.rect((6, 2, 6, 3), 'outline')


def wisp_tail(g, teal=False):
    # Three trailing scallops taper into a flat right-hand body seam.
    body = 'teal' if teal else 'bone'
    g.poly([(4, 0), (1, 0), (2, 2), (0, 3), (2, 4), (1, 6), (3, 7), (4, 7)], body)
    g.rect((3, 6, 4, 7), 'teal_dark' if teal else 'ghost_shade')


def grave_candle_second(g):
    # A left-leaning flame sits on the same wax stub, wick and base.
    grave_candle(g, True)
    g.draw.rectangle((0, 0, 7, 4), fill=(0, 0, 0, 0))
    g.poly([(1, 0), (4, 1), (5, 3), (5, 5), (2, 5), (1, 3)], 'outline')
    g.poly([(2, 1), (3, 2), (4, 4), (2, 4)], 'gold')
    g.rect((3, 3, 3, 4), 'flame')


def drop_tip(g, teal=False):
    # A pointed drop has a rounded lower bulb and a single bright glint.
    g.poly([(3, 0), (3, 2), (5, 4), (5, 6), (4, 7), (1, 7), (0, 6), (0, 4), (2, 2)],
           'teal_dark' if teal else 'brass_dark')
    g.poly([(3, 2), (4, 4), (4, 6), (1, 6), (1, 4)], 'teal' if teal else 'gold')
    g.rect((2, 4, 2, 5), 'teal_light' if teal else 'flame')


def wick_flame(g, teal=False):
    # A narrow flame fits the wick strip without extending into a label.
    g.poly([(3, 0), (3, 2), (5, 4), (4, 6), (3, 7), (1, 6), (0, 4), (2, 2)],
           'teal_dark' if teal else 'ember')
    g.poly([(3, 2), (4, 4), (3, 6), (1, 5), (2, 3)], 'teal' if teal else 'gold')
    g.rect((2, 4, 2, 5), 'teal_light' if teal else 'flame')


def crypt_mini(g):
    # A stepped roof frames a dark arched door between two stone pillars.
    g.poly([(0, 7), (3, 5), (6, 5), (6, 3), (9, 3), (9, 1),
            (12, 1), (12, 3), (15, 3), (15, 5), (18, 5), (21, 7),
            (20, 9), (20, 17), (1, 17), (1, 9)], 'outline')
    g.poly([(3, 7), (7, 5), (10, 3), (11, 3), (14, 5), (18, 7)], 'stone_light')
    g.rect((3, 9, 18, 15), 'stone')
    g.poly([(8, 16), (8, 11), (10, 9), (12, 9), (14, 11), (14, 16)], 'outline')
    g.rect((4, 10, 4, 14), 'stone_light')
    g.rect((17, 10, 17, 14), 'stone_light')
    g.rect((3, 16, 18, 16), 'stone_dark')
    g.rect((3, 15, 5, 16), 'moss')


def flask_mini(g):
    # A corked flask has a rectangular aperture and transparent exterior.
    g.rect((4, 0, 7, 2), 'wood')
    g.rect((4, 3, 7, 6), 'stone_light')
    g.poly([(3, 6), (8, 6), (11, 10), (11, 13), (9, 15),
            (2, 15), (0, 13), (0, 10)], 'outline')
    g.poly([(4, 6), (7, 6), (9, 9), (10, 12), (8, 14),
            (3, 14), (1, 12), (2, 9)], 'ghost_shade')
    g.draw.rectangle((3, 10, 8, 12), fill=(0, 0, 0, 0))
    g.rect((3, 8, 3, 9), 'bone')


def miniature(g, drawer, width, height):
    # Nearest-neighbor sampling keeps the compact rider and car edges aliased.
    source = Grid(width, height)
    drawer(source)
    g.image = source.image.resize(g.image.size, Image.Resampling.NEAREST)


def wisp_body(g, teal=False):
    # Periodic scallops share a solid middle and matching terminal columns.
    tops = (2, 2, 1, 1, 0, 0, 0, 1, 1, 2, 2, 2) * 2
    for x, top in enumerate(tops):
        g.rect((x, top, x, 7 - top), 'teal' if teal else 'bone')


def wick_flame_second(g, teal=False):
    # A stretched left lean keeps the flame rooted at the same bottom pixel.
    g.poly([(1, 0), (2, 1), (2, 2), (4, 3), (5, 5), (4, 6), (3, 7),
            (1, 6), (0, 4), (1, 2)], 'teal_dark' if teal else 'ember')
    g.poly([(1, 2), (3, 3), (4, 5), (3, 6), (1, 5)], 'teal' if teal else 'gold')
    g.rect((2, 4, 2, 5), 'teal_light' if teal else 'flame')


def ship(g, teal=False):
    # A white horizontal hull and swept fins join a provider-colored exhaust seam.
    accent, shade = ('teal', 'teal_dark') if teal else ('ember', 'rust')
    g.poly([(4, 3), (6, 1), (8, 1), (9, 3), (11, 3), (13, 4),
            (13, 5), (11, 6), (9, 6), (8, 8), (6, 8), (4, 6)], 'outline')
    g.rect((5, 3, 10, 6), 'suit')
    g.rect((5, 2, 7, 2), accent)
    g.rect((5, 7, 7, 7), accent)
    g.rect((10, 3, 10, 6), accent)
    g.rect((11, 4, 12, 5), accent)
    g.rect((7, 4, 8, 5), 'sea')
    g.rect((7, 4, 7, 4), 'teal_glint')
    g.rect((4, 3, 4, 6), shade)
    g.rect((0, 4, 3, 5), accent)
    g.rect((2, 4, 3, 4), 'teal_light' if teal else 'flame')


def lunar_moon(g):
    # Pale paired spans and mirrored crater rims give the background disc soft edges.
    for box in ((9, 0, 16, 25), (6, 1, 19, 24), (4, 2, 21, 23),
                (2, 4, 23, 21), (1, 6, 24, 19), (0, 9, 25, 16)):
        g.rect(box, 'wax')
    for box in ((9, 1, 16, 23), (6, 2, 19, 22), (4, 3, 21, 21),
                (3, 5, 22, 19), (2, 7, 23, 17), (1, 10, 24, 15)):
        g.rect(box, 'bone')
    g.rect((9, 2, 16, 3), 'suit')
    g.poly([(11, 5), (14, 5), (16, 7), (16, 9), (14, 11),
            (11, 11), (9, 9), (9, 7)], 'wax')
    g.rect((11, 6, 14, 8), 'bone_dim')
    for x in (4, 17):
        g.poly([(x + 1, 15), (x + 3, 15), (x + 4, 16), (x + 4, 18),
                (x + 3, 19), (x + 1, 19), (x, 18), (x, 16)], 'wax')
        g.rect((x + 1, 16, x + 3, 17), 'bone_dim')
    for x in (9, 15):
        g.rect((x, 21, x + 1, 21), 'wax')


def lander(g):
    # Four splayed legs support gold foil, a boxy cabin and twin antenna tips.
    g.rect((8, 0, 9, 3), 'suit')
    g.rect((6, 0, 11, 0), 'stone_light')
    g.rect((5, 3, 12, 8), 'outline')
    g.rect((6, 4, 11, 7), 'suit')
    for x in (6, 10):
        g.rect((x, 5, x + 1, 6), 'sea')
    g.rect((4, 8, 13, 11), 'brass_dark')
    g.rect((5, 8, 12, 10), 'gold')
    for x in (5, 11):
        g.rect((x, 8, x + 1, 9), 'flame')
    for points in ([(4, 9), (1, 14)], [(6, 11), (4, 14)],
                   [(13, 9), (16, 14)], [(11, 11), (13, 14)]):
        g.line(points, 'stone_light')
    for x in (0, 3, 12, 15):
        g.rect((x, 15, x + 2, 15), 'suit')


def lunar_flag(g, teal=False, flying=False):
    # A blank provider pennant shares a pale pole in planted and tilted-flight poses.
    accent = 'teal' if teal else 'ember'
    if flying:
        g.line([(2, 7), (9, 0)], 'suit', 2)
        g.poly([(8, 0), (11, 2), (10, 5), (6, 3)], accent)
        g.line([(8, 1), (10, 2)], 'teal_light' if teal else 'gold')
    else:
        g.rect((3, 0, 4, 11), 'suit')
        g.rect((0, 1, 7, 3), accent)
        g.rect((1, 4, 6, 4), accent)
        g.rect((1, 1, 6, 1), 'teal_light' if teal else 'gold')


def astronaut(g, frame, teal=False):
    # A right-facing visor and backpack identify the suit; alternating boots show a stride.
    accent = 'teal' if teal else 'ember'
    g.rect((0, 5, 2, 10), 'stone_light')
    g.rect((1, 6, 1, 9), accent)
    g.poly([(3, 0), (7, 0), (8, 1), (9, 2), (9, 5), (7, 6),
            (3, 6), (2, 4), (2, 2)], 'outline')
    g.rect((3, 1, 7, 5), 'suit')
    g.rect((6, 2, 9, 4), 'sea')
    g.rect((7, 2, 8, 2), 'teal_glint')
    g.rect((3, 6, 7, 10), 'suit')
    g.rect((3, 6, 7, 6), accent)
    g.rect((3, 10, 7, 10), accent)
    g.rect((8, 7, 9, 8 if frame == 1 else 9), 'suit')
    for x, y in ((2, 11), (6, 12)) if frame == 1 else ((3, 12), (7, 11)):
        g.rect((x, 11, x + 1, y), 'suit')
        g.rect((x, y + 1, x + 2, y + 1), 'stone_light')


def fence(g):
    # Two uninterrupted rails join at either tile edge between paired posts.
    for x in (3, 11):
        g.rect((x, 0, x + 1, 7), 'wood_dark')
        g.rect((x, 0, x, 7), 'wood_light')
    for y in (2, 5):
        g.rect((0, y, 15, y + 1), 'wood')
        g.rect((0, y, 15, y), 'wood_light')


def crowd(g, frame):
    # Three different coats sit behind the rail with raised cheering arms.
    for index, (x, coat, hair) in enumerate(((2, 'ember', 'wood_dark'),
                                           (10, 'teal', 'wax'), (18, 'moss', 'stone'))):
        g.rect((x + 1, 2, x + 3, 4), 'wax')
        g.rect((x + 1, 1, x + 3, 2), hair)
        g.rect((x, 5, x + 4, 9), coat)
        if frame == 2:
            g.line([(x, 6), (x - 1, 3), (x - 1, index % 2)], coat)
            g.line([(x + 4, 6), (x + 5, 3), (x + 5, (index + 1) % 2)], coat)
            g.rect((x - 1, index % 2, x - 1, index % 2), 'wax')
            g.rect((x + 5, (index + 1) % 2, x + 5, (index + 1) % 2), 'bone')
        else:
            g.rect((x - 1, 7, x + 5, 8), coat)
            g.rect((x - 1, 8, x - 1, 9), 'wax')
            g.rect((x + 5, 8, x + 5, 9), 'wax')


def dust(g, frame):
    # Rounded earth puffs roll through two distinct trailing silhouettes.
    spans = ((1, 3, 6, 5), (3, 1, 5, 4), (0, 4, 7, 4)) if frame == 1 else (
        (0, 2, 4, 4), (2, 0, 3, 3), (4, 3, 7, 5))
    for box in spans:
        g.rect(box, 'wood')
    g.rect((2 if frame == 1 else 1, 3, 4, 3), 'wood_light')
    g.rect((4, 5, 6, 5), 'soil')


def rail(g):
    # Steel rails span the tile edges above four regularly spaced sleepers.
    for x in (2, 8, 14, 20):
        g.rect((x, 0, x + 1, 7), 'wood_dark')
    for y in (1, 5):
        g.rect((0, y, 23, y + 1), 'stone')
        g.rect((0, y, 23, y), 'stone_light')


def commuter(g, kind, frame):
    # Distinct hair, coats and bags accompany a one-pixel planted-foot shift.
    coat, hair = (('ember', 'wood_dark'), ('teal', 'outline'), ('stone_light', 'wax'))[kind]
    head_x = 2 + (frame - 1 if kind == 2 else 0)
    g.rect((head_x, 0, head_x + 2, 3), 'wax')
    g.rect((head_x, 0, head_x + 2, 0), hair)
    g.rect((head_x + 1, 2, head_x + 1, 2), 'outline')
    g.rect((2, 4, 5, 9), coat)
    g.rect((1, 5, 1, 8), coat)
    g.rect((6, 6, 7, 9), 'wood' if kind != 1 else 'teal_dark')
    g.rect((2, 10, 2, 12), 'outline')
    g.rect((5, 10, 5, 12 - (frame - 1)), 'outline')
    g.rect((1, 13, 2, 13), 'stone_dark')
    g.rect((5, 13 - (frame - 1), 6, 13 - (frame - 1)), 'stone_dark')


# Only variants referenced by the seven theme packages are emitted.
# Each entry is (master, width, height, sizes, right-facing, drawer).
def zombie(g, frame):
    # A forward jaw and outstretched arm keep the shamble directional at 1x.
    g.poly([(3, 0), (7, 0), (8, 2), (9, 3), (8, 5), (4, 5), (2, 3)], 'outline')
    g.rect((3, 1, 7, 3), 'moss')
    g.rect((4, 4, 7, 4), 'stone_light')
    g.rect((7, 2, 7, 2), 'bone')
    g.poly([(2, 5), (6, 5), (7, 7), (9, 7), (9, 9), (6, 9),
            (6, 10), (1, 10), (0, 8)], 'outline')
    g.rect((2, 6, 5, 9), 'stone_dark')
    g.rect((3, 6, 4, 8), 'stone')
    g.rect((6, 7, 8, 8), 'moss')
    g.rect((1, 8, 2, 9), 'moss_dark')
    legs = ((1, 10, 2, 12), (5, 10, 6, 13)) if frame == 1 else (
        (2, 10, 3, 13), (6, 10, 7, 11))
    for box in legs:
        g.rect(box, 'wood_dark')
        x, _, right, bottom = box
        g.rect((x, bottom, min(9, right + 1), bottom), 'outline')


def vampire(g):
    # Rust cape lining separates the dark cape from the night canvas.
    g.poly([(2, 4), (7, 4), (8, 8), (9, 12), (7, 13), (0, 13), (1, 8)], 'outline')
    g.poly([(2, 6), (6, 6), (7, 10), (8, 12), (1, 12)], 'rust')
    g.rect((3, 1, 7, 4), 'outline')
    g.rect((4, 2, 7, 4), 'bone')
    g.rect((8, 3, 8, 3), 'bone')
    g.rect((7, 2, 7, 2), 'outline')
    g.rect((7, 4, 7, 4), 'suit')
    g.poly([(3, 5), (6, 6), (7, 5), (6, 10), (3, 10)], 'stone_dark')
    g.rect((5, 6, 5, 8), 'bone')
    g.rect((5, 6, 6, 6), 'ember')
    g.rect((3, 11, 4, 13), 'outline')
    g.rect((6, 11, 7, 13), 'outline')


def bat(g, frame):
    wings = ([(0, 0), (3, 1), (5, 3), (7, 1), (9, 0), (8, 4), (6, 4),
              (5, 5), (3, 4), (1, 4)] if frame == 1 else
             [(0, 5), (1, 2), (3, 2), (5, 1), (7, 2), (8, 2), (9, 5),
              (6, 4), (5, 3), (3, 4)])
    g.poly(wings, 'stone_dark')
    g.line([(1, 1 if frame == 1 else 4), (4, 3), (8, 1 if frame == 1 else 4)], 'rust')
    g.rect((4, 2, 6, 4), 'outline')
    g.rect((6, 1, 6, 2), 'outline')
    g.rect((6, 2, 6, 2), 'bone')
    g.rect((7, 3, 7, 3), 'stone_light')


SPECS = [
    ('al-drop', 6, 8, ('big', 'small'), False, drop_tip),
    ('al-drop-teal', 6, 8, ('big', 'small'), False, lambda g: drop_tip(g, True)),
    ('al-flask-mini', 12, 16, ('big', 'small'), False, flask_mini),
    ('alch-books', 20, 12, ('small',), False, books),
    ('alch-candle', 10, 16, ('small',), False, alch_candle),
    ('alch-mortar', 14, 10, ('small',), False, mortar),
    ('alch-skull', 16, 14, ('small',), False, skull),
    ('alch-vial', 14, 24, ('small',), False, vial),
    ('candle-flame-1', 10, 14, ('small',), False, lambda g: flame(g, False)),
    ('candle-flame-2', 10, 14, ('small',), False, lambda g: flame(g, True)),
    ('candle-flame-teal-1', 10, 14, ('small',), False, lambda g: flame(g, False, True)),
    ('candle-flame-teal-2', 10, 14, ('small',), False, lambda g: flame(g, True, True)),
    ('candle-holder', 28, 10, ('small',), False, holder),
    ('grave-candle-lit-2', 8, 12, ('small',), False, grave_candle_second),
    ('grave-candle-lit', 8, 12, ('small',), False, lambda g: grave_candle(g, True)),
    ('grave-candle-out', 8, 12, ('small',), False, lambda g: grave_candle(g, False)),
    ('grave-crypt', 44, 36, ('small',), False, crypt),
    ('grave-ghost', 24, 32, ('small',), True, ghost),
    ('grave-ghost-teal', 24, 32, ('small',), True, lambda g: ghost(g, True)),
    ('grave-moon', 30, 30, ('small',), False, moon),
    ('grave-pumpkin', 14, 12, ('small',), False, pumpkin),
    ('grave-tomb-1', 16, 20, ('small',), False, tomb_one),
    ('grave-tomb-2', 14, 20, ('small',), False, tomb_two),
    ('grave-tomb-3', 18, 14, ('small',), False, tomb_three),
    ('grave-tree', 32, 44, ('small',), False, tree),
    ('gy-crypt-mini', 20, 16, ('small',), False, lambda g: miniature(g, crypt_mini, 22, 18)),
    ('gy-zombie-1', 10, 14, ('small',), True, lambda g: zombie(g, 1)),
    ('gy-zombie-2', 10, 14, ('small',), True, lambda g: zombie(g, 2)),
    ('gy-vampire', 10, 14, ('small',), True, vampire),
    ('gy-bat-1', 10, 6, ('small',), True, lambda g: bat(g, 1)),
    ('gy-bat-2', 10, 6, ('small',), True, lambda g: bat(g, 2)),
    ('gy-wisp-body', 24, 8, ('big', 'small'), False, wisp_body),
    ('gy-wisp-body-teal', 24, 8, ('big', 'small'), False, lambda g: wisp_body(g, True)),
    ('gy-wisp-head', 8, 8, ('big', 'small'), True, wisp_head),
    ('gy-wisp-head-teal', 8, 8, ('big', 'small'), True, lambda g: wisp_head(g, True)),
    ('gy-wisp-tail', 5, 8, ('big', 'small'), True, wisp_tail),
    ('gy-wisp-tail-teal', 5, 8, ('big', 'small'), True, lambda g: wisp_tail(g, True)),
    ('ho-checker', 2, 16, ('big', 'small'), False, race_checker),
    ('ho-crowd-1', 24, 10, ('big', 'small'), False, lambda g: crowd(g, 1)),
    ('ho-crowd-2', 24, 10, ('big', 'small'), False, lambda g: crowd(g, 2)),
    ('ho-dust-1', 8, 6, ('big', 'small'), False, lambda g: dust(g, 1)),
    ('ho-dust-2', 8, 6, ('big', 'small'), False, lambda g: dust(g, 2)),
    ('ho-fence', 16, 8, ('big', 'small'), False, fence),
    ('ho-horse-teal-mini-1', 12, 8, ('big', 'small'), True, lambda g: miniature(g, lambda source: horse(source, 1, True), 24, 16)),
    ('ho-horse-teal-mini-2', 12, 8, ('big', 'small'), True, lambda g: miniature(g, lambda source: horse(source, 2, True), 24, 16)),
    ('ho-horse-warm-mini-1', 12, 8, ('big', 'small'), True, lambda g: miniature(g, lambda source: horse(source, 1, False), 24, 16)),
    ('ho-horse-warm-mini-2', 12, 8, ('big', 'small'), True, lambda g: miniature(g, lambda source: horse(source, 2, False), 24, 16)),
    ('me-actor-a-1', 8, 14, ('small',), False, lambda g: commuter(g, 0, 1)),
    ('me-actor-a-2', 8, 14, ('small',), False, lambda g: commuter(g, 0, 2)),
    ('me-actor-b-1', 8, 14, ('small',), False, lambda g: commuter(g, 1, 1)),
    ('me-actor-b-2', 8, 14, ('small',), False, lambda g: commuter(g, 1, 2)),
    ('me-actor-c-1', 8, 14, ('small',), False, lambda g: commuter(g, 2, 1)),
    ('me-actor-c-2', 8, 14, ('small',), False, lambda g: commuter(g, 2, 2)),
    ('me-car-teal-mini', 13, 6, ('big', 'small'), True, lambda g: miniature(g, lambda source: train(source, True), 26, 12)),
    ('me-car-warm-mini', 13, 6, ('big', 'small'), True, lambda g: miniature(g, lambda source: train(source, False), 26, 12)),
    ('me-rail', 24, 8, ('big', 'small'), False, rail),
    ('mo-moon', 26, 26, ('small',), False, lunar_moon),
    ('mo-lander', 18, 16, ('small',), False, lander),
    ('mo-flag-warm', 8, 12, ('small',), False, lunar_flag),
    ('mo-flag-teal', 8, 12, ('small',), False, lambda g: lunar_flag(g, True)),
    ('mo-flag-warm-fly', 12, 8, ('small',), False, lambda g: lunar_flag(g, flying=True)),
    ('mo-flag-teal-fly', 12, 8, ('small',), False, lambda g: lunar_flag(g, True, True)),
    ('mo-astro-warm-1', 10, 14, ('small',), True, lambda g: astronaut(g, 1)),
    ('mo-astro-warm-2', 10, 14, ('small',), True, lambda g: astronaut(g, 2)),
    ('mo-astro-teal-1', 10, 14, ('small',), True, lambda g: astronaut(g, 1, True)),
    ('mo-astro-teal-2', 10, 14, ('small',), True, lambda g: astronaut(g, 2, True)),
    ('so-ship', 14, 10, ('big', 'small'), True, ship),
    ('so-ship-teal', 14, 10, ('big', 'small'), True, lambda g: ship(g, True)),
    ('wick-flame-2', 6, 8, ('big', 'small'), False, wick_flame_second),
    ('wick-flame', 6, 8, ('big', 'small'), False, wick_flame),
    ('wick-flame-teal-2', 6, 8, ('big', 'small'), False, lambda g: wick_flame_second(g, True)),
    ('wick-flame-teal', 6, 8, ('big', 'small'), False, lambda g: wick_flame(g, True)),
]


def sprite_facings(name, directional):
    # Scene actors turn or enter from either edge; track art still travels right.
    roaming = ('grave-ghost', 'gy-zombie-', 'gy-vampire', 'gy-bat-', 'mo-astro-')
    return ('-r', '-l') if name.startswith(roaming) else (('-r',) if directional else ('',))


def sprite_stems():
    return [f'{name}-{size}{suffix}'
            for name, _, _, sizes, directional, _ in SPECS for size in sizes
            for suffix in sprite_facings(name, directional)]


def generate(output, previews):
    output.mkdir(parents=True, exist_ok=True)
    rows = {2: [], 1: []}
    for name, width, height, sizes, directional, draw in SPECS:
        grid = Grid(width, height)
        draw(grid)
        master = grid.image
        for scale, label in ((2, 'big'), (1, 'small')):
            if label not in sizes:
                continue
            resized = master.resize((width * scale, height * scale), Image.Resampling.NEAREST)
            for suffix in sprite_facings(name, directional):
                sprite = resized.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if suffix == '-l' else resized
                sprite.save(output / f'{name}-{label}{suffix}.png', optimize=False, compress_level=9)
                rows[scale].append(sprite)
    # Superseded Moon-theme files are absent from the shipped output directory.
    for pattern in ('so-rocket*.png', 'so-comet*.png', 'so-sun-mini*.png'):
        for obsolete in output.glob(pattern):
            obsolete.unlink()
    padding = 8
    big_height = max(sprite.height for sprite in rows[2])
    small_height = max(sprite.height for sprite in rows[1])
    sheet_width = max(sum(sprite.width + padding for sprite in row) + padding
                      for row in rows.values())
    sheet = Image.new('RGBA', (sheet_width, big_height + small_height + padding * 3),
                      PALETTE['canvas'])
    for scale, y, row_height in ((2, padding, big_height), (1, big_height + padding * 2, small_height)):
        x = padding
        for sprite in rows[scale]:
            sheet.alpha_composite(sprite, (x, y + row_height - sprite.height))
            x += sprite.width + padding
    previews.mkdir(parents=True, exist_ok=True)
    sheet.save(previews / 'contact.png', optimize=False, compress_level=9)


# Preview-only approximation of the theme pages: coordinates and font
# metrics here can drift from the LVGL pages. packages/theme-*.yaml is the
# authoritative layout.
LAYOUTS = {
    (320, 240): {
        'scale': 2, 'font': 16, 'percent_font': 26,
        'status': (118, 2, 110, 16), 'scene': (8, 22, 304, 38),
        'row_y': (62, 106, 150, 194),
        'label_xw': (8, 88), 'value_xw': (108, 68), 'reset_xw': (184, 128),
        'text_offset': 4, 'track_xw': (16, 288), 'track_offset': 28, 'track_height': 16,
    },
    (240, 135): {
        'scale': 1, 'font': 13, 'percent_font': 18,
        'status': (92, 0, 70, 13), 'scene': (4, 14, 232, 16),
        'row_y': (31, 57, 83, 109),
        'label_xw': (4, 64), 'value_xw': (72, 46), 'reset_xw': (124, 112),
        'text_offset': 0, 'track_xw': (8, 224), 'track_offset': 18, 'track_height': 8,
    },
}
THEMES = ('graveyard', 'alchemy', 'candle', 'solar', 'horses', 'metro', 'text')


def amount(length, usage):
    return int(length * max(0, min(100, usage or 0)) / 100 + 0.5)


def flat(image, rect, color):
    x, y, width, height = rect
    if width > 0 and height > 0:
        ImageDraw.Draw(image).rectangle((x, y, x + width - 1, y + height - 1),
                                        fill=PALETTE[color])


def label(image, zone, value, size, color='bone', right=False, ellipsis=False, center=False):
    # Nominal-size aliased glyphs stand in for the firmware's fixed fonts.
    font = ImageFont.load_default(size=size)
    x, y, width, height = zone

    def ink_bounds(text):
        return font.getmask(text, mode='1').getbbox() or (0, 0, 0, 0)

    def fits(text):
        bounds = ink_bounds(text)
        return max(font.getlength(text), bounds[2] - bounds[0]) <= width

    if ellipsis:
        original = value
        while not fits(value) and original:
            original = original[:-1]
            value = original + '...'
    assert fits(value), (value, size, zone)
    bounds = ink_bounds(value)
    assert bounds[3] - bounds[1] <= height, (value, size, zone)
    # Align painted edges so glyph overhang cannot escape a countdown zone.
    x -= bounds[0]
    if right:
        x += width - (bounds[2] - bounds[0])
    elif center:
        x += (width - (bounds[2] - bounds[0])) // 2
    draw = ImageDraw.Draw(image)
    draw.fontmode = '1'
    draw.text((x, y), value, font=font, fill=PALETTE[color], anchor='lt')


def scene_sprite(image, assets, name, xy, scale=1, directional=False, facing='r'):
    suffix = f'-{facing}' if directional else ''
    image.alpha_composite(assets[f'{name}-{"big" if scale == 2 else "small"}{suffix}'], xy)


def bob(tick, step=3):
    return (0, -1, 0, 1)[(tick // step) % 4]


def frame_pair(tick, dwell=2):
    return 1 + (tick // dwell) % 2


MOON_SCENES = {
    True: {'width': 304, 'surface_y': 32, 'moon': (170, 0), 'lander': (72, 16),
           'flag': (118, 20), 'astro_y': 18, 'step': 6, 'throw_dx': -4},
    False: {'width': 232, 'surface_y': 27, 'moon': (118, 0), 'lander': (56, 11),
            'flag': (88, 15), 'astro_y': 13, 'step': 4, 'throw_dx': -3},
}


def moon_loop(tick, large):
    # A bounded cycle alternates planted providers with one walker and one thrown flag.
    config = MOON_SCENES[large]
    flag_x, flag_y = config['flag']
    stop_x = flag_x + 4
    walk_ticks = (config['width'] - stop_x + config['step'] - 1) // config['step']
    throw_ticks = (flag_y - 2 + 8 + 3) // 4
    durations = (8, walk_ticks, 3, throw_ticks, 3, walk_ticks)
    half = sum(durations)
    clock = tick % (2 * half)
    planted, visitor = ('warm', 'teal') if clock < half else ('teal', 'warm')
    phase_tick = clock % half
    for phase, duration in zip(('DWELL', 'WALK_IN', 'PULL', 'HURL', 'PLANT', 'WALK_OUT'),
                               durations, strict=True):
        if phase_tick < duration:
            break
        phase_tick -= duration
    astro_x = stop_x
    if phase == 'WALK_IN':
        astro_x = max(stop_x, config['width'] - (phase_tick + 1) * config['step'])
    elif phase == 'WALK_OUT':
        astro_x = min(config['width'], stop_x + (phase_tick + 1) * config['step'])
    return {
        'phase': phase, 'phase_tick': phase_tick, 'half_ticks': half,
        'planted': visitor if phase in ('PLANT', 'WALK_OUT') else planted,
        'flag_visible': phase != 'HURL', 'visitor': visitor, 'thrown': planted,
        'flag_xy': (flag_x, flag_y - 2 if phase == 'PULL' else flag_y),
        'fly_visible': phase == 'HURL',
        'fly_xy': (flag_x + phase_tick * config['throw_dx'], flag_y - 2 - phase_tick * 4),
        'astro_visible': phase != 'DWELL' and astro_x < config['width'],
        'astro_xy': (astro_x, config['astro_y']),
        'facing': 'r' if phase == 'WALK_OUT' else 'l',
        'frame': 1 + phase_tick % 2 if phase in ('WALK_IN', 'WALK_OUT') else (
            2 if phase == 'HURL' else 1),
    }


def theme_title(theme):
    return 'Moon' if theme == 'solar' else theme.title()


def theme_layout(size, theme):
    layout = dict(LAYOUTS[size])
    if theme in ('horses', 'metro'):
        layout['scene'] = (8, 20, 304, 40) if layout['scale'] == 2 else (4, 0, 232, 30)
    elif theme == 'solar' and layout['scale'] == 1:
        layout['scene'] = (4, 0, 232, 30)
    if theme in ('horses', 'metro', 'solar') and layout['scale'] == 1:
        layout['status'] = (166, 0, 70, 13)
    if theme == 'text':
        layout['text_grid'] = True
        layout['status'] = (234, 2, 78, 16) if layout['scale'] == 2 else (166, 0, 70, 13)
        layout['row_y'] = (24, 78, 132, 186) if layout['scale'] == 2 else (27, 53, 79, 105)
    return layout


def tile_strip(image, tile, rect, shift=0):
    # A rectangular parent clips the translated run of native image tiles.
    x, y, width, height = rect
    if width <= 0 or height <= 0:
        return
    strip = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    for tx in range(-shift, width, tile.width):
        strip.alpha_composite(tile, (tx, 0))
    image.alpha_composite(strip, (x, y))


def placard(image, theme, rect, text, font):
    # Runtime rectangles replace the unused blank-board sprites.
    x, y, width, height = rect
    if theme == 'horses':
        for px in (x + 4, x + width - 6):
            flat(image, (px, y, 2, 4), 'stone')
    top = 3 if theme == 'horses' else 1
    flat(image, (x, y + top, width, height - top), 'wood_dark')
    flat(image, (x + 2, y + top + 1, width - 4, height - top - 2), 'bone')
    label(image, (x + 4, y + top + 1, width - 8, font), text, font, 'outline')
    if theme == 'metro':
        for px in (x + 2, x + width - 3):
            flat(image, (px, y + height, 1, 4), 'stone')


ACTOR_RANGES = {
    True: ((16, 72), (124, 172), (230, 286)),
    False: ((14, 60), (90, 136), (168, 216)),
}


def actor_state(slot, tick, large):
    # A seeded integer slot simulation keeps every preview regeneration stable.
    rng = (117, 911, 2027)[slot]

    def choose(low, high):
        nonlocal rng
        rng = (25173 * rng + 13849) % 65536
        return low + rng % (high - low + 1)

    low, high = ACTOR_RANGES[large][slot]
    target = x = choose(low, high)
    remaining = choose(12 + slot * 2, 24 + slot * 2)
    state, direction = 'idle', (-1 if slot == 1 else 1)
    edge = 304 if large else 232
    step = 2 if large else 1
    for _ in range(tick):
        if state in ('idle', 'hidden'):
            remaining -= 1
            if remaining == 0:
                if state == 'idle':
                    state = 'leave'
                else:
                    direction = -1 if choose(0, 1) else 1
                    target = choose(low, high)
                    x = -8 if direction == 1 else edge
                    state = 'enter'
        elif state == 'enter':
            x += direction * min(step, abs(target - x))
            if x == target:
                state, remaining = 'idle', choose(12 + slot * 2, 24 + slot * 2)
        else:
            x += direction * step
            if x <= -8 or x >= edge:
                state, remaining = 'hidden', choose(4, 12)
    return state, x


def ghost_patrol(slot, tick, large):
    rng = (313, 1597)[slot]

    def choose(low, high):
        nonlocal rng
        rng = (25173 * rng + 13849) % 65536
        return low + rng % (high - low + 1)

    width, step = (304, 2) if large else (232, 1)
    low, high = 12, width - 36
    x = ((55, 155) if large else (36, 124))[slot]
    direction = 1 if slot == 0 else -1
    state, target, remaining = 'drift', x, choose(48, 120)
    for _ in range(tick):
        if state == 'hidden':
            remaining -= 1
            if remaining == 0:
                direction = -1 if choose(0, 65535) // 32768 else 1
                target = choose(low, high)
                x = -24 if direction == 1 else width
                state = 'enter'
        elif state == 'enter':
            x += direction * min(step, abs(target - x))
            if x == target:
                state, remaining = 'drift', choose(48, 120)
        elif state == 'leave':
            x += direction * step
            if x <= -24 or x >= width:
                x = max(-24, min(width, x))
                state, remaining = 'hidden', choose(16, 40)
        else:
            x = max(low, min(high, x + direction * step))
            if x in (low, high):
                direction = -direction
            remaining -= 1
            if remaining == 0:
                if choose(0, 65535) // 16384 == 0:
                    state = 'leave'
                else:
                    direction = -direction
                    remaining = choose(48, 120)
    return {'state': state, 'x': x, 'facing': 'r' if direction == 1 else 'l',
            'visible': state != 'hidden'}


def spook_state(tick, large):
    # One slot owns the whole visit, including the one-tick transform handoff.
    rng = 7331

    def choose(low, high):
        nonlocal rng
        rng = (25173 * rng + 13849) % 65536
        return low + rng % (high - low + 1)

    width, y, step = (304, 21, 2) if large else (232, 7, 1)
    state, act, direction, x, target, phase = 'wait', 'zombie', 1, -10, 0, 0
    remaining = choose(24, 48)
    for _ in range(tick):
        if state == 'wait':
            remaining -= 1
            if remaining == 0:
                act = 'vampire' if choose(0, 65535) // 32768 else 'zombie'
                direction = -1 if choose(0, 65535) // 32768 else 1
                x, y, phase = (-10 if direction == 1 else width), (21 if large else 7), 0
                target = choose(96, 192) if large else choose(72, 152)
                state = 'walk'
        elif state == 'walk':
            phase = (phase + 1) % 4
            if act == 'zombie':
                if large or phase % 2 == 0:
                    x += direction
                    if x <= -10 or x >= width:
                        x = max(-10, min(width, x))
                        state, remaining = 'wait', choose(32, 72)
            else:
                x += direction * min(step, abs(target - x))
                if x == target:
                    state, remaining = 'stop', choose(6, 12)
        elif state == 'stop':
            remaining -= 1
            if remaining == 0:
                state = 'transform'
        elif state == 'transform':
            state, phase = 'bat', 0
        else:
            phase = (phase + 1) % 4
            x += direction * (3 if large else 2)
            y -= 2 if large else 1
            if x <= -10 or x >= width or y <= -6:
                state, remaining = 'wait', choose(32, 72)
    return {'state': state, 'act': act, 'xy': (x, y), 'phase': phase,
            'facing': 'r' if direction == 1 else 'l', 'visible': state != 'wait',
            'frame': 1 + (phase % 2 if state == 'bat' else phase // 2)}


def vessel_bubble(tick, index, large, mouth, filled):
    # Four independent bounded phases allocate at most one bubble per vessel.
    phase = (tick + (0, 4, 8, 12)[index]) % 16
    size, life = (2, 8) if large else (1, 5)
    x, y = mouth[0] - size // 2, mouth[1] - size - phase
    return (x, y, size, size) if filled and phase < life and y >= 0 else None


def draw_scene(image, assets, layout, theme, values, present, tick, flame_frame):
    # A clipped top strip separates scenery from the four fixed data rows.
    sx, sy, width, height = layout['scene']
    scene = Image.new('RGBA', (width, height), PALETTE['canvas'])
    large = layout['scale'] == 2
    if theme == 'graveyard':
        if large:
            flat(scene, (0, 35, width, 3), 'soil')
            scene_sprite(scene, assets, 'grave-moon', (266, 0))
            scene_sprite(scene, assets, 'grave-crypt', (212, 1))
            scene_sprite(scene, assets, 'grave-tree', (0, -6))
            candle_x = (108, 124, 140, 264, 280)
            candle_y = 26
        else:
            scene_sprite(scene, assets, 'gy-crypt-mini', (184, 0))
            flat(scene, (0, 15, width, 1), 'soil')
            candle_x, candle_y = (8, 20, 70, 82, 214), 3
        for slot, name in enumerate(('grave-ghost', 'grave-ghost-teal')):
            ghost_state = ghost_patrol(slot, tick, large)
            if ghost_state['visible'] and (slot == 0 or present):
                scene_sprite(scene, assets, name,
                             (ghost_state['x'], (2 if large else 0) + bob(tick + slot * 3)),
                             directional=True, facing=ghost_state['facing'])
        if large:
            for index, x in enumerate((38, 88, 180), 1):
                scene_sprite(scene, assets, f'grave-tomb-{index}', (x, height - (20 if index < 3 else 14)))
        spook = spook_state(tick, large)
        if spook['visible']:
            name = (f'gy-bat-{spook["frame"]}' if spook['state'] == 'bat' else (
                f'gy-zombie-{spook["frame"]}' if spook['act'] == 'zombie' else 'gy-vampire'))
            scene_sprite(scene, assets, name, spook['xy'], directional=True, facing=spook['facing'])
        for threshold, x in zip((20, 40, 60, 80, 100), candle_x, strict=True):
            name = 'grave-candle-out'
            if (values[0] or 0) >= threshold:
                name = 'grave-candle-lit' if frame_pair(tick) == 1 else 'grave-candle-lit-2'
            scene_sprite(scene, assets, name, (x, candle_y))
    elif theme == 'alchemy':
        if large:
            flat(scene, (0, 34, width, 4), 'wood')
            flat(scene, (0, 34, width, 1), 'wood_light')
            flask_xy, flask_scale = (36, 6), 2
            scene_sprite(scene, assets, 'alch-skull', (8, 20))
            scene_sprite(scene, assets, 'alch-books', (74, 22))
            scene_sprite(scene, assets, 'alch-mortar', (260, 24))
            scene_sprite(scene, assets, 'alch-candle', (286, 18))
            vial_x, vial_y = (118, 164, 210), 10
            bubble_x = 48
        else:
            flat(scene, (0, 15, width, 1), 'wood_light')
            flask_xy, flask_scale = (28, 3), 1
            scene_sprite(scene, assets, 'alch-books', (54, 3))
            scene_sprite(scene, assets, 'alch-mortar', (212, 5))
            vial_x, vial_y = (94, 132, 170), 3
            bubble_x = 34
        fx, fy = flask_xy
        liquid_height = amount(3 * flask_scale, values[0])
        flat(scene, (fx + 3 * flask_scale, fy + 13 * flask_scale - liquid_height,
                     6 * flask_scale, liquid_height), 'rust' if (values[0] or 0) >= 80 else 'gold')
        if liquid_height:
            # A glint moves inside the filled aperture without crossing its bottom.
            by = fy + 13 * flask_scale - min(liquid_height, 2 + (tick // 2) % 2)
            flat(scene, (bubble_x, by, 1, 1), 'flame')
        scene_sprite(scene, assets, 'al-flask-mini', flask_xy, flask_scale)
        # The bench candle retains a one-pixel flicker even with an empty flask.
        if large:
            flat(scene, (290, 20 + (tick // 2) % 2, 1, 1), 'flame')
        else:
            scene_sprite(scene, assets, 'al-drop', (82, 4 + bob(tick, 2)))
        for index, x in enumerate(vial_x, 1):
            if index > 1 and not present:
                continue
            usage = values[index]
            fill_height = amount(15, usage)
            liquid = 'teal_light' if index > 1 and (usage or 0) >= 80 else (
                'teal' if index > 1 else ('rust' if (usage or 0) >= 80 else 'gold'))
            flat(scene, (x + 5, vial_y + 20 - fill_height, 4, fill_height), liquid)
            scene_sprite(scene, assets, 'alch-vial', (x, vial_y))
        mouths = [(fx + 6 * flask_scale, fy)] + [(x + 7, vial_y + 2) for x in vial_x]
        fills = [liquid_height] + [amount(15, usage) for usage in values[1:]]
        for index, mouth in enumerate(mouths):
            bubble = vessel_bubble(tick, index, large, mouth,
                                   fills[index] > 0 and (index < 2 or present))
            if bubble:
                glint = 'teal_glint' if index > 1 and (values[index] or 0) >= 80 else (
                    'teal_light' if index > 1 else 'flame')
                flat(scene, bubble, glint)
    elif theme == 'candle':
        for index, x in enumerate((28, 96, 164, 232) if large else (20, 76, 132, 188)):
            if index > 1 and not present:
                continue
            wax_height = (18 if index % 2 == 0 else 12) if large else (7 if index % 2 == 0 else 5)
            bottom = height - (6 if large else 1)
            top = bottom - wax_height
            flat(scene, (x, top, 8 if large else 5, wax_height), 'wax')
            flat(scene, (x, top, 8 if large else 5, 1), 'bone')
            if large:
                f = flame_frame or frame_pair(tick)
                name = f'candle-flame-{"teal-" if index > 1 else ""}{f}'
                scene_sprite(scene, assets, name, (x - 1, top - 13))
                scene_sprite(scene, assets, 'candle-holder', (x - 8, bottom - 2))
            else:
                name = 'wick-flame-teal' if index > 1 else 'wick-flame'
                scene_sprite(scene, assets, name, (x, top - 7 + (tick // 2) % 2))
                flat(scene, (x - 2, bottom, 9, 1), 'brass')
    elif theme == 'solar':
        config = MOON_SCENES[large]
        loop = moon_loop(tick, large)
        scene_sprite(scene, assets, 'mo-moon', config['moon'])
        for x, y in ((6, 7), (width - 26, 17)):
            flat(scene, (x, y, 1, 1), 'bone')
        flat(scene, (0, config['surface_y'], width, height - config['surface_y']), 'stone_dark')
        flat(scene, (0, config['surface_y'], width, 1), 'stone_light')
        for x in (12, 54, 104, 160, 208, 270):
            if x + 3 <= width:
                flat(scene, (x, config['surface_y'] + (3 if large else 2), 3, 1), 'stone')
        scene_sprite(scene, assets, 'mo-lander', config['lander'])
        if loop['flag_visible']:
            scene_sprite(scene, assets, f'mo-flag-{loop["planted"]}', loop['flag_xy'])
        if loop['fly_visible']:
            scene_sprite(scene, assets, f'mo-flag-{loop["thrown"]}-fly', loop['fly_xy'])
        if loop['astro_visible']:
            scene_sprite(scene, assets, f'mo-astro-{loop["visitor"]}-{loop["frame"]}',
                         loop['astro_xy'], directional=True, facing=loop['facing'])
    elif theme == 'horses':
        flat(scene, (0, height - 2, width, 2), 'soil')
        crowd_y, fence_y = (10, 24) if large else (18, 22)
        suffix = 'big' if large else 'small'
        tile_strip(scene, assets[f'ho-crowd-{frame_pair(tick, 3)}-{suffix}'],
                   (0, crowd_y, width, 20 if large else 10))
        tile_strip(scene, assets[f'ho-fence-{suffix}'], (0, fence_y, width, 16 if large else 8))
        placard(scene, theme, (78, 0, 148, 24) if large else (0, 0, 125, 18),
                'Agents Horse Race', layout['font'])
    elif theme == 'metro':
        placard(scene, theme, (68, 0, 168, 24) if large else (0, 0, 136, 16),
                'Agents Metro Station', layout['font'])
        actor_y = 24 if large else 15
        for slot, kind in enumerate('abc'):
            state, actor_x = actor_state(slot, tick, large)
            if state != 'hidden':
                frame = frame_pair(tick + slot, 2) if layout.get('motion', True) else 1
                scene_sprite(scene, assets, f'me-actor-{kind}-{frame}', (actor_x, actor_y))
        flat(scene, (0, height - 2, width, 2), 'stone_dark')
        flat(scene, (0, height - 2, width, 1), 'stone_light')
    image.alpha_composite(scene, (sx, sy))


def row_zones(layout, index):
    y = layout['row_y'][index]
    if layout.get('text_grid'):
        if layout['scale'] == 2:
            return {'label': (12, y, 200, 26), 'value': (228, y, 80, 26),
                    'countdown': (12, y + 26, 296, 26)}
        return {'label': (4, y, 86, 18), 'value': (96, y, 46, 18),
                'countdown': (148, y, 88, 18)}
    small_y = y + layout['text_offset']
    size = layout['font']
    return {
        'label': (layout['label_xw'][0], small_y, layout['label_xw'][1], size),
        'value': (layout['value_xw'][0], y, layout['value_xw'][1], layout['percent_font']),
        'countdown': (layout['reset_xw'][0], small_y, layout['reset_xw'][1], size),
        'track': (layout['track_xw'][0], y + layout['track_offset'],
                  layout['track_xw'][1], layout['track_height']),
    }


def themed_track(image, assets, layout, theme, index, usage, tick, gallop_frame=None):
    x, y, width, height = row_zones(layout, index)['track']
    scale, codex = layout['scale'], index > 1
    provider = 'teal' if codex else 'ember'
    if theme == 'graveyard':
        name = 'gy-wisp-head' + ('-teal' if codex else '')
        tail = 'gy-wisp-tail' + ('-teal' if codex else '')
        pad, sprite_width, sprite_height = 4 * scale, 8 * scale, 8 * scale
        fill_color, background = ('teal' if codex else 'bone'), 'stone_dark'
    elif theme == 'alchemy':
        name, tail = ('al-drop-teal' if codex else 'al-drop'), None
        pad, sprite_width, sprite_height = 3 * scale, 6 * scale, 8 * scale
        fill_color = ('teal_light' if (usage or 0) >= 80 else 'teal') if codex else (
            'rust' if (usage or 0) >= 80 else 'gold')
        background = 'wood_dark'
    elif theme == 'candle':
        name, tail = ('wick-flame-teal' if codex else 'wick-flame'), None
        if frame_pair(tick, 2) == 2:
            name += '-2'
        pad, sprite_width, sprite_height = 3 * scale, 6 * scale, 8 * scale
        fill_color, background = 'soil', 'bone'
    elif theme == 'solar':
        name, tail = ('so-ship-teal' if codex else 'so-ship'), None
        pad, sprite_width, sprite_height = 7 * scale, 14 * scale, 10 * scale
        fill_color, background = provider, 'stone_dark'
    elif theme == 'horses':
        frame = gallop_frame or frame_pair(tick, 1)
        name = f'ho-horse-{"teal" if codex else "warm"}-mini-{frame}'
        tail = None
        pad, sprite_width, sprite_height = 6 * scale, 12 * scale, 8 * scale
        fill_color, background = None, 'soil'
    elif theme == 'metro':
        name, tail = f'me-car-{"teal" if codex else "warm"}-mini', None
        pad, sprite_width, sprite_height = (7 if scale == 1 else 13), 13 * scale, 6 * scale
        fill_color, background = provider, 'stone_dark'
    else:
        return
    span = width - 2 * pad
    length = amount(span, usage)
    anchor = x + pad + length
    directional = theme in ('graveyard', 'solar', 'horses', 'metro')
    if theme == 'alchemy':
        flat(image, (x, y, width, height), 'stone_light')
        flat(image, (x + 1, y + 1, width - 2, height - 2), background)
        if length:
            flat(image, (x + pad, y + 1, length, height - 2), fill_color)
    else:
        flat(image, (x, y, width, height), background)
        if theme == 'graveyard':
            body = assets[f'gy-wisp-body{"-teal" if codex else ""}-{"big" if scale == 2 else "small"}']
            tile_strip(image, body, (x + pad, y, length, height), (tick // 2) % body.width)
        elif theme == 'metro':
            tile_strip(image, assets[f'me-rail-{"big" if scale == 2 else "small"}'],
                       (x, y, width, height))
            flat(image, (x + pad, y + 3 * scale, length, 2 * scale), fill_color)
        elif fill_color:
            flat(image, (x + pad, y, length, height), fill_color)
    if theme == 'alchemy' and length:
        liquid_height, bubble_size = height - 2, scale
        run = liquid_height - bubble_size + 1
        for bubble in range(2):
            bx = x + pad + max(0, length // (3 if bubble == 0 else 2) - bubble_size // 2)
            by = y + 1 + run - 1 - (tick + index * 2 + bubble * (run // 2)) % run
            if bx + bubble_size <= x + pad + length:
                glint = 'teal_glint' if codex and (usage or 0) >= 80 else ('teal_light' if codex else 'flame')
                flat(image, (bx, by, bubble_size, bubble_size), glint)
    if theme == 'horses':
        flat(image, (x, y + height - 1, width, 1), 'stone_dark')
        # Two native tiles and a bright edge mark the finish beneath the rider.
        tile = assets[f'ho-checker-{"big" if scale == 2 else "small"}']
        finish_x = x + width - pad - tile.width
        tile_strip(image, tile, (finish_x, y, tile.width * 2, height))
        flat(image, (finish_x - 1, y, 1, height), 'suit')
    if theme == 'metro':
        dot = 6 if scale == 2 else 3
        for station in range(6):
            center = x + pad + amount(span, station * 20)
            left, top = center - dot // 2, y + (height - dot) // 2
            flat(image, (left, top, dot, dot), provider)
            if usage is None or center > anchor:
                flat(image, (left + 1, top + 1, dot - 2, dot - 2), 'canvas')
    if usage is None and theme != 'horses':
        return
    if theme == 'horses' and usage is not None and amount(100, usage) > 0:
        dust_frame = frame_pair(tick + index, 2) if layout.get('motion', True) else 1
        dust = assets[f'ho-dust-{dust_frame}-{"big" if scale == 2 else "small"}']
        lane = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        lane.alpha_composite(dust, (anchor - x - sprite_width // 2 - 7 * scale, height - dust.height))
        image.alpha_composite(lane, (x, y))
    if tail and length >= 9 * scale:
        scene_sprite(image, assets, tail, (x, y), scale, True)
    tip_y = y + (height - sprite_height) // 2
    if theme == 'metro':
        tip_y += bob(tick)
    elif theme == 'candle':
        tip_y -= ((tick + 1) // 2) % 2
    scene_sprite(image, assets, name, (anchor - sprite_width // 2, tip_y), scale, directional)


def shared_widgets(image, assets, layout, values, present, theme, tick, countdowns, gallop_frame):
    status = 'Waiting for data' if values[0] is None else (
        'Updated 14:02' if layout['scale'] == 2 and theme != 'text' else '14:02')
    # Two palette colors represent the status shimmer's composited endpoints.
    status_color = 'bone_dim' if theme == 'text' and (tick // 8) % 2 else 'bone'
    label(image, layout['status'], status, layout['font'], status_color, right=True, ellipsis=True)
    for index in range(4):
        if index > 1 and not present:
            continue
        zones = row_zones(layout, index)
        name = ('Claude' if index < 2 else 'Codex') + (' 5h' if index % 2 == 0 else ' 7d')
        value = '--%' if values[index] is None else f'{amount(100, values[index])}%'
        assert set(value) <= set('0123456789%?-')
        text_font = layout['percent_font'] if theme == 'text' else layout['font']
        label(image, zones['label'], name, text_font)
        color = 'teal' if index > 1 else ('bone' if theme == 'graveyard' else 'ember')
        label(image, zones['value'], value, layout['percent_font'], color, right=True)
        countdown = countdowns[index] or 'reset unknown'
        if theme == 'text' and layout['scale'] == 1:
            countdown = countdown.removeprefix('resets in ').replace('reset unknown', 'unknown')
        label(image, zones['countdown'], countdown, text_font, right=True)
        if theme != 'text':
            themed_track(image, assets, layout, theme, index, values[index], tick, gallop_frame)


def render_frame(assets, size, theme, values, present=True, flame_frame=None,
                 gallop_frame=None, tick=0, motion=True, countdowns=None):
    if theme not in THEMES:
        raise ValueError(f'Unknown theme: {theme}')
    if len(values) != 4:
        raise ValueError('Four independent metrics are required')
    if tick < 0 or int(tick) != tick:
        raise ValueError('tick must be a nonnegative integer')
    if any(v is not None and (not isinstance(v, (int, float)) or not math.isfinite(v)) for v in values):
        raise ValueError('Metrics must be finite numbers or None')
    countdowns = ('resets in 23h 59m',) * 4 if countdowns is None else countdowns
    if len(countdowns) != 4:
        raise ValueError('Four countdowns are required')
    layout = theme_layout(size, theme)
    layout['motion'] = motion
    tick = int(tick) if motion else 0
    if not motion:
        flame_frame = gallop_frame = 1
    image = Image.new('RGBA', size, PALETTE['canvas'])
    if theme != 'text':
        draw_scene(image, assets, layout, theme, values, present, tick, flame_frame)
    shared_widgets(image, assets, layout, values, present, theme, tick, countdowns, gallop_frame)
    return image


def activity_previews(assets, size, previews):
    width, height = size
    large = width == 320
    spooks = [spook_state(tick, large) for tick in range(4096)]
    predicates = (
        lambda s: s['act'] == 'zombie' and s['state'] == 'walk' and s['facing'] == 'r' and s['xy'][0] > 40,
        lambda s: s['act'] == 'zombie' and s['state'] == 'walk' and s['facing'] == 'l' and s['xy'][0] < 160,
        lambda s: s['act'] == 'vampire' and s['state'] == 'walk' and 60 < s['xy'][0] < 160,
        lambda s: s['state'] == 'stop',
        lambda s: s['state'] == 'transform',
        lambda s: s['state'] == 'bat' and s['phase'] == 0,
        lambda s: s['state'] == 'bat' and s['xy'][1] <= 0,
        lambda s: s['state'] == 'wait' and s['xy'][1] < 0,
    )
    visits = [next(t for t, state in enumerate(spooks) if predicate(state)) for predicate in predicates]
    patrols = [ghost_patrol(0, tick, large) for tick in range(2048)]
    patrol_ticks = [0, next(t for t, state in enumerate(patrols) if state['facing'] == 'l')]
    patrol_ticks += [next(t for t, state in enumerate(patrols) if state['state'] == name
                         and (name == 'hidden' or 0 <= state['x'] < 180))
                     for name in ('leave', 'hidden', 'enter')]
    sheet = Image.new('RGBA', (8 * width + 72, 2 * (height + 32) + 8), PALETTE['canvas'])
    for row, ticks in enumerate((visits, patrol_ticks)):
        for column, tick in enumerate(ticks):
            x, y = 8 + column * (width + 8), 8 + row * (height + 32)
            state = spooks[tick] if row == 0 else patrols[tick]
            title = f'{state["act"]} {state["state"]}' if row == 0 else f'ghost {state["state"]}'
            label(sheet, (x, y, width, 16), f'{title} t={tick}', 16)
            sheet.alpha_composite(render_frame(assets, size, 'graveyard', (65, 25, 86, 38), tick=tick),
                                  (x, y + 24))
    sheet.save(previews / f'graveyard-roaming-{width}x{height}.png', optimize=False, compress_level=9)
    sheet = Image.new('RGBA', (4 * width + 40, 2 * (height + 32) + 8), PALETTE['canvas'])
    for row, ticks in enumerate(((0, 4, 8, 12), (1, 5, 9, 13))):
        for column, tick in enumerate(ticks):
            x, y = 8 + column * (width + 8), 8 + row * (height + 32)
            label(sheet, (x, y, width, 16), f'Vessel bubbles t={tick}', 16)
            sheet.alpha_composite(render_frame(assets, size, 'alchemy', (65, 25, 86, 38), tick=tick),
                                  (x, y + 24))
    sheet.save(previews / f'alchemy-bubbles-{width}x{height}.png', optimize=False, compress_level=9)


def generate_previews(output, previews):
    previews.mkdir(parents=True, exist_ok=True)
    stems = sprite_stems()
    assets = {stem: Image.open(output / f'{stem}.png').convert('RGBA') for stem in stems}
    batches = [('', ('graveyard', 'alchemy', 'candle')),
               ('2', ('solar', 'horses', 'metro', 'text'))]
    for batch, themes in batches:
        rows = [(theme, present) for theme in themes for present in (True, False)]
        for size in LAYOUTS:
            width, height = size
            padding, header, row_label = 8, 24, 24
            sheet = Image.new('RGBA', (4 * width + 5 * padding,
                              header + len(rows) * (height + row_label + padding) + padding),
                              PALETTE['canvas'])
            for column, usage in enumerate((0, 40, 80, 100)):
                label(sheet, (padding + column * (width + padding), 4, width, 16),
                      f'{usage}%', 16)
            for row, (theme, present) in enumerate(rows):
                y = header + padding + row * (height + row_label + padding)
                label(sheet, (padding, y, sheet.width - 2 * padding, row_label),
                      f'{theme_title(theme)} | Codex {"present" if present else "absent"}', 16)
                for column, usage in enumerate((0, 40, 80, 100)):
                    frame = render_frame(assets, size, theme, (usage,) * 4, present)
                    sheet.alpha_composite(frame, (padding + column * (width + padding), y + row_label))
            sheet.save(previews / f'layouts{batch}-{width}x{height}.png', optimize=False, compress_level=9)
    # Motion and state sheets use the same compositor as the main comparisons.
    for size in LAYOUTS:
        width, height = size
        contact = Image.new('RGBA', (2 * width + 24, 4 * (height + 24) + 8), PALETTE['canvas'])
        for index, theme in enumerate(THEMES):
            x, y = 8 + (index % 2) * (width + 8), 8 + (index // 2) * (height + 24)
            label(contact, (x, y, width, 16), theme_title(theme), 16)
            panel = render_frame(
                assets, size, theme, (65, 25, 86, 38))
            contact.alpha_composite(panel, (x, y + 20))
            preview_name = 'moon' if theme == 'solar' else theme
            panel.save(previews / f'round3-{preview_name}-{width}x{height}.png', optimize=False, compress_level=9)
        (previews / f'round3-solar-{width}x{height}.png').unlink(missing_ok=True)
        contact.save(previews / f'round3-contact-{width}x{height}.png', optimize=False, compress_level=9)
        # Each provider's six phases share the same bounded scene compositor.
        large = width == 320
        config = MOON_SCENES[large]
        walk_ticks = (config['width'] - config['flag'][0] - 4 + config['step'] - 1) // config['step']
        throw_ticks = (config['flag'][1] - 2 + 8 + 3) // 4
        phase_ticks = (0, 8 + walk_ticks // 2, 8 + walk_ticks,
                       8 + walk_ticks + 3 + throw_ticks // 2,
                       8 + walk_ticks + 3 + throw_ticks,
                       8 + walk_ticks + 3 + throw_ticks + 3 + walk_ticks // 2)
        half = moon_loop(0, large)['half_ticks']
        sheet = Image.new('RGBA', (6 * width + 56, 2 * (height + 32) + 8), PALETTE['canvas'])
        for row in range(2):
            for column, phase_tick in enumerate(phase_ticks):
                tick = phase_tick + row * half
                state = moon_loop(tick, large)
                x, y = 8 + column * (width + 8), 8 + row * (height + 32)
                label(sheet, (x, y, width, 16), f'{state["phase"]} {state["visitor"]} t={tick}', 16)
                sheet.alpha_composite(render_frame(assets, size, 'solar', (40, 80, 40, 80), tick=tick),
                                      (x, y + 24))
        sheet.save(previews / f'moon-loop-{width}x{height}.png', optimize=False, compress_level=9)
        sheet = Image.new('RGBA', (4 * width + 40, height + 32), PALETTE['canvas'])
        for column, tick in enumerate((0, 20, 80, 240)):
            x = 8 + column * (width + 8)
            panel = render_frame(assets, size, 'metro', (65, 25, 86, 38), tick=tick)
            label(sheet, (x, 4, width, 16), f'Platform tick {tick}', 16)
            sheet.alpha_composite(panel, (x, 24))
        sheet.save(previews / f'platform-{width}x{height}.png', optimize=False, compress_level=9)
        for kind in ('motion', 'states'):
            sheet = Image.new('RGBA', (4 * width + 40, 32 + 7 * (height + 32)), PALETTE['canvas'])
            headings = ('tick 0', 'tick 2', 'tick 3', 'tick 8') if kind == 'motion' else (
                'independent', 'partial unknown', 'waiting', 'Codex absent')
            for column, heading in enumerate(headings):
                label(sheet, (8 + column * (width + 8), 4, width, 16), heading, 16)
            for row, theme in enumerate(THEMES):
                y = 32 + row * (height + 32)
                label(sheet, (8, y, sheet.width - 16, 16), theme_title(theme), 16)
                for column in range(4):
                    if kind == 'motion':
                        frame = render_frame(assets, size, theme, (40, 80, 40, 80), tick=(0, 2, 3, 8)[column])
                    else:
                        values = ((0, 40, 80, 100), (None, 40, 80, None),
                                  (None,) * 4, (100, 80, 40, 0))[column]
                        frame = render_frame(assets, size, theme, values, present=column != 3,
                                             countdowns=(None,) * 4 if column in (1, 2) else None)
                    sheet.alpha_composite(frame, (8 + column * (width + 8), y + 24))
            sheet.save(previews / f'{kind}-{width}x{height}.png', optimize=False, compress_level=9)
        activity_previews(assets, size, previews)
    contact = Image.open(previews / 'contact.png').convert('RGBA')
    big_height = max(height * 2 for _, _, height, sizes, _, _ in SPECS if 'big' in sizes)
    smalls = contact.crop((0, big_height + 8, contact.width, contact.height))
    smalls.resize((smalls.width * 4, smalls.height * 4), Image.Resampling.NEAREST).save(
        previews / 'zoom-smalls.png', optimize=False, compress_level=9)


def main():
    parser = argparse.ArgumentParser(description='Draw pixel-art sprites, a contact sheet and fixed-font layout previews.')
    parser.add_argument('output', type=Path, help='Directory for the PNG collection')
    parser.add_argument('--previews', type=Path,
                        help='Directory for the contact sheet and layout previews; '
                             'defaults to a system temp directory, outside the repository')
    args = parser.parse_args()
    previews = args.previews or Path(tempfile.gettempdir()) / 'tokentide-theme-previews'
    generate(args.output, previews)
    generate_previews(args.output, previews)
    print(f'previews: {previews}')


if __name__ == '__main__':
    main()
