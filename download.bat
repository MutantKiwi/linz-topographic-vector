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
    nztopo50_carto_symbol
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
