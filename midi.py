import math
import usb_midi


class MidiLogic:
    def __init__(self):
        self.note_processor = MidiNoteProcessor()
        self.control_processor = MidiControlProcessor()  
        self.midi_out = usb_midi.ports[1]
        self.last_pitch_bend = {}  # Store last pitch bend value for each key

    def process_pot_changes(self, changed_pots, instrument_config):
        midi_events = []
        pots_config = instrument_config.get('pots', {})
        pitch_bend_config = instrument_config.get('pitch_bend', {})
        
        for pot_index, old_value, new_value in changed_pots:
            if pot_index in pots_config:
                cc_number = pots_config[pot_index]['cc']
                pot_name = pots_config[pot_index]['name']
                min_val = pots_config[pot_index]['min']
                max_val = pots_config[pot_index]['max']
                
                # Scale the new_value to the pot's min-max range
                scaled_value = min_val + new_value * (max_val - min_val)
                
                if pot_name == 'Bend Range':
                    pitch_bend_config['range'] = scaled_value
                elif pot_name == 'Bend Curve':
                    pitch_bend_config['curve'] = scaled_value
                
                midi_value = int(new_value * 127)  # Scale to MIDI range
                midi_events.append(('control_change', cc_number, midi_value, scaled_value))
        
        return midi_events

    def process_key_changes(self, changed_keys, instrument_config):
        return self.note_processor.process_key_changes(changed_keys, instrument_config)

    def handle_octave_shift(self, direction):
        return self.note_processor.handle_octave_shift(direction)

    def update(self, changed_keys, changed_pots, instrument_config):
        midi_events = []
        midi_events.extend(self.process_key_changes(changed_keys, instrument_config))
        midi_events.extend(self.process_pot_changes(changed_pots, instrument_config))
        return midi_events

    def send_midi_event(self, event):
        event_type, *params = event
        if event_type == 'note_on':
            midi_note, velocity, _ = params
            self.midi_out.write(bytes([0x90, int(midi_note), velocity]))
        elif event_type == 'note_off':
            midi_note, velocity, _ = params
            self.midi_out.write(bytes([0x80, int(midi_note), velocity]))
        elif event_type == 'control_change':
            cc_number, midi_value, _ = params
            self.midi_out.write(bytes([0xB0, cc_number, midi_value]))
        elif event_type == 'pitch_bend':
            key_id, bend_value = params
            if self.last_pitch_bend.get(key_id) != bend_value:
                lsb = bend_value & 0x7F
                msb = (bend_value >> 7) & 0x7F
                self.midi_out.write(bytes([0xE0, lsb, msb]))
                self.last_pitch_bend[key_id] = bend_value

    def process_and_send_midi_events(self, midi_events):
        for event in midi_events:
            event_type = event[0]
            if event_type in ['note_on', 'note_off', 'control_change', 'pitch_bend']:
                self.send_midi_event(event)
        return midi_events  # Return events for use by the synthesizer

    def set_instrument(self, instrument):
        self.note_processor.set_instrument(instrument)
        self.control_processor.set_instrument(instrument)

    def get_pitch_bend(self, key_id):
        return self.note_processor.get_pitch_bend(key_id)

class MidiNoteProcessor:
    def __init__(self):
        self.octave_shift = 0
        self.key_states = {}
        self.key_pressures = {}
        self.key_velocities = {}
        self.key_pitch_bends = {}
        self.base_root_note = 60  # MIDI note number for C4
        self.transposition = 0
        self.octave_shift = 0
        self.note_mapping = self._generate_note_mapping()
        self.instrument = None

    def set_instrument(self, instrument):
        self.instrument = instrument

    def set_octave(self, octave):
        self.octave_shift = octave
        self.note_mapping = self._generate_note_mapping()

    def process_key_changes(self, changed_keys, instrument_config):
        midi_events = []
        midi_config = instrument_config.get('midi', {})
        velocity_sensitivity = midi_config.get('velocity_sensitivity', 1.0)
        pitch_bend_config = instrument_config.get('pitch_bend', {'enabled': False})
        
        for key_id, left, right in changed_keys:
            avg_pressure = (left + right) / 2
            pressure = max(left, right)
            self.key_pressures[key_id] = pressure

            if pressure > 0.01:  # KEY_PRESS_THRESHOLD from constants
                velocity = int(avg_pressure * 127 * velocity_sensitivity)
                midi_events.extend(self._handle_key_press(key_id, velocity))
                
                if pitch_bend_config['enabled']:
                    pitch_bend = self.calculate_pitch_bend(left, right, pitch_bend_config)
                    self.key_pitch_bends[key_id] = pitch_bend
                    midi_events.append(('pitch_bend', key_id, self._convert_to_midi_pitch_bend(pitch_bend)))
            else:
                midi_events.extend(self._handle_key_release(key_id))
                if key_id in self.key_pitch_bends:
                    del self.key_pitch_bends[key_id]

        return midi_events

    def _generate_note_mapping(self):
        return [self.base_root_note + self.transposition + self.octave_shift * 12 + interval 
                for interval in range(1, 26)]  # SCALE_INTERVALS from constants

    def calculate_pitch_bend(self, left, right, pitch_bend_config):
        pressure_diff = right - left
        max_pressure = max(left, right)
        if max_pressure == 0:
            return 0
        
        linear_bend = pressure_diff / max_pressure
        
        # Apply quadratic curve
        curve_factor = pitch_bend_config.get('curve', 2)
        quadratic_bend = math.copysign(1, linear_bend) * (linear_bend ** 2) * curve_factor
        
        # Scale to pitch bend range
        bend_range = pitch_bend_config.get('range', 2)
        scaled_bend = quadratic_bend * (bend_range / 2)
        
        return max(-1, min(1, scaled_bend))

    def _convert_to_midi_pitch_bend(self, normalized_bend):
        return int((normalized_bend + 1) * 8191.5)

    def _handle_key_press(self, key_id, velocity):
        events = []
        midi_note = self._get_midi_note(key_id)
        if key_id not in self.key_states or not self.key_states[key_id]:
            self.key_velocities[key_id] = velocity
            events.append(('note_on', midi_note, velocity, key_id))
            self.key_states[key_id] = True
        else:
            events.append(('note_update', midi_note, self.key_velocities[key_id], key_id))
        
        return events

    def _handle_key_release(self, key_id):
        if key_id in self.key_states and self.key_states[key_id]:
            midi_note = self.note_mapping[key_id]
            self.key_states[key_id] = False
            del self.key_pressures[key_id]
            del self.key_velocities[key_id]
            return [('note_off', midi_note, 0, key_id)]
        return []

    def _get_midi_note(self, key_id):
        return self.note_mapping[key_id]

    def handle_octave_shift(self, direction):
        self.octave_shift -= direction
        self.note_mapping = self._generate_note_mapping()
        return self._generate_octave_shift_events()

    def _generate_octave_shift_events(self):
        events = []
        for key_id, is_pressed in self.key_states.items():
            if is_pressed:
                pressure = self.key_pressures[key_id]
                events.extend(self._handle_key_release(key_id))
                events.extend(self._handle_key_press(key_id, int(pressure * 127)))
        return events

    def get_pitch_bend(self, key_id):
        return self.key_pitch_bends.get(key_id, 0)
    
class MidiControlProcessor:
    def __init__(self):
        self.instrument = None

    def set_instrument(self, instrument):
        self.instrument = instrument

    def process_pot_changes(self, changed_pots, instrument_config):
        midi_events = []
        pots_config = instrument_config.get('pots', {})
        for pot_index, old_value, new_value in changed_pots:
            if pot_index in pots_config:
                cc_number = pots_config[pot_index]['cc']
                midi_value = int(new_value * 127)  # Scale to MIDI range
                midi_events.append(('control_change', cc_number, midi_value, new_value))
        return midi_events

    def get_envelope_settings(self):
        return self.envelope_settings

    def update_envelope_setting(self, param, value):
        if param in self.envelope_settings:
            self.envelope_settings[param] = value

    def process_control_change(self, cc_number, value):
        return [('control_change', cc_number, value, value/127)]
