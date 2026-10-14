import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile
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

    def template_settings(self):
        return dict(printer_model='Bambu Lab A1', printer_settings_id='Bambu Lab A1 0.4 nozzle',
                    print_settings_id='My tuned profile', curr_bed_type='Smooth PEI Plate',
                    nozzle_diameter=['0.4'], min_layer_height=['0.08'], max_layer_height=['0.28'],
                    machine_start_gcode='CUSTOM START', machine_end_gcode='CUSTOM END',
                    change_filament_gcode='CUSTOM CHANGE',
                    filament_settings_id=['Bambu PLA Matte @BBL A1']*4, filament_type=['PLA']*4,
                    filament_colour=[item['filamentDef']['Color'] for item in self.stack])

    def test_template_preserves_machine_bed_calibration_and_modified_keys(self):
        settings = self.template_settings()
        settings.update(flush_volumes_matrix=['calibrated'], flush_multiplier=['.8'],
                        different_settings_to_system=['top_surface_speed', '', '', '', '', 'machine_start_gcode'])
        h.validate_template(settings, self.stack, .16, .08)
        h.apply_project_settings(settings, self.stack, .16, .08)
        self.assertEqual(settings['printer_model'], 'Bambu Lab A1')
        self.assertEqual(settings['curr_bed_type'], 'Smooth PEI Plate')
        self.assertEqual(settings['machine_start_gcode'], 'CUSTOM START')
        self.assertEqual(settings['flush_volumes_matrix'], ['calibrated'])
        self.assertEqual(settings['flush_multiplier'], ['.8'])
        self.assertIn('top_surface_speed', settings['different_settings_to_system'][0])
        self.assertEqual(settings['different_settings_to_system'][-1], 'machine_start_gcode')

    def test_template_checks_nozzle_filament_count_and_family(self):
        for mutation in ('nozzle', 'count', 'family'):
            settings = self.template_settings()
            if mutation == 'nozzle': settings['min_layer_height'] = ['.12']
            if mutation == 'count': settings['filament_settings_id'].pop()
            if mutation == 'family': settings['filament_settings_id'][0] = 'Generic PETG'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                h.validate_template(settings, self.stack, .16, .08)

    def test_read_template_rejects_wrong_archive_material_and_multi_extruder(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'template.3mf'
            path.write_text('not a zip')
            with self.assertRaises(ValueError): h.read_template(path)
            for mutation in ('valid', 'multi', 'material', 'missing', 'color'):
                settings = self.template_settings()
                if mutation == 'multi': settings['nozzle_diameter'] = ['.4', '.4']
                if mutation == 'material': settings['filament_type'][0] = 'PETG'
                if mutation == 'missing': del settings['machine_start_gcode']
                if mutation == 'color': settings['filament_colour'][0] = 'bad'
                with zipfile.ZipFile(path, 'w') as z:
                    z.writestr('Metadata/project_settings.config', json.dumps(settings))
                if mutation == 'valid': self.assertEqual(h.read_template(path), settings)
                else:
                    with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                        h.read_template(path)

    def test_never_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'existing.3mf'
            path.write_bytes(b'keep')
            with self.assertRaises(ValueError): h.convert(Path('absent'), Path('absent'), path, Path('absent'))
            self.assertEqual(path.read_bytes(), b'keep')


if __name__ == '__main__':
    unittest.main()
