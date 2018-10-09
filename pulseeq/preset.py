import os, pprint

from pulseeq.constants import *

class Band:
    def __init__(self, control, frequency):
        self.frequency = frequency
        self.control = control

class Preset:
    def __init__(self):
        self.system = False
        self.filename = None
        self.plugin = 'mbeq_1197'
        self.plugin_name = 'Multiband EQ'
        self.plugin_label = 'mbeq'
        controls = [0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0]
        frequencies = [50,100,156,220,311,440,622,880,1250,1750,2500,3500,5000,10000,20000]
        self.bands = [Band(ctrl, frq) for ctrl, frq in zip(controls, frequencies)]
        self.name = ''

    @staticmethod
    def from_file(filename=None, system=False, config=False):
        if filename is not None:
            preset = Preset()
            f = open(filename, 'r')
            lines = f.read().split('\n')
            f.close()

            preset.filename = filename
            preset.system = system

            preset.plugin = lines[0]
            preset.plugin_name = lines[1]
            preset.plugin_label = lines[2]

            preset.name = lines[4]
            offset = 10 if config else 6
            num_controls = int(lines[offset - 1])
            controls = [float(ctrl) for ctrl in lines[offset:offset + num_controls]]
            frequencies = [int(frq) for frq in lines[offset + num_controls:offset + (num_controls * 2)]]
            preset.bands = [Band(ctrl, frq) for ctrl, frq in zip(controls, frequencies)]

            return preset

    def save(self):
        if self.system or self.filename is not None: return

        self.filename = os.path.join(USER_PRESET_DIR, self.name + '.preset')

        f = open(self.filename, 'w+')
        lines = [self.plugin, self.plugin_name, self.plugin_label,
                 '', self.name, str(len(self.bands))]
        lines += [str(band.control) for band in self.bands]
        lines += [str(band.frequency) for band in self.bands]
        lines.append('\n')
        f.write('\n'.join(lines))
        f.close()

    def remove(self):
        if self.filename is not None:
            os.remove(self.filename)
