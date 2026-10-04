# Crash reports with th ehelp of Claude


# 1. QGIS crash: font marker symbols with labels

Record of a QGIS crash in the NZ Topo50 project, what caused it, and the
workarounds.

## Summary

QGIS 4.2.2 crashes with an access violation while rendering the map. The crash
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

## Reporting it

If the crash can be reproduced, report it on the QGIS issue tracker
(<https://github.com/qgis/QGIS/issues>) with:

- The crash report above.
- The two layer names and the fact that they combine font marker symbols with
  labels.
- Which workaround, if any, stopped it.

## How to investigate a QGIS crash in general

1. **Crash dialog.** Use **Copy Report** in the "QGIS unexpectedly ended"
   dialog. The top lines of the stack trace name the area at fault.
2. **Windows Event Viewer.** If there was no dialog, look in Windows Logs >
   Application for an Error naming `qgis-bin.exe`. It gives the faulting module
   and exception code.
3. **Reproduce and narrow down.** Note the last action before the crash and
   undo the most recent change.
4. **Rule out plugins.** Start with `qgis --noplugins` from the OSGeo4W Shell.
5. **Rule out the profile.** Try a new profile under Settings > User Profiles.
