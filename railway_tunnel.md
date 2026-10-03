# Fix rail-line attributes to add tunnels

Marks the tunnel sections of the Topo50 railway lines and styles the result in
QGIS.

`railway_line.parquet` has no tunnel information, and its features are long, so a tunnel cannot be flagged on a whole feature. `railway_tunnel.py`
splits each railway line at the tunnel portals and sets `subtype = 'tunnel'` on
the sections inside a tunnel. The result is `railway_line_tunnel.parquet`.

## What you need

Python 3.10 or later with `geopandas`, `shapely` 2.x, `numpy`, `pandas` and
`pyarrow`.

On Windows with QGIS installed, open the **OSGeo4W Shell** and run:

```
python -m pip install geopandas pyarrow
```

## Inputs

| File | Used for |
|---|---|
| `railway_line.parquet` | The railway lines to split. |
| `tunnel_line.parquet` | Tunnel centrelines. Only features with `type = 'train'` are used. |

The KiwiRail tunnel shapefile (`KiwiRailTunnels/KiwiRailTunnels.shp`) is not
used. The 189 train tunnels in `tunnel_line.parquet` sit on the railway
geometry, whereas 23 of the 179 KiwiRail tunnels do not touch any railway line.

## Step 1: create railway_line_tunnel.parquet

From the folder holding the parquet files:

```
python railway_tunnel.py --railway railway_line.parquet --tunnel tunnel_line.parquet ^
    --output railway_line_tunnel.parquet
```

(`^` continues a line in the Windows shell. Use `\` on Linux or macOS.)

It prints the number of features written and how many are tunnel sections.
`railway_line.parquet` is not modified.

## Output

`railway_line_tunnel.parquet`, in NZGD2000 (EPSG:4167), LineString geometry,
with the same columns as `railway_line.parquet`.

| | railway_line | railway_line_tunnel |
|---|---|---|
| Features | 567 | 943 |
| `subtype = 'tunnel'` | 0 | 190 (93.8 km) |
| `subtype = 'siding'` | 290 | 290 |
| `subtype` empty | 277 | 463 |
| Total length | 4,219.5 km | 4,219.5 km |

- **Tunnel sections** have `subtype = 'tunnel'`. All other attributes are copied
  from the railway line they were cut from.
- **Unsplit lines** (521 features with no tunnel) keep their original id and
  geometry exactly.
- **Split pieces** get a new id derived from the original id and the piece
  number, so re-running gives the same ids. They keep the original `t50_fid`.
- **Sidings.** Setting `subtype = 'tunnel'` would replace `siding` on a siding
  inside a tunnel. In the current data no siding is inside a tunnel.

## How the split works

Work is done in NZTM2000 (EPSG:2193) so distances are in metres.

1. For each railway line, find the train tunnels within 10 m of it.
2. Sample each tunnel every 2 m and project the samples that are within 10 m
   onto the railway line. The lowest and highest positions give the tunnel's
   start and end along the line.
3. If a tunnel runs past the end of a railway line, the tunnel section extends
   to that end.
4. Overlapping or touching sections are merged. Portals within 1 m of a line
   end are moved to the end, and sections shorter than 1 m are ignored.
5. The line is cut at the portals. Pieces inside a tunnel get
   `subtype = 'tunnel'`.

The 10 m tolerance is needed for one tunnel in Hamilton whose centreline runs
about 8 m to the side of the railway line for part of its length. The settings
(`TOL`, `STEP`, `SNAP`, `MIN_LEN`) are constants at the top of
`railway_tunnel.py`.

## Step 2: style it in QGIS

Add `railway_line_tunnel.parquet` in place of `railway_line`, open Symbology
and choose **Rule-based**. Delete the default "(no filter)" rule, then add
these three rules.

| Rule | Filter |
|---|---|
| Tunnel | `"subtype" = 'tunnel'` |
| Multiple track | `"track_type" = 'multiple' AND coalesce("subtype", '') <> 'tunnel'` |
| Single track | `"track_type" = 'single' AND coalesce("subtype", '') <> 'tunnel'` |

The `coalesce` is needed because most features have an empty subtype, and a
plain `"subtype" <> 'tunnel'` would exclude them.

### Symbols

The sizes are starting values estimated from the printed map. Adjust by eye at
1:50,000.

**Tunnel** - dashed black line. One Simple Line:

- Colour black, stroke width 0.3 mm, cap style Flat.
- Use custom dash pattern: dash 2 mm, space 1 mm.

**Multiple track** - black line with long white blocks and short black blocks.
Two Simple Line layers, white on top of black:

| Layer | Colour | Width | Cap | Dash pattern |
|---|---|---|---|---|
| Top | White | 0.45 mm | Flat | Custom: dash 3 mm, space 1 mm |
| Bottom | Black | 0.8 mm | Flat | Solid |

The white must be narrower than the black so a black edge shows on both sides.
The space in the white dash pattern is where the black shows through, so the
space length is the black block length.

**Single track** - solid black line. One Simple Line, black, 0.3 mm.

### Editing symbol layers

- Click a **Simple Line** in the symbol tree (not the bold **Line** above it) to
  see its settings. Enlarge the Edit Rule dialog if they are hidden below.
- The green plus adds a layer, the red minus removes one, and the arrows
  reorder them. The layer at the bottom of the tree is drawn first.
- To edit a dash pattern, tick **Use custom dash pattern** and click the
  dashed-line preview box beneath it.

### Things to check

- **Symbol levels.** If black line ends show through the white blocks where
  features join, click Symbol Levels at the bottom of the rule list, enable
  them, and put the white layer on a higher level than the black.
- **Tunnels on multiple track.** The tunnel rule applies to every tunnel
  section, so a double-track tunnel draws as the plain dashed line. Add a rule
  for `"subtype" = 'tunnel' AND "track_type" = 'multiple'` if these should look
  different.

## Re-running

If `railway_line.parquet` or `tunnel_line.parquet` changes, run Step 1 again.
The QGIS style does not need to change.
