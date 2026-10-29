"""Colours. Flat vector look with thick near-black outlines."""

BG = (16, 22, 36)  # window background
PANEL = (26, 35, 56)
PANEL_EDGE = (44, 58, 88)
OUTLINE = (12, 14, 20)  # the thick cartoon outline
TEXT = (236, 240, 248)
TEXT_DIM = (150, 162, 186)
ACCENT = (250, 222, 60)

# table, after the reference picture: bright cloth fading to deep green at the edges
CLOTH_CENTRE = (98, 190, 102)
CLOTH_EDGE = (34, 104, 50)
MINI_CLOTH = (62, 146, 80)  # the cloth of the small tables in the how-to-play pictures
CUSHION = (24, 98, 50)
CUSHION_NOSE = (72, 152, 88)  # the lit edge facing the cloth
CUSHION_BASE = (14, 62, 32)
# wood across the rail: (position 0 = outer edge .. 1 = inner lip, colour)
WOOD_STOPS = (
    (0.0, (70, 36, 16)),
    (0.18, (118, 64, 30)),
    (0.55, (152, 90, 44)),
    (0.85, (122, 68, 32)),
    (1.0, (84, 44, 20)),
)
PLATE = (228, 204, 146)  # brass pocket plates
PLATE_EDGE = (112, 82, 38)
PLATE_INNER = (172, 138, 78)
SIGHT = (242, 204, 106)  # the diamonds on the rails
SIGHT_EDGE = (128, 90, 36)
POCKET = (4, 4, 5)  # the deepest part of the hole
POCKET_WALL = (34, 35, 39)  # the near wall, a crescent around the hole
POCKET_RIM = (58, 60, 66)  # dark ring between the lip and the wall
POCKET_LIP = (132, 134, 140)  # the light metal lip

ERROR = (240, 96, 90)
OK = (126, 226, 126)

AIM = (226, 255, 130)
AIM_GLOW = (190, 240, 90)

BALL_COLORS = {
    0: (250, 250, 244),  # cue
    1: (252, 202, 36),
    2: (46, 98, 226),
    3: (232, 56, 52),
    4: (134, 64, 186),
    5: (246, 132, 34),
    6: (34, 156, 76),
    7: (146, 44, 46),
    8: (28, 28, 34),
}
WHITE = (252, 252, 248)
