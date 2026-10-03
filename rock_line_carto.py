# rock_line_carto

A hand-drawn style rock symbol for NZ Topo50, baked into geometry.

`rock_line_carto.py` takes the `rock_line` layer and produces
`rock_line_carto.parquet`: a jagged rock outline with irregular ticks pointing
towards the land, imitating the rock symbol on the printed Topo50 maps. Because
the symbol is stored as geometry, QGIS only needs a plain black line to draw it.

![Preview](rock_line_carto_preview.png)

## What you need

Python 3.10 or later with `geopandas`, `shapely` 2.x, `numpy`, `pandas` and
`pyarrow`.

On Windows with QGIS installed, open the **OSGeo4W Shell** and run:

```
python -m pip install geopandas pyarrow
```

## Inputs

All inputs are GeoParquet files from the Topo50 project folder.

| File | Required | Used for |
|---|---|---|
| `rock_line.parquet` | yes | The rock outlines to draw. Must have a `marine_id` column. |
| `marine.parquet` | yes | Rock polygons (`type = 'rock'`), used to find the landward side and to stop ticks leaving the rock. |
| `coastline.parquet` | optional | Stops ticks crossing the coastline. |
| `island.parquet` | optional | Stops ticks crossing island shores. |
| `water.parquet` | optional | Stops ticks crossing lake shores (`type = 'lake'`). |

The three optional files are recommended. Without them, ticks are only limited
by the rock polygon and can run over land where a rock polygon overlaps it.

## Step 1: create rock_line.parquet (if you don't have it)

`rock_line.parquet` is the boundary of each rock polygon, with any stretch that
duplicates a coastline, island shore or lake shore removed (1 m tolerance).

It comes from LINZ's `rock_line.py` in the `topographic-system` repository
(`packages/data-prep/src/data_prep/rock_line.py`):

```
python -m data_prep.rock_line --marine marine.parquet --coastline coastline.parquet ^
    --island island.parquet --water water.parquet --output rock_line.parquet
```

Any equivalent output works, as long as each feature carries the `marine_id` of
the rock polygon it came from.

## Step 2: create rock_line_carto.parquet

From the folder holding the parquet files:

```
python rock_line_carto.py --rock-line rock_line.parquet --marine marine.parquet ^
    --coastline coastline.parquet --island island.parquet --water water.parquet ^
    --output rock_line_carto.parquet
```

(`^` continues a line in the Windows shell. Use `\` on Linux or macOS.)

It takes about 10 seconds for the whole country and prints the number of
features written.

## Output

`rock_line_carto.parquet`, in NZGD2000 (EPSG:4167), MultiLineString geometry.

| Column | Contents |
|---|---|
| `marine_id` | Id of the source rock polygon |
| `type`, `name`, `subtype` | Carried over from `rock_line` |
| `part` | `outline` (the jagged line) or `tick` (the strokes) |
| `geometry` | One MultiLineString per rock feature per part |

Each rock feature gives up to two rows: one `outline` and one `tick`.

## Step 3: style it in QGIS

1. Add `rock_line_carto.parquet` to the project.
2. Symbology: Single Symbol, Simple Line, black, 0.1 mm wide, round cap and
   round join.

No hashed line or geometry generator is needed. To draw the outline and ticks
at different widths, use Categorized symbology on the `part` column.

## How the symbol is built

Work is done in NZTM2000 (EPSG:2193) so distances are in metres, then
reprojected back to NZGD2000.

1. **Resample.** Points are placed along each rock line at irregular intervals
   (about 10.5 m apart, varying by 40% either way).
2. **Jagged outline.** Each point is nudged sideways by up to 5 m. The two ends
   of an open line are not moved, so the outline still meets the coast.
3. **Ticks.** A stroke is drawn from each outline point towards the land (the
   inside of the rock polygon). Lengths run from 12 to 40 m and vary in runs of
   longer and shorter strokes. Each tick's angle wobbles slightly, and about 5%
   are left out to give occasional gaps.
4. **Trimming.** Ticks are cut short where they would leave the rock polygon,
   cross a coastline, island or lake shore, reach the far side of a small rock,
   or cross another tick.
5. **Repeatability.** The random numbers are seeded from each feature's
   `marine_id`, so re-running on the same input gives an identical result.

Rock line fragments shorter than 12 m are left out. These are slivers left over
from removing the coastline.

## Tuning the look

The settings are constants at the top of `rock_line_carto.py`. All distances
are ground metres; divide by 50 for millimetres on the map at 1:50,000.

| Setting | Default | Effect |
|---|---|---|
| `SPACING` | 10.5 | Mean distance between ticks |
| `SPACING_JITTER` | 0.40 | How uneven the spacing is (fraction of `SPACING`) |
| `JAG` | 5.0 | Maximum sideways nudge of the outline |
| `TICK_MIN`, `TICK_MAX` | 12.0, 40.0 | Shortest and longest tick |
| `TICK_RUN` | 110.0 | Distance over which tick length drifts |
| `TICK_WHITE` | 0.45 | 0 = smooth runs only, 1 = every tick independent |
| `ANGLE_JITTER` | 11.0 | Spread of tick angle from perpendicular, in degrees |
| `SKIP` | 0.05 | Fraction of ticks left out |
| `LAND_GAP` | 0.85 | Fraction of length kept when a tick is cut by land |
| `OPPOSITE_GAP` | 0.45 | How far across a small rock a tick may reach |
| `CROSS_GAP` | 0.6 | How far short of a neighbour a crossing tick stops |
| `TIP_CLEARANCE` | 5.0 | Clearance kept between tick tips |
| `MIN_TICK` | 4.0 | Ticks shorter than this after cutting are dropped |
| `MIN_PART` | 12.0 | Rock line fragments shorter than this are left out |

Edit the values and re-run Step 2.

## Limits

- **Scale.** The symbol is sized for 1:50,000. At very different scales it will
  look too fine or too coarse; scale the distance settings to suit.
- **Touching ticks.** Ticks never cross, but in tight corners a few sit close
  enough to merge at print line width, as they do on the printed map.
- **Seeding.** The drawing is tied to `marine_id`. If the ids change, the same
  rock will be drawn with a different (but equivalent) pattern.
