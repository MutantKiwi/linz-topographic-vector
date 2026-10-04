"""
Build a hand-drawn style cartographic rock line for NZ Topo50.

Takes the rock_line layer (rock outlines with coast/island/lake linework
removed) and bakes the printed-map symbol into geometry:

  * outline - the rock line resampled at irregular intervals and nudged
              sideways by a small random amount, giving a jagged line
  * tick    - a short stroke from every outline vertex towards the land
              (the inside of the rock polygon), with varying length and angle

Lengths vary with a blend of slow-moving and per-tick noise, so ticks come in
runs of longer and shorter strokes like the printed map rather than looking
like static. Ticks are cut where they would leave the rock polygon or cross
the coastline, so they never run over the land.

Everything is seeded from each feature's marine_id, so re-running gives the
same drawing.

All distances are ground metres. At 1:50,000, 1 mm on the map = 50 m.

Usage:
  python rock_line_carto.py --rock-line rock_line.parquet --marine marine.parquet \
      --coastline coastline.parquet --island island.parquet --water water.parquet \
      --output rock_line_carto.parquet
"""

import argparse
import hashlib
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

NZTM = 2193
NZGD2000 = 4167

# ---- symbol parameters (ground metres; divide by 50 for map mm at 1:50,000)
SPACING = 10.5        # mean distance between ticks
SPACING_JITTER = 0.40  # +/- fraction of SPACING
JAG = 5.0             # max sideways nudge of the outline
TICK_MIN = 12.0       # shortest tick
TICK_MAX = 40.0       # longest tick
TICK_RUN = 110.0      # distance over which tick length drifts (runs of long/short)
TICK_WHITE = 0.45     # 0 = smooth runs only, 1 = every tick independent
ANGLE_JITTER = 11.0   # std dev of tick angle away from perpendicular, degrees
SKIP = 0.05           # fraction of ticks left out, for occasional gaps
TANGENT_WINDOW = 9.0  # half-window used to measure the line direction
LAND_GAP = 0.85       # ticks cut by land keep this fraction of their length
OPPOSITE_GAP = 0.45   # ticks heading for the far side of the same outline stop this far across
CROSS_GAP = 0.6       # a tick that would cross a neighbour stops this far short of it
MIN_TICK = 4.0        # ticks shorter than this after cutting are dropped
MIN_PART = 12.0       # rock line fragments shorter than this are left out
TIP_CLEARANCE = 5.0   # ticks are treated as this much longer when testing for crossings
CROSS_PASSES = 3      # rounds of trimming ticks that cross each other


def _rng(seed: str) -> np.random.Generator:
    return np.random.default_rng(int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8], "big"))


def _draw_part(line, poly, rng):
    """Return (outline LineString, tick start xy, tick end xy) for one line part."""
    length = line.length
    closed = line.is_ring
    n = max(int(round(length / SPACING)), 3 if closed else 1)

    steps = 1.0 + rng.uniform(-SPACING_JITTER, SPACING_JITTER, n)
    d = np.concatenate([[0.0], np.cumsum(steps)])
    d = d / d[-1] * length

    def at(dist):
        dist = np.mod(dist, length) if closed else np.clip(dist, 0.0, length)
        return shapely.get_coordinates(shapely.line_interpolate_point(line, dist))

    pts = at(d)
    tangent = at(d + TANGENT_WINDOW) - at(d - TANGENT_WINDOW)
    norm = np.hypot(tangent[:, 0], tangent[:, 1])
    norm[norm == 0] = 1.0
    tangent /= norm[:, None]
    normal = np.column_stack([-tangent[:, 1], tangent[:, 0]])  # left of travel

    # which side is land (inside the rock polygon)?
    if poly is not None:
        probe = pts + normal * 2.0
        inside = shapely.contains_xy(poly, probe[:, 0], probe[:, 1])
        if inside.mean() < 0.5:
            normal = -normal

    jag = rng.uniform(-JAG, JAG, n + 1)
    if closed:
        jag[-1] = jag[0]
    else:
        jag[0] = jag[-1] = 0.0  # keep the ends on the coast
    base = pts + normal * jag[:, None]
    outline = shapely.LineString(base) if len(base) > 1 else None

    # tick length: slow drift blended with per-tick noise, skewed towards short
    knots = max(int(np.ceil(length / TICK_RUN)), 1) + 1
    kv = rng.uniform(0, 1, knots)
    if closed:
        kv[-1] = kv[0]
    slow = np.interp(d / length * (knots - 1), np.arange(knots), kv)
    mix = (1 - TICK_WHITE) * slow + TICK_WHITE * rng.uniform(0, 1, n + 1)
    tick_len = TICK_MIN + (TICK_MAX - TICK_MIN) * mix**1.4

    ang = np.radians(rng.normal(0, ANGLE_JITTER, n + 1))
    cos, sin = np.cos(ang), np.sin(ang)
    direction = np.column_stack(
        [normal[:, 0] * cos - normal[:, 1] * sin, normal[:, 0] * sin + normal[:, 1] * cos]
    )
    ends = base + direction * tick_len[:, None]

    keep = rng.uniform(0, 1, n + 1) >= SKIP
    if closed:
        keep[-1] = False  # same point as the first
    else:
        keep[0] = keep[-1] = False
    return outline, base[keep], ends[keep]


def _nearby_segments(lines, rock_lines):
    """Explode shoreline linework into single segments, keeping only those near rock lines."""
    coords, idx = shapely.get_coordinates(lines, return_index=True)
    same = idx[:-1] == idx[1:]
    a, b = coords[:-1][same], coords[1:][same]
    reach = TICK_MAX + JAG
    bounds = shapely.bounds(rock_lines) + np.array([-reach, -reach, reach, reach])
    tree = shapely.STRtree(shapely.box(*bounds.T))
    near = np.unique(tree.query(shapely.points((a + b) / 2), predicate="intersects")[0])
    return shapely.linestrings(np.stack([a[near], b[near]], axis=1))


def _cut_ticks(starts, ends, poly_idx, polys, land_lines, outlines):
    """Shorten ticks that leave their rock polygon, cross a shoreline, or run into other linework."""
    full = np.hypot(*(ends - starts).T)
    reach = full.copy()

    ticks = shapely.linestrings(np.stack([starts, ends], axis=1))
    start_pts = shapely.points(starts)

    def first_hit(barriers, sel):
        hit = shapely.intersection(ticks[sel], barriers)
        dist = shapely.distance(start_pts[sel], hit)  # nan when no intersection
        return np.where(np.isnan(dist), np.inf, dist)

    # leaving the rock polygon: first crossing of its boundary beyond the jag zone
    has_poly = poly_idx >= 0
    if has_poly.any():
        sel = np.flatnonzero(has_poly)
        shrunk = shapely.linestrings(
            np.stack([starts[sel] + (ends[sel] - starts[sel]) * np.minimum((JAG * 1.5 + 1.0) / full[sel], 1.0)[:, None], ends[sel]], axis=1)
        )
        hit = shapely.intersection(shrunk, shapely.boundary(polys[poly_idx[sel]]))
        dist = shapely.distance(start_pts[sel], hit)
        reach[sel] = np.minimum(reach[sel], np.where(np.isnan(dist), np.inf, dist))

    # crossing a coastline / island / lake shore
    if land_lines is not None and len(land_lines):
        tree = shapely.STRtree(land_lines)
        ti, li = tree.query(ticks, predicate="intersects")
        if len(ti):
            dist = first_hit(land_lines[li], ti)
            np.minimum.at(reach, ti, dist)

    new_len = np.where(reach < full, reach * LAND_GAP, full)

    # running into the far side of the same outline (small or narrow rocks):
    # stop before the middle so opposing ticks don't meet
    lead = np.minimum(2.0 / full, 1.0)[:, None]
    inner = shapely.linestrings(np.stack([starts + (ends - starts) * lead, ends], axis=1))
    shapely.prepare(outlines)
    hit = np.flatnonzero(shapely.intersects(outlines, inner))
    if len(hit):
        dist = shapely.distance(start_pts[hit], shapely.intersection(inner[hit], outlines[hit]))
        new_len[hit] = np.minimum(new_len[hit], dist * OPPOSITE_GAP)

    # where ticks cross each other (inside of bends, small rocks), stop the one
    # that is crossed nearer its tip short of the crossing
    for _ in range(CROSS_PASSES):
        # test with each tick extended a little, so tips also keep clear of each other
        lines = shapely.linestrings(
            np.stack([starts, starts + (ends - starts) * ((new_len + TIP_CLEARANCE) / full)[:, None]], axis=1)
        )
        ia, ib = shapely.STRtree(lines).query(lines, predicate="intersects")
        pair = ia < ib
        ia, ib = ia[pair], ib[pair]
        if not len(ia):
            break
        cross = shapely.intersection(lines[ia], lines[ib])
        da, db = shapely.distance(start_pts[ia], cross), shapely.distance(start_pts[ib], cross)
        trim_b = db / new_len[ib] >= da / new_len[ia]
        which = np.where(trim_b, ib, ia)
        np.minimum.at(new_len, which, np.where(trim_b, db, da) * CROSS_GAP)
    new_ends = starts + (ends - starts) * (new_len / full)[:, None]

    ok = new_len >= MIN_TICK
    return starts[ok], new_ends[ok], ok


def run(rock_line_path, marine_path, output_path, coastline_path=None, island_path=None, water_path=None):
    rock_line = gpd.read_parquet(rock_line_path).to_crs(NZTM)
    marine = gpd.read_parquet(marine_path).to_crs(NZTM)
    rock = marine[marine["type"] == "rock"].set_index("id")

    land = []
    if coastline_path:
        land.append(gpd.read_parquet(coastline_path).to_crs(NZTM).geometry)
    if island_path:
        land.append(gpd.read_parquet(island_path).to_crs(NZTM).geometry.boundary)
    if water_path:
        water = gpd.read_parquet(water_path).to_crs(NZTM)
        land.append(water[water["type"] == "lake"].geometry.boundary)
    land_lines = None
    if land:
        land_lines = _nearby_segments(pd.concat(land, ignore_index=True).values, rock_line.geometry.values)

    polys = np.asarray(rock.geometry.reindex(rock_line["marine_id"]).values, dtype=object)
    shapely.prepare(polys)

    outlines, t_start, t_end, t_feat = [], [], [], []
    for fi, (mid, geom, poly) in enumerate(zip(rock_line["marine_id"], rock_line.geometry.values, polys)):
        rng = _rng(f"rock_line_carto/{mid}")
        feat_outlines = []
        for part in shapely.get_parts(geom):
            if part.length < MIN_PART:
                continue
            outline, s, e = _draw_part(part, poly, rng)
            if outline is not None:
                feat_outlines.append(outline)
            if len(s):
                t_start.append(s)
                t_end.append(e)
                t_feat.append(np.full(len(s), fi))
        outlines.append(shapely.MultiLineString(feat_outlines) if feat_outlines else None)

    t_start, t_end, t_feat = np.vstack(t_start), np.vstack(t_end), np.concatenate(t_feat)
    poly_idx = np.where(pd.isna(polys)[t_feat], -1, t_feat)
    outline_arr = np.array(outlines, dtype=object)
    s, e, ok = _cut_ticks(t_start, t_end, poly_idx, polys, land_lines, outline_arr[t_feat])
    t_feat = t_feat[ok]

    tick_lines = shapely.linestrings(np.stack([s, e], axis=1))
    order = np.argsort(t_feat, kind="stable")
    feats, first = np.unique(t_feat[order], return_index=True)
    groups = np.split(tick_lines[order], first[1:])
    ticks = np.full(len(rock_line), None, dtype=object)
    for f, g in zip(feats, groups):
        ticks[f] = shapely.MultiLineString(list(g))

    keep_cols = [c for c in ("marine_id", "type", "name", "subtype") if c in rock_line.columns]
    attrs = rock_line[keep_cols].reset_index(drop=True)
    out = pd.concat(
        [
            gpd.GeoDataFrame(attrs.assign(part="outline"), geometry=outlines, crs=NZTM),
            gpd.GeoDataFrame(attrs.assign(part="tick"), geometry=list(ticks), crs=NZTM),
        ],
        ignore_index=True,
    )
    out = out[~out.geometry.isna()].to_crs(NZGD2000)
    out.to_parquet(output_path)
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rock-line", required=True, type=Path)
    p.add_argument("--marine", required=True, type=Path)
    p.add_argument("--coastline", type=Path)
    p.add_argument("--island", type=Path)
    p.add_argument("--water", type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    result = run(a.rock_line, a.marine, a.output, a.coastline, a.island, a.water)
    print(f"Wrote {len(result)} features to {a.output}")
