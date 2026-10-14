import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
import hueforge_bambu as h


class ConverterTests(unittest.TestCase):
    def setUp(self):
        self.stack = [{'enabled': True, 'value': value, 'filamentDef':
                       {'Type': 'PLA', 'Brand': 'BambuLab Matte', 'Color': color}}
                      for value, color in [(3, '#000000'), (7, '#545454'),
                                           (11, '#f99963'), (18, '#ffffff')]]
        self.project = {'base_layer_height': .159999996, 'layer_height': .079999998,
                        'core_graph_color': {'data': {'segments': [
                            {'stack': self.stack, 'children': []}]}},
                        'width_in_mm': 50, 'height_in_mm': 150}

    def test_exact_new_color_layers_and_ams_tools(self):
        stack, first, height = h.read_stack(self.project)
        root = ET.fromstring(h.changes_xml(stack, first, height))
        layers = root.findall('plate/layer')
        self.assertEqual([float(x.get('top_z')) for x in layers], [.4, .72, 1.04])
        self.assertEqual([x.get('extruder') for x in layers], ['2', '3', '4'])
        self.assertTrue(all(x.get('type') == '2' for x in layers))
        self.assertEqual(root.find('plate/mode').get('value'), 'MultiAsSingle')

    def test_reject_unsupported_and_invalid_stacks(self):
        for mutation in ('material', 'branched', 'boundary', 'nan', 'disabled'):
            p = copy.deepcopy(self.project)
            stack = p['core_graph_color']['data']['segments'][0]['stack']
            if mutation == 'material': stack[0]['filamentDef']['Type'] = 'PETG'
            if mutation == 'branched': p['core_graph_color']['data']['segments'].append({})
            if mutation == 'boundary': stack[1]['value'] = 3
            if mutation == 'nan': p['layer_height'] = float('nan')
            if mutation == 'disabled': stack[0]['enabled'] = False
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                h.read_stack(p)

    def test_profile_inheritance_and_gcode_include(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name, data in {'base': {'layer_height': '.2', 'speed': '50'},
                               'code': {'name': 'code', 'machine_start_gcode': 'G28'},
                               'child': {'name': 'child', 'inherits': 'base',
                                         'include': ['code'], 'layer_height': '.08'}}.items():
                (folder / (name+'.json')).write_text(json.dumps(data))
            self.assertEqual(h.resolve_profile(folder, 'child'),
                             {'name': 'child', 'layer_height': '.08',
                              'speed': '50', 'machine_start_gcode': 'G28'})
            (folder/'base.json').write_text('{"inherits":"child"}')
            with self.assertRaises(ValueError): h.resolve_profile(folder, 'child')

    def test_stl_size_mismatch_and_truncation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'test.stl'
            data = bytes(80) + struct.pack('<I', 1) + struct.pack(
                '<12fH', 0, 0, 1, 0, 0, 0, 50, 0, 1.52, 0, 150, 1.52, 0)
            path.write_bytes(data)
            h.validate_stl(path, self.project, self.stack, .16, .08)
            self.project['width_in_mm'] = 45
            with self.assertRaises(ValueError):
                h.validate_stl(path, self.project, self.stack, .16, .08)
            path.write_bytes(data[:-1])
            with self.assertRaises(ValueError):
                h.validate_stl(path, self.project, self.stack, .16, .08)

    def test_studio_preserves_overrides_and_filament_colors(self):
        settings = {'layer_height': '.2', 'ironing_type': 'all solid surfaces',
                    'flush_multiplier': ['.3']}
        h.apply_project_settings(settings, self.stack, .16, .08)
        self.assertEqual(settings['initial_layer_print_height'], '0.16')
        self.assertEqual(settings['infill_combination'], '0')
        self.assertEqual(settings['ironing_type'], 'no ironing')
        self.assertEqual(settings['sparse_infill_density'], '100%')
        self.assertEqual(settings['flush_multiplier'], ['1'])
        changes = settings['different_settings_to_system']
        self.assertEqual(len(changes), len(self.stack)+2)
        self.assertIn('initial_layer_print_height', changes[0].split(';'))
        self.assertTrue(set(h.PROCESS_OVERRIDES).issubset(changes[0].split(';')))
        self.assertEqual(changes[1:5], ['filament_colour']*4)
        self.assertEqual(len(settings['flush_volumes_matrix']), 16)

    def test_never_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'existing.3mf'
            path.write_bytes(b'keep')
            with self.assertRaises(ValueError): h.convert(Path('absent'), Path('absent'), path)
            self.assertEqual(path.read_bytes(), b'keep')


if __name__ == '__main__':
    unittest.main()
