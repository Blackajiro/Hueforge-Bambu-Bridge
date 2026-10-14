# HueForge settings for Bambu Studio

Reviewed 2026-10-14 for ordinary, front-facing filament paintings on a **P2S with
0.4 mm nozzle and AMS**, using Bambu Studio 02.08.02.61. This is an evidence-based
baseline, not a universal “best quality” profile or a physical calibration.

## Applied to every export

| Setting | Applied value | Why |
|---|---|---|
| Regular / initial layer heights | Exact HFP values | Keeps geometry and color changes aligned with HueForge. Our bookmark uses 0.08 / 0.16 mm. |
| Infill | 100%, Rectilinear (`zig-zag`) | Solid layers support predictable optical blending. |
| Top surface | Monotonic line | Keeps a consistent surface direction; inherited from Bambu High Quality. |
| Ironing | Off | Conservative choice for a textured relief: avoids reworking thin exposed color layers. |
| Infill combination | Off | Keeps infill on the same uniform Z grid as the surface. |
| Precise Z height | Off | Prevents adjustment of the last layer heights. |
| Sequence | By layer; spiral vase off | Changes apply at uniform layer boundaries. |
| Supports | Off | Flat front-facing relief is printed base-down. |
| Flush into infill / objects | Off | Purged colors must not enter translucent artwork. |
| Prime tower | On | Stabilizes extrusion after filament changes; not a replacement for purging. |
| Purge multiplier | 1 | Makes the configured purge volumes explicit. |
| Purge matrix | 650 mm³ off-diagonal; 0 diagonal | Conservative prototype fallback, **not color-calibrated**. |
| Build plate | Textured PEI | Matches the initial supported target. Select your actual plate before printing. |

The bridge starts from installed **0.08mm High Quality @BBL P2S**, and matching
Bambu PLA Matte/Basic filament profiles. It keeps their temperatures, cooling,
volumetric limits, flow, speeds, line widths and shells. The installed profile has
2 walls, 9 top layers and 7 bottom layers. These are inherited defaults, not a
requirement to cover the entire relief with dozens of extra top layers.

Project-specific overrides are also declared in `different_settings_to_system`.
This matters: the Studio GUI can otherwise restore the system preset instead of
keeping values that the CLI correctly reads. Unit tests check this metadata;
integration tests check the serialized settings and actual sliced Z/tool changes.

## Decisions that need a physical test

There is no substantiated universal nozzle temperature or speed for all HueForge
PLA prints. We do **not** force 190°C, slow every move to an arbitrary speed, change
flow ratios, reduce line widths or disable the prime tower based on community
anecdotes. Tune these on the actual spool and printer. Calibrating TD and flow
matters more than copying another person's profile.

For purge, use Studio's **Flushing volumes → Re-calculate** for your actual colors,
then validate dark-to-light transitions with your spools. The fixed 650 mm³ value
is deliberately disclosed and may waste material. A calibrated matrix imported
from the user's own project would be a future improvement; this version does not
claim to preserve one.

The converter's 0.08–0.28 mm validation range reflects supported nozzle layer
heights, not a recommendation to paint at 0.28 mm. It preserves the HFP values;
0.08/0.16 mm is the tested bookmark configuration. Never scale Z, enable adaptive
layers or change first-layer height after export without rechecking all swaps.

## Primary sources and how they were used

- [HueForge troubleshooting FAQ](https://shop.thehueforge.com/pages/troubleshooting-faq):
  match both layer heights; uniform scaling changes Z; spikes/thin regions may be lost.
- [HueForge developer's worked example](https://devlog.thehueforge.com/p/designing-a-chessboard-in-hueforge):
  demonstrates 0.08 mm layers, 0.16 mm base and 100% infill. This is an example,
  not proof that these heights fit every project.
- [Bambu Studio configuration definitions](https://github.com/bambulab/BambuStudio/blob/master/src/libslic3r/PrintConfig.cpp):
  prime tower pressure stabilization, purge multiplier, flush into model and
  precise Z behavior. Installed P2S presets supply the actual machine/material values.
- [Bambu Studio preset import](https://github.com/bambulab/BambuStudio/blob/master/src/libslic3r/PresetBundle.cpp):
  process/filament/printer modified-key metadata used when opening external projects.
- [Bambu Studio 3MF reader/writer](https://github.com/bambulab/BambuStudio/blob/master/src/libslic3r/Format/bbs_3mf.cpp):
  per-layer ToolChange metadata; verified against actual sliced output.

Ironing-off, keeping purge out of the artwork, uniform layers and retaining
material presets are our engineering choices based on the relief/blending model
and Bambu's documented option behavior. They are not presented as a vendor-issued
HueForge profile. Bambu wiki pages were unavailable to the research tool; the
vendor's published source and locally installed presets were checked instead.
