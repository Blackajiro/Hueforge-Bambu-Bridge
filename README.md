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
2. Click **Choose Project…** and select your saved `.hfp` file.
3. Wait for **Waiting for your next save**, then save in HueForge and confirm its dialog.

Keep the bridge open. Each completed save creates a new `.3mf` in
**Bambu Bridge Exports**, next to your project. Automatic opening in Bambu Studio
is optional. **Show in Finder** takes you to the exported file.

Before printing, open the 3MF **as a project**, slice, check the build plate,
and map the project colors to your actual AMS spools.

## What it supports

**P2S · 0.4 mm nozzle · AMS · Textured PEI Plate**

- One flat Color Core, with 1–4 BambuLab Matte/Basic PLA entries.
- A saved HFP and its matching binary `_Front_*.stl` in the same folder.
- Original first/regular layer heights, 100% infill and automatic layer changes.

The app waits for both saved files to finish changing. It never overwrites an
export. If you use **Save As**, reconnect the new project. Keep only one matching
Front STL in that folder. **Disconnect** or quit to stop watching.

This is a local prototype: build it on each Mac with Python installed. It is not
a signed, notarized, self-contained download. It does not send prints.

## Print settings

The bridge uses installed Bambu profiles plus explicit HueForge overrides:
solid infill, uniform layer heights, no ironing, no flushing into the artwork,
and a prime tower. Temperatures, speeds and material flow come from Bambu presets.
Purge is a conservative starting point, **not a calibrated optimum**.

[Settings and sources](docs/print-settings.md) · [Validation and limits](docs/validation.md)

## Command line & tests

```sh
python3 hueforge_bambu.py project.hfp project_Front_50x150.stl output.3mf
python3 -m unittest discover -s tests -v
```

[Integration test](tests/verify_integration.py) uses your local Bambu Studio and
HueForge export. [Native plugin notes](docs/native-plugin.md) cover the optional
future menu integration.

[MIT](LICENSE). Independent project; not affiliated with HueForge or Bambu Lab.
