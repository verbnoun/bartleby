import time
from constants import (
    DEBUG,
    VELOCITY_DELAY,
    PRESSURE_HISTORY_SIZE,
    RELEASE_VELOCITY_THRESHOLD,
    PITCH_BEND_CENTER,
    PITCH_BEND_MAX,
    TIMBRE_CENTER
)

class NoteState:
    """Memory-efficient note state tracking for CircuitPython with active state tracking"""
    __slots__ = ['key_id', 'midi_note', 'channel', 'velocity', 'timestamp', 
                 'pressure', 'pitch_bend', 'timbre', 'active', 'activation_time',
                 'pressure_history', 'pressure_timestamps']
    
    def __init__(self, key_id, midi_note, channel, velocity):
        self.key_id = key_id
        self.midi_note = midi_note
        self.channel = channel
        self.velocity = velocity
        self.timestamp = time.monotonic()
        self.activation_time = self.timestamp
        self.pressure = 0
        self.pitch_bend = PITCH_BEND_CENTER
        self.timbre = TIMBRE_CENTER
        self.active = True
        self.pressure_history = []
        self.pressure_timestamps = []

    def update_pressure(self, pressure):
        """Update pressure history for release velocity calculation"""
        current_time = time.monotonic()
        self.pressure = pressure
        
        # Add new pressure reading with timestamp
        self.pressure_history.append(pressure)
        self.pressure_timestamps.append(current_time)
        
        # Keep only the most recent readings
        if len(self.pressure_history) > PRESSURE_HISTORY_SIZE:
            self.pressure_history.pop(0)
            self.pressure_timestamps.pop(0)

    def calculate_release_velocity(self):
        """Calculate release velocity based on pressure decay rate"""
        if len(self.pressure_history) < 2:
            return 0
            
        # Calculate average rate of change over the last few readings
        total_change = 0
        total_time = 0
        
        for i in range(1, len(self.pressure_history)):
            pressure_change = self.pressure_history[i] - self.pressure_history[i-1]
            time_change = self.pressure_timestamps[i] - self.pressure_timestamps[i-1]
            if time_change > 0:
                total_change += pressure_change
                total_time += time_change
        
        if total_time <= 0:
            return 0
            
        avg_decay_rate = abs(total_change / total_time)
        
        # Convert decay rate to MIDI velocity (0-127)
        if avg_decay_rate < RELEASE_VELOCITY_THRESHOLD:
            return 0
            
        # Scale the decay rate and apply curve for more natural response
        scaled_rate = avg_decay_rate * 2.0  # Double the rate to make it more sensitive
        velocity = min(127, int(scaled_rate * 127))
        
        if DEBUG:
            print(f"Release velocity calculation:")
            print(f"  Pressure history: {self.pressure_history}")
            print(f"  Average decay rate: {avg_decay_rate:.3f}")
            print(f"  Calculated velocity: {velocity}")
            
        return velocity

class MPENoteProcessor:
    """Memory-efficient MPE note processing for CircuitPython"""
    def __init__(self, channel_manager):
        self.channel_manager = channel_manager
        self.octave_shift = 0
        self.base_root_note = 60  # Middle C
        self.active_notes = set()
        self.pending_velocities = {}  # Store initial pressures for delayed velocity

    def process_key_changes(self, changed_keys, config):
        midi_events = []
        current_time = time.monotonic()
        
        for key_id, position, pressure, strike_velocity in changed_keys:
            note_state = self.channel_manager.get_note_state(key_id)
            
            if pressure > 0.01:  # Key is active
                midi_note = self.base_root_note + self.octave_shift * 12 + key_id
                
                if not note_state:  # New note
                    if key_id not in self.pending_velocities:
                        # Store initial pressure and time for delayed velocity calculation
                        self.pending_velocities[key_id] = {
                            'pressure': pressure,
                            'time': current_time,
                            'midi_note': midi_note,
                            'position': position
                        }
                    elif current_time - self.pending_velocities[key_id]['time'] >= VELOCITY_DELAY:
                        # Enough time has passed, use the current pressure as velocity
                        velocity = int(pressure * 127)
                        # Proper MPE order: Pressure → Pitch Bend → Note On
                        midi_events.extend([
                            ('pressure_init', key_id, pressure),  # Z-axis
                            ('pitch_bend_init', key_id, position),  # X-axis
                            ('note_on', midi_note, velocity, key_id)
                        ])
                        self.active_notes.add(key_id)
                        del self.pending_velocities[key_id]
                        if DEBUG:
                            print(f"New note: key={key_id}, note={midi_note}, velocity={velocity}")
                
                elif note_state.active:
                    note_state.update_pressure(pressure)
                    midi_events.extend([
                        ('pressure_update', key_id, pressure),
                        ('pitch_bend_update', key_id, position)
                    ])
                
            else:  # Key released
                if key_id in self.pending_velocities:
                    del self.pending_velocities[key_id]
                
                if key_id in self.active_notes and note_state and note_state.active:
                    midi_note = note_state.midi_note
                    release_velocity = note_state.calculate_release_velocity()
                    midi_events.extend([
                        ('pressure_update', key_id, 0),  # Final pressure of 0
                        ('note_off', midi_note, release_velocity, key_id)
                    ])
                    self.active_notes.remove(key_id)
                    if DEBUG:
                        print(f"Note off: key={key_id}, note={midi_note}, release_velocity={release_velocity}")

        return midi_events

    def handle_octave_shift(self, direction):
        midi_events = []
        # Changed from -2/+2 to -3/+3 to match hardware encoder range
        new_octave = max(-3, min(3, self.octave_shift + direction))
        
        if new_octave != self.octave_shift:
            if DEBUG:
                print(f"Octave shift: {self.octave_shift} -> {new_octave}")
            self.octave_shift = new_octave
            
            for note_state in self.channel_manager.get_active_notes():
                old_note = note_state.midi_note
                new_note = self.base_root_note + self.octave_shift * 12 + note_state.key_id
                
                # Use stored values from note_state
                position = (note_state.pitch_bend - PITCH_BEND_CENTER) / (PITCH_BEND_MAX / 2)
                
                midi_events.extend([
                    ('pressure_init', note_state.key_id, note_state.pressure),
                    ('pitch_bend_init', note_state.key_id, position),
                    ('note_off', old_note, 0, note_state.key_id),
                    ('note_on', new_note, note_state.velocity, note_state.key_id)
                ])
                
                if note_state.active and note_state.pressure > 0:
                    midi_events.extend([
                        ('pressure_update', note_state.key_id, note_state.pressure),
                        ('pitch_bend_update', note_state.key_id, position)
                    ])
            
        return midi_events
