# HueForge Bambu Bridge

Open-source conversion of a saved HueForge project and its exported STL into a
Bambu Studio project with automatic AMS filament changes.

**Status: working macOS command-line prototype. Native HueForge plugin integration
is pending access to the HueForge SDK.** This is an independent project, not an
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

## Usage

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

The intended workflow is a HueForge menu action that exports the open project
and opens the resulting 3MF in Bambu Studio. No native plugin binary or guessed
SDK bindings are included. See the [integration plan](docs/native-plugin.md)
and the [SDK request draft](docs/sdk-request.md).

## License

Our code is available under the [MIT License](LICENSE). HueForge and Bambu Studio
are separate products with their own licenses. SDK redistribution/publication
terms must be established before adding the native adapter.
