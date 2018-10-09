#!/usr/bin/env python
# -*- coding: utf-8 -*-

# PulseAudio Equalizer (PyGTK Interface)
#
# Intended for use in conjunction with pulseaudio-equalizer script
#
# Author: Conn O'Griofa <connogriofa AT gmail DOT com>
# Version: (see '/usr/pulseaudio-equalizer' script)
#

import gi
gi.check_version('3.30')
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GLib, GObject

import copy, glob, os, sys

from pulseeq.constants import *
from pulseeq.preset import Preset

def GetSettings():
    global preamp
    global status
    global persistence
    global ranges

    print('Getting settings...')

    os.system('pulseaudio-equalizer interface.getsettings')

    f = open(CONFIG_FILE, 'r')
    rawdata = f.read().split('\n')
    f.close()

    preamp = rawdata[3]
    status = int(rawdata[5])
    persistence = int(rawdata[6])
    ranges = rawdata[7:9]

    preset = Preset.from_file(filename=CONFIG_FILE, config=True)

    return preset

def ApplySettings(preset):
    f = open(CONFIG_FILE, 'w+')
    lines = [preset.plugin, preset.plugin_name, preset.plugin_label,
             str(preamp), preset.name, str(status), str(persistence)]
    lines += [str(r) for r in ranges]
    lines.append(str(len(preset.bands)))
    lines += [str(band.control) for band in preset.bands]
    lines += [str(band.frequency) for band in preset.bands]
    lines.append('\n')
    f.write('\n'.join(lines))
    f.close()

    os.system('pulseaudio-equalizer interface.applysettings')

class FrequencyLabel(Gtk.Label):
    def __init__(self, frequency=None):
        super(FrequencyLabel, self).__init__(visible=True, use_markup=True,
                                             justify=Gtk.Justification.CENTER)
        if frequency is not None:
            self.set_frequency(frequency)

    def set_frequency(self, frequency):
        frequency = float(frequency)
        suffix = 'Hz'

        if frequency > 999:
            frequency = frequency / 1000
            suffix = 'KHz'

        self.set_label('<small>{0:g}\n{1}</small>'.format(frequency, suffix))

@Gtk.Template(resource_path='/com/github/pulseaudio-equalizer-ladspa/Equalizer/ui/Equalizer.ui')
class Equalizer(Gtk.ApplicationWindow):
    __gtype_name__= "Equalizer"

    grid = Gtk.Template.Child()
    presetsbox = Gtk.Template.Child()

    def on_scale(self, scale, idx):
        if not self.update_preset:
            if self.preset.name in self.presets:
                self.preset = copy.deepcopy(self.preset)
            self.preset.filename = None
            self.preset.name = ''
            self.presetsbox.get_child().set_text(self.preset.name)

            if self.apply_event_source is not None:
                GLib.source_remove (self.apply_event_source);

            self.apply_event_source = GLib.timeout_add (500, self.on_apply_event)

        self.preset.bands[idx].control = float(round(scale.get_value(), 1))
        self.scalevalues[idx].set_markup('<small>{0}\ndB</small>'.format(self.preset.bands[idx].control))

    def on_apply_event(self):
        ApplySettings(self.preset)
        self.apply_event_source = None
        return False

    @Gtk.Template.Callback()
    def on_presetsbox(self, combo):
        if self.update_preset: return

        if self.apply_event_source is not None:
            GLib.source_remove (self.apply_event_source);

        preset_name = combo.get_child().get_text()
        tree_iter = combo.get_active_iter()

        if tree_iter is not None or preset_name in self.presets:
            if tree_iter is not None:
                model = combo.get_model()
                preset = model[tree_iter][1]
            else:
                preset = self.presets[preset_name]

            self.set_preset(preset)
        else:
            if self.preset.name in self.presets:
                self.preset = copy.deepcopy(self.preset)
            self.preset.name = preset_name
            self.preset.filename = None
            self.preset.system = False
            self.apply_event_source = GLib.timeout_add (500, self.on_apply_event)

    def on_resetsettings(self, action=None, param=None):
        print('Resetting to defaults...')
        os.system('pulseaudio-equalizer interface.resetsettings')

        preset = GetSettings()

        self.lookup_action('eqenabled').set_state(GLib.Variant('b', status))
        Gio.Application.get_default().lookup_action('keepsettings').set_state(GLib.Variant('b', persistence))

        self.set_preset(preset)

    def on_savepreset(self, action, param):
        if self.preset.name == '' or self.preset.name in self.presets:
            print('Invalid preset name')
        else:
            self.preset.save()
            self.presets[self.preset.name] = self.preset
            self.presetsstore.append((self.preset.name, self.preset))

            ApplySettings(self.preset)

            action.set_enabled(False)
            self.lookup_action('remove').set_enabled(True)

    def on_eqenabled(self, action, state):
        global status
        status = int(state.get_boolean())
        ApplySettings(self.preset)
        action.set_state(state)

    def on_removepreset(self, action, param):
        del self.presets[self.preset.name]
        self.preset.remove()
        self.update_preset = True
        for row in self.presetsstore:
            if row[0] == self.preset.name:
                self.presetsstore.remove(row.iter)
                break
        self.update_preset = False

        self.preset.name = ''
        self.set_preset(self.preset)

        action.set_enabled(False)

    def set_preset(self, preset):
        self.preset = preset

        self.update_preset = True
        for idx, band in enumerate(self.preset.bands):
            self.scales[idx].set_value(band.control)
            self.labels[idx].set_frequency(band.frequency)
            self.scalevalues[idx].set_markup('<small>{0}\ndB</small>'.format(band.control))

        self.presetsbox.get_child().set_text(self.preset.name)
        self.update_preset = False

        self.lookup_action('save').set_enabled(self.preset.name not in self.presets
                                               and self.preset.name != '')

        self.lookup_action('remove').set_enabled(self.preset.name in self.presets
                                                 and not self.preset.system)

        ApplySettings(self.preset)

    def __init__(self, *args, **kwargs):
        super(Equalizer, self).__init__(*args, **kwargs)
        global status

        self.presets = {}
        # read all system presets
        for filename in glob.glob(os.path.join(SYSTEM_PRESET_DIR, '*.preset')):
            system_preset = Preset.from_file(filename=filename, system=True)
            self.presets[system_preset.name] = system_preset

        # read all user presets overriding system preset if it allready exists
        for filename in glob.glob(os.path.join(USER_PRESET_DIR, '*.preset')):
            user_preset = Preset.from_file(filename=filename)
            self.presets[user_preset.name] = user_preset

        preset = GetSettings()

        if preset.name in self.presets:
            preset = self.presets[preset.name]

        self.update_preset = False

        self.apply_event_source = None

        # Equalizer bands
        self.scales = {}
        self.labels = {}
        self.scalevalues = {}
        for idx, band in enumerate(preset.bands):
            scale = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL,
                              draw_value=False, inverted=True, digits=1,
                              expand=True, visible=True)
            self.scales[idx] = scale
            scale.set_range(float(ranges[0]), float(ranges[1]))
            scale.set_increments(1, 0.1)
            scale.set_size_request(35, 200)
            scale.connect('value-changed', self.on_scale, idx)
            label = FrequencyLabel(frequency = band.frequency)
            self.labels[idx] = label
            scalevalue = Gtk.Label(visible=True, use_markup=True)
            self.scalevalues[idx] = scalevalue
            self.grid.attach(label, idx, 0, 1, 1)
            self.grid.attach(scale, idx, 1, 1, 2)
            self.grid.attach(scalevalue, idx, 3, 1, 1)

        action = Gio.SimpleAction.new('save', None)
        action.connect('activate', self.on_savepreset)
        self.add_action(action)

        action = Gio.SimpleAction.new('remove', None)
        action.connect('activate', self.on_removepreset)
        self.add_action(action)

        self.presetsstore = Gtk.ListStore(str, GObject.TYPE_PYOBJECT)
        self.presetsstore.set_sort_column_id(0, Gtk.SortType.ASCENDING)
        for item in self.presets.items():
            self.presetsstore.append(item)

        self.presetsbox.set_entry_text_column(0)
        self.presetsbox.set_model(self.presetsstore)

        self.set_preset(preset)

        action = Gio.SimpleAction.new_stateful('eqenabled', None,
                                               GLib.Variant('b', status))
        action.connect('change-state', self.on_eqenabled)
        self.add_action(action)

        self.show()


class Application(Gtk.Application):

    def __init__(self, *args, **kwargs):
        super(Application, self).__init__(*args,
            application_id='com.github.pulseaudio-equalizer-ladspa.Equalizer',
            resource_base_path='/com/github/pulseaudio-equalizer-ladspa/Equalizer',
            **kwargs)

        self.window = None

    def do_startup(self):
        global persistence

        Gtk.Application.do_startup(self)
        GetSettings()

        self.window = Equalizer(application=self)

        action = Gio.SimpleAction.new('resetsettings', None)
        action.connect('activate', self.window.on_resetsettings)
        self.add_action(action)

        action = Gio.SimpleAction.new_stateful('keepsettings', None,
                                               GLib.Variant('b', persistence))
        action.connect('change-state', self.on_keepsettings)
        self.add_action(action)

        action = Gio.SimpleAction.new('quit', None)
        action.connect('activate', self.on_quit)
        self.add_action(action)

    def do_activate(self):
        if not self.window:
            self.window = Equalizer(application=self)

        self.window.present()

    def on_keepsettings(self, action, state):
        global persistence
        persistence = int(state.get_boolean())
        ApplySettings(self.window.preset)
        action.set_state(state)

    def on_quit(self, action, param):
        Gio.Application.get_default().quit()
