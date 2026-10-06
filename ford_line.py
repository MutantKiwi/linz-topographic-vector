"""
Build a short line for every ford point, lying along the road it sits on.

A ford is stored as a point. To draw the ford symbol (a small rectangle across
the road) at the right angle, each point is turned into a 10 m line that
follows the road beneath it.

Usage:
  python ford_line.py --ford nz-ford-points-topo-150k.gpkg --road road_line.parquet \
      [--track track_line.parquet] --output ford_line.parquet
"""

import argparse
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.ops import substring

NZTM = 2193
NZGD2000 = 4167

LENGTH = 10.0   # length of each ford line, metres
SNAP = 10.0     # a ford further than this from a road or track is left unmatched


def read(path):
    path = Path(path)
    gdf = gpd.read_parquet(path) if path.suffix == ".parquet" else gpd.read_file(path)
    return gdf.to_crs(NZTM)


def ford_segment(line, point):
    """LENGTH metres of `line` centred on the place nearest `point` (shifted to fit near a line end)."""
    total = line.length
    at = line.project(point)
    if total <= LENGTH:
        return line
    start = min(max(at - LENGTH / 2, 0.0), total - LENGTH)
    return substring(line, start, start + LENGTH)


def bearing(segment):
    """Direction of the segment in degrees clockwise from grid north, 0 to 180."""
    (x1, y1), (x2, y2) = segment.coords[0], segment.coords[-1]
    return round(math.degrees(math.atan2(x2 - x1, y2 - y1)) % 180.0, 1)


def run(ford_path, road_path, output_path, track_path=None):
    fords = read(ford_path).reset_index(drop=True)
    sources = [("road", read(road_path))]
    if track_path:
        sources.append(("track", read(track_path)))

    best = pd.DataFrame({"dist": np.full(len(fords), np.inf), "source": None, "row": -1})
    for name, layer in sources:
        tree = shapely.STRtree(layer.geometry.values)
        (fi, li), dist = tree.query_nearest(
            fords.geometry.values, max_distance=SNAP, return_distance=True, all_matches=False
        )
        # roads take priority: a track only wins where no road was within SNAP
        better = dist < best["dist"].values[fi] if name == "road" else np.isinf(best["dist"].values[fi])
        best.loc[fi[better], ["dist", "source", "row"]] = np.column_stack(
            [dist[better], np.full(better.sum(), name, dtype=object), li[better]]
        )
    layers = dict(sources)

    rows = []
    for i, ford in fords.iterrows():
        source = best.at[i, "source"]
        if source is None:
            continue
        line_feature = layers[source].iloc[int(best.at[i, "row"])]
        segment = ford_segment(line_feature.geometry, ford.geometry)
        rows.append(
            {
                "t50_fid": ford.get("t50_fid"),
                "name": ford.get("name"),
                "type": "ford",
                "on": source,
                "line_id": line_feature.get("id"),
                "line_t50_fid": line_feature.get("t50_fid"),
                "distance_m": round(float(best.at[i, "dist"]), 2),
                "angle": bearing(segment),
                "length_m": round(segment.length, 2),
                "geometry": segment,
            }
        )
    out = gpd.GeoDataFrame(rows, geometry="geometry", crs=NZTM).to_crs(NZGD2000)
    out.to_parquet(output_path)
    unmatched = fords[best["source"].isna().values]
    return out, unmatched


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ford", required=True)
    p.add_argument("--road", required=True)
    p.add_argument("--track")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    result, missed = run(a.ford, a.road, a.output, a.track)
    print(f"Wrote {len(result)} ford lines to {a.output}")
    print(result["on"].value_counts().to_string())
    print(f"{len(missed)} ford(s) had no road or track within {SNAP:g} m")
    if len(missed):
        missed_path = Path(a.output).with_name(Path(a.output).stem + "_unmatched.gpkg")
        missed.to_crs(NZGD2000).to_file(missed_path, driver="GPKG")
        print(f"Unmatched fords saved to {missed_path}")
