def classFactory(iface):
    from .plugin import Topo50AtlasPlugin

    return Topo50AtlasPlugin(iface)
