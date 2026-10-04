layer = iface.activeLayer()
settings = layer.labeling().settings()
props = settings.dataDefinedProperties()

key = next(k for k, d in QgsPalLayerSettings.propertyDefinitions().items()
           if d.name() == 'CurvedLabelMode')

props.setProperty(key, QgsProperty.fromExpression(
    "if(\"charplace\" = 'StretchWordSpacingToFit' AND \"text_bend\" = 7, "
    "'StretchCharacterSpacingToFit', \"charplace\")"))

settings.setDataDefinedProperties(props)
layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
layer.triggerRepaint()
