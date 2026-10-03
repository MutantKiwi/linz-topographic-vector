# linz-topographic-vector

Notes, scripts and QGIS styling for working with the LINZ NZ Topo50 vector
data and QGIS project.

LINZ publishes the Topo50 map as a QGIS project backed by GeoParquet layers.
This repository records how to download that project, and the additions made
to bring the rendered map closer to the printed Topo50 sheets.

## Getting the data

Start here. [download.md](download.md) covers:

- Downloading the QGIS project and data with the LINZ `map` Docker container.
- A Windows batch script that downloads all the parquet files directly, for
  when the container leaves them empty.
- A direct link to the QGIS project file:
  <https://d1jzh93b1t1cv.cloudfront.net/qgis/nztopo50/latest/nztopo50.qgs>

## Cartographic additions

| Doc | What it does | Why |
|---|---|---|
| [rock_line_carto.md](https://github.com/MutantKiwi/linz-topographic-vector/blob/main/rock_line_carto.md) | Builds a hand-drawn style rock symbol: a jagged rock outline with irregular ticks pointing towards the land, baked into a new layer. | A QGIS hashed line gives uniform ticks. The printed map's rock symbol is irregular, so it is generated as geometry instead. |
| [railway_tunnel.md](https://github.com/MutantKiwi/linz-topographic-vector/blob/main/railway_tunnel.md) | Splits the railway lines at tunnel portals, sets `subtype = 'tunnel'` on the tunnel sections, and gives the QGIS rules for single track, multiple track and tunnel. | `railway_line` has no tunnel attribute and its features are too long to flag as a whole, so tunnels could not be drawn differently. |
| [label_line_split.md](https://github.com/MutantKiwi/linz-topographic-vector/blob/main/label_line_split.md) | A QGIS label Geometry Generator expression that removes the sharp joining segment from a label line. | Curved text placement fails or bends around the corner where a label line doubles back on itself. |

## Typical order of work

1. Download the project and data ([download.md](download.md)).
2. Open `nztopo50.qgs` in QGIS and confirm the layers load.
3. Create the rock line layer and style it ([rock_line_carto.md](https://github.com/MutantKiwi/linz-topographic-vector/blob/main/rock_line_carto.md)).
4. Create the railway tunnel layer and apply the rule-based style ([railway_tunnel.md](https://github.com/MutantKiwi/linz-topographic-vector/blob/main/railway_tunnel.md)).
5. Apply the label line expression to fix curved text placement ([label_line_split.md](https://github.com/MutantKiwi/linz-topographic-vector/blob/main/label_line_split.md)).

## Requirements

- QGIS 3.28 or later.
- Docker, for the container download.
- `wget.exe` on the PATH, for the batch script.
- Python 3.10 or later with `geopandas`, `shapely` 2.x and `pyarrow`, for the
  rock line and railway tunnel scripts.

## Source

The data, QGIS project, styles and symbols come from Toitū Te Whenua Land
Information New Zealand (LINZ). See the
[linz/topographic-system](https://github.com/linz/topographic-system)
repository for the upstream code and licence.
