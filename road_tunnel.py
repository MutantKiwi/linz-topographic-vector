"""
Mark road tunnel sections in road_line.

Splits each road at the portals of the vehicle tunnels in tunnel_line
(type = 'vehicle') that run along it. The sections inside a tunnel get
type = 'tunnel' and tunnel = true. Everything else is carried over unchanged
with tunnel = false.

Most vehicle tunnels in tunnel_line are short livestock underpasses that pass
*under* a road, crossing it. Those do not put the road in a tunnel, so a tunnel
only counts when it runs along the road, not across it.

Usage:
  python road_tunnel.py --road road_line.parquet --tunnel tunnel_line.parquet \
      --output road_line_tunnel.parquet
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
TOL = 10.0        # a tunnel point within this distance of a road is on that road (metres)
STEP = 2.0        # tunnel lines are sampled at this spacing
ALONG = 0.7       # the tunnel must cover at least this much road per metre of tunnel to count as running along it
SNAP = 3.0        # portals closer than this to a road end are moved to the end
MIN_LEN = 5.0     # shorter tunnel sections are ignored
ID_NAMESPACE = uuid.UUID("3b0c5a52-7d1e-4f0a-9a63-5e2f1c7d9b10")


def tunnel_spans(roads, tunnels):
    """
    For every tunnel, find the stretch of each road it runs along.

    Each sample point on a tunnel is given to its single nearest road, so a road
    that merely runs parallel nearby is not marked.

    Returns {road_row: [(start, end, tunnel_row), ...]} in metres along the road.
    """
    road_geoms = roads.geometry.values
    tree = shapely.STRtree(road_geoms)
    spans = {}
    for ti, tunnel in enumerate(tunnels.geometry.values):
        n = max(int(np.ceil(tunnel.length / STEP)), 1)
        dists = np.linspace(0.0, tunnel.length, n + 1)
        spacing = tunnel.length / n
        pts = shapely.line_interpolate_point(tunnel, dists)
        (pi, ri), _ = tree.query_nearest(pts, max_distance=TOL, return_distance=True, all_matches=False)
        for road_row in np.unique(ri):
            mine = pi[ri == road_row]
            road = road_geoms[road_row]
            along = shapely.line_locate_point(road, pts[mine])
            start, end = float(along.min()), float(along.max())
            tunnel_len = max((len(mine) - 1) * spacing, spacing)
            if end - start < MIN_LEN or (end - start) / tunnel_len < ALONG:
                continue  # crosses the road rather than running along it
            spans.setdefault(int(road_row), []).append((start, end, ti))
    return spans


def merge_spans(spans, length):
    merged = []
    for a, b, ti in sorted(spans):
        a = 0.0 if a < SNAP else a
        b = length if length - b < SNAP else b
        if merged and a <= merged[-1][1] + SNAP:
            merged[-1][1] = max(merged[-1][1], b)
            merged[-1][2].add(ti)
        else:
            merged.append([a, b, {ti}])
    return merged


def run(road_path, tunnel_path, output_path):
    road_src = gpd.read_parquet(road_path)
    roads = road_src.to_crs(NZTM)
    tunnels = gpd.read_parquet(tunnel_path).to_crs(NZTM)
    tunnels = tunnels[tunnels["type"] == "vehicle"].reset_index(drop=True)

    spans = tunnel_spans(roads, tunnels)
    used_tunnels = set()

    out = road_src.copy()
    out["tunnel"] = False
    keep = np.ones(len(out), dtype=bool)
    new_rows, new_geoms = [], []
    for road_row, road_spans in spans.items():
        line = roads.geometry.values[road_row]
        merged = merge_spans(road_spans, line.length)
        if not merged:
            continue
        keep[road_row] = False
        attrs = road_src.iloc[road_row].drop("geometry").to_dict()
        cuts = [(0.0, False)]
        for a, b, tis in merged:
            cuts += [(a, True), (b, False)]
            used_tunnels |= tis
        cuts.append((line.length, None))
        piece = 0
        for (a, in_tunnel), (b, _) in zip(cuts[:-1], cuts[1:]):
            if b - a <= 0:
                continue
            row = dict(attrs)
            row["tunnel"] = bool(in_tunnel)
            if in_tunnel:
                row["type"] = "tunnel"
            row["id"] = str(uuid.uuid5(ID_NAMESPACE, f"{attrs['id']}/{piece}"))
            new_rows.append(row)
            new_geoms.append(substring(line, a, b))
            piece += 1

    out = out[keep]
    if new_rows:
        pieces = gpd.GeoDataFrame(new_rows, geometry=new_geoms, crs=NZTM).to_crs(road_src.crs)
        pieces = pieces.astype({c: out[c].dtype for c in out.columns if c != "geometry" and c in pieces}, errors="ignore")
        out = pd.concat([out, pieces[list(out.columns)]], ignore_index=True)
    out = gpd.GeoDataFrame(out, geometry="geometry", crs=road_src.crs)
    out.to_parquet(output_path, compression="zstd")

    tunnels["matched"] = tunnels.index.isin(used_tunnels)
    return out, tunnels


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--road", required=True, type=Path)
    p.add_argument("--tunnel", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    result, tunnel_report = run(a.road, a.tunnel, a.output)
    print(f"Wrote {len(result)} features ({int(result['tunnel'].sum())} tunnel sections) to {a.output}")
    print(f"{int(tunnel_report['matched'].sum())} of {len(tunnel_report)} vehicle tunnels run along a road")
