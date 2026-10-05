"""
Page numbering and adjoining-sheet labels for an atlas grid.

Pure Python, no QGIS imports, so it can be tested on its own.

The base grid is a regular lattice of sheets (12 km x 18 km for A3 at
1:50,000). A sheet is a dict with at least:
    atlas_code, sheet_code, quad_pos, xmin, ymin, xmax, ymax
"""

DIRECTIONS = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}

EN_DASH = "–"


def sheet_label(sheet):
    return "{}{}{}".format(sheet["sheet_code"], EN_DASH, sheet["quad_pos"])


def lattice_key(x, y):
    return (int(round(x)), int(round(y)))


def build_lattice(sheets):
    """Index every sheet of the base grid by its lower-left corner."""
    return {lattice_key(s["xmin"], s["ymin"]): s for s in sheets}


def number_pages(selected, lattice):
    """
    Order the selected sheets row by row (top-left to bottom-right), number
    them from 1, and work out each sheet's four neighbours.

    Returns a new list of dicts in page order. Each has the original keys plus:
        page, page_count, page_label
        adj_<d>        neighbour's atlas_code, or None
        adj_<d>_name   neighbour's label, or None
        adj_<d>_page   neighbour's page number if it is in the selection
        adj_<d>_label  finished text for the layout
    for d in n, s, e, w.
    """
    ordered = sorted(selected, key=lambda s: (-int(round(s["ymax"])), int(round(s["xmin"]))))
    page_of = {s["atlas_code"]: i + 1 for i, s in enumerate(ordered)}
    count = len(ordered)

    out = []
    for i, sheet in enumerate(ordered):
        row = dict(sheet)
        row["page"] = i + 1
        row["page_count"] = count
        row["page_label"] = sheet_label(sheet)
        width = int(round(sheet["xmax"])) - int(round(sheet["xmin"]))
        height = int(round(sheet["ymax"])) - int(round(sheet["ymin"]))
        for d, (dx, dy) in DIRECTIONS.items():
            neighbour = lattice.get(lattice_key(sheet["xmin"] + dx * width, sheet["ymin"] + dy * height))
            if neighbour is None:
                row["adj_" + d] = None
                row["adj_" + d + "_name"] = None
                row["adj_" + d + "_page"] = None
                row["adj_" + d + "_label"] = ""
                continue
            name = sheet_label(neighbour)
            page = page_of.get(neighbour["atlas_code"])
            row["adj_" + d] = neighbour["atlas_code"]
            row["adj_" + d + "_name"] = name
            row["adj_" + d + "_page"] = page
            row["adj_" + d + "_label"] = name if page is None else "Joins Page {} ({})".format(page, name)
        out.append(row)
    return out


def side_filters(start_side, first_page=None, last_page=None):
    """
    Atlas filter expressions for the right-hand and left-hand layouts.

    start_side is 'right' or 'left': the side page 1 falls on.
    Returns (right_expression, left_expression).
    """
    right_remainder = 1 if start_side == "right" else 0
    left_remainder = 1 - right_remainder
    page_range = ""
    if first_page and last_page:
        page_range = ' AND "page" BETWEEN {} AND {}'.format(int(first_page), int(last_page))
    elif first_page:
        page_range = ' AND "page" >= {}'.format(int(first_page))
    elif last_page:
        page_range = ' AND "page" <= {}'.format(int(last_page))
    return (
        '"page" % 2 = {}{}'.format(right_remainder, page_range),
        '"page" % 2 = {}{}'.format(left_remainder, page_range),
    )


def safe_name(text):
    """A project name made safe for use as a folder and file name."""
    import re
    import unicodedata

    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", ascii_text.replace("'", "")).strip("_")
    return cleaned or "atlas"
