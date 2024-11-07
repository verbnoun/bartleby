import time
import usb_midi
from collections import deque

class Constants:
    # MPE Configuration
    MPE_MASTER_CHANNEL = 0      # MIDI channel 1 (zero-based)
    MPE_ZONE_START = 1          # MIDI channel 2 (zero-based)
    MPE_ZONE_END = 11           # MIDI channel 15 (leaving channel 16 free per MPE spec)

    # MIDI CC Numbers
    CC_LEFT_PRESSURE = 78       # Left sensor pressure
    CC_RIGHT_PRESSURE = 79      # Right sensor pressure
    CC_CHANNEL_PRESSURE = 74    # Standard MPE channel pressure
    
    # MIDI RPN Messages
    RPN_MSB = 0
    RPN_LSB_MPE = 6
    
    # MIDI Pitch Bend
    PITCH_BEND_CENTER = 8192
    PITCH_BEND_MAX = 16383
    
    # Note Management
    MAX_ACTIVE_NOTES = 14       # Maximum concurrent notes (matches available MPE channels)
    
    # MPE Settings
    MPE_PITCH_BEND_RANGE = 48   # Default to 48 semitones for MPE
    
    # Debug
    DEBUG = True

class NoteState:
    """Memory-efficient note state tracking for CircuitPython"""
    __slots__ = ['key_id', 'midi_note', 'channel', 'velocity', 'timestamp', 
                 'left_pressure', 'right_pressure', 'pitch_bend']
    
    def __init__(self, key_id, midi_note, channel, velocity):
        self.key_id = key_id
        self.midi_note = midi_note
        self.channel = channel
        self.velocity = velocity
        self.timestamp = time.monotonic()
        self.left_pressure = 0
        self.right_pressure = 0
        self.pitch_bend = Constants.PITCH_BEND_CENTER

class MPEChannelManager:
    def __init__(self):
        self.active_notes = {}
        self.note_queue = deque((), Constants.MAX_ACTIVE_NOTES)  # Use positional args instead
        self.available_channels = list(range(
            Constants.MPE_ZONE_START, 
            Constants.MPE_ZONE_END + 1
        ))

    def allocate_channel(self, key_id):
        if key_id in self.active_notes:
            return self.active_notes[key_id].channel

        if self.available_channels:
            return self.available_channels.pop(0)
            
        # Steal channel from oldest note if queue not empty
        if len(self.note_queue):
            oldest_key_id = self.note_queue.popleft()  # Use popleft for FIFO behavior
            channel = self.active_notes[oldest_key_id].channel
            self._release_note(oldest_key_id)
            return channel
            
        return Constants.MPE_ZONE_START  # Fallback

    def add_note(self, key_id, midi_note, channel, velocity):
        note_state = NoteState(key_id, midi_note, channel, velocity)
        self.active_notes[key_id] = note_state
        self.note_queue.append(key_id)  # Queue will automatically maintain its size
        return note_state

    def _release_note(self, key_id):
        if key_id in self.active_notes:
            note_state = self.active_notes[key_id]
            channel = note_state.channel
            if channel not in self.available_channels:
                self.available_channels.append(channel)
            del self.active_notes[key_id]

    def release_note(self, key_id):
        self._release_note(key_id)

    def get_note_state(self, key_id):
        return self.active_notes.get(key_id)

    def get_active_notes(self):
        return list(self.active_notes.values())

class MPENoteProcessor:
    """Memory-efficient MPE note processing for CircuitPython"""
    def __init__(self, channel_manager):
        self.channel_manager = channel_manager
        self.octave_shift = 0
        self.base_root_note = 60  # Middle C
        self.active_notes = set()  # Using set for O(1) lookups

    def process_key_changes(self, changed_keys, config):
        midi_events = []
        
        for key_id, left, right in changed_keys:
            avg_pressure = (left + right) / 2
            
            if avg_pressure > 0.01:  # Key is active
                note_state = self.channel_manager.get_note_state(key_id)
                midi_note = self.base_root_note + self.octave_shift * 12 + key_id
                
                if not note_state:  # New note
                    velocity = int(avg_pressure * 127)
                    midi_events.append(('note_on', midi_note, velocity, key_id))
                    self.active_notes.add(key_id)
                
                # Always send pressure updates for active notes
                midi_events.append(('pressure_update', key_id, left, right))
                
            else:  # Key released
                if key_id in self.active_notes:
                    note_state = self.channel_manager.get_note_state(key_id)
                    if note_state:
                        midi_note = note_state.midi_note
                        midi_events.append(('note_off', midi_note, 0, key_id))
                        self.active_notes.remove(key_id)

        return midi_events

    def handle_octave_shift(self, direction):
        midi_events = []
        new_octave = max(-2, min(2, self.octave_shift + direction))
        
        if new_octave != self.octave_shift:
            self.octave_shift = new_octave
            
            for note_state in self.channel_manager.get_active_notes():
                old_note = note_state.midi_note
                new_note = self.base_root_note + self.octave_shift * 12 + note_state.key_id
                
                midi_events.append(('note_off', old_note, 0, note_state.key_id))
                midi_events.append(('note_on', new_note, note_state.velocity, note_state.key_id))
                
                if note_state.left_pressure > 0 or note_state.right_pressure > 0:
                    midi_events.append((
                        'pressure_update',
                        note_state.key_id,
                        note_state.left_pressure,
                        note_state.right_pressure
                    ))
            
        return midi_events

class MidiControlProcessor:
    """Handles MIDI control change processing"""
    def __init__(self):
        pass

    def process_pot_changes(self, changed_pots):
        midi_events = []
        for pot_index, old_value, new_value in changed_pots:
            midi_value = int(new_value * 127)
            midi_events.append(('control_change', pot_index, midi_value, new_value))
        return midi_events

class MidiLogic:
    def __init__(self):
        self.channel_manager = MPEChannelManager()
        self.note_processor = MPENoteProcessor(self.channel_manager)
        self.control_processor = MidiControlProcessor()
        self.midi_out = usb_midi.ports[1]
        self.configure_mpe()

    def configure_mpe(self):
        """Send MPE configuration messages"""
        # Reset all channels
        self._send_message(0xB0, 121, 0)  # Reset all controllers
        self._send_message(0xB0, 123, 0)  # All notes off
        
        # Configure MPE zone
        self._send_message(0xB0, 101, Constants.RPN_MSB)       # RPN MSB
        self._send_message(0xB0, 100, Constants.RPN_LSB_MPE)   # RPN LSB (MCM message)
        self._send_message(0xB0, 6, Constants.MPE_ZONE_END)    # Number of member channels
        
        # Configure pitch bend range
        self._send_message(0xB0, 101, 0)  # RPN MSB
        self._send_message(0xB0, 100, 0)  # RPN LSB (pitch bend range)
        self._send_message(0xB0, 6, Constants.MPE_PITCH_BEND_RANGE)  # Set pitch bend range
        self._send_message(0xB0, 38, 0)   # LSB (always 0 for pitch bend range)

    def process_pot_changes(self, changed_pots, _):
        return self.control_processor.process_pot_changes(changed_pots)

    def process_key_changes(self, changed_keys, config):
        return self.note_processor.process_key_changes(changed_keys, config)  # Removed second argument

    def handle_octave_shift(self, direction):
        return self.note_processor.handle_octave_shift(direction)

    def update(self, changed_keys, changed_pots, config):
        midi_events = []
        if changed_keys:
            midi_events.extend(self.process_key_changes(changed_keys, config))
        if changed_pots:
            midi_events.extend(self.process_pot_changes(changed_pots, None))
        return midi_events

    def _send_message(self, status, data1, data2):
        """Send raw MIDI message"""
        self.midi_out.write(bytes([status, data1, data2]))

    def send_midi_event(self, event):
        """Send MIDI event via USB"""
        event_type = event[0]
        params = event[1:]
        
        if event_type == 'note_on':
            midi_note, velocity, key_id = params
            channel = self.channel_manager.allocate_channel(key_id)
            note_state = self.channel_manager.add_note(key_id, midi_note, channel, velocity)
            if Constants.DEBUG:
                print(f"\nKey {key_id} MIDI Events:")
                print(f"  Note ON:")
                print(f"    Channel: {channel + 1}")  # Display 1-based channel
                print(f"    Note: {midi_note}")
                print(f"    Velocity: {velocity}")
            self._send_message(0x90 | channel, int(midi_note), velocity)
                
        elif event_type == 'note_off':
            midi_note, velocity, key_id = params
            note_state = self.channel_manager.get_note_state(key_id)
            if note_state:
                if Constants.DEBUG:
                    print(f"\nKey {key_id} MIDI Events:")
                    print(f"  Note OFF:")
                    print(f"    Channel: {note_state.channel + 1}")  # Display 1-based channel
                    print(f"    Note: {midi_note}")
                self._send_message(0x80 | note_state.channel, int(midi_note), velocity)
                self.channel_manager.release_note(key_id)
                    
        elif event_type == 'pressure_update':
            key_id, left, right = params
            note_state = self.channel_manager.get_note_state(key_id)
            if note_state:
                # Calculate and store average pressure
                avg_pressure = (left + right) / 2
                channel_pressure = int(avg_pressure * 127)
                
                # Calculate pitch bend
                bend_value = self._calculate_pitch_bend(left, right)
                lsb = bend_value & 0x7F
                msb = (bend_value >> 7) & 0x7F
                normalized_bend = (bend_value - Constants.PITCH_BEND_CENTER) / Constants.PITCH_BEND_CENTER
                
                if Constants.DEBUG:
                    print(f"\nKey {key_id} MIDI Events:")
                    print(f"  Hardware Values:")
                    print(f"    Left Pressure: {left:.3f}")
                    print(f"    Right Pressure: {right:.3f}")
                    print(f"  MIDI Updates:")
                    print(f"    Channel: {note_state.channel + 1}")  # Display 1-based channel
                    print(f"    Pressure: {channel_pressure}")
                    print(f"    Pitch Bend: {normalized_bend:+.3f}")
                
                # Send MPE channel pressure
                self._send_message(0xB0 | note_state.channel, Constants.CC_CHANNEL_PRESSURE, channel_pressure)
                
                # Send pitch bend
                self._send_message(0xE0 | note_state.channel, lsb, msb)
                
                # Store pressure values
                note_state.left_pressure = left
                note_state.right_pressure = right
                    
        elif event_type == 'control_change':
            cc_number, midi_value, _ = params
            if Constants.DEBUG:
                print(f"\nControl Change:")
                print(f"  CC Number: {cc_number}")
                print(f"  Value: {midi_value}")
            self._send_message(0xB0 | Constants.MPE_MASTER_CHANNEL, cc_number, midi_value)

    def _calculate_pitch_bend(self, left, right):
        """Calculate pitch bend value from left/right pressure differential"""
        diff = right - left  # Range: -1 to 1
        normalized = (diff + 1) / 2  # Range: 0 to 1
        return int(normalized * Constants.PITCH_BEND_MAX)
