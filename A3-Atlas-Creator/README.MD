# Topo50 Atlas Builder

A QGIS plugin that builds a NZTopo50 A3 atlas for any area and exports it as one
PDF, using separate layouts for left-hand and right-hand pages.



## Summary

1. **Area.** Pick one or more polygons. The plugin finds the NZTopo50 A3 sheets
   (12 km x 18 km, 1:50,000) that cover them and writes a grid file with page
   numbers and adjoining-page labels.
2. **Layouts.** It loads a right-hand and a left-hand layout template, points
   both at the grid, and gives each one the correct pages.
3. **Export.** It exports every page from the right template, merges them in
   page order, and saves `<project>_<yyyymmdd>.pdf`.

## Why

Left-hand and right-hand pages differ in more than their margins (grid ticks,
the lower margin block and the page number all mirror), so they need separate
layouts. A QGIS atlas uses one layout, and its own page counter restarts in
each filtered layout. The plugin avoids both problems by storing page numbers
in the grid file and choosing the layout per page.

## Install

1. In QGIS: Plugins > Manage and Install Plugins > **Install from ZIP**.
2. Choose `topo50_atlas.zip` and click Install Plugin.
3. The **Topo50 Atlas Builder** button appears on the toolbar and under
   Plugins > Topo50 Atlas.

Requires QGIS 3.28 or later, including QGIS 4. Nothing else needs installing:
the A3 base grid and the PDF library (pypdf) are bundled.

## Use

Open the project you want to print (the map layers and styles come from the
open project), then click the toolbar button.

### 1. Area

| Field | What to enter |
|---|---|
| Project name | Used for the title (`area_name`), the folder name and the PDF name |
| Polygon layer | Any polygon layer in the project, in any coordinate system |
| Use the features selected on the map | Uses every selected polygon in that layer, merged into one area |
| Choose one feature from the list | Pick a single polygon without selecting it on the map |
| Minimum overlap | A sheet is included when it holds at least this much of the area. Default 0.1 km² |

### 2. Page layouts

| Field | What to enter |
|---|---|
| Right-hand template | The `.qpt` for right-hand pages |
| Left-hand template | The `.qpt` for left-hand pages |
| Page 1 is a | Right-hand page (default) or left-hand page |

### 3. Export

| Field | What it does |
|---|---|
| Export folder | A subfolder named after the project is created inside it |
| Pages | Leave as "first" to "last" for everything, or set a range to test a few pages |
| Resolution | Export resolution in dpi |
| Turn off label masks while exporting | Works around the QGIS crash when exporting with label masks. The project's labelling is restored afterwards |
| Always export as vectors | Passed to the PDF export |
| Keep the individual page PDFs | Keeps the `pages` folder after merging |

### Buttons

- **Create grid only** writes the grid file and adds it to the map, without exporting.
- **Export atlas** creates the grid, exports every page and merges them.
- **Cancel** (while running) stops after the current page.
- **Open folder** opens the project's output folder.

## Output

For a project named "Otago Region" exported on 5 October 2026:

```
<export folder>\
    Otago_Region\
        Otago_Region_grid.parquet      the page grid
        Otago_Region_20261005.pdf      the merged atlas
        pages\                         only if "Keep the individual page PDFs" is ticked
            page_0001.pdf
            page_0002.pdf
```

The plugin also leaves two layouts in the project, `<project> - right` and
`<project> - left`, so you can open them and preview any page.

If the QGIS in use cannot write Parquet, the grid is saved as GeoPackage
(`.gpkg`) with the same columns.

## How pages are assigned

Pages are numbered row by row: top-left across to the right, then down.

| Page 1 is a | Right-hand layout gets | Left-hand layout gets |
|---|---|---|
| Right-hand page | odd pages | even pages |
| Left-hand page | even pages | odd pages |

The plugin sets these as atlas filters (`"page" % 2 = 1` and `"page" % 2 = 0`)
and sorts both layouts by `page`. You do not set a filter yourself.

## Making the templates

Design the two layouts in QGIS, then save each with Layout > Save as Template.
Put them in the plugin's `templates` folder as `A3_right.qpt` and `A3_left.qpt`
to make them the defaults, or browse to them in the dialog.

Two simple example templates are included (`A3_right_example.qpt`,
`A3_left_example.qpt`) so the plugin can be tried straight away.

Each template needs:

- **A map set to "Controlled by Atlas"** (Item Properties of the map). The
  plugin warns if none is.
- **Text taken from the grid columns**, not from the atlas counter:

| Purpose | Label text |
|---|---|
| Page number | `Page [% "page" %] of [% "page_count" %]` |
| Sheet name | `[% "page_label" %]` |
| Area title | `[% "area_name" %]` |
| Adjoining sheets | `[% "adj_n_label" %]`, `[% "adj_s_label" %]`, `[% "adj_e_label" %]`, `[% "adj_w_label" %]` |

Do not use `@atlas_featurenumber` for page numbers. It restarts at 1 in each
layout.

Things a template does not carry with it:

- **Layers.** A template refers to layers by internal id. Leave the map
  following the project's visible layers or a map theme. A locked layer list
  only works in the project the template was saved from.
- **Pictures.** Logos are stored as file paths. Keep them where the template
  expects, or re-point them after the first export.
- **Fonts.** The fonts must be installed.

## Grid columns

The grid file has the same columns as the regional and territorial grid files:
the base sheet columns (`atlas_code`, `sheet_code`, `sheet_name`, `quad`,
`quad_pos`, `edition`, `revised`, `xmin`, `ymin`, `xmax`, `ymax` and so on)
plus `series`, `area_name`, `page`, `page_count`, `page_label`, and for each of
n, s, e, w: `adj_<d>`, `adj_<d>_name`, `adj_<d>_page`, `adj_<d>_label`.

## What has been tested

Tested headless on QGIS 3.34 (Qt 5):

- Page numbering reproduces all 82 existing regional and territorial grid
  files exactly (4,084 pages).
- Grids built from polygons match the reference files, from NZTM and from
  WGS84 input.
- Export from both templates, merge, page range, cancel, starting on a
  left-hand or right-hand page, and the label-mask switch with restore.
- The dialog, run end to end.

Not tested:

- **QGIS 4 / Qt 6.** The code is written to run on both, but it has not been
  run on QGIS 4.
- **Writing Parquet.** The test machine's QGIS could not write Parquet, so only
  the GeoPackage fallback was exercised.
- **Your real templates and the full Topo50 project.**
- **Windows.**

## Limits

- **A3 at 1:50,000 only.** Other page sizes need their own base grid.
- **New Zealand mainland sheets only.** The Chatham Islands are not in the base grid.
- **Exports run in the foreground.** QGIS is busy until the export finishes or is cancelled.
- **PDF text.** Whether text is searchable in the PDF follows the layout's own export settings.

## Files

| File | Purpose |
|---|---|
| `plugin.py` | Toolbar button and menu entry |
| `dialog.py` | The dialog |
| `grid.py` | Page numbering and adjoining labels (no QGIS dependency) |
| `builder.py` | Finds the sheets for an area and writes the grid file |
| `exporter.py` | Loads templates, exports pages, merges PDFs |
| `data/topo50_a3_grid.gpkg` | The A3 base grid, 1,575 sheets |
| `templates/` | Layout templates |
| `ext/pypdf/` | Bundled PDF library (BSD licence, see `ext/pypdf_LICENSE`) |
