# Crash reports with the help of Claude


# 1. QGIS crash: font marker symbols with labels

## Summary

QGIS 4.2.2 crashed with an access violation while rendering the map. The crash
happens when QGIS measures a **font marker** symbol so that labels can avoid
it, on a background render thread.

Two layers have the combination that triggers it (font marker symbols plus
labels):

- `nztopo50_carto_symbol`
- `nztopo50_carto_symbol_label`

The font they use (Nimbus Sans LINZ) is installed, so this is not a missing
font. It points to a bug in QGIS 4.2.2 / Qt 6.11.1 rather than a problem with
the data.

**Status:** workarounds identified. Whether they stop the crash has not yet
been confirmed.

## Crash report

```
Python Stack Trace
Windows fatal exception: access violation

Stack Trace
QFontMetrics::horizontalAdvance :
QgsFontMarkerSymbolLayer::characterToRender :
QgsFontMarkerSymbolLayer::bounds :
QgsMarkerSymbol::bounds :
QgsVectorLayerLabelProvider::getPointObstacleGeometry :
QgsVectorLayerProfileResults::visitFeaturesInRange :
QgsVectorLayerProfileResults::visitFeaturesInRange :
QgsVectorLayerProfileResults::visitFeaturesInRange :
QgsMapRendererParallelJob::renderLayerStatic :
QgsProfilePlotRenderer::replaceSourceInternal :
QgsMapRendererParallelJob::renderingFinished :
QgsMapRendererParallelJob::takeLabelingResults :
QtConcurrent::ThreadEngineBase::run :
QThreadPoolPrivate::reset :
QThread::start :
BaseThreadInitThunk :
RtlUserThreadStart :
```

| | |
|---|---|
| QGIS version | 4.2.2-Belém do Pará (revision f1431de8676) |
| Qt | 6.11.1 |
| GDAL | 3.13.3 |
| OS | Windows, kernel 10.0.26200, x86_64 |

## Reading the stack trace

From the bottom up:

| Frames | Meaning |
|---|---|
| `QThread::start` ... `QtConcurrent::ThreadEngineBase::run` | A worker thread from the render thread pool. |
| `QgsMapRendererParallelJob::renderLayerStatic` | A layer being drawn on that thread during a normal map render. |
| `QgsVectorLayerLabelProvider::getPointObstacleGeometry` | The layer has labels, and QGIS is working out the size of each point's symbol so labels can avoid it. |
| `QgsMarkerSymbol::bounds` > `QgsFontMarkerSymbolLayer::bounds` > `characterToRender` | The symbol is a font marker, so the glyph has to be measured. |
| `QFontMetrics::horizontalAdvance` | The crash, inside Qt's font measuring. |

The `QgsVectorLayerProfileResults` and `QgsProfilePlotRenderer` frames are
almost certainly mislabelled. Nothing in the project uses elevation profiles.

## Diagnosis

### 1. Find layers with font markers and labels

Run in the QGIS Python console:

```python
for lyr in QgsProject.instance().mapLayers().values():
    if lyr.type() != QgsMapLayerType.VectorLayer or not lyr.renderer():
        continue
    fonts = set()
    for sym in lyr.renderer().symbols(QgsRenderContext()):
        for sl in sym.symbolLayers():
            if sl.layerType() == 'FontMarker':
                fonts.add(sl.fontFamily())
    if fonts:
        print(lyr.name(), '| labels on:', lyr.labelsEnabled(), '| fonts:', fonts)
```

Result:

```
nztopo50_carto_symbol | labels on: True | fonts: {'Nimbus Sans LINZ'}
nztopo50_carto_symbol_label | labels on: True | fonts: {'Nimbus Sans LINZ'}
```

### 2. Check the font is installed

```python
from qgis.PyQt.QtGui import QFontDatabase
print([f for f in QFontDatabase.families() if 'Nimbus' in f])
```

Result:

```
['Nimbus Sans LINZ', 'Nimbus Sans LINZ Narrow']
```

The font is available to QGIS, which rules out a missing font.

## Workarounds

Save the project before trying each one. A crash loses unsaved style changes.

### 1. Stop the symbols acting as label obstacles

This skips the step that crashed. Do it on both layers.

1. Open the layer's Properties > Labels.
2. If the labelling is rule-based, double-click the rule to edit it.
3. On the Rendering tab, untick **Features act as obstacles**.
4. Click OK, then Apply.

Trade-off: other labels may now be placed over these symbols. Check a busy
area afterwards.

### 2. Turn off parallel rendering

Use this if the crash continues.

Settings > Options > Rendering > untick **Render layers in parallel using many
CPU cores**.

Trade-off: the map draws more slowly. If this stops the crash, it confirms a
thread-safety bug.

### 3. Replace the font markers

Change the font marker symbols on the two layers to SVG or simple markers. The
project's `symbol` folder has SVGs for most Topo50 point symbols.

## If the font had been missing

Install the eight `NimbusSansLINZ-*.otf` files from the project folder (select
them, right-click, **Install for all users**) and restart QGIS.

#


# 2. QGIS crash: PDF export with label masks

Record of a QGIS crash when exporting the NZ Topo50 print layout to PDF, the
likely cause, and what to try.

## Summary

QGIS 4.2.2 crashes with an access violation while exporting the print layout
to PDF. The crash is in the step that applies **selective masks**: the label
masks set up so the grid lines and contours break around text.

The most likely cause is memory. Each masked layer needs several full-page
images at the export resolution, and if one cannot be created QGIS tries to
draw an empty image and crashes.

**Status:** cause not yet confirmed. The tests below have not been run.

## Crash report

```
Python Stack Trace
Windows fatal exception: access violation

Stack Trace
QImage::hasAlphaChannel :
QRasterPaintEngine::brushOriginChanged :
QRasterPaintEngine::drawImage :
QPainter::drawImage :
QgsMapRendererJob::composeSecondPass :
QgsMapRendererCustomPainterJob::doRender :
QgsMapRendererCustomPainterJob::startPrivate :
QgsMapRendererCustomPainterJob::renderSynchronously :
QgsLayoutItemMap::drawMap :
QgsLayoutItemMap::paint :
QGraphicsScene::dragMoveEvent :
QGraphicsScene::drawItems :
QGraphicsScene::drawItems :
QGraphicsScene::render :
QgsLayoutExporter::renderRegion :
QgsLayoutExporter::renderPage :
QgsLayoutExporter::printPrivate :
QgsLayoutExporter::exportToPdf :
QgsGeoreferencerMainWindow::dragEnterEvent :
QgisApp::identifyMapTool :
QObject::qt_static_metacall :
QMetaObject::activate :
QAction::activate :
QAbstractButton::click :
...
main :
BaseThreadInitThunk :
RtlUserThreadStart :
```

| | |
|---|---|
| QGIS version | 4.2.2-Belém do Pará (revision f1431de8676) |
| Qt | 6.11.1 |
| GDAL | 3.13.3 |
| OS | Windows, kernel 10.0.26200, x86_64 |

## Reading the stack trace

From the bottom up:

| Frames | Meaning |
|---|---|
| `QAbstractButton::click` ... `QAction::activate` | A toolbar button was clicked (Export as PDF). |
| `QgsLayoutExporter::exportToPdf` > `renderPage` | The layout is exporting a page to PDF. |
| `QgsLayoutItemMap::paint` > `drawMap` | The map item is being drawn. |
| `QgsMapRendererCustomPainterJob::doRender` | The map is rendered on the main thread for the export. |
| `QgsMapRendererJob::composeSecondPass` | The masking step. Masked layers are drawn a second time and combined with a mask image. |
| `QPainter::drawImage` > `QImage::hasAlphaChannel` | The crash, while drawing one of those images. This usually means the image was never created. |

The `QgsGeoreferencerMainWindow::dragEnterEvent` and `QgisApp::identifyMapTool`
frames are mislabelled. The georeferencer and identify tool are not involved.

## Likely cause

Selective masking draws each masked layer into its own full-page images at the
export resolution, then combines them.

| Export resolution | Approximate size of one full-sheet image |
|---|---|
| 150 dpi | 70 MB |
| 300 dpi | 270 MB |
| 600 dpi | 1 GB |

With several masked layers (grid lines, contours) and several images per layer,
the total can exceed what QGIS can allocate. The contour layer is the heaviest.

These sizes are estimates for a Topo50 sheet. The memory explanation is
inferred from the stack trace and has not been confirmed.

## What to try

Save the project before each test. A crash loses unsaved changes.

### 1. Confirm the masks are the trigger

1. Open the `contour` layer's Properties > Masks and untick the mask sources.
2. Do the same on `Grid_lines`.
3. Export the layout to PDF.

If it exports, the masks are the trigger.

### 2. Lower the export resolution

1. Turn the masks back on.
2. In the layout, open the Layout panel > Export Settings and set **Export
   resolution** to 150 dpi.
3. Export to PDF.

If that works, step up to 200 and 300 dpi to find the limit.

### 3. Export as vectors

1. In Export Settings, tick **Always export as vectors**.
2. In the PDF export dialog, leave the rasterize options off.

Recent QGIS versions apply masks as vector clipping in this mode, which avoids
the large images.

### 4. Mask fewer layers

If the grid mask alone exports without crashing, keep it and drop the contour
mask. Use a small text buffer on the contour values instead.

## Masks currently set up

| Masked layer | Mask source | Purpose |
|---|---|---|
| `Grid_lines` | `nztopo50_carto_text` label mask, plus grid label and symbol masks | Grid lines break around place names. |
| `contour` | `contour` label mask and/or `nztopo50_carto_symbol` label mask | Contour lines break around contour values. |


## Results

Fill in after testing.

| Test | Result |
|---|---|
| 1. Masks off | YES |
| 2. 150 dpi with masks | |
| 3. Always export as vectors | YES |
| 4. Grid mask only | |

Workaround seems to export as vector only

