# Native HueForge plugin integration

## Working without the SDK

The macOS companion app watches a user-selected saved HFP and its matching Front
STL. A completed HueForge save triggers conversion and opening in Studio through
macOS NSWorkspace. The bridge uses only filesystem snapshots, the installed Bambu
CLI and native AppKit controls. There is no injection, patched HueForge binary,
reconstructed plugin vtable or unsupported in-process binding.

This implements the practical export workflow now, without requiring developer
access. A menu item inside HueForge remains a separate optional integration.

## Optional native plugin boundary

The conversion engine works on saved HFP + STL files. It is not yet a plugin
loadable by HueForge. No official SDK headers or examples were found in the
installed HueForge 0.9.4.4 application or in the public resources checked on
2026-10-14. The developer has indicated that beta SDK access can be requested:

- [Developer discussion](https://www.reddit.com/r/HueForge/comments/1to9xze/hueforge_v094_release_and_3rd_party_3mf_export/)
- [Official 0.9.4.4 host/plugin release notes](https://devlog.thehueforge.com/p/hueforge-v0944-release-notes)

## Intended user flow

1. Open and tune a project in HueForge.
2. Choose **Export to Bambu Studio** from a plugin-provided menu action.
3. Confirm output path and review the P2S/0.4 mm/AMS target and color stack.
4. Export a current mesh and matching project state through supported host APIs.
5. Run the existing converter outside the host UI thread.
6. Open the completed 3MF in Bambu Studio using the supported platform API.

First release retains the converter's current printer/material limits. It does
not send a print, synchronize physical AMS slots, or change the filament library.

## SDK questions to resolve before implementation

- Plugin entry point, menu registration, host/plugin ABI and compatible Qt version.
- Current project snapshot: layer heights, ordered real Color Core and mesh export.
- Save/export completion and cancellation, threading, errors and output lifetime.
- Whether Python can be invoked from a native adapter or the converter needs
  packaging/porting; no Python runtime will be injected into the host speculatively.
- macOS bundle/archive structure, signing and version compatibility declarations.
- Permission to publish the adapter under MIT, including any SDK headers/examples
  required to build it, or instructions to obtain them separately.

## Acceptance checks once the SDK is available

Install/uninstall through HueForge's normal plugin flow; show the menu action;
export the current unsaved state safely or require an explicit save; propagate
cancel/export failures without a partial output; keep the host responsive;
reopen the generated file in Studio; verify matching mesh dimensions, heights
and tool changes in actual sliced layers. Test supported host-version rejection.

There is deliberately no C++ scaffold until the actual interface is available.
