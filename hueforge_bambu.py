#!/usr/bin/env python3
"""Convert a HueForge color stack using a Bambu Studio printer template."""
import argparse
from functools import lru_cache
import json
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

APP = Path('/Applications/BambuStudio.app/Contents')

# Project geometry and optical blending require uniform, solid layers.
PROCESS_OVERRIDES = {
    'sparse_infill_density': '100%', 'sparse_infill_pattern': 'zig-zag',
    'enable_support': '0', 'enable_prime_tower': '1',
    'flush_into_infill': '0', 'flush_into_objects': '0',
    'ironing_type': 'no ironing', 'top_surface_pattern': 'monotonicline',
    'infill_combination': '0', 'precise_z_height': '0',
    'print_sequence': 'by layer', 'spiral_mode': '0',
}


def apply_project_settings(settings, stack, first, height):
    settings.update(PROCESS_OVERRIDES)
    settings.update(layer_height=str(height), initial_layer_print_height=str(first))
    count = len(stack)
    colors = [item['filamentDef']['Color'] for item in stack]
    # Keep calibrated purge only when the template has exactly the same colors/order.
    if [c.lower() for c in settings.get('filament_colour', [])] != [c.lower() for c in colors]:
        settings['flush_volumes_matrix'] = ['0' if i == j else '650'
                                           for i in range(count) for j in range(count)]
        settings['flush_volumes_vector'] = ['140'] * (2 * count)
        settings['flush_multiplier'] = ['1']
    settings['filament_colour'] = colors
    changes = settings.get('different_settings_to_system', [''] * (count+2))
    if len(changes) != count+2:
        changes = [''] * (count+2)
    process_keys = set(changes[0].split(';')) | set(PROCESS_OVERRIDES) | {'layer_height', 'initial_layer_print_height'}
    settings['different_settings_to_system'] = [
        ';'.join(sorted(process_keys - {''})),
        *[';'.join(sorted(set(changes[i+1].split(';')) - {''} | {'filament_colour'}))
          for i in range(count)], changes[-1],
    ]


PROFILES = APP / 'Resources/profiles/BBL'
BEDS = {'Textured PEI Plate': 'Textured PEI Plate',
        'High Temp Plate': 'Smooth PEI / High Temp Plate',
        'Cool Plate': 'Cool Plate', 'Engineering Plate': 'Engineering Plate',
        'Supertack Plate': 'Cool Plate SuperTack'}


@lru_cache(maxsize=None)
def resolve_profile(folder, name, trail=()):
    if name in trail or Path(name).name != name:
        raise ValueError('Invalid preset inheritance')
    source = json.loads((folder / (name + '.json')).read_text())
    result = {}
    if source.get('inherits'):
        result.update(resolve_profile(folder, source['inherits'], trail + (name,)))
    result.update(source)
    for include in source.get('include', []):
        part = resolve_profile(folder, include, trail + (name,))
        result.update({k: v for k, v in part.items() if k not in
                       {'name', 'type', 'from', 'setting_id', 'instantiation'}})
    result.pop('inherits', None); result.pop('include', None)
    return result


@lru_cache(maxsize=None)
def leaf_profiles(kind):
    entries = []
    for path in sorted((PROFILES / kind).glob('*.json')):
        source = json.loads(path.read_text())
        if kind == 'filament' and not source.get('name', '').startswith(('Bambu PLA Matte @', 'Bambu PLA Basic @')):
            continue
        if source.get('type') == kind and source.get('instantiation') == 'true':
            entries.append(resolve_profile(PROFILES / kind, path.stem))
    return entries


def printer_catalog():
    result = []
    for machine in leaf_profiles('machine'):
        if len(machine.get('nozzle_diameter', [])) != 1 or len(machine.get('extruder_offset', ['0x0'])) != 1:
            continue
        model = machine.get('printer_model')
        if not model:
            continue
        model_path = PROFILES / 'machine' / (model + '.json')
        info = json.loads(model_path.read_text()) if model_path.exists() else {}
        excluded = info.get('not_support_bed_type', '').split(';')
        beds = [{'id': key, 'name': name} for key, name in BEDS.items() if key not in excluded]
        result.append(dict(id=machine['name'], model=model,
                           nozzle=machine['nozzle_diameter'][0], beds=beds,
                           default_bed=info.get('default_bed_type', 'Textured PEI Plate')))
    return sorted(result, key=lambda p: (p['model'], float(p['nozzle']), p['id']))


def preset_configs(printer, bed, stack, first, height):
    catalog = {p['id']: p for p in printer_catalog()}
    if printer not in catalog:
        raise ValueError('Choose a printer preset installed in Bambu Studio')
    if bed not in [b['id'] for b in catalog[printer]['beds']]:
        raise ValueError('Choose a supported build plate for this preset')
    machine = dict(resolve_profile(PROFILES / 'machine', printer))
    compatible = [p for p in leaf_profiles('process') if printer in p.get('compatible_printers', [])]
    if not compatible:
        raise ValueError('No compatible process preset found; choose another printer as a base')
    compatible.sort(key=lambda p: (not p['name'].startswith('0.08mm High Quality'),
                                    p['name'] != machine.get('default_print_profile'), p['name']))
    process = dict(compatible[0])
    process.update(PROCESS_OVERRIDES)
    process.update(layer_height=str(height), initial_layer_print_height=str(first), curr_bed_type=bed)
    validate_layer_heights(machine, first, height)
    filaments = []
    for item in stack:
        family = 'Matte' if item['filamentDef']['Brand'].endswith('Matte') else 'Basic'
        choices = [p for p in leaf_profiles('filament')
                   if p['name'].startswith(f'Bambu PLA {family} @') and
                   printer in p.get('compatible_printers', [])]
        if not choices:
            raise ValueError(f'No Bambu PLA {family} preset for this printer; choose another base preset')
        preset = dict(sorted(choices, key=lambda p: (len(p['name']), p['name']))[0])
        preset['filament_colour'] = [item['filamentDef']['Color']]
        filaments.append(preset)
    return machine, process, filaments


def read_template(path):
    try:
        with zipfile.ZipFile(path) as archive:
            entry = archive.getinfo('Metadata/project_settings.config')
            if entry.file_size > 16 * 1024 * 1024:
                raise ValueError('Template settings are too large')
            settings = json.loads(archive.read(entry))
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as error:
        raise ValueError('Choose a project 3MF saved by Bambu Studio, not an STL or sliced-only file') from error
    if not isinstance(settings, dict):
        raise ValueError('Template settings must be a JSON object')
    if not str(settings.get('printer_model', '')).startswith('Bambu Lab '):
        raise ValueError('This version supports Bambu Lab printer templates only')
    nozzles = settings.get('nozzle_diameter', [])
    if (not isinstance(nozzles, list) or len(nozzles) != 1 or
            len(settings.get('extruder_offset', ['0x0'])) != 1):
        raise ValueError('Choose a single-nozzle printer template; multi-extruder machines are not supported yet')
    diameter = float(nozzles[0])
    if not math.isfinite(diameter) or not 0.2 <= diameter <= 0.8:
        raise ValueError('Unsupported nozzle diameter')
    for key in ['printer_settings_id', 'print_settings_id', 'curr_bed_type',
                'machine_start_gcode', 'machine_end_gcode', 'change_filament_gcode']:
        if not settings.get(key):
            raise ValueError(f'Template is missing {key}; save a complete project in Studio')
    names = settings.get('filament_settings_id', [])
    types = settings.get('filament_type', [])
    if not isinstance(names, list) or not 1 <= len(names) <= 4 or types != ['PLA'] * len(names):
        raise ValueError('Prepare 1–4 PLA project filaments in the template')
    colors = settings.get('filament_colour', [])
    if not isinstance(colors, list) or len(colors) != len(names) or any(
            not isinstance(c, str) or len(c) != 7 or c[0] != '#' for c in colors):
        raise ValueError('Template filament colors are incomplete')
    for color in colors:
        int(color[1:], 16)
    return settings


def validate_template(settings, stack, first, height):
    if len(settings['filament_settings_id']) != len(stack):
        raise ValueError(f'Template needs exactly {len(stack)} project filaments, in HueForge bottom-to-top order')
    for item, preset in zip(stack, settings['filament_settings_id']):
        family = 'Matte' if item['filamentDef']['Brand'].endswith('Matte') else 'Basic'
        if not preset.startswith(f'Bambu PLA {family}'):
            raise ValueError(f'Template filament must use Bambu PLA {family}: {preset}')
    validate_layer_heights(settings, first, height)


def validate_layer_heights(settings, first, height):
    nozzle = float(settings['nozzle_diameter'][0])
    low = float(settings.get('min_layer_height', [0.25 * nozzle])[0])
    high = float(settings.get('max_layer_height', [0.75 * nozzle])[0])
    if not all(math.isfinite(v) for v in (low, high)) or not 0 < low <= high:
        raise ValueError('Template has invalid layer-height limits')
    if not all(low-1e-5 <= v <= high+1e-5 for v in (first, height)):
        raise ValueError(f'HueForge layer heights must fit this nozzle: {low:g}–{high:g} mm')


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
            0 < first <= 1 and 0 < height <= 1):
        raise ValueError('Invalid HueForge layer heights')
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


def convert(hfp, stl, output, template=None, printer=None, bed="Textured PEI Plate"):
    if output.exists():
        raise ValueError(f'Refusing to overwrite: {output}')
    project = json.loads(hfp.read_text())
    stack, first, height = read_stack(project)
    if stl.suffix.lower() != '.stl' or not stl.is_file():
        raise ValueError('Provide the STL exported alongside the HFP')
    validate_stl(stl, project, stack, first, height)
    settings = None
    if template:
        settings = read_template(template)
        validate_template(settings, stack, first, height)
        apply_project_settings(settings, stack, first, height)
        configs = []
        for kind, name in [('machine', settings['printer_settings_id']),
                           ('process', settings['print_settings_id'])]:
            config = dict(settings, type=kind, name=name, **{'from': 'system'})
            config['compatible_printers'] = [settings['printer_settings_id']]
            configs.append(config)
        filaments = []
        expected_model = settings['printer_model']
    else:
        machine, process, filaments = preset_configs(printer, bed, stack, first, height)
        configs = [machine, process]
        expected_model = machine['printer_model']
    with tempfile.TemporaryDirectory(prefix='hueforge-bambu-') as tmp:
        tmp = Path(tmp)
        for kind, config in zip(['machine', 'process'], configs):
            (tmp / (kind + '.json')).write_text(json.dumps(config))
        filament_files = []
        for index, config in enumerate(filaments):
            file = tmp / f'filament{index}.json'
            file.write_text(json.dumps(config)); filament_files.append(str(file))
        base = tmp / 'base.3mf'
        command = [str(APP / 'MacOS/BambuStudio'), '--load-settings',
                   f'{tmp}/machine.json;{tmp}/process.json', '--arrange', '1', '--orient', '0',
                   '--export-3mf', str(base), str(stl.resolve())]
        if filament_files:
            command[1:1] = ['--load-filaments', ';'.join(filament_files)]
        result = subprocess.run(command, capture_output=True, text=True, cwd=tmp)
        if result.returncode or not base.exists():
            raise RuntimeError('Bambu export failed:\n' + result.stdout[-4000:] + result.stderr[-4000:])
        with zipfile.ZipFile(base) as original:
            generated = json.loads(original.read('Metadata/project_settings.config'))
            if generated['printer_model'] != expected_model:
                raise RuntimeError('Bambu did not apply the selected printer')
            if settings is None:
                settings = generated
                # Fresh presets have no calibrated color-pair purge matrix.
                settings['filament_colour'] = []
                apply_project_settings(settings, stack, first, height)
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
    print(f"Created {output}: {settings['printer_settings_id']}, {first:g}/{height:g} mm, 100% infill")
    for slot, item in enumerate(stack, 1):
        f = item['filamentDef']
        print(f'{slot}: {f["Brand"]} {f["Name"]}')
    for item in stack[:-1]:
        print(f'Swap layer {item["value"]+1}, Z={first+item["value"]*height:.2f} mm')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('hfp', type=Path, nargs='?')
    parser.add_argument('stl', type=Path, nargs='?')
    parser.add_argument('output', type=Path, nargs='?')
    target = parser.add_mutually_exclusive_group()
    target.add_argument('--template', type=Path, help='Optional custom Bambu Studio 3MF')
    target.add_argument('--printer', help='Installed Bambu Studio printer preset name')
    parser.add_argument('--bed', default='Textured PEI Plate')
    parser.add_argument('--list-printers', action='store_true')
    parser.add_argument('--inspect-template', action='store_true')
    args = parser.parse_args()
    try:
        if args.list_printers:
            print(json.dumps(printer_catalog()))
        elif args.inspect_template:
            if not args.template:
                parser.error('--inspect-template requires --template')
            settings = read_template(args.template)
            print(json.dumps({'printer': settings['printer_settings_id'],
                              'nozzle': settings['nozzle_diameter'][0],
                              'bed': settings['curr_bed_type'],
                              'filaments': len(settings['filament_settings_id'])}))
        else:
            if not all([args.hfp, args.stl, args.output]):
                parser.error('Provide HFP, STL and output paths')
            convert(args.hfp, args.stl, args.output, args.template, args.printer, args.bed)
    except (ValueError, KeyError, TypeError, OSError, RuntimeError) as error:
        parser.exit(1, f'{error}\n')
