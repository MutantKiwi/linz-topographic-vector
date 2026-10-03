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
