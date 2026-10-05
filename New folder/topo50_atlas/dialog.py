"""The plugin's single dialog: choose an area, templates and output, then build and export."""

import os
import traceback
from datetime import datetime

from qgis.core import Qgis, QgsFillSymbol, QgsProject, QgsSettings, QgsSingleSymbolRenderer, QgsVectorLayer
from qgis.gui import QgsFeaturePickerWidget, QgsFileWidget, QgsMapLayerComboBox
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from . import builder, exporter, grid
from .compat import enum_value

SETTINGS_PREFIX = "topo50_atlas/"
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def _polygon_filter():
    try:
        return Qgis.LayerFilter.PolygonLayer
    except AttributeError:
        from qgis.core import QgsMapLayerProxyModel

        return QgsMapLayerProxyModel.PolygonLayer


class AtlasDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.cancel_requested = False
        self.running = False
        self.last_output = None
        self.setWindowTitle("Topo50 Atlas Builder")
        self.setMinimumWidth(560)
        self._build_ui()
        self._load_settings()
        self._update_area_mode()

    # ---------------------------------------------------------------- UI

    def _build_ui(self):
        outer = QVBoxLayout(self)

        # 1. Area
        area_box = QGroupBox("1. Area")
        area_form = QFormLayout(area_box)
        self.project_name = QLineEdit()
        self.project_name.setPlaceholderText("For example: Otago Region")
        area_form.addRow("Project name", self.project_name)

        self.layer_combo = QgsMapLayerComboBox()
        self.layer_combo.setFilters(_polygon_filter())
        self.layer_combo.layerChanged.connect(self._layer_changed)
        area_form.addRow("Polygon layer", self.layer_combo)

        self.use_selected = QRadioButton("Use the features selected on the map")
        self.use_picked = QRadioButton("Choose one feature from the list")
        self.use_selected.setChecked(True)
        self.use_selected.toggled.connect(self._update_area_mode)
        area_form.addRow(self.use_selected)
        area_form.addRow(self.use_picked)
        self.feature_picker = QgsFeaturePickerWidget()
        area_form.addRow("Feature", self.feature_picker)
        self.selection_note = QLabel("")
        area_form.addRow("", self.selection_note)

        self.min_overlap = QDoubleSpinBox()
        self.min_overlap.setDecimals(2)
        self.min_overlap.setRange(0.0, 500.0)
        self.min_overlap.setSingleStep(0.1)
        self.min_overlap.setValue(0.1)
        self.min_overlap.setSuffix(" km²")
        self.min_overlap.setToolTip("A sheet is included when it holds at least this much of the area.")
        area_form.addRow("Minimum overlap", self.min_overlap)
        outer.addWidget(area_box)

        # 2. Layout
        layout_box = QGroupBox("2. Page layouts")
        layout_form = QFormLayout(layout_box)
        self.right_template = self._file_widget("Right-hand page template")
        self.left_template = self._file_widget("Left-hand page template")
        layout_form.addRow("Right-hand template", self.right_template)
        layout_form.addRow("Left-hand template", self.left_template)
        self.start_side = QComboBox()
        self.start_side.addItem("Right-hand page", "right")
        self.start_side.addItem("Left-hand page", "left")
        layout_form.addRow("Page 1 is a", self.start_side)
        outer.addWidget(layout_box)

        # 3. Output
        out_box = QGroupBox("3. Export")
        out_form = QFormLayout(out_box)
        self.out_folder = QgsFileWidget()
        self.out_folder.setStorageMode(enum_value(QgsFileWidget, "StorageMode", "GetDirectory"))
        self.out_folder.setDialogTitle("Folder to export into")
        out_form.addRow("Export folder", self.out_folder)

        range_row = QHBoxLayout()
        self.first_page = QSpinBox()
        self.first_page.setRange(0, 9999)
        self.first_page.setSpecialValueText("first")
        self.last_page = QSpinBox()
        self.last_page.setRange(0, 9999)
        self.last_page.setSpecialValueText("last")
        range_row.addWidget(self.first_page)
        range_row.addWidget(QLabel("to"))
        range_row.addWidget(self.last_page)
        range_row.addStretch(1)
        out_form.addRow("Pages", range_row)

        self.dpi = QSpinBox()
        self.dpi.setRange(72, 1200)
        self.dpi.setSingleStep(50)
        self.dpi.setValue(300)
        self.dpi.setSuffix(" dpi")
        out_form.addRow("Resolution", self.dpi)

        self.disable_masks = QCheckBox("Turn off label masks while exporting (avoids a known QGIS crash)")
        self.hide_area = QCheckBox("Hide the polygon layer while exporting (so it does not cover the map)")
        self.hide_area.setChecked(True)
        self.force_vector = QCheckBox("Always export as vectors")
        self.keep_pages = QCheckBox("Keep the individual page PDFs")
        out_form.addRow(self.hide_area)
        out_form.addRow(self.disable_masks)
        out_form.addRow(self.force_vector)
        out_form.addRow(self.keep_pages)
        outer.addWidget(out_box)

        # progress and log
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        outer.addWidget(self.progress)
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumBlockCount(2000)
        self.log_box.setMinimumHeight(110)
        outer.addWidget(self.log_box)

        # buttons
        buttons = QHBoxLayout()
        self.grid_button = QPushButton("Create grid only")
        self.grid_button.setToolTip("Write the page grid file and add it to the map, without exporting.")
        self.export_button = QPushButton("Export atlas")
        self.export_button.setDefault(True)
        self.open_button = QPushButton("Open folder")
        self.open_button.setEnabled(False)
        self.cancel_button = QPushButton("Close")
        buttons.addWidget(self.grid_button)
        buttons.addStretch(1)
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.export_button)
        buttons.addWidget(self.cancel_button)
        outer.addLayout(buttons)

        self.grid_button.clicked.connect(self.create_grid_clicked)
        self.export_button.clicked.connect(self.export_clicked)
        self.cancel_button.clicked.connect(self.cancel_or_close)
        self.open_button.clicked.connect(self.open_output)

    def _file_widget(self, title):
        widget = QgsFileWidget()
        widget.setStorageMode(enum_value(QgsFileWidget, "StorageMode", "GetFile"))
        widget.setFilter("QGIS layout templates (*.qpt)")
        widget.setDialogTitle(title)
        widget.setDefaultRoot(TEMPLATE_DIR)
        return widget

    # ---------------------------------------------------------- settings

    def _load_settings(self):
        s = QgsSettings()
        self.right_template.setFilePath(self._saved_template(s, "right"))
        self.left_template.setFilePath(self._saved_template(s, "left"))
        self.out_folder.setFilePath(s.value(SETTINGS_PREFIX + "out_folder", ""))
        self.dpi.setValue(int(s.value(SETTINGS_PREFIX + "dpi", 300)))
        self.min_overlap.setValue(float(s.value(SETTINGS_PREFIX + "min_overlap", 0.1)))
        index = self.start_side.findData(s.value(SETTINGS_PREFIX + "start_side", "right"))
        self.start_side.setCurrentIndex(max(index, 0))
        self.disable_masks.setChecked(str(s.value(SETTINGS_PREFIX + "disable_masks", "false")).lower() == "true")
        self.force_vector.setChecked(str(s.value(SETTINGS_PREFIX + "force_vector", "false")).lower() == "true")
        self.keep_pages.setChecked(str(s.value(SETTINGS_PREFIX + "keep_pages", "false")).lower() == "true")
        self.hide_area.setChecked(str(s.value(SETTINGS_PREFIX + "hide_area", "true")).lower() == "true")

    def _save_settings(self):
        s = QgsSettings()
        s.setValue(SETTINGS_PREFIX + "right_template", self.right_template.filePath())
        s.setValue(SETTINGS_PREFIX + "left_template", self.left_template.filePath())
        s.setValue(SETTINGS_PREFIX + "out_folder", self.out_folder.filePath())
        s.setValue(SETTINGS_PREFIX + "dpi", self.dpi.value())
        s.setValue(SETTINGS_PREFIX + "min_overlap", self.min_overlap.value())
        s.setValue(SETTINGS_PREFIX + "start_side", self.start_side.currentData())
        s.setValue(SETTINGS_PREFIX + "disable_masks", "true" if self.disable_masks.isChecked() else "false")
        s.setValue(SETTINGS_PREFIX + "force_vector", "true" if self.force_vector.isChecked() else "false")
        s.setValue(SETTINGS_PREFIX + "keep_pages", "true" if self.keep_pages.isChecked() else "false")
        s.setValue(SETTINGS_PREFIX + "hide_area", "true" if self.hide_area.isChecked() else "false")

    def _saved_template(self, settings, side):
        """The remembered template, unless it is missing or is only the bundled example."""
        default = self._default_template(side)
        saved = settings.value(SETTINGS_PREFIX + side + "_template", "") or ""
        if not saved or not os.path.isfile(saved):
            return default
        if os.path.basename(saved).endswith("_example.qpt") and default and not default.endswith("_example.qpt"):
            return default
        return saved

    @staticmethod
    def _default_template(side):
        for name in ("A3_{}.qpt".format(side), "A3_{}_example.qpt".format(side)):
            path = os.path.join(TEMPLATE_DIR, name)
            if os.path.isfile(path):
                return path
        return ""

    # ------------------------------------------------------- area choice

    def refresh_from_project(self):
        """Called each time the dialog is shown."""
        active = self.iface.activeLayer() if self.iface else None
        if isinstance(active, QgsVectorLayer) and self.layer_combo.findText(active.name()) >= 0:
            self.layer_combo.setLayer(active)
        self._layer_changed(self.layer_combo.currentLayer())

    def _layer_changed(self, layer):
        if isinstance(layer, QgsVectorLayer):
            self.feature_picker.setLayer(layer)
            display = layer.displayExpression()
            if display:
                self.feature_picker.setDisplayExpression(display)
        self._update_area_mode()

    def _update_area_mode(self):
        picked = self.use_picked.isChecked()
        self.feature_picker.setEnabled(picked)
        layer = self.layer_combo.currentLayer()
        if isinstance(layer, QgsVectorLayer) and not picked:
            count = layer.selectedFeatureCount()
            self.selection_note.setText(
                "{} feature(s) selected in this layer.".format(count)
                if count
                else "Nothing is selected in this layer yet."
            )
        else:
            self.selection_note.setText("")

    def _area_features(self):
        layer = self.layer_combo.currentLayer()
        if not isinstance(layer, QgsVectorLayer):
            raise builder.GridError("Choose a polygon layer.")
        if self.use_selected.isChecked():
            features = list(layer.getSelectedFeatures())
            if not features:
                raise builder.GridError(
                    "No features are selected in '{}'. Select one or more polygons on the map, "
                    "or switch to 'Choose one feature from the list'.".format(layer.name())
                )
        else:
            feature = self.feature_picker.feature()
            if not feature.isValid():
                raise builder.GridError("Choose a feature from the list.")
            features = [feature]
        return layer, features

    # ------------------------------------------------------------ helpers

    def log(self, text):
        self.log_box.appendPlainText(text)
        QApplication.processEvents()

    def _set_running(self, running):
        self.running = running
        self.cancel_requested = False
        self.grid_button.setEnabled(not running)
        self.export_button.setEnabled(not running)
        self.cancel_button.setText("Cancel" if running else "Close")

    def cancel_or_close(self):
        if self.running:
            self.cancel_requested = True
            self.log("Cancelling after the current page...")
        else:
            self._save_settings()
            self.close()

    def reject(self):
        if self.running:
            self.cancel_requested = True
            return
        self._save_settings()
        super().reject()

    def open_output(self):
        if self.last_output and os.path.isdir(self.last_output):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_output))

    def _project_folder(self):
        name = self.project_name.text().strip()
        if not name:
            raise builder.GridError("Enter a project name.")
        root = self.out_folder.filePath().strip()
        if not root or not os.path.isdir(root):
            raise builder.GridError("Choose an existing export folder.")
        safe = grid.safe_name(name)
        folder = os.path.join(root, safe)
        os.makedirs(folder, exist_ok=True)
        return name, safe, folder

    def _add_grid_to_project(self, path, safe):
        project = QgsProject.instance()
        layer_name = safe + "_grid"
        for existing in project.mapLayersByName(layer_name):
            project.removeMapLayer(existing.id())
        layer = QgsVectorLayer(path, layer_name, "ogr")
        if not layer.isValid():
            raise builder.GridError("The grid file was written but could not be loaded:\n{}".format(path))
        # outline only, and switched off in the layer list, so the grid never covers the map
        try:
            symbol = QgsFillSymbol.createSimple(
                {"style": "no", "outline_color": "200,0,120,255", "outline_width": "0.4", "outline_style": "solid"}
            )
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        except Exception:
            pass
        project.addMapLayer(layer, False)
        root = project.layerTreeRoot()
        node = root.insertLayer(0, layer)
        if node is not None:
            node.setItemVisibilityChecked(False)
        return layer

    def _create_grid(self):
        name, safe, folder = self._project_folder()
        layer, features = self._area_features()
        self.log("Finding A3 sheets for '{}'...".format(name))
        # release any earlier copy of this grid so its file can be replaced
        project = QgsProject.instance()
        for existing in project.mapLayersByName(safe + "_grid"):
            project.removeMapLayer(existing.id())
        QApplication.processEvents()
        path, count = builder.create_grid_file(
            layer, features, name, folder, safe + "_grid", self.min_overlap.value(), QgsProject.instance()
        )
        if not path.lower().endswith(".parquet"):
            self.log("This QGIS cannot write Parquet, so the grid was saved as GeoPackage.")
        grid_layer = self._add_grid_to_project(path, safe)
        self.log("Grid: {} page(s) written to {}".format(count, path))
        self.last_output = folder
        self.open_button.setEnabled(True)
        return name, safe, folder, grid_layer, count

    def _fail(self, error):
        self.log("Stopped: {}".format(error))
        QMessageBox.warning(self, "Topo50 Atlas Builder", str(error))

    # ------------------------------------------------------------ actions

    def create_grid_clicked(self):
        self._save_settings()
        self._set_running(True)
        try:
            self._create_grid()
            self.progress.setValue(100)
        except builder.GridError as error:
            self._fail(error)
        except Exception as error:  # unexpected: show the detail in the log
            self.log(traceback.format_exc())
            self._fail(error)
        finally:
            self._set_running(False)

    def export_clicked(self):
        self._save_settings()
        self.progress.setValue(0)
        self._set_running(True)
        try:
            for label, widget in (("right-hand", self.right_template), ("left-hand", self.left_template)):
                if not os.path.isfile(widget.filePath()):
                    raise exporter.ExportError("Choose the {} template (.qpt file).".format(label))

            name, safe, folder, grid_layer, count = self._create_grid()

            first, last = self.first_page.value(), self.last_page.value()
            if first and last and last < first:
                raise exporter.ExportError("The last page is before the first page.")
            right_filter, left_filter = grid.side_filters(self.start_side.currentData(), first or None, last or None)

            pages_folder = os.path.join(folder, "pages")
            merged = os.path.join(folder, "{}_{}.pdf".format(safe, datetime.now().strftime("%Y%m%d")))

            def progress(done, total):
                self.progress.setValue(int(done * 100 / max(total, 1)))
                QApplication.processEvents()

            # switch the polygon layer off for the export, and put it back afterwards
            area_node, area_was_visible = None, False
            if self.hide_area.isChecked():
                area_layer = self.layer_combo.currentLayer()
                if area_layer is not None:
                    area_node = QgsProject.instance().layerTreeRoot().findLayer(area_layer.id())
                if area_node is not None:
                    area_was_visible = area_node.itemVisibilityChecked()
                    area_node.setItemVisibilityChecked(False)

            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                merged_path, exported = exporter.export_atlas(
                    QgsProject.instance(),
                    grid_layer,
                    self.right_template.filePath(),
                    self.left_template.filePath(),
                    name,
                    right_filter,
                    left_filter,
                    pages_folder,
                    merged,
                    dpi=self.dpi.value(),
                    force_vector=self.force_vector.isChecked(),
                    disable_masks=self.disable_masks.isChecked(),
                    log=self.log,
                    progress=progress,
                    is_cancelled=lambda: self.cancel_requested,
                )
            finally:
                QApplication.restoreOverrideCursor()
                if area_node is not None and area_was_visible:
                    area_node.setItemVisibilityChecked(True)

            if not self.keep_pages.isChecked():
                for file_name in os.listdir(pages_folder):
                    if file_name.startswith("page_") and file_name.endswith(".pdf"):
                        os.remove(os.path.join(pages_folder, file_name))
                if not os.listdir(pages_folder):
                    os.rmdir(pages_folder)

            self.progress.setValue(100)
            self.log("Done: {} page(s) in {}".format(exported, merged_path))
            QMessageBox.information(
                self, "Topo50 Atlas Builder", "Exported {} page(s) to:\n{}".format(exported, merged_path)
            )
        except exporter.Cancelled:
            self.log("Cancelled. Pages already exported are in the 'pages' folder.")
        except (builder.GridError, exporter.ExportError) as error:
            self._fail(error)
        except Exception as error:
            self.log(traceback.format_exc())
            self._fail(error)
        finally:
            self._set_running(False)
