import os

from qgis.PyQt.QtGui import QIcon

try:  # Qt6
    from qgis.PyQt.QtGui import QAction
except ImportError:  # Qt5
    from qgis.PyQt.QtWidgets import QAction

MENU = "Topo50 Atlas"


class Topo50AtlasPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        icon = QIcon(os.path.join(os.path.dirname(__file__), "icon.svg"))
        self.action = QAction(icon, "Topo50 Atlas Builder", self.iface.mainWindow())
        self.action.setToolTip("Build a Topo50 A3 atlas for an area and export it as one PDF")
        self.action.triggered.connect(self.show_dialog)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(MENU, self.action)

    def unload(self):
        if self.action is not None:
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginMenu(MENU, self.action)
            self.action = None
        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None

    def show_dialog(self):
        from .dialog import AtlasDialog

        if self.dialog is None:
            self.dialog = AtlasDialog(self.iface, self.iface.mainWindow())
        self.dialog.refresh_from_project()
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
