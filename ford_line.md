# Ford symbol

Creates a short line for every ford, lying along the road it crosses, so the
ford symbol can be drawn at the same angle as the road.

## Summary

On Topo50 a ford (where a road crosses a river through the water) is drawn as
a small rectangle across the road. The ford data is a point layer, and a point
has no direction, so a rectangle drawn on it always sits square to the page
whatever way the road runs.

`ford_line.py` turns each ford point into a 10 m line taken from the road
beneath it. The line carries the road's direction, which the symbol can then
follow. There are two ways to draw the symbol from it, described below.

## Why a line and not a rotated point

A point marker can be rotated, but only if the layer has an angle to rotate
by, and the ford points have none. The road they sit on does. Cutting a short
piece of that road gives both a geometry QGIS can follow automatically and an
angle value that can be stored as an attribute.

## Process

Work is done in NZTM2000 (EPSG:2193) so distances are in metres. The output is
reprojected to NZGD2000 (EPSG:4167) to match the other Topo50 layers.

1. **Find the road under each ford.** For each ford point, find the nearest
   road line within 10 m.
2. **Fall back to tracks.** A ford with no road within 10 m is matched to the
   nearest track instead. Roads always take priority: a track is only used
   where no road was close enough.
3. **Cut the line.** Find the place on the road nearest the ford, then take
   the piece of road from 5 m before it to 5 m after it. The line follows the
   road's own shape, so it overlays the road exactly.
4. **Handle road ends.** If the ford is within 5 m of the end of a road
   feature, the 10 m piece is shifted so it still fits on that feature. The
   line is then off-centre from the ford, but its direction is still correct.
5. **Record the angle.** The direction from the line's first point to its last
   is stored as a bearing in degrees clockwise from grid north, from 0 to 180.

### Result for the current data

| | |
|---|---|
| Ford points | 1,005 |
| Matched to a road | 991 |
| Matched to a track | 14 |
| Unmatched | 0 |
| Line length | 10.0 m for every ford |
| Fords exactly on their road or track | all but a few (largest gap 7.5 m) |
| Fords at a road end, so the line is off-centre | 5 |

## Files

| File | Purpose |
|---|---|
| `ford_line.py` | The script |
| `ford_line.parquet` | Output: one line per ford |
| `lds-nz-ford-points-topo-150k-GPKG/nz-ford-points-topo-150k.gpkg` | Input: LINZ ford points |
| `road_line.parquet` | Input: roads |
| `track_line.parquet` | Input: tracks (optional) |

## Running it

Requires Python 3.10 or later with `geopandas`, `shapely` 2.x and `pyarrow`.

```
python ford_line.py --ford lds-nz-ford-points-topo-150k-GPKG\nz-ford-points-topo-150k.gpkg ^
    --road road_line.parquet --track track_line.parquet --output ford_line.parquet
```

(`^` continues a line in the Windows shell. Use `\` on Linux or macOS.)

Leave out `--track` to match roads only. Any ford with nothing within 10 m is
then written to `ford_line_unmatched.gpkg` so the missed ones can be checked.

## Output columns

| Column | Contents |
|---|---|
| `t50_fid` | The ford's Topo50 feature id |
| `name` | The ford's name, where it has one |
| `type` | Always `ford` |
| `on` | `road` or `track` |
| `line_id` | Id of the road or track the ford lies on |
| `line_t50_fid` | Topo50 feature id of that road or track |
| `distance_m` | Distance from the ford point to the road or track |
| `angle` | Bearing of the line, degrees clockwise from grid north (0 to 180) |
| `length_m` | Length of the line |

## Drawing the symbol: two options

The line is 10 m long on the ground. At 1:50,000 that is 0.2 mm on the map, so
drawing the line itself as the rectangle gives a dot. The two options differ
in how they deal with that.

### Option 1: use the line for direction only (recommended)

Draw a rectangle marker of a fixed size in millimetres at the middle of each
line, turned to follow it.

1. Add `ford_line.parquet` to the project and open its Symbology.
2. Change the symbol layer type to **Marker Line**.
3. Under marker placement, tick **On central point** and untick the others.
4. Leave **Rotate marker to follow line direction** ticked.
5. Click the marker's **Simple Marker**, choose the rectangle shape, and set
   its size in millimetres (for example 1.6 mm long by 0.8 mm wide), with the
   fill and stroke the symbol needs.

| For | Against |
|---|---|
| The symbol is a fixed size on paper, as on the printed map | The rectangle is no longer tied to a real distance on the ground |
| Size is changed in the style, with no need to re-run the script | |
| Stays readable at any map scale | |

### Option 2: make the line itself the symbol

Lengthen the line so that it is big enough to see, and draw it as a thick line.

1. Open `ford_line.py` and change `LENGTH` at the top. 50 m gives a 1 mm long
   symbol at 1:50,000.
2. Re-run the script.
3. Style the layer as a **Simple Line** with a flat cap, with the stroke width
   set to the width the rectangle should be.

| For | Against |
|---|---|
| The symbol follows a bend in the road | The size is fixed in the data, so changing it means re-running the script |
| No marker settings to manage | The symbol is only the right size at one map scale |
| | A long line can run past a nearby junction or along a curve and look wrong |

### A third route: rotate the original points

Because the output has an `angle` column, the line layer can be skipped. Join
`angle` to the ford points on `t50_fid`, style the points with a rectangle
marker, and set the marker's rotation to the `angle` field. The result looks
the same as Option 1. It keeps the fords as points, at the cost of maintaining
a join.

### Which to use

Option 1 suits a printed map: the symbol size is a cartographic choice, not a
ground measurement, and it is easiest to adjust. Option 2 only makes sense if
the ford should be drawn to scale.

## Settings

Constants at the top of `ford_line.py`:

| Setting | Default | Effect |
|---|---|---|
| `LENGTH` | 10.0 | Length of each ford line, in metres |
| `SNAP` | 10.0 | A ford further than this from a road or track is left unmatched |

## Limits

- **Fords at a join between two road features.** The line is cut from one
  feature only, so it sits to one side of the ford. Five fords are affected.
- **Roads shorter than the line length.** The whole road is used, so the line
  is shorter than `LENGTH`. None are affected at 10 m.
- **Nearest road is assumed to be the right one.** Where two roads pass within
  10 m of a ford, the closer one is used.
- **Not checked in QGIS.** The output has been checked for length, position
  and matching, but the symbol steps above have not been tried on the layer.
