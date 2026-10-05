"""Load the left and right layout templates, export atlas pages, merge PDFs."""

import os
import sys

from qgis.core import (
    QgsLayoutExporter,
    QgsLayoutItemMap,
    QgsPalLayerSettings,
    QgsPrintLayout,
    QgsProject,
    QgsReadWriteContext,
    QgsRuleBasedLabeling,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtXml import QDomDocument

from .compat import enum_value

PLUGIN_DIR = os.path.dirname(__file__)
EXT_DIR = os.path.join(PLUGIN_DIR, "ext")


class ExportError(Exception):
    pass


class Cancelled(Exception):
    pass


def load_layout(project, template_path, name):
    """Create a print layout in the project from a .qpt template, replacing any layout of the same name."""
    if not template_path or not os.path.isfile(template_path):
        raise ExportError("Layout template not found:\n{}".format(template_path))
    with open(template_path, "r", encoding="utf-8") as handle:
        text = handle.read()
    doc = QDomDocument()
    parsed = doc.setContent(text)
    if isinstance(parsed, tuple):
        parsed = parsed[0]
    if not parsed:
        raise ExportError("The template is not a valid layout file:\n{}".format(template_path))

    manager = project.layoutManager()
    existing = manager.layoutByName(name)
    if existing is not None:
        manager.removeLayout(existing)

    # resolve relative paths in the template (logos and other pictures) against the project folder
    context = QgsReadWriteContext()
    context.setPathResolver(project.pathResolver())
    layout = QgsPrintLayout(project)
    result = layout.loadFromTemplate(doc, context)
    ok = result[1] if isinstance(result, tuple) and len(result) > 1 else True
    if not ok:
        raise ExportError("QGIS could not load the template:\n{}".format(template_path))
    layout.setName(name)
    manager.addLayout(layout)
    return layout


def atlas_maps(layout):
    return [i for i in layout.items() if isinstance(i, QgsLayoutItemMap) and i.atlasDriven()]


def configure_atlas(layout, grid_layer, filter_expression):
    """Point a layout's atlas at the grid, sorted by page, filtered to its side."""
    atlas = layout.atlas()
    atlas.setCoverageLayer(grid_layer)
    atlas.setEnabled(True)
    atlas.setHideCoverage(True)
    atlas.setSortFeatures(True)
    atlas.setSortExpression('"page"')
    atlas.setSortAscending(True)
    atlas.setPageNameExpression('"page"')
    atlas.setFilterFeatures(True)
    result = atlas.setFilterExpression(filter_expression)
    ok = result[0] if isinstance(result, tuple) else result
    if ok is False:
        raise ExportError("The atlas filter was rejected: {}".format(filter_expression))
    atlas.setFilenameExpression("'page_' || lpad(to_string(\"page\"), 4, '0')")
    return atlas


def page_file(folder, page):
    return os.path.join(folder, "page_{:04d}.pdf".format(int(page)))


def export_layout_pages(layout, folder, dpi, force_vector, progress, is_cancelled):
    """
    Export every atlas page of a layout as its own PDF named by page number.

    progress(page_number) is called after each page.
    Returns a list of (page_number, path).
    """
    atlas = layout.atlas()
    success = enum_value(QgsLayoutExporter, "ExportResult", "Success")
    settings = QgsLayoutExporter.PdfExportSettings()
    settings.dpi = dpi
    settings.rasterizeWholeImage = False
    settings.forceVectorOutput = bool(force_vector)

    written = []
    exporter = QgsLayoutExporter(layout)
    atlas.beginRender()
    try:
        atlas.updateFeatures()
        more = atlas.first()
        while more:
            if is_cancelled():
                raise Cancelled()
            feature = layout.reportContext().feature()
            page = int(feature["page"])
            path = page_file(folder, page)
            result = exporter.exportToPdf(path, settings)
            if result != success:
                raise ExportError(
                    "Page {} failed to export from layout '{}' ({}).".format(page, layout.name(), result)
                )
            written.append((page, path))
            progress(page)
            more = atlas.next()
    finally:
        atlas.endRender()
    return written


def pdf_writer_class():
    """pypdf's PdfWriter, from QGIS's Python if installed, otherwise the bundled copy."""
    try:
        from pypdf import PdfWriter
    except ImportError:
        if EXT_DIR not in sys.path:
            sys.path.insert(0, EXT_DIR)
        from pypdf import PdfWriter
    return PdfWriter


def merge_pdfs(page_paths, output_path):
    """Merge PDFs in page-number order. page_paths is a list of (page_number, path)."""
    writer = pdf_writer_class()()
    for _, path in sorted(page_paths):
        writer.append(path)
    with open(output_path, "wb") as handle:
        writer.write(handle)
    writer.close()
    return output_path


class LabelMasksDisabled:
    """
    Context manager that switches off label masks on every vector layer and
    puts the original labelling back afterwards.

    Exporting with selective masking can crash QGIS on large pages, so this
    lets an export run without masks and leaves the project as it was.
    """

    def __init__(self, project=None):
        self.project = project or QgsProject.instance()
        self.saved = []

    @staticmethod
    def _without_mask(settings):
        copy = QgsPalLayerSettings(settings)
        text_format = copy.format()
        mask = text_format.mask()
        if not mask.enabled():
            return None
        mask.setEnabled(False)
        text_format.setMask(mask)
        copy.setFormat(text_format)
        return copy

    def __enter__(self):
        for layer in self.project.mapLayers().values():
            if not isinstance(layer, QgsVectorLayer) or layer.labeling() is None:
                continue
            labeling = layer.labeling()
            changed = False
            replacement = labeling.clone()
            if isinstance(replacement, QgsRuleBasedLabeling):
                rules = [replacement.rootRule()] + list(replacement.rootRule().descendants())
                for rule in rules:
                    if rule.settings() is None:
                        continue
                    new_settings = self._without_mask(rule.settings())
                    if new_settings is not None:
                        rule.setSettings(new_settings)
                        changed = True
            elif isinstance(replacement, QgsVectorLayerSimpleLabeling):
                new_settings = self._without_mask(replacement.settings())
                if new_settings is not None:
                    replacement = QgsVectorLayerSimpleLabeling(new_settings)
                    changed = True
            if changed:
                self.saved.append((layer, labeling.clone()))
                layer.setLabeling(replacement)
        return self

    def __exit__(self, exc_type, exc, tb):
        for layer, original in self.saved:
            layer.setLabeling(original)
        self.saved = []
        return False


def export_atlas(
    project,
    grid_layer,
    right_template,
    left_template,
    layout_prefix,
    right_filter,
    left_filter,
    pages_folder,
    merged_path,
    dpi=300,
    force_vector=False,
    disable_masks=False,
    log=lambda text: None,
    progress=lambda done, total: None,
    is_cancelled=lambda: False,
):
    """
    Run the whole export: both layouts, every page, then one merged PDF.

    Returns (merged_path, number_of_pages).
    """
    os.makedirs(pages_folder, exist_ok=True)
    layouts = []
    for side, template, expression in (("right", right_template, right_filter), ("left", left_template, left_filter)):
        layout = load_layout(project, template, "{} - {}".format(layout_prefix, side))
        if not atlas_maps(layout):
            log(
                "Warning: no map in the {}-hand template is set to 'Controlled by Atlas'. "
                "Every page will show the same map view.".format(side)
            )
        atlas = configure_atlas(layout, grid_layer, expression)
        count = atlas.updateFeatures()
        log("{}-hand layout: {} page(s).".format(side.capitalize(), count))
        layouts.append((side, layout, count))

    total = sum(count for _, _, count in layouts)
    if total == 0:
        raise ExportError("No pages matched. Check the page range.")

    done = [0]

    def step(page):
        done[0] += 1
        progress(done[0], total)
        log("Exported page {} ({} of {}).".format(page, done[0], total))

    written = []

    def run():
        for _, layout, count in layouts:
            if count:
                written.extend(export_layout_pages(layout, pages_folder, dpi, force_vector, step, is_cancelled))

    if disable_masks:
        with LabelMasksDisabled(project):
            run()
    else:
        run()

    log("Merging {} page(s)...".format(len(written)))
    merge_pdfs(written, merged_path)
    return merged_path, len(written)
