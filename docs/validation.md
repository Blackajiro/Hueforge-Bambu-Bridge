# Validation and known limits

Verified locally on 2026-10-14 with HueForge **0.9.4.4** and Bambu Studio
**02.08.02.61**, using an exported 50 × 150 × 1.52 mm winter bookmark.

| Setting | Observed result |
|---|---|
| Printer/nozzle | P2S / 0.4 mm |
| First / regular layer | 0.16 / 0.08 mm |
| Infill | 100%, rectilinear (`zig-zag` in Bambu config) |
| Model layers | 18 |
| Material ranges | 1–3, 4–7, 8–11, 12–18 |
| Tool changes | T1 at Z 0.40, T2 at Z 0.72, T3 at Z 1.04 mm |
| Materials | Matte Charcoal → Basic Dark Gray → Matte Mandarin Orange → Matte Ivory White |
| Estimated time / total material | 4008 seconds / 11.13 g |

The motor's sliced `layer_filament_lists` and actual G-code tool changes were
checked, in addition to the unsliced project metadata. The test artifact is not
bundled: use your own saved project with the opt-in integration test.

The installed G-code parser logs `Invalid T command (T65535)` at the end. This
command is present in Bambu's official P2S end G-code for unloading to AMS; the
converter does not introduce or rewrite it. Slicing produced all expected layers
and material ranges despite the diagnostic.

## Limits

- In-process native plugin: awaiting SDK; the separate AppKit companion needs no SDK.
- The AppKit companion was built and exercised: project selection, a real HueForge
  save, generated 3MF validation, disabling automatic opening and disconnect.
  Studio window inspection still times out, so automatic opening was requested
  through NSWorkspace but acceptance of the new document was not visually confirmed.
- Nine unit tests cover conversion, both save orders, incomplete saves, debounce,
  duplicate prevention and ambiguous STL names. A real watcher subprocess was
  additionally tested with the installed Bambu CLI: HFP-only changes produced no
  output; updating the STL then produced exactly one 3MF, with no duplicate export.
  The CLI slicer was verified.
- No physical print, adhesion, TD accuracy, purge tuning or optical color match
  has been verified.
- HFP structure and Bambu preset/XML behavior are version-dependent.
- The STL dimensions check cannot distinguish different meshes with the same
  bounds. Always use the STL regenerated alongside the project being converted.
- Binary STL parsing here checks dimensions and finite vertices, not manifoldness,
  self-intersections or printability.
- Profile names, printer, build plate and PLA families are intentionally restricted
  for the first prototype; other machines and platforms have not been tested.

## References

- [Official Bambu 3MF reader/writer](https://github.com/bambulab/BambuStudio/blob/master/src/libslic3r/Format/bbs_3mf.cpp)
- [Official tool change types](https://github.com/bambulab/BambuStudio/blob/master/src/libslic3r/CustomGCode.hpp)
- [Official CLI implementation](https://github.com/bambulab/BambuStudio/blob/master/src/BambuStudio.cpp)

Vendor source was consulted to understand file formats. The repository uses
its own implementation and does not bundle vendor source or application assets.

## Version 0.3 settings and UI verification

The app now uses English throughout, separates connection/save/export/error
states, keeps complete error details in tooltips, and offers both
Open in Bambu Studio and Show in Finder. Automatic opening is remembered.
Selection uses a nonblocking native sheet; the window can resize.

Ten unit tests pass, including explicit modified-preset key metadata. A new live
HueForge save produced a 3MF with the documented overrides. The integration test
checks every process override in the sliced project as well as the 18 layer Z
positions and three AMS transitions. Updated project copies are regenerated;
previous timestamped exports remain historical files and are not silently edited.

See [print-settings.md](print-settings.md) for the research, sources and distinction
between guaranteed export settings and material-dependent physical calibration.

## Version 0.4 printer selection

Printer/nozzle/plate/material settings now come from an explicitly imported Bambu
Studio project 3MF. The UI validates it, shows a printer summary, saves a local copy
and restores it on launch. The converter has no hardcoded P2S preset lookup.

The same bookmark was converted and sliced using both P2S and A1 0.4 mm templates
from the installed vendor presets. Both retain 18 layers and the three expected
AMS changes. This is software validation, not a physical test of either printer.
Multi-extruder templates are rejected; other models have not yet been tested.
Twelve unit tests cover template validation, filament/nozzle compatibility,
custom machine settings, plate, purge preservation and the existing workflow.
Historical notes above describe earlier versions; current behavior is documented
in the README and print-settings guide.

The template was also imported in the running macOS UI and restored after a quit/relaunch.
A real watcher subprocess exported a saved file pair with the selected A1 template.

## Version 0.5 direct printer selection

The standard UI now lists installed printer models, available nozzle diameters
and supported plate types. It resolves compatible process and Matte/Basic PLA
presets automatically. A 3MF template is no longer required; custom-template CLI
support remains optional. The installed version exposed 40 single-nozzle presets.

Thirteen unit tests pass, including a generated preset tree with inheritance,
plate exclusions and automatic filament-family matching. Direct A1 / Smooth PEI
and P2S / Textured PEI selections were converted and sliced with the expected
18 layers and three AMS changes. No physical print was performed.

The three native selection menus were exercised; selections survived app restart.
A real watcher subprocess exported with direct P2S/nozzle/plate arguments and no template.
