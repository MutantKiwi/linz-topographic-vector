# Working with LINZ topographic vector data 

Notes, scripts and QGIS styling for working with the Toitū Te Whenua Land Information New Zealand NZTopo50 vector
data and QGIS project.

<img width="1074" height="866" alt="image" src="https://github.com/user-attachments/assets/c85cb3d6-8bb0-451a-857a-efbb6cb93c18" />

LINZ publishes the Topo50 map as a QGIS project backed by GeoParquet layers.
This repository is an 'unofficial project' that records how to download that project and the additions made
to bring the rendered map closer to the printed Topo50 sheets.

This project is not endorsed and/or supported by Toitū Te Whenua Land Information New Zealand

[Todo List](TODO.md)

[Nice to Have](NICE-TO-HAVE.MD)

[Crash review](CRASH.MD)

Link to the [Atlas Grids](atlas_grids/atlas_grids.md)


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
| [label_word_spacing.md](https://github.com/MutantKiwi/linz-topographic-vector/blob/main/label_word_spacing.md) | Restores the gap between words in curved place names (for example "WaitahaCove") by using the project's own font and, for curved labels only (`text_bend = 7`), fitting text to its line by character spacing instead of word spacing. | Curved labels are fitted to the exact length of their label line. With the wrong font or word-spacing fitting, the space between words is squeezed to nothing. Limiting the change to curved text stops stacked labels such as "Houghton / Bay" being spread out. |
| [label_word_spacing.md](https://github.com/MutantKiwi/linz-topographic-vector/blob/main/label_word_spacing.md) | Restores the gap between words in curved place names (for example "WaitahaCove") by using the project's own font and, for curved labels only (`text_bend = 7`), fitting text to its line by character spacing instead of word spacing. | Curved labels are fitted to the exact length of their label line. With the wrong font or word-spacing fitting, the space between words is squeezed to nothing. Limiting the change to curved text stops stacked labels such as "Houghton / Bay" being spread out. |

## Typical order of work

1. Download the project and data ([download.md](download.md)).
2. Open `nztopo50.qgs` in QGIS and confirm the layers load.
3. Create the rock line layer and style it ([rock_line_carto.md](https://github.com/MutantKiwi/linz-topographic-vector/blob/main/rock_line_carto.md)).
4. Create the railway tunnel layer and apply the rule-based style ([railway_tunnel.md](https://github.com/MutantKiwi/linz-topographic-vector/blob/main/railway_tunnel.md)).
5. Apply the label line expression to fix curved text placement ([label_line_split.md](https://github.com/MutantKiwi/linz-topographic-vector/blob/main/label_line_split.md)).
6. Fix the font and word spacing on the text layer ([label_word_spacing.md](https://github.com/MutantKiwi/linz-topographic-vector/blob/main/label_word_spacing.md)).

## Requirements

- QGIS 3.28 or later (QGIS 4.x preferred). The word spacing fix needs QGIS 4.x, which has the
  fit-to-line curved label modes.
- Docker, for the container download.
- `wget.exe` on the PATH, for the batch script.
- Python 3.10 or later with `geopandas`, `shapely` 2.x and `pyarrow`, for the
  rock line and railway tunnel scripts.

## Source

The data, QGIS project, styles and symbols come from Toitū Te Whenua Land
Information New Zealand (LINZ). See the
[linz/topographic-system](https://github.com/linz/topographic-system)
repository for the upstream code and licence.
