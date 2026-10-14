# HueForge settings for Bambu Studio

Reviewed 2026-10-14 for ordinary, front-facing filament paintings on a **imported single-nozzle Bambu printer templates with AMS**, using Bambu Studio 02.08.02.61. This is an evidence-based
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
| Purge multiplier | Imported, or 1 on color mismatch | Preserves calibrated matching-color templates. |
| Purge matrix | Imported for matching colors/order; otherwise 650 mm³ off-diagonal | Fallback is conservative, **not color-calibrated**. |
| Build plate | Imported from template | Select the correct plate before saving your Studio template. |

The bridge reads the full settings from a project 3MF saved in Bambu Studio.
It preserves the selected printer/nozzle, plate, machine G-code, material profiles,
temperatures, cooling, flow, speeds, line widths and shells. Configure exactly the
same number of PLA filaments as HueForge uses, with Bambu Matte/Basic profiles in
bottom-to-top order. Geometry and old color changes in the template are replaced;
we do not merge its model with the HueForge artwork.

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
then validate dark-to-light transitions with your spools. Your imported matrix is preserved when template colors match the HueForge stack.
If colors differ, the disclosed 650 mm³ fallback may waste material; use Studio
to recalculate and tune before printing.

Layer heights are checked against the imported nozzle limits (or conservative
nozzle-relative limits when absent), not a hardcoded P2S range. The tested bookmark
uses 0.08/0.16 mm. A different nozzle can require retuning the project in HueForge.
Never scale Z or enable adaptive layers after export without rechecking all swaps.

## Primary sources and how they were used

- [HueForge troubleshooting FAQ](https://shop.thehueforge.com/pages/troubleshooting-faq):
  match both layer heights; uniform scaling changes Z; spikes/thin regions may be lost.
- [HueForge developer's worked example](https://devlog.thehueforge.com/p/designing-a-chessboard-in-hueforge):
  demonstrates 0.08 mm layers, 0.16 mm base and 100% infill. This is an example,
  not proof that these heights fit every project.
- [Bambu Studio configuration definitions](https://github.com/bambulab/BambuStudio/blob/master/src/libslic3r/PrintConfig.cpp):
  prime tower pressure stabilization, purge multiplier, flush into model and
  precise Z behavior. The imported template supplies the actual machine/material values.
- [Bambu Studio preset import](https://github.com/bambulab/BambuStudio/blob/master/src/libslic3r/PresetBundle.cpp):
  process/filament/printer modified-key metadata used when opening external projects.
- [Bambu Studio 3MF reader/writer](https://github.com/bambulab/BambuStudio/blob/master/src/libslic3r/Format/bbs_3mf.cpp):
  per-layer ToolChange metadata; verified against actual sliced output.

Ironing-off, keeping purge out of the artwork, uniform layers and retaining
material presets are our engineering choices based on the relief/blending model
and Bambu's documented option behavior. They are not presented as a vendor-issued
HueForge profile. Bambu wiki pages were unavailable to the research tool; the
vendor's published source and locally installed presets were checked instead.
