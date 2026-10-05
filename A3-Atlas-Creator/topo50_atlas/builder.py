"""Build an atlas grid file for an area from the bundled A3 base grid."""

import os

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

from . import grid
from .compat import enum_value

PLUGIN_DIR = os.path.dirname(__file__)
BASE_GRID = os.path.join(PLUGIN_DIR, "data", "topo50_a3_grid.gpkg")
BASE_GRID_LAYER = "a3_sheets"

# attributes copied from the base grid, in output order
BASE_FIELDS = [
    ("atlas_code", "string(20)"),
    ("sheet_code", "string(20)"),
    ("sheet_name", "string(120)"),
    ("quad", "integer"),
    ("quad_pos", "string(4)"),
    ("src_sheet", "string(40)"),
    ("overlap_pct", "integer"),
    ("t50_fid", "integer"),
    ("edition", "string(80)"),
    ("revised", "string(120)"),
    ("xmin", "integer"),
    ("ymin", "integer"),
    ("xmax", "integer"),
    ("ymax", "integer"),
]

# attributes added for the atlas, in output order (matches the regional files)
ATLAS_FIELDS = (
    [("adj_n", "string(20)"), ("adj_s", "string(20)"), ("adj_e", "string(20)"), ("adj_w", "string(20)")]
    + [("adj_%s_name" % d, "string(20)") for d in "nsew"]
    + [
        ("series", "string(20)"),
        ("area_name", "string(120)"),
        ("page", "integer"),
        ("page_count", "integer"),
        ("page_label", "string(20)"),
    ]
    + [f for d in "nsew" for f in (("adj_%s_page" % d, "integer"), ("adj_%s_label" % d, "string(60)"))]
)

ALL_FIELDS = BASE_FIELDS + ATLAS_FIELDS


class GridError(Exception):
    pass


def load_base_grid():
    layer = QgsVectorLayer("{}|layername={}".format(BASE_GRID, BASE_GRID_LAYER), "a3_base_grid", "ogr")
    if not layer.isValid():
        raise GridError("The bundled A3 base grid could not be read:\n{}".format(BASE_GRID))
    return layer


def area_geometry(layer, features, target_crs, project=None):
    """Union the polygon features and transform them into the grid's CRS."""
    geoms = [QgsGeometry(f.geometry()) for f in features if f.hasGeometry()]
    if not geoms:
        raise GridError("No polygon was supplied. Select at least one polygon feature.")
    union = QgsGeometry.unaryUnion(geoms)
    if union.isEmpty():
        raise GridError("The selected polygons have no area.")
    if layer.crs() != target_crs:
        context = (project or QgsProject.instance()).transformContext()
        union.transform(QgsCoordinateTransform(layer.crs(), target_crs, context))
    if not union.isGeosValid():
        union = union.makeValid()
    return union


def select_sheets(base, area, min_overlap_km2):
    """Return (selected sheet dicts with a 'geometry' key, lattice of all sheets)."""
    names = [n for n, _ in BASE_FIELDS]
    available = set(base.fields().names())
    all_sheets, selected = [], []
    bbox = area.boundingBox()
    engine = QgsGeometry.createGeometryEngine(area.constGet())
    engine.prepareGeometry()
    for feat in base.getFeatures(QgsFeatureRequest()):
        sheet = {n: (feat[n] if n in available else None) for n in names}
        for key in ("xmin", "ymin", "xmax", "ymax", "quad", "overlap_pct", "t50_fid"):
            if sheet.get(key) is not None:
                try:
                    sheet[key] = int(sheet[key])
                except (TypeError, ValueError):
                    sheet[key] = None
        all_sheets.append(sheet)
        geom = feat.geometry()
        if not geom.boundingBox().intersects(bbox):
            continue
        if not engine.intersects(geom.constGet()):
            continue
        overlap_km2 = geom.intersection(area).area() / 1e6
        if overlap_km2 >= min_overlap_km2:
            picked = dict(sheet)
            picked["geometry"] = QgsGeometry(geom)
            selected.append(picked)
    return selected, grid.build_lattice(all_sheets)


def build_pages(area_layer, features, area_name, min_overlap_km2=0.1, project=None):
    """Work out the numbered pages for an area. Returns (pages, crs)."""
    base = load_base_grid()
    area = area_geometry(area_layer, features, base.crs(), project)
    selected, lattice = select_sheets(base, area, min_overlap_km2)
    if not selected:
        raise GridError(
            "No A3 sheets overlap the selected area by at least {} km². "
            "Check the polygon is in New Zealand.".format(min_overlap_km2)
        )
    pages = grid.number_pages(selected, lattice)
    for page in pages:
        page["series"] = "custom"
        page["area_name"] = area_name
    return pages, base.crs()


def pages_to_layer(pages, crs, name):
    """Put the pages into a memory layer with the standard atlas columns."""
    uri = "Polygon?crs={}&{}".format(crs.authid(), "&".join("field={}:{}".format(n, t) for n, t in ALL_FIELDS))
    layer = QgsVectorLayer(uri, name, "memory")
    if not layer.isValid():
        raise GridError("Could not create the grid layer in memory.")
    provider = layer.dataProvider()
    feats = []
    for page in pages:
        feat = QgsFeature(layer.fields())
        feat.setGeometry(page["geometry"])
        feat.setAttributes([page.get(n) for n, _ in ALL_FIELDS])
        feats.append(feat)
    provider.addFeatures(feats)
    layer.updateExtents()
    return layer


def parquet_available():
    try:
        from osgeo import ogr

        return ogr.GetDriverByName("Parquet") is not None
    except Exception:
        return False


def write_grid(layer, folder, base_name, project=None):
    """
    Write the grid as GeoParquet, or GeoPackage when this QGIS cannot write
    Parquet. Returns the path written.
    """
    use_parquet = parquet_available()
    path = os.path.join(folder, base_name + (".parquet" if use_parquet else ".gpkg"))
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            raise GridError(
                "The existing grid file is in use and could not be replaced:\n{}\n"
                "Remove its layer from the project (or close other programs using it) and try again.".format(path)
            )
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "Parquet" if use_parquet else "GPKG"
    options.fileEncoding = "UTF-8"
    if not use_parquet:
        options.layerName = base_name
    context = (project or QgsProject.instance()).transformContext()
    result = QgsVectorFileWriter.writeAsVectorFormatV3(layer, path, context, options)
    code, message = result[0], result[1]
    no_error = enum_value(QgsVectorFileWriter, "WriterError", "NoError")
    if code != no_error:
        raise GridError("Could not write the grid file:\n{}\n{}".format(path, message))
    return path


def create_grid_file(area_layer, features, area_name, folder, base_name, min_overlap_km2=0.1, project=None):
    """Build the pages for an area and write them to disk. Returns (path, page_count)."""
    pages, crs = build_pages(area_layer, features, area_name, min_overlap_km2, project)
    layer = pages_to_layer(pages, crs, base_name)
    path = write_grid(layer, folder, base_name, project)
    return path, len(pages)


def nztm():
    return QgsCoordinateReferenceSystem("EPSG:2193")
