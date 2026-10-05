"""Small helpers so the same code runs on QGIS 3 (Qt5) and QGIS 4 (Qt6)."""


def enum_value(owner, scope, name):
    """Return owner.scope.name (Qt6 style) or owner.name (Qt5 style)."""
    scoped = getattr(owner, scope, None)
    if scoped is not None and hasattr(scoped, name):
        return getattr(scoped, name)
    return getattr(owner, name)
