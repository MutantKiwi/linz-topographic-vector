# Label word spacing (missing space in curved names)

Fixes curved place names in `nztopo50_carto_text` that render with no gap
between words, such as "WaitahaCove" and "ElsdonPoint", even though the text
attribute contains a space.

Before

<img width="733" height="541" alt="image" src="https://github.com/user-attachments/assets/c533d1c2-46d6-4c54-9e6a-e2d690266ccb" />

After

<img width="470" height="331" alt="image" src="https://github.com/user-attachments/assets/a4259b7e-6b5c-4122-926a-697feab66079" />


## Summary

Curved labels in this layer are fitted to the exact length of their label line.
For some labels the only thing QGIS may adjust to make the text fit is the gap
between words. When the rendered text is slightly wider than the line, that gap
is squeezed to nothing.

There are two fixes, applied in this order:

1. **Use the right font.** Point the font override at the `font` column
   instead of `text_font`.
2. **Spread the squeeze across the letters, for curved labels only.** If the
   gap is still missing, change the curved label mode so the adjustment is
   shared by every character instead of taken from the word gap. This is
   limited to curved text (`text_bend = 7`) so stacked labels are not affected.

## Why it happens

- **Fit-to-line mode.** The layer's curved label mode is data-defined from the
  `charplace` column. Labels with `StretchWordSpacingToFit` are made to span
  the label line exactly by changing only the space between words. Labels with
  `StretchCharacterSpacingToFit` change the spacing between all characters.
- **The line is only as long as the original text.** Each curved label line is
  built from one short segment per character of the original production font.
  For "Waitaha Cove" the line is 623 m long (12.5 mm at 1:50,000), and the
  space was given just 29 m (about 0.6 mm).
- **Extra width comes out of the space.** If the rendered text is wider than
  the line, the word gap is the only thing allowed to shrink, so it closes.
- **Straight labels hide it.** Names such as "Arthurs Nose" use
  `StretchCharacterSpacingToFit`, so the same squeeze is spread over every
  letter and is not noticeable.

Two things make the rendered text wider than the line:

| Cause | Detail |
|---|---|
| Wrong font | The font override reads `text_font`, which holds the original LINZ production font name (for example `ATTriumMou-Italic`). If that font is not installed, QGIS substitutes one with different letter widths. |
| Map scale | The line is in ground metres but the text size is in points. They only match at exactly 1:50,000. Zoomed out further, the line is shorter relative to the text and the gap closes. |

## Fix 1: use the font shipped with the project

The `font` column holds `Nimbus Sans LINZ`, which is supplied in the project
folder as `.otf` files. The `style` column holds the matching style (Regular,
Italic, Narrow).

1. Open `nztopo50_carto_text` > Properties > Labels > Text.
2. Click the data-defined override button beside **Font** and choose Edit.
3. Replace `"text_font"` with `"font"`.
4. Check the preview reads `'Nimbus Sans LINZ'`, then click OK and Apply.

Leave the Style override on the `style` column.

Then set the map scale to exactly 1:50,000 and check the labels again.

## Fix 2: spread the adjustment across all characters

Only needed if the word gap is still missing at 1:50,000 with the correct font.

This changes the curved label mode override from the field `charplace` to an
expression that swaps word-spacing fitting for character-spacing fitting, on
curved labels only:

```
if("charplace" = 'StretchWordSpacingToFit' AND "text_bend" = 7, 'StretchCharacterSpacingToFit', "charplace")
```

The text still fits its line, but the word gap stays visible.

### Why it is limited to `text_bend = 7`

Applying the swap to every label spreads out the letters of stacked labels.
In "Houghton / Bay" each line of text has its own line segment, and a
single-word line such as "Bay" has no word gap to adjust. With word-spacing
fitting it is left alone; with character-spacing fitting its letters are
stretched to fill the segment ("B a y").

The `text_bend` column separates the cases:

| `text_bend` | Kind of label | Example | Swap applied |
|---|---|---|---|
| 0 | Straight | Arthurs Nose, Te Raekaihau | No |
| 7 | Curved | Waitaha Cove, Elsdon Point | Yes |
| 9 | Stacked (multi-line) | Houghton Bay, Taputeranga Island | No |

The meaning of these values is inferred from the data, not from LINZ
documentation. Among labels marked `StretchWordSpacingToFit`, 58,485 have
`text_bend = 7` and none of them contain a line break, while almost all with
`text_bend = 9` do.

### In the label settings

On the Placement tab, with the mode set to Curved, find the curved label mode
option and edit its data-defined override to use the expression above. The
position of this option in the QGIS 4 dialog has not been confirmed.

### From the Python console

Select `nztopo50_carto_text` in the Layers panel, open Plugins > Python
Console, and paste:

```python
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
```

To undo it, run the same code with `QgsProperty.fromField('charplace')` in
place of the expression.

This code has not been tested against QGIS 4. It looks the property up by the
name used in the project file (`CurvedLabelMode`).

## Alternative: shrink the text slightly

If you would rather keep word-spacing fitting, make the text a little smaller
so it fits with room to spare. Change the Size override from the field `size`
to:

```
"size" * 0.95
```

## Columns involved

| Column | Used for | Example |
|---|---|---|
| `text_string` | The label text | `Waitaha Cove` |
| `charplace` | Curved label mode | `StretchWordSpacingToFit` |
| `text_bend` | Kind of label: 0 straight, 7 curved, 9 stacked | `7` |
| `font` | Font family to use | `Nimbus Sans LINZ` |
| `style` | Font style | `Italic` |
| `text_font` | Original production font (do not use for rendering) | `ATTriumMou-Italic` |
| `size` | Text size in points | `6.0` |

## Notes

- **Requires a QGIS version with fit-to-line curved label modes** (QGIS 4.x).
- **Check at 1:50,000.** Label fitting only looks right at the scale the lines
  were built for, on screen and in print layouts.
- **Word spacing override.** The project's word spacing override points at a
  field named `t_w_s_d`, which is not in the parquet (the column is
  `text_word_spacing_distance`). It is not the cause of this problem; the
  values are zero for these labels.
- **Save the style.** After applying the fixes, save the layer style (Style >
  Save Style) so they are kept when the project or data is refreshed.
