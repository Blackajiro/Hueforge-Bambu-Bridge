# HueForge Bambu Bridge

Save in HueForge. Get a Bambu Studio project with your colors and AMS changes ready to slice.

A small, open-source macOS companion app. No HueForge SDK or plugin installation needed.

## Get started

Requires **macOS 12+**, **Python 3.10+**, **Xcode Command Line Tools**, and
[Bambu Studio](https://bambulab.com/en/download/studio) in `/Applications`.

```sh
git clone https://github.com/Blackajiro/Hueforge-Bambu-Bridge.git
cd Hueforge-Bambu-Bridge
python3 macos/build.py
```

1. Open **HueForge Bambu Bridge.app** in `dist`.
2. Choose **Printer**, **Nozzle** and **Build plate** from the menus.
3. Click **Choose Project…**, select your `.hfp`, then save in HueForge and confirm
   its dialog after **Waiting for your next save** appears.

No profile file is needed. The menus read the presets installed with Bambu Studio.
If your model is missing, choose another printer as a starting point, then switch
it or adjust its settings in Bambu Studio before printing. Your selections are remembered.

Keep the bridge open. Each completed save creates a new `.3mf` in
**Bambu Bridge Exports**, next to your project. Automatic opening in Bambu Studio
is optional. **Show in Finder** takes you to the exported file.

Before printing, open the 3MF **as a project**, slice, check the build plate,
and map the project colors to your actual AMS spools.

## What it supports

**Installed Bambu Studio presets · Single-nozzle Bambu printers · AMS**

- One flat Color Core, with 1–4 BambuLab Matte/Basic PLA entries.
- A saved HFP and its matching binary `_Front_*.stl` in the same folder.
- Original first/regular layer heights, 100% infill and automatic layer changes.
- Printer/nozzle/build plate selections and matching PLA material presets are automatic.
- Multi-extruder printers are not supported. Choose a supported base preset if needed.
- Conversion/slicing verified with P2S and A1 presets; other models still need testing.

The app waits for both saved files to finish changing. It never overwrites an
export. If you use **Save As**, reconnect the new project. Keep only one matching
Front STL in that folder. **Disconnect** or quit to stop watching.

This is a local prototype: build it on each Mac with Python installed. It is not
a signed, notarized, self-contained download. It does not send prints.

## Print settings

The bridge uses installed Bambu profiles plus explicit HueForge overrides:
solid infill, uniform layer heights, no ironing, no flushing into the artwork,
and a prime tower. Printer G-code, temperatures, speeds and material flow come from installed presets.
Purge uses a conservative fallback, **not a calibrated optimum**.

[Settings and sources](docs/print-settings.md) · [Validation and limits](docs/validation.md)

## Command line & tests

```sh
python3 hueforge_bambu.py project.hfp project_Front_50x150.stl output.3mf --printer "Bambu Lab A1 0.4 nozzle"
python3 -m unittest discover -s tests -v
```

Custom settings are still available from the command line with `--template my-printer.3mf`
instead of `--printer`. This advanced route is optional.

[Integration test](tests/verify_integration.py) uses your local Bambu Studio and
HueForge export. [Native plugin notes](docs/native-plugin.md) cover the optional
future menu integration.

[MIT](LICENSE). Independent project; not affiliated with HueForge or Bambu Lab.
