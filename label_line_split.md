# Label line split (curved text placement)

A QGIS expression for the label **Geometry Generator** that removes the sharp
"joining" segment from a label line, so curved text is placed along two clean
lines instead of being forced around a hairpin.

Code created by Alan Cheung

## Summary

The expression looks at every interior segment of a line and measures how
sharply the line turns into it and out of it. If the sharpest segment has a
combined turn of 100° or more, that segment is treated as a join between two
separate runs of the line and is cut out. The label is then placed on the two
remaining pieces. If no segment is that sharp, the line is used unchanged.

## Why we use it

Curved label placement in QGIS follows the line geometry it is given. Some
label lines are really two runs joined by a short connecting segment, which
makes the line double back on itself. QGIS then either bends the text around
the join, squeezes characters into the corner, or fails to place the label at
all.

Removing the joining segment at render time fixes the placement without
editing the data. The source layer stays as delivered, and the fix is applied
again automatically whenever the data is refreshed.

## The expression

```
with_variable('segs', geometries_to_array(segments_to_lines($geometry)),
with_variable('scores',
  array_foreach(
    generate_series(1, array_length(@segs) - 2),
    with_variable('i', @element,
      degrees(acos(cos(
        azimuth(start_point(array_get(@segs, @i - 1)), end_point(array_get(@segs, @i - 1)))
        - azimuth(start_point(array_get(@segs, @i)), end_point(array_get(@segs, @i)))
      )))
      +
      degrees(acos(cos(
        azimuth(start_point(array_get(@segs, @i)), end_point(array_get(@segs, @i)))
        - azimuth(start_point(array_get(@segs, @i + 1)), end_point(array_get(@segs, @i + 1)))
      )))
    )
  ),
with_variable('join_i', array_find(@scores, array_max(@scores)) + 1,
with_variable('join_seg', array_get(@segs, @join_i),
with_variable('d1', line_locate_point($geometry, start_point(@join_seg)),
with_variable('d2', line_locate_point($geometry, end_point(@join_seg)),
  CASE
    WHEN array_max(@scores) >= 100 THEN
      collect_geometries(
        line_substring($geometry, 0, @d1),
        line_substring($geometry, @d2, length($geometry))
      )
    ELSE $geometry
  END
))))))
```

## How to apply it

1. Open the layer's **Properties > Labels**, and go to the **Placement** tab.
2. Set the placement mode to **Curved**.
3. Tick **Geometry Generator**, paste the expression, and set the geometry
   type to **LineString / MultiLineString**.
4. Click Apply.

Requires QGIS 3.28 or later (for `geometries_to_array`).

## How it works

| Variable | What it holds |
|---|---|
| `segs` | The line broken into its individual two-point segments, as an array. |
| `scores` | One score per interior segment: the turn angle into the segment plus the turn angle out of it, in degrees (0 to 360). |
| `join_i` | The position in `segs` of the highest-scoring segment. |
| `join_seg` | That segment's geometry. |
| `d1`, `d2` | The distance along the original line to the start and end of that segment. |

Step by step:

1. **Break the line into segments.** `segments_to_lines` splits the line at
   every vertex.
2. **Score each interior segment.** For segment `i`, the turn angle is the
   difference in bearing between it and its neighbour. `acos(cos(...))` folds
   the difference into the range 0° to 180°, so a left turn and a right turn
   score the same. The turn in and the turn out are added together. The first
   and last segments are skipped because they have only one neighbour.
3. **Find the sharpest segment.** The highest score marks the candidate join.
   If two segments tie, the first one along the line is used.
4. **Decide whether to cut.** A score of 100° or more means the line turns
   sharply on both sides of the segment, which is the signature of a short
   connector between two runs. A gentle curve scores far lower.
5. **Cut it out.** The result is a two-part line: from the start to the
   beginning of the join, and from the end of the join to the end of the line.
   Otherwise the original geometry is returned.

## Tuning

The only setting is the threshold in `WHEN array_max(@scores) >= 100`.

- **Lower it** (for example 80) if some joins are not being removed.
- **Raise it** (for example 140) if lines with ordinary sharp bends are being
  split when they should not be.

## Limits

- **One join per line.** Only the single sharpest segment is removed. A line
  with two joins keeps the second one.
- **Short lines.** A line needs at least three segments to have an interior
  segment. Lines with one or two segments are returned unchanged.
- **Single-part lines only.** `line_substring` and `line_locate_point` expect a
  single linestring. A multi-part feature returns no geometry and loses its
  label.
- **Lines that cross or retrace themselves.** `line_locate_point` finds the
  nearest position on the line to a point. If the line passes through the
  join's endpoint more than once, the cut can land in the wrong place.
- **Which piece gets the label.** QGIS chooses where on the two-part result to
  place the text. Use the label placement options (for example "Label every
  part of multi-part features" under Rendering) if both pieces need text.

## Troubleshooting

**Syntax errors or "Function ... is not known" after pasting.** The usual cause
is non-breaking spaces picked up when copying the expression from a chat window
or web page. QGIS reads them as part of a name instead of as whitespace, giving
errors such as:

```
syntax error, unexpected STRING, expecting COMMA or ')'
Function     geometries_to_array is not known
```

Paste the expression into a plain text editor first and replace the
non-breaking spaces (`\xA0` in regex mode) with normal spaces, or delete all the
leading indentation. The expression does not need indentation to work.
