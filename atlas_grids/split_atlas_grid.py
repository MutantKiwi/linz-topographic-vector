"""
Split the Topo50 A3 atlas grid into one page set per regional council and per
territorial authority, with hard-coded page numbers and adjoining-page labels.

Each output file holds the A3 sheets that contain land of that area. Pages are
numbered row by row: top-left across to the right, then down to the next row.

Usage:
  python split_atlas_grid.py --grid topo50_a3_atlas_grid_aligned.gpkg \
      --regional regional-council-2025.shp --territorial territorial-authority-2025.shp \
      --output atlas_grids
"""

import argparse
import re
import unicodedata
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely

MIN_OVERLAP_KM2 = 0.1  # a sheet is included when it holds at least this much of the area's land
DIRECTIONS = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}


def file_name(prefix, name):
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return f"{prefix}_{re.sub(r'[^A-Za-z0-9]+', '_', ascii_name.replace(chr(39), '')).strip('_')}"


def build(grid, area_geom, series, area_name):
    hit = grid[grid.intersects(area_geom)]
    overlap = hit.geometry.intersection(area_geom).area / 1e6
    pages = hit[overlap >= MIN_OVERLAP_KM2].copy()
    if pages.empty:
        return pages
    pages = pages.sort_values(["ymax", "xmin"], ascending=[False, True]).reset_index(drop=True)
    pages["series"] = series
    pages["area_name"] = area_name
    pages["page"] = range(1, len(pages) + 1)
    pages["page_count"] = len(pages)
    pages["page_label"] = pages["sheet_code"] + "–" + pages["quad_pos"]
    page_of = dict(zip(pages["atlas_code"], pages["page"]))
    for d in DIRECTIONS:
        code = pages[f"adj_{d}"]
        name = pages[f"adj_{d}_name"]
        page = code.map(page_of).astype("Int64")
        pages[f"adj_{d}_page"] = page
        label = name.where(page.isna(), "Joins Page " + page.astype(str) + " (" + name + ")")
        pages[f"adj_{d}_label"] = label.where(code.notna(), "")
    return pages


def run(grid_path, regional_path, territorial_path, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    grid = gpd.read_file(grid_path)

    # neighbours worked out from the grid itself: sheets are 12 km x 18 km on a regular lattice
    w = int((grid["xmax"] - grid["xmin"]).iloc[0])
    h = int((grid["ymax"] - grid["ymin"]).iloc[0])
    at = dict(zip(zip(grid["xmin"], grid["ymin"]), grid.index))
    label = grid["sheet_code"] + "–" + grid["quad_pos"]
    for d, (dx, dy) in DIRECTIONS.items():
        idx = [at.get((x + dx * w, y + dy * h)) for x, y in zip(grid["xmin"], grid["ymin"])]
        grid[f"adj_{d}"] = [grid["atlas_code"].iloc[i] if i is not None else None for i in idx]
        grid[f"adj_{d}_name"] = [label.iloc[i] if i is not None else None for i in idx]

    regional = gpd.read_file(regional_path).to_crs(grid.crs)
    territorial = gpd.read_file(territorial_path).to_crs(grid.crs)
    ta_name_col, rc_name_col = territorial.columns[1], regional.columns[1]
    territorial = territorial[~territorial[ta_name_col].str.startswith("Area Outside")]
    regional = regional[~regional[rc_name_col].str.startswith("Area Outside")]
    # regional council polygons run out to sea; territorial authorities give the land
    land = shapely.union_all(territorial.geometry.values)

    summary, combined = [], []
    for series, prefix, gdf, col, clip in (
        ("regional", "regional", regional, rc_name_col, True),
        ("territorial", "territorial", territorial, ta_name_col, False),
    ):
        for name, geom in zip(gdf[col], gdf.geometry):
            geom = geom.intersection(land) if clip else geom
            pages = build(grid, geom, series, name)
            fname = file_name(prefix, name)
            summary.append({"series": series, "area_name": name, "file": fname + ".parquet" if len(pages) else None, "pages": len(pages)})
            if pages.empty:
                continue
            pages.to_parquet(out_dir / f"{fname}.parquet")
            combined.append(pages)

    allpages = pd.concat(combined, ignore_index=True)
    gpd.GeoDataFrame(allpages, crs=grid.crs).to_parquet(out_dir / "atlas_pages_all.parquet")
    summary = pd.DataFrame(summary)
    summary.to_csv(out_dir / "atlas_grids_index.csv", index=False)
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--grid", required=True)
    p.add_argument("--regional", required=True)
    p.add_argument("--territorial", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    s = run(a.grid, a.regional, a.territorial, a.output)
    print(s.to_string())
