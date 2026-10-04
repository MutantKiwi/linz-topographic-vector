# Atlas grids by region and district

Splits the Topo50 A3 sheet grid into one page set per regional council and per
territorial authority, with hard-coded page numbers and adjoining-page labels,
and explains how to use one as a QGIS atlas.

## Summary

The A3 atlas grid covers New Zealand in 1,575 sheets of 12 km by 18 km.
`split_atlas_grid.py` cuts that grid into 82 smaller grids: 16 regions and 66
districts. Each file holds only the sheets containing land of that area.

Every sheet in a file carries its own page number and the finished text for its
four adjoining-sheet labels. The atlas layout reads those columns directly, so
the layout needs no page-counting expressions.

## Why

The earlier layout worked out each neighbour's page number with an expression
that counted sheets in the atlas. That depended on the atlas sort order, a
filter variable and the grid's adjacency columns all agreeing, and the page
numbers came out wrong. Storing the numbers in the data removes that
dependency.

## Files

All in the `atlas_grids` folder.

| File | Contents |
|---|---|
| `regional_<name>.parquet` | One per regional council (16 files) |
| `territorial_<name>.parquet` | One per territorial authority (66 files) |
| `atlas_pages_all.parquet` | Every page set in a single layer |
| `atlas_grids_index.csv` | List of files with their page counts |
| `split_atlas_grid.py` | The script that builds them |

File names are plain ASCII: spaces become underscores, and macrons and
apostrophes are dropped (for example `regional_Manawatu_Whanganui_Region.parquet`,
`regional_Hawkes_Bay_Region.parquet`). The proper name is in the `area_name`
column.

All files are GeoParquet in NZTM2000 (EPSG:2193).

## Columns

Each file keeps the original grid columns (`atlas_code`, `sheet_code`,
`sheet_name`, `quad`, `quad_pos`, `edition`, `revised`, `xmin`, `ymin`, `xmax`,
`ymax` and so on) and adds:

| Column | Contents | Example |
|---|---|---|
| `series` | `regional` or `territorial` | `regional` |
| `area_name` | Region or district name | `Nelson Region` |
| `page` | Page number within this file | `5` |
| `page_count` | Total pages in this file | `9` |
| `page_label` | This sheet's name | `BQ26–NE` |
| `adj_n`, `adj_s`, `adj_e`, `adj_w` | Neighbouring sheet's `atlas_code` | `BQ27-1` |
| `adj_n_name` ... `adj_w_name` | Neighbouring sheet's name | `BQ27–NW` |
| `adj_n_page` ... `adj_w_page` | Neighbour's page number in this file, empty if it is not in the file | `6` |
| `adj_n_label` ... `adj_w_label` | Finished label text | `Joins Page 6 (BQ27–NW)` |

The label columns have three forms:

| Situation | Label |
|---|---|
| Neighbour is in this file | `Joins Page 6 (BQ27–NW)` |
| Neighbour exists but is not in this file | `BQ27–SW` |
| No neighbouring sheet | (blank) |

## How the split works

1. **Sheets per area.** A sheet belongs to an area if it holds at least
   0.1 km² of that area's land.
2. **Land only for regions.** Regional council boundaries run out to the
   12-mile limit, so they are clipped to the land covered by the territorial
   authorities. Without this, a region would pick up sheets that only contain
   its sea.
3. **Page numbers.** Sheets are numbered row by row: top-left across to the
   right, then down to the next row. Rows with gaps are simply skipped over.

   ```
    1   2   3   4   5   6
    7   8   9  10  11  12
   13  14  15  16  17  18
   ```

4. **Neighbours.** The four neighbours are worked out from sheet positions on
   the regular 12 km by 18 km grid. The original grid's `adj_` columns pointed
   to 288 sheet codes that do not exist in the grid; those are now blank.

Not included: Chatham Islands Territory (no A3 sheets in the grid) and the
"Area Outside Region" and "Area Outside Territorial Authority" entries.

## Rebuilding the files

Needed only if the grid or the boundaries change.

Requires Python 3.10 or later with `geopandas`, `shapely` 2.x and `pyarrow`.

```
python split_atlas_grid.py --grid topo50_a3_atlas_grid_aligned.gpkg ^
    --regional regional-council-2025.shp ^
    --territorial territorial-authority-2025.shp ^
    --output atlas_grids
```

(`^` continues a line in the Windows shell. Use `\` on Linux or macOS.)

| Input | Source |
|---|---|
| `topo50_a3_atlas_grid_aligned.gpkg` | The A3 sheet grid (layer `a3_sheets`) |
| `regional-council-2025.shp` | Stats NZ Regional Council 2025 |
| `territorial-authority-2025.shp` | Stats NZ Territorial Authority 2025 |

The minimum land overlap is the constant `MIN_OVERLAP_KM2` at the top of the
script.

## Using a grid as an atlas

Example: Otago Region.

### 1. Add the grid to the project

Drag `atlas_grids\regional_Otago_Region.parquet` into QGIS.

### 2. Point the atlas at it

In the layout, open the Atlas panel (View > Panels > Atlas) and set:

| Setting | Value |
|---|---|
| Generate an atlas | ticked |
| Coverage layer | `regional_Otago_Region` |
| Page name | `"page"` |
| Filter with | unticked |
| Sort by | `"page"`, ascending |
| Output filename expression | `'Otago_p' \|\| lpad("page", 3, '0')` |

Sorting by `page` is what keeps the numbering correct: atlas page 1 is the
sheet with `page = 1`, and so on.

### 3. Check the map follows the atlas

Click the main map, open Item Properties, and confirm **Controlled by Atlas**
is ticked.

### 4. Set the adjoining-sheet labels

Replace the whole text of each label:

| Label item | Text |
|---|---|
| `AdjN` | `[% "adj_n_label" %]` |
| `AdjS` | `[% "adj_s_label" %]` |
| `AdjE` | `[% "adj_e_label" %]` |
| `AdjW` | `[% "adj_w_label" %]` |

### 5. Set the page number and titles

| Purpose | Text |
|---|---|
| Page number | `Page [% "page" %] of [% "page_count" %]` |
| Sheet name | `[% "page_label" %]` |
| Region or district title | `[% "area_name" %]` |

### 6. Preview and export

1. Turn on Atlas > Preview Atlas and step through a few pages. Check that the
   page number, the sheet name and the "Joins Page" labels agree.
2. Export with Atlas > Export Atlas as PDF.

### Switching to another region or district

Repeat steps 1 and 2 with the other file. The labels from steps 4 and 5 do not
need changing.

## Alternative: one coverage layer for everything

Swapping the coverage layer for each area can be avoided by using
`atlas_pages_all.parquet`, which holds all 82 page sets.

| Setting | Value |
|---|---|
| Coverage layer | `atlas_pages_all` |
| Filter with | `"series" = 'regional' AND "area_name" = 'Otago Region'` |
| Sort by | `"page"`, ascending |

To change area, edit only the filter. Use `'territorial'` and the district name
for a district. The labels are the same as above.

## Page counts

Largest and smallest, from `atlas_grids_index.csv`:

| Area | Pages |
|---|---|
| Canterbury Region | 270 |
| Southland Region | 213 |
| Southland District | 207 |
| Otago Region | 188 |
| ... | |
| Hamilton City | 3 |
| Porirua City | 3 |
| Kawerau District | 2 |

## Not yet done

- **Index page.** A key map for each area showing the page grid with page
  numbers. The same files can drive it.
- **Old layout variables.** `@grid_layer` and `@atlas_filter` are no longer
  used by the labels and can be removed from the layout.

## Notes

- **Test before a full export.** Exporting with label masks on crashed QGIS
  4.2.2 (see `error.md`). Export a few pages first, or leave the masks off.
- **Not tested in the layout.** The files and their numbering have been
  checked, but the atlas steps above have not been run against the layout.
