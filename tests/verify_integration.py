"""Opt-in check using a local HueForge export and the real Bambu slicer."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hueforge_bambu as bridge


def verify(hfp, stl, template):
    stack, first, height = bridge.read_stack(json.loads(hfp.read_text()))
    with tempfile.TemporaryDirectory(prefix='hueforge-integration-') as folder:
        folder = Path(folder)
        project, sliced = folder/'project.3mf', folder/'sliced.3mf'
        bridge.convert(hfp, stl, project, template)
        result = subprocess.run([str(bridge.APP/'MacOS/BambuStudio'), '--slice', '0',
                                 '--export-3mf', str(sliced), str(project)],
                                capture_output=True, text=True, cwd=folder)
        if result.returncode or not sliced.exists():
            raise RuntimeError('Slicing failed: ' + result.stdout[-4000:] + result.stderr[-4000:])
        with zipfile.ZipFile(sliced) as archive:
            settings = json.loads(archive.read('Metadata/project_settings.config'))
            for key, value in bridge.PROCESS_OVERRIDES.items():
                assert settings[key] == value, (key, settings[key], value)
            assert abs(float(settings['initial_layer_print_height'])-first) < 1e-5
            template_settings = bridge.read_template(template)
            for key in ['printer_settings_id', 'nozzle_diameter', 'curr_bed_type',
                        'machine_start_gcode', 'machine_end_gcode', 'change_filament_gcode']:
                assert settings[key] == template_settings[key], key
            gcode = archive.read('Metadata/plate_1.gcode').decode('utf-8')
            info = ET.fromstring(archive.read('Metadata/slice_info.config'))
            used = info.findall('plate/filament')
            assert len(used) == len(stack), 'Unexpected number of materials'
            assert all(f.get('used_for_object') == 'true' for f in used)
            current_z, observed, layers = None, [], []
            for line in gcode.splitlines():
                if line.startswith('; Z_HEIGHT:'):
                    current_z = float(line.split()[-1])
                    layers.append(current_z)
                if current_z is not None and re.fullmatch(r'T[1-3]', line.strip()):
                    observed.append((round(current_z, 5), line.strip()))
            expected = [(round(first + item['value']*height, 5), f'T{slot}')
                        for slot, item in enumerate(stack[:-1], 1)]
            assert observed == expected, (observed, expected)
            assert layers and abs(layers[0]-first) < 1e-5
            assert all(abs(b-a-height) < 1e-5 for a,b in zip(layers,layers[1:]))
            assert not any('M600' == line.strip() for line in gcode.splitlines())
            print(f'PASS: {len(layers)} layers, {len(used)} object materials, changes {observed}')
            if result.stdout.strip() or result.stderr.strip():
                print('Slicer diagnostics:')
                print((result.stdout + result.stderr).strip()[-2000:])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('hfp', type=Path)
    parser.add_argument('stl', type=Path)
    parser.add_argument('--template', type=Path, required=True)
    args = parser.parse_args()
    verify(args.hfp, args.stl, args.template)
