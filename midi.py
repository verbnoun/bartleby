import board
import busio
import digitalio
import time
import math
import usb_midi

class MidiLogic:
    def __init__(self):
        self.note_processor = MidiNoteProcessor()
        self.control_processor = MidiControlProcessor()
        self.midi_out = usb_midi.ports[1]
        self.last_pitch_bend = {}  # Store last pitch bend value for each key

    def process_pot_changes(self, changed_pots, _):  # _ for unused config
        """Convert pot changes to MIDI events"""
        midi_events = []
        for pot_index, old_value, new_value in changed_pots:
            midi_value = int(new_value * 127)  # Scale to MIDI range
            midi_events.append(('control_change', pot_index, midi_value, new_value))
        return midi_events

    def process_key_changes(self, changed_keys, _):  # _ for unused config
        """Process key changes into MIDI events"""
        return self.note_processor.process_key_changes(changed_keys)

    def handle_octave_shift(self, direction):
        """Handle octave shift and generate note updates"""
        return self.note_processor.handle_octave_shift(direction)

    def update(self, changed_keys, changed_pots, _):  # _ for unused config
        """Process all hardware changes into MIDI events"""
        midi_events = []
        midi_events.extend(self.process_key_changes(changed_keys, None))
        midi_events.extend(self.process_pot_changes(changed_pots, None))
        return midi_events

    def send_midi_event(self, event):
        """Send single MIDI event via USB"""
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

class MidiNoteProcessor:
    """Handles note processing and octave management"""
    def __init__(self):
        self.note_states = {}  # Tracks active notes and their velocities
        self.key_pressures = {}  # Track key pressures
        self.octave_shift = 0
        self.base_root_note = 60  # Middle C
        
    def process_key_changes(self, changed_keys):
        """Process key changes into MIDI events"""
        midi_events = []
        
        for key_id, left, right in changed_keys:
            avg_pressure = (left + right) / 2
            
            if avg_pressure > 0.01:  # Key pressed/held
                midi_note = self.base_root_note + self.octave_shift * 12 + key_id
                velocity = int(avg_pressure * 127)
                
                if key_id not in self.note_states or not self.note_states[key_id]:
                    # Note On
                    midi_events.append(('note_on', midi_note, velocity, key_id))
                    self.note_states[key_id] = True
                    
            elif key_id in self.note_states and self.note_states[key_id]:
                # Note Off
                midi_note = self.base_root_note + self.octave_shift * 12 + key_id
                midi_events.append(('note_off', midi_note, 0, key_id))
                self.note_states[key_id] = False
                
        return midi_events

    def handle_octave_shift(self, direction):
        """Handle octave shift and generate note updates"""
        midi_events = []
        self.octave_shift = max(-2, min(2, self.octave_shift + direction))
        
        # Update any currently pressed notes
        for key_id, is_pressed in self.note_states.items():
            if is_pressed:
                old_note = self.base_root_note + (self.octave_shift - direction) * 12 + key_id
                new_note = self.base_root_note + self.octave_shift * 12 + key_id
                
                # Send note off for old note
                midi_events.append(('note_off', old_note, 0, key_id))
                # Send note on for new note
                midi_events.append(('note_on', new_note, 64, key_id))  # Default to middle velocity
                
        return midi_events
    
class MidiControlProcessor:
    """Handles MIDI control change processing"""
    def __init__(self):
        pass  # No initialization needed after removing instrument-specific logic

    def process_pot_changes(self, changed_pots):
        """Convert pot changes to MIDI CC events"""
        midi_events = []
        for pot_index, old_value, new_value in changed_pots:
            midi_value = int(new_value * 127)  # Scale to MIDI range
            midi_events.append(('control_change', pot_index, midi_value, new_value))
        return midi_events

    def process_control_change(self, cc_number, value):
        """Process a single control change"""
        return [('control_change', cc_number, value, value/127)]