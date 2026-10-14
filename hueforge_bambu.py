#!/usr/bin/env python3
"""Convert a flat PLA HueForge color stack to a P2S 0.4 mm AMS project."""
import argparse
import json
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

APP = Path('/Applications/BambuStudio.app/Contents')


def resolve_profile(folder, name, trail=()):
    if name in trail:
        raise ValueError('Cyclic Bambu preset inheritance')
    source = json.loads((folder / (name + '.json')).read_text())
    result = {}
    if source.get('inherits'):
        result.update(resolve_profile(folder, source['inherits'], trail + (name,)))
    result.update(source)
    for include in source.get('include', []):
        part = resolve_profile(folder, include, trail + (name,))
        result.update({k: v for k, v in part.items() if k not in
                       {'name', 'type', 'from', 'setting_id', 'instantiation'}})
    result.pop('inherits', None)
    result.pop('include', None)
    return result


def read_stack(project):
    segments = project['core_graph_color']['data']['segments']
    if len(segments) != 1 or segments[0].get('children'):
        raise ValueError('Only a single flat Color Core is supported')
    stack = segments[0]['stack']
    if not 1 <= len(stack) <= 4 or any(not s['enabled'] for s in stack):
        raise ValueError('Use 1–4 enabled filaments for this AMS converter')
    first = round(float(project['base_layer_height']), 5)
    height = round(float(project['layer_height']), 5)
    if not (math.isfinite(first) and math.isfinite(height) and
            0.08 <= first <= 0.28 and 0.08 <= height <= 0.28):
        raise ValueError('Layer heights outside P2S 0.4 mm range')
    previous = 0
    for item in stack:
        value = item['value']
        filament = item['filamentDef']
        if isinstance(value, bool) or not isinstance(value, int) or value <= previous:
            raise ValueError('Expected increasing integer Color Core boundaries')
        previous = value
        if filament['Type'] != 'PLA' or filament['Brand'] not in ('BambuLab Matte', 'BambuLab Basic'):
            raise ValueError('Only BambuLab Matte/Basic PLA profiles are supported')
        color = filament['Color']
        if len(color) != 7 or color[0] != '#':
            raise ValueError('Invalid filament color')
        int(color[1:], 16)
    return stack, first, height


def changes_xml(stack, first, height):
    root = ET.Element('custom_gcodes_per_layer')
    plate = ET.SubElement(root, 'plate')
    ET.SubElement(plate, 'plate_info', id='1')
    for slot, previous in enumerate(stack[:-1], 2):
        # HueForge value is the last old-color layer; top_z is the first new one.
        z = first + previous['value'] * height
        ET.SubElement(plate, 'layer', top_z=f'{z:.5f}', type='2',
                      extruder=str(slot), color=stack[slot-1]['filamentDef']['Color'],
                      extra='', gcode='tool_change')
    ET.SubElement(plate, 'mode', value='MultiAsSingle')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def validate_stl(stl, project, stack, first, height):
    data = stl.read_bytes()
    if len(data) < 84:
        raise ValueError('Truncated binary STL')
    count = struct.unpack_from('<I', data, 80)[0]
    if not count or len(data) != 84 + 50 * count:
        raise ValueError('Expected a complete binary HueForge STL')
    low, high = [math.inf] * 3, [-math.inf] * 3
    for face in struct.iter_unpack('<12fH', data[84:]):
        for start in (3, 6, 9):
            for axis, value in enumerate(face[start:start+3]):
                if not math.isfinite(value):
                    raise ValueError('Non-finite STL vertex')
                low[axis], high[axis] = min(low[axis], value), max(high[axis], value)
    expected = [project['width_in_mm'], project['height_in_mm']]
    if any(abs(high[i]-low[i]-float(expected[i])) > 0.01 for i in (0, 1)):
        raise ValueError('STL dimensions do not match HFP; re-export in HueForge')
    if abs(low[2]) > 0.001 or high[2] > first + (stack[-1]['value']-1)*height + 0.01:
        raise ValueError('STL height does not fit the Color Core')
    if len(stack) > 1 and high[2] < first + stack[-2]['value']*height - 0.001:
        raise ValueError('Last filament change lies above the STL')


def convert(hfp, stl, output):
    if output.exists():
        raise ValueError(f'Refusing to overwrite: {output}')
    project = json.loads(hfp.read_text())
    stack, first, height = read_stack(project)
    if stl.suffix.lower() != '.stl' or not stl.is_file():
        raise ValueError('Provide the STL exported alongside the HFP')
    validate_stl(stl, project, stack, first, height)
    profiles = APP / 'Resources/profiles/BBL'
    machine = resolve_profile(profiles / 'machine', 'Bambu Lab P2S 0.4 nozzle')
    process = resolve_profile(profiles / 'process', '0.08mm High Quality @BBL P2S')
    process.update(layer_height=str(height), initial_layer_print_height=str(first),
                   sparse_infill_density='100%', sparse_infill_pattern='zig-zag',
                   enable_support='0', enable_prime_tower='1',
                   flush_into_infill='0', flush_into_objects='0',
                   curr_bed_type='Textured PEI Plate')
    with tempfile.TemporaryDirectory(prefix='hueforge-bambu-') as tmp:
        tmp = Path(tmp)
        for name, data in [('machine', machine), ('process', process)]:
            (tmp / (name + '.json')).write_text(json.dumps(data))
        filenames = []
        for slot, item in enumerate(stack, 1):
            f = item['filamentDef']
            family = 'Matte' if f['Brand'].endswith('Matte') else 'Basic'
            preset = resolve_profile(profiles / 'filament', f'Bambu PLA {family} @BBL P2S')
            preset['filament_colour'] = [f['Color']]
            file = tmp / f'filament{slot}.json'
            file.write_text(json.dumps(preset))
            filenames.append(str(file))
        base = tmp / 'base.3mf'
        command = [str(APP / 'MacOS/BambuStudio'), '--load-settings',
                   f'{tmp}/machine.json;{tmp}/process.json', '--load-filaments',
                   ';'.join(filenames), '--arrange', '1', '--orient', '0',
                   '--export-3mf', str(base), str(stl.resolve())]
        result = subprocess.run(command, capture_output=True, text=True, cwd=tmp)
        if result.returncode or not base.exists():
            raise RuntimeError('Bambu export failed:\n' + result.stdout[-4000:] + result.stderr[-4000:])
        with zipfile.ZipFile(base) as original:
            settings = json.loads(original.read('Metadata/project_settings.config'))
            if (settings['printer_model'] != 'Bambu Lab P2S' or
                    len(settings['machine_start_gcode']) < 1000 or
                    settings['sparse_infill_pattern'] != 'zig-zag' or
                    settings['sparse_infill_density'] != '100%' or
                    len(settings['filament_settings_id']) != len(stack) or
                    abs(float(settings['layer_height'])-height) > 1e-5):
                raise RuntimeError('Bambu did not apply resolved profiles correctly')
            settings['filament_colour'] = [i['filamentDef']['Color'] for i in stack]
            # shortcut: conservative fixed purge, tune in Studio after a physical color test.
            count = len(stack)
            settings['flush_volumes_matrix'] = ['0' if i == j else '650'
                                               for i in range(count) for j in range(count)]
            settings['flush_volumes_vector'] = ['140'] * (2 * count)
            with zipfile.ZipFile(tmp / 'final.3mf', 'w', zipfile.ZIP_DEFLATED) as target:
                for entry in original.infolist():
                    if entry.filename == 'Metadata/project_settings.config':
                        target.writestr(entry.filename, json.dumps(settings))
                    elif entry.filename != 'Metadata/custom_gcode_per_layer.xml':
                        target.writestr(entry, original.read(entry.filename))
                target.writestr('Metadata/custom_gcode_per_layer.xml', changes_xml(stack, first, height))
        output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation also protects against a file appearing during conversion.
        with output.open('xb') as target:
            target.write((tmp / 'final.3mf').read_bytes())
    print(f'Created {output}: P2S 0.4 mm, {first:g}/{height:g} mm, 100% infill')
    for slot, item in enumerate(stack, 1):
        f = item['filamentDef']
        print(f'{slot}: {f["Brand"]} {f["Name"]}')
    for item in stack[:-1]:
        print(f'Swap layer {item["value"]+1}, Z={first+item["value"]*height:.2f} mm')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('hfp', type=Path)
    parser.add_argument('stl', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        convert(args.hfp, args.stl, args.output)
    except (ValueError, KeyError, OSError, RuntimeError) as error:
        parser.exit(1, f'{error}\n')
