# HueForge Bambu Bridge

Open-source conversion of a saved HueForge project and its exported STL into a
Bambu Studio project with automatic AMS filament changes.

**Status: working macOS companion app and command-line converter, without a HueForge
SDK dependency.** This is an independent project, not an
official HueForge or Bambu Lab product.

## Supported today

- macOS with Bambu Studio installed at `/Applications/BambuStudio.app`.
- Bambu Lab P2S, 0.4 mm nozzle, AMS, Textured PEI Plate.
- One flat Color Core with 1–4 enabled BambuLab Matte/Basic PLA entries.
- JSON HFP with `core_graph_color` and a matching binary STL exported by HueForge.
- Python 3.10 or newer; standard library only.

The exporter uses Bambu Studio's own CLI to build the mesh/project and resolves
its installed preset inheritance and G-code includes. No printer presets, vendor
binaries, artwork, or personal filament libraries are bundled here.

## macOS app — no SDK needed

Build locally with the installed Swift compiler (Xcode/Command Line Tools) and Python 3.10+:

```sh
python3 macos/build.py
```

Open `dist/HueForge Bambu Bridge.app`, click **Scegli progetto HueForge…** and
select the saved HFP. Wait for **Collegato**, then save in HueForge, confirming
its save dialog. Keep the bridge open. Each completed save creates a new 3MF in `Bambu Bridge Exports/`
beside the project and opens it in Bambu Studio. Automatic opening can be disabled.

The bridge deliberately waits for the **next save after connecting**. Both HFP
and the matching `_Front_*.stl` must change and remain stable for three seconds.
It snapshots both files and checks for changes during conversion. Saving again
during conversion discards the outdated result and processes the newer save.
No existing 3MF is overwritten; each export is a separate revision. There must
be exactly one matching Front STL in the selected project's folder. If you use
Save As under a different name/folder, reconnect the new HFP.

**Scollega** stops watching. Closing the app stops the bridge. No login item,
background service, Accessibility permission or HueForge binary modification is
required. The local build records the Python interpreter used to build it; this
is not yet a standalone signed/notarized release for other Macs. Rebuild on the
target Mac with Python installed.

## Command-line usage

Save the project in HueForge to regenerate its STL, then run from this directory:

```sh
python3 hueforge_bambu.py "/path/project.hfp" "/path/project_Front.stl" "/path/output.3mf"
```

Open the output **as a project** in Bambu Studio and slice it. Before printing,
check the selected build plate and map the four project filaments to the actual
AMS spools. Project filament numbers are not physical AMS slot assignments.

The exporter carries over the first/regular layer heights, uses 100% rectilinear
infill, disables supports and flushing into the model, and enables the prime
tower. It preserves the installed P2S machine G-code. It refuses to overwrite
an existing output. It does not start a print or modify the source project.

Purge is currently a conservative **650 mm³ between different project filaments**,
with multiplier 1. Tune it after a physical test, particularly before white.
Do not scale Z or enable adaptive layer heights after conversion.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

Unit tests need neither HueForge nor Bambu Studio. An opt-in integration test
converts and slices your own project using the installed Bambu Studio:

```sh
python3 tests/verify_integration.py "/path/project.hfp" "/path/project_Front.stl"
```

See [validation](docs/validation.md) for the tested app versions, actual slicing
results, and limits. Automated tests do not establish physical color fidelity.

## Native plugin

The companion app provides a save-to-export workflow without the SDK. It runs
alongside HueForge rather than adding a menu inside it. A future native menu
adapter is optional; see the [integration notes](docs/native-plugin.md).

## License

Our code is available under the [MIT License](LICENSE). HueForge and Bambu Studio
are separate products with their own licenses. SDK redistribution/publication
terms must be established before adding the native adapter.
