# Downloading the NZ Topo50 project and data

How to get the LINZ NZ Topo50 QGIS project and its parquet data onto your
machine.

## Summary

There are two ways to get the data:

1. **Docker (preferred).** The LINZ `map` container downloads the QGIS project,
   styles, symbols and parquet files in one step.
2. **Batch script (fallback).** If the container leaves the parquet files empty,
   a Windows batch script downloads every parquet file directly with `wget`.

The QGIS project file can also be downloaded on its own:
<https://d1jzh93b1t1cv.cloudfront.net/qgis/nztopo50/latest/nztopo50.qgs>

## Option 1: download with Docker

Requires Docker Desktop (or another Docker engine) running.

```
docker run -it --rm -v <download folder>:/working ghcr.io/linz/topographic-system/map:latest download --project https://d1jzh93b1t1cv.cloudfront.net/qgis/nztopo50/latest/nztopo50.json --output /working/output/project/ --cache /working/cache/
```

Replace `<download folder>` with a folder on your machine, for example
`F:\Project\linz-test3`.

| Part | Meaning |
|---|---|
| `-v <download folder>:/working` | Makes your folder available inside the container as `/working`. |
| `--project ...nztopo50.json` | The project definition listing the QGIS project and its datasets. |
| `--output /working/output/project/` | Where the project is written. On your machine this is `<download folder>\output\project`. |
| `--cache /working/cache/` | Where downloads are cached. On your machine this is `<download folder>\cache`. |

When it finishes, `<download folder>\output\project` holds `nztopo50.qgs`, the
parquet files, and the `style-layer` and `symbol` folders.

## Option 2: download the parquet files with a batch script

If the parquet files from Option 1 are null (empty), use this script to
download them directly.

Requires `wget.exe` on the PATH.

1. Save the script below as a `.bat` file (for example `pq.bat`) in
   `<download folder>\output\project`.
2. Double-click it, or run it from a command prompt in that folder.
3. The files are saved into a `parquet` subfolder.

```bat
@echo off
REM Downloads all NZTopo50 parquet files referenced (via dataset collection.json links)
REM from https://d1jzh93b1t1cv.cloudfront.net/qgis/nztopo50/latest/nztopo50.json
REM Requires wget.exe on the PATH. Files are saved into the "parquet" subfolder.
REM Each dataset lives at data/<name>/latest/<name>.parquet

setlocal
set BASE=https://d1jzh93b1t1cv.cloudfront.net/data
set OUTDIR=parquet
set WGET_OPTS=-c -N --no-verbose -P %OUTDIR%

if not exist "%OUTDIR%" mkdir "%OUTDIR%"

for %%D in (
    descriptive_text
    geographic_name
    nztopo50_map_sheet
    coastline
    nztopo50_carto_text
    nz_topo50_dms_grid
    nz_topo50_grid
    bridge_line
    road_line
    track_line
    railway_line
    runway
    structure_point
    building
    building_point
    residential_area
    vegetation_point
    water
    trig_point
    relief_point
    relief_line
    fence_line
    water_line
    vegetation_line
    vegetation
    landcover
    nztopo50_ice_contour
    contour
    island
    nztopo50_sea_polygon
    structure_line
    structure
    transport_point
    tunnel_line
    airport
    landuse
    place_point
    landcover_point
    landcover_line
    water_point
    marine
) do (
    echo Downloading %%D.parquet ...
    wget %WGET_OPTS% "%BASE%/%%D/latest/%%D.parquet"
)

echo.
echo Done. Files are in "%CD%\%OUTDIR%".
endlocal
pause
```

### Notes on the script

- **41 datasets.** Each one is fetched from
  `https://d1jzh93b1t1cv.cloudfront.net/data/<name>/latest/<name>.parquet`.
- **Safe to re-run.** `-c` resumes a partial download and `-N` skips files that
  have not changed on the server.
- **Size.** `contour.parquet` is about 1.75 GB. The rest are much smaller.
- **Where QGIS looks.** The script saves into the `parquet` subfolder. If the
  QGIS project cannot find its layers, copy the parquet files up into the same
  folder as `nztopo50.qgs`.

## Links

- QGIS project file: <https://d1jzh93b1t1cv.cloudfront.net/qgis/nztopo50/latest/nztopo50.qgs>
- Project definition: <https://d1jzh93b1t1cv.cloudfront.net/qgis/nztopo50/latest/nztopo50.json>
- LINZ topographic-system repository: <https://github.com/linz/topographic-system>
