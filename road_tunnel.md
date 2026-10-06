# Road tunnel

Marks the tunnel sections of the Topo50 roads and draws them with the Topo50
tunnel symbol in QGIS.

## Summary

`road_line.parquet` has no tunnel information. A road feature runs straight
through a tunnel with nothing to say where the tunnel starts or stops.

`road_tunnel.py` overlays the vehicle tunnels from `tunnel_line.parquet` on the
roads, splits each road at the tunnel portals, and marks the sections inside a
tunnel with `tunnel = true` and `type = 'tunnel'`. The result is
`road_line_tunnel.parquet`, which replaces `road_line.parquet` in the project.

The tunnel sections are then drawn as two dashed lines with a portal arc at
each end.

This is the road version of [rail-line-tunnel.md](rail-line-tunnel.md).

## Why

On the printed map a road in a tunnel changes from the solid orange road to a
dashed outline. A symbol can only change where a feature changes, so the road
has to be cut at the portals and the tunnel piece given its own attribute.

Drawing `tunnel_line` on top of the roads does not work: the solid road would
still show underneath the dashes.

## Why not every vehicle tunnel is used

Most `type = 'vehicle'` tunnels in `tunnel_line` are not road tunnels. They are
short livestock underpasses that go *under* a road, crossing it. Those do not
put the road in a tunnel.

The script therefore only counts a tunnel that runs **along** a road, not
across it.

| Vehicle tunnels in `tunnel_line` | 932 |
|---|---|
| Run along a road, so used | 61 |
| Of those, ordinary road tunnels (Homer, Mt Victoria and so on) | 56 |
| Of those, livestock tunnels that follow a road | 5 |
| Other non-livestock tunnels, not on a road | 46 (44 of them are on tracks) |

## What you need

Python 3.10 or later with `geopandas`, `shapely` 2.x, `numpy`, `pandas` and
`pyarrow`.

On Windows with QGIS installed, open the **OSGeo4W Shell** and run:

```
python -m pip install geopandas pyarrow
```

## Inputs

| File | Used for |
|---|---|
| `road_line.parquet` | The roads to split. |
| `tunnel_line.parquet` | Tunnel centrelines. Only features with `type = 'vehicle'` are used. |

## Step 1: create road_line_tunnel.parquet

```
cd /d F:\Project\output\project
python road_tunnel.py --road road_line.parquet --tunnel tunnel_line.parquet --output road_line_tunnel.parquet
```

`road_line.parquet` is not modified. The output is about 99 MB.

## Process

Work is done in NZTM2000 (EPSG:2193) so distances are in metres. The output is
written in the same coordinate system as the input roads.

1. **Sample the tunnel.** Each vehicle tunnel is turned into points 2 m apart.
2. **Give each point to one road.** A point belongs to its single nearest road
   within 10 m. A road that only runs parallel nearby gets no points.
3. **Test along or across.** For each road, the points give a start and end
   distance along it. The tunnel counts only if that stretch is at least 5 m
   long and at least 0.7 times the length of tunnel matched to the road. A
   tunnel crossing a road covers only a metre or two of it, so it fails.
4. **Tidy the portals.** A portal within 3 m of the end of a road feature is
   moved to the end, so no tiny leftover piece is made.
5. **Split the road.** The road is cut at each portal. Pieces inside a tunnel
   get `tunnel = true` and `type = 'tunnel'`. Every other attribute is copied
   from the original road.

## Output

`road_line_tunnel.parquet`, with the same columns as `road_line.parquet` plus
`tunnel`.

| | road_line | road_line_tunnel |
|---|---|---|
| Features | 153,518 | 153,621 |
| Tunnel sections | 0 | 63 (13.6 km) |

| Column | Tunnel section | Everything else |
|---|---|---|
| `tunnel` | `true` | `false` |
| `type` | `tunnel` | `road` (unchanged) |
| `lane_count`, `highway_number`, `surface`, `name` ... | Copied from the road | Unchanged |

`road_tunnel_sections.parquet` holds just the 63 tunnel sections, for checking
them without loading the full road layer.

## Step 2: filter the road rules

Because the tunnel pieces are still roads with a lane count and highway
number, every existing road rule would draw them too. Add a "not a tunnel"
test to each rule.

| Where | Write |
|---|---|
| Rule filter (Symbology) | `"lane_count" > 1 AND "highway_number" IS NOT NULL AND NOT "tunnel"` |
| Query Builder (layer Source filter) | `"tunnel" = 0` |

The Query Builder does not accept `true` or `false`. Use `1` and `0` there.

The tunnel rule itself is simply `"tunnel"`.

## Step 3: the tunnel symbol

From the LINZ Topo50 specification: the road ends at a portal arc and
continues as two dashed lines, one along each edge of the road.

| Part | Specification |
|---|---|
| Dashes | 1 mm dash, 0.5 mm gap, black |
| Portal arc | Radius 2.5 mm, 0.15 mm line, as wide as the road |
| Width | Follows the width of the road it joins (its lane count) |

See `tunnel_symbol\tunnel_symbol_preview.png` for the result.

### Import the ready-made style

1. **Settings > Style Manager > Import/Export > Import Item(s)**.
2. Choose `tunnel_symbol\nztopo50_tunnel_symbols.xml` and import
   **Topo50 tunnel - road**. (The file also holds the rail tunnel symbol.)
3. On the road layer, add a rule with the filter `"tunnel"` and pick that
   symbol.
4. Move the rule to the top of the list so the arc draws over the end of the
   orange road.

The portal arc is stored inside the style, so there is no SVG path to break.

### Or build it by hand

Four symbol layers:

| Layer | Settings |
|---|---|
| Simple Line | Black, 0.15 mm, custom dash 1 / 0.5 mm, flat cap, **Offset** +0.925 mm |
| Simple Line | The same, **Offset** -0.925 mm |
| Marker Line | Placement **first vertex only**. SVG marker `nztopo50_tunnel_portal_road.svg`, size 2.2 mm, stroke 0.15 mm, rotation 0 |
| Marker Line | Placement **last vertex only**. Same marker, rotation 180 |

Leave **Rotate marker to follow line direction** ticked on both marker lines.

### Matching the road width

The style is set up for a road drawn 2 mm wide, which is a placeholder. For
each road width:

| Setting | Value |
|---|---|
| Offset of the two dashed lines | Half the road casing width, minus 0.075 mm |
| Size of the portal arc | 1.1 times the road casing width |

If road classes are drawn at different widths, copy the tunnel rule for each
one, for example `"tunnel" AND "lane_count" > 1` and
`"tunnel" AND "lane_count" = 1`, each with its own offsets.

## Files

| File | Purpose |
|---|---|
| `road_tunnel.py` | The script |
| `road_line_tunnel.parquet` | Output: all roads, split at tunnel portals |
| `road_tunnel_sections.parquet` | The 63 tunnel sections only |
| `tunnel_symbol\nztopo50_tunnel_symbols.xml` | QGIS style with the road and rail tunnel symbols |
| `tunnel_symbol\nztopo50_tunnel_portal_road.svg` | Portal arc for roads |
| `tunnel_symbol\nztopo50_tunnel_portal_rail.svg` | Portal arc for rail |
| `tunnel_symbol\tunnel_symbol_preview.png` | Test render at 1:50,000 |

## Settings

Constants at the top of `road_tunnel.py`:

| Setting | Default | Effect |
|---|---|---|
| `TOL` | 10.0 | A tunnel point further than this from a road is not on it (metres) |
| `STEP` | 2.0 | Spacing of the sample points along a tunnel (metres) |
| `ALONG` | 0.7 | Share of the tunnel's length that must lie along the road |
| `SNAP` | 3.0 | A portal closer than this to a road end is moved to the end (metres) |
| `MIN_LEN` | 5.0 | Shorter tunnel sections are ignored (metres) |

## Limits

- **Tunnels on tracks are not handled.** 44 vehicle tunnels lie on tracks, not
  roads. `track_line` would need the same treatment.
- **Two non-livestock tunnels match nothing.** They are neither on a road nor
  on a track and are left out.
- **Arc direction.** The arcs bulge into the tunnel. If they should face the
  other way, swap the 0 and 180 rotations.
- **Sharp bends.** The two offset dashed lines can fall slightly out of step
  with each other around a bend inside a tunnel.
- **Tested in QGIS 3.34 only.** The symbol has not been checked in QGIS 4.2,
  and the script's output has not been checked against the printed map.

