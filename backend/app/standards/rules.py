"""The numbers of the Product Design Manual, in one place.

`docs/manual/{en,es}` is the source of truth; `tests/test_validators.py` checks that the
numbers quoted in the manual match these constants. Lengths in millimetres.
"""

from typing import Final

RULE_EDITION: Final = "Edition 1 (2026-11)"

# GEN-01 units and resolution
STEP_MM: Final = 0.1
GENERAL_TOLERANCE_MM: Final = 0.1

# GB-01 mandrel sizes
MANDREL_SIZES_MM: Final = (1.0, 1.5, 2.0, 2.5)
# GB-02 glass wall around the hole
MIN_GLASS_WALL_MM: Final = 1.5
# GB-03 bead diameter
BEAD_DIAMETER_MM: Final = (4.0, 20.0)
FACETED_MIN_DIAMETER_MM: Final = 6.0
# GB-04 lentil thickness / diameter
LENTIL_RATIO: Final = (0.40, 0.70)
# GB-05 facets
FACET_COUNT: Final = (8, 32)
FACET_ROWS: Final = (1, 3)
MIN_FACET_WIDTH_MM: Final = 1.5
# GB-06 rondelle height / diameter
RONDELLE_RATIO: Final = (0.40, 0.80)

# CH-01 charm thickness
CHARM_THICKNESS_MM: Final = (1.0, 3.0)
# CH-02 hanging loop
MIN_LOOP_INNER_MM: Final = 1.5
MIN_LOOP_WALL_MM: Final = 0.8
# CH-03 smallest feature (mold limit) and the tip radius that guarantees it
MIN_FEATURE_MM: Final = 0.6
TIP_RADIUS_MM: Final = 0.3
# CH-04 charm body height (discs: diameter)
CHARM_HEIGHT_MM: Final = (8.0, 30.0)
# CH-06 disc engraving
ENGRAVING_MAX_CHARS: Final = 12
ENGRAVING_FONT: Final = "montserrat_extrabold"
ENGRAVING_MIN_LETTER_MM: Final = 3.0  # measured: each text is also checked against CH-03
ENGRAVING_TEXT_FIT: Final = 0.80  # the text fits within 80% of the disc diameter
ENGRAVING_DEPTH_MM: Final = (0.2, 0.4)
# CH-07 initial charms, measured with `python -m app.cli measure-fonts` (2026-11-17):
# minimum letter height per font, letters that need more, and letters a font cannot make.
FONT_MIN_HEIGHT_MM: Final = {
    "pacifico": 10.5,
    "cinzel_bold": 16.5,
    "montserrat_extrabold": 8.0,  # the font passes from 4.5 mm; CH-04 sets 8.0
}
LETTER_MIN_HEIGHT_MM: Final = {("pacifico", "Y"): 18.5}
FONT_UNAVAILABLE_LETTERS: Final = {"cinzel_bold": "K"}  # drawn in two separate pieces
# CH-08 crescent proportions
CRESCENT_WIDTH_RATIO: Final = (0.20, 0.45)  # band width / body height
CRESCENT_MAX_STAR_RATIO: Final = 0.50  # star diameter / body height

FONT_FILES: Final = {
    "pacifico": "Pacifico-Regular.ttf",
    "cinzel_bold": "Cinzel-Bold.ttf",
    "montserrat_extrabold": "Montserrat-ExtraBold.ttf",
}
