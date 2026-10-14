# HueForge SDK access request — draft, not sent

Subject: SDK access for an open-source HueForge → Bambu Studio export plugin

Hi HueForge team,

I am building an independent open-source export plugin that would add an
“Export to Bambu Studio” action inside HueForge.

The current Python prototype converts a saved HFP plus its matching STL into
a Bambu Studio 3MF with the real Color Core filament order, original layer
heights, printer settings and automatic AMS tool changes. It uses the locally
installed Bambu Studio CLI and presets. The initial supported target is the
Bambu Lab P2S with a 0.4 mm nozzle and AMS.

I have verified a four-color bookmark with the installed Bambu Studio slicer:
18 layers, tool changes at Z 0.40, 0.72 and 1.04 mm, and all four filaments
used on the model. No HueForge binaries, SDK code, paid plugin implementation,
printer presets or personal filament libraries are included in the repository.

Could you provide access to the current plugin SDK, a minimal exporter example,
and macOS build/packaging instructions? I would need supported access to the
active project's color stack and layer settings, mesh export completion, and
menu registration.

I intend to publish my implementation under MIT. Please clarify what SDK
interfaces, headers or examples may be redistributed and whether contributors
can obtain the SDK to build the native adapter themselves.

Repository: https://github.com/Blackajiro/Hueforge-Bambu-Bridge

Thanks!
