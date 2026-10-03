"""
Mark railway tunnel sections in railway_line.

Splits each railway line at the portals of the train tunnels in tunnel_line
(type = 'train') and sets subtype = 'tunnel' on the sections inside a tunnel.
Everything else is carried over unchanged.

Usage:
  python railway_tunnel.py --railway railway_line.parquet --tunnel tunnel_line.parquet \
      --output railway_line_tunnel.parquet
"""

import argparse
import uuid
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.ops import substring

NZTM = 2193
TOL = 10.0       # a tunnel within this distance of a railway line is on that line (metres)
STEP = 2.0       # tunnel lines are sampled at this spacing to find where they run along the railway
SNAP = 1.0       # portals closer than this to a line end are moved to the end
MIN_LEN = 1.0    # shorter tunnel sections are ignored
ID_NAMESPACE = uuid.UUID("6f1d7c0e-5b0a-4f6e-9d0e-0a1b2c3d4e5f")


def tunnel_intervals(line, tunnels):
    """Distances along `line` (start, end) that lie inside any of `tunnels`."""
    length = line.length
    spans = []
    for tun in tunnels:
        pts = shapely.get_coordinates(shapely.segmentize(tun, STEP))
        p = shapely.points(pts)
        near = shapely.distance(p, line) <= TOL
        d = list(shapely.line_locate_point(line, p[near]))
        # a tunnel that runs past the end of this line covers the line right to that end
        ends = shapely.points(shapely.get_coordinates(line)[[0, -1]])
        if shapely.distance(ends[0], tun) <= TOL:
            d.append(0.0)
        if shapely.distance(ends[1], tun) <= TOL:
            d.append(length)
        if len(d) >= 2:
            spans.append((min(d), max(d)))
    merged = []
    for a, b in sorted(spans):
        a = 0.0 if a < SNAP else a
        b = length if length - b < SNAP else b
        if b - a < MIN_LEN:
            continue
        if merged and a <= merged[-1][1] + SNAP:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged, length


def run(railway_path, tunnel_path, output_path):
    rail_src = gpd.read_parquet(railway_path)
    rail = rail_src.to_crs(NZTM)
    tun = gpd.read_parquet(tunnel_path).to_crs(NZTM)
    tun = tun[tun["type"] == "train"]
    tgeoms = tun.geometry.values
    tree = shapely.STRtree(tgeoms)

    rows, geoms = [], []
    for i in range(len(rail)):
        line = rail.geometry.values[i]
        attrs = rail_src.iloc[i].drop("geometry").to_dict()
        hits = tree.query(line, predicate="dwithin", distance=TOL)
        spans, length = tunnel_intervals(line, tgeoms[hits]) if len(hits) else ([], line.length)
        if not spans:
            rows.append(attrs)
            geoms.append(rail_src.geometry.values[i])  # untouched original
            continue
        cuts = [0.0]
        for a, b in spans:
            cuts += [a, b]
        cuts.append(length)
        piece = 0
        for k in range(len(cuts) - 1):
            a, b = cuts[k], cuts[k + 1]
            if b - a <= 0:
                continue
            row = dict(attrs)
            if k % 2 == 1:
                row["subtype"] = "tunnel"
            row["id"] = str(uuid.uuid5(ID_NAMESPACE, f"{attrs['id']}/{piece}"))
            rows.append(row)
            geoms.append(substring(line, a, b))  # NZTM, reprojected below
            piece += 1

    out = gpd.GeoDataFrame(rows, geometry=None)
    # split pieces are in NZTM, untouched originals already in source CRS
    original_ids = set(rail_src["id"])
    is_split = np.array([r["id"] not in original_ids for r in rows])
    g = np.array(geoms, dtype=object)
    if is_split.any():
        g[is_split] = gpd.GeoSeries(list(g[is_split]), crs=NZTM).to_crs(rail_src.crs).values
    out = gpd.GeoDataFrame(out, geometry=list(g), crs=rail_src.crs)[list(rail_src.columns)]
    out["t50_fid"] = out["t50_fid"].astype(rail_src["t50_fid"].dtype)
    out.to_parquet(output_path)
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--railway", required=True, type=Path)
    p.add_argument("--tunnel", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    result = run(a.railway, a.tunnel, a.output)
    n = (result["subtype"] == "tunnel").sum()
    print(f"Wrote {len(result)} features ({n} tunnel sections) to {a.output}")
