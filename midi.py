import time
import usb_midi
import busio
from collections import deque

class Constants:
    DEBUG = False
    # MIDI Transport Settings
    MIDI_BAUDRATE = 31250
    UART_TIMEOUT = 0.001
    
    # MPE Configuration
    ZONE_MANAGER = 0           # MIDI channel 1 (zero-based) - aligned with Candide naming
    ZONE_START = 1            # MIDI channel 2 (zero-based)
    ZONE_END = 15            # MIDI channel 16 (15 member channels)

    # MIDI CC Numbers - Standard Controls
    CC_MODULATION = 1
    CC_VOLUME = 7
    CC_FILTER_RESONANCE = 71
    CC_RELEASE_TIME = 72
    CC_ATTACK_TIME = 73
    CC_TIMBRE = 74             # MPE Y-axis expression
    CC_DECAY_TIME = 75
    CC_SUSTAIN_LEVEL = 76
    
    # MIDI RPN Messages
    RPN_MSB = 0
    RPN_LSB_MPE = 6
    RPN_LSB_PITCH = 0
    
    # MIDI Pitch Bend
    PITCH_BEND_CENTER = 8192
    PITCH_BEND_MAX = 16383
    
    # Note Management
    MAX_ACTIVE_NOTES = 15       # Maximum concurrent notes (matches available channels)
    
    # MPE Settings
    MPE_MEMBER_PITCH_BEND_RANGE = 48   # 48 semitones for Member Channels
    MPE_MASTER_PITCH_BEND_RANGE = 2    # 2 semitones for Manager Channel

    # Default CC Assignments for Pots
    DEFAULT_CC_ASSIGNMENTS = {
        0: CC_TIMBRE,           # Pot 0: Timbre (CC74)
        1: CC_FILTER_RESONANCE, # Pot 1: Filter Resonance
        2: CC_ATTACK_TIME,      # Pot 2: Attack
        3: CC_DECAY_TIME,       # Pot 3: Decay
        4: CC_SUSTAIN_LEVEL,    # Pot 4: Sustain
        5: CC_RELEASE_TIME,     # Pot 5: Release
        6: CC_VOLUME,           # Pot 6: Volume
        7: CC_MODULATION,       # Pot 7: Modulation
        8: 20,                  # Pot 8: Unassigned (CC20)
        9: 21,                  # Pot 9: Unassigned (CC21)
        10: 22,                 # Pot 10: Unassigned (CC22)
        11: 23,                 # Pot 11: Unassigned (CC23)
        12: 24,                 # Pot 12: Unassigned (CC24)
        13: 25,                 # Pot 13: Unassigned (CC25)
    }

    # MPE Expression Dimensions
    TIMBRE_CENTER = 64         # Center value for CC74 Y-axis

class MidiTransportManager:
    """Manages both UART and USB MIDI output streams"""
    def __init__(self, tx_pin, rx_pin, midi_callback=None):
        if Constants.DEBUG:
            print("Initializing MIDI Transport Manager")
        self.midi_callback = midi_callback
        self._setup_uart(tx_pin, rx_pin)
        self._setup_usb()
        
    def _setup_uart(self, tx_pin, rx_pin):
        """Initialize UART for MIDI communication"""
        try:
            self.uart = busio.UART(
                tx=tx_pin,
                rx=rx_pin,
                baudrate=Constants.MIDI_BAUDRATE,
                bits=8,
                parity=None,
                stop=1,
                timeout=Constants.UART_TIMEOUT
            )
            if Constants.DEBUG:
                print(f"UART MIDI initialized on TX:{tx_pin}, RX:{rx_pin}")
        except Exception as e:
            print(f"UART initialization error on pins TX:{tx_pin}, RX:{rx_pin} - {str(e)}")
            raise

    def _setup_usb(self):
        """Initialize USB MIDI output"""
        try:
            self.usb_midi = usb_midi.ports[1]
            if Constants.DEBUG:
                print("USB MIDI initialized on port 1")
        except Exception as e:
            print(f"USB MIDI initialization error on port 1 - {str(e)}")
            raise

    def send_message(self, message):
        """Send MIDI message to both UART and USB outputs"""
        try:
            self.uart.write(bytes(message))
            self.usb_midi.write(bytes(message))
        except Exception as e:
            if str(e):
                print(f"Error sending MIDI message {message.hex() if hasattr(message, 'hex') else message}: {str(e)}")

    def cleanup(self):
        """Clean shutdown of MIDI transport"""
        try:
            self.uart.deinit()
            if Constants.DEBUG:
                print("MIDI transport cleaned up successfully")
        except Exception as e:
            if str(e):
                print(f"Error during MIDI transport cleanup: {str(e)}")

class ControllerManager:  # Renamed from CCConfigManager for clarity
    """Manages controller assignments and configuration for pots"""
    def __init__(self):
        self.controller_assignments = Constants.DEFAULT_CC_ASSIGNMENTS.copy()

    def reset_to_defaults(self):
        """Reset all controller assignments to default values"""
        self.controller_assignments = Constants.DEFAULT_CC_ASSIGNMENTS.copy()
        if Constants.DEBUG:
            print("Controller assignments reset to defaults")

    def get_controller_for_pot(self, pot_number):  # Renamed from get_cc_for_pot
        """Get the controller number assigned to a pot"""
        return self.controller_assignments.get(pot_number, pot_number)

    def handle_config_message(self, message):  # Renamed from parse_config_message to match Candide style
        """Handle configuration message from Candide
        Format: cc:0=74,1=71,2=73
        Returns True if successful, False if invalid format
        """
        try:
            if not message.startswith("cc:"):
                return False

            assignments = message[3:].split(',')
            for assignment in assignments:
                if '=' not in assignment:
                    continue
                pot, cc = assignment.split('=')
                pot_num = int(pot)
                cc_num = int(cc)
                if 0 <= pot_num <= 13 and 0 <= cc_num <= 127:
                    self.controller_assignments[pot_num] = cc_num
                    if Constants.DEBUG:
                        print(f"Assigned Pot {pot_num} to CC {cc_num}")

            return True

        except Exception as e:
            print(f"Error parsing controller config: {str(e)}")
            return False

class NoteState:
    """Memory-efficient note state tracking for CircuitPython with active state tracking"""
    __slots__ = ['key_id', 'midi_note', 'channel', 'velocity', 'timestamp', 
                 'pressure', 'pitch_bend', 'timbre', 'active']
    
    def __init__(self, key_id, midi_note, channel, velocity):
        self.key_id = key_id
        self.midi_note = midi_note
        self.channel = channel
        self.velocity = velocity
        self.timestamp = time.monotonic()
        self.pressure = 0
        self.pitch_bend = Constants.PITCH_BEND_CENTER
        self.timbre = Constants.TIMBRE_CENTER
        self.active = True

class ZoneManager:  # Renamed from MPEChannelManager to align with Candide
    def __init__(self):
        self.active_notes = {}
        self.channel_notes = {}  # NEW: channel to set of key_ids mapping
        self.available_channels = list(range(
            Constants.ZONE_START, 
            Constants.ZONE_END + 1
        ))

    def allocate_channel(self, key_id):
        """Get next available channel using robust allocation strategy"""
        # 1. Check if note already has an active channel
        if key_id in self.active_notes and self.active_notes[key_id].active:
            return self.active_notes[key_id].channel

        # 2. Find completely free channel first
        for channel in self.available_channels:
            if channel not in self.channel_notes or not self.channel_notes[channel]:
                if Constants.DEBUG:
                    print(f"Allocated free channel {channel} for key {key_id}")
                return channel

        # 3. If no free channels, find channel with fewest active notes
        min_notes = float('inf')
        best_channel = None
        
        for channel in self.available_channels:
            note_count = len(self.channel_notes.get(channel, set()))
            if note_count < min_notes:
                min_notes = note_count
                best_channel = channel

        if best_channel is not None:
            if Constants.DEBUG:
                print(f"Allocated least used channel {best_channel} for key {key_id}")
            return best_channel

        # 4. Fallback to first channel if all else fails
        if Constants.DEBUG:
            print(f"No optimal channels available, using first MPE channel for key {key_id}")
        return Constants.ZONE_START

    def add_note(self, key_id, midi_note, channel, velocity):
        """Add new note and track its channel allocation"""
        note_state = NoteState(key_id, midi_note, channel, velocity)
        self.active_notes[key_id] = note_state
        
        # Track channel usage
        if channel not in self.channel_notes:
            self.channel_notes[channel] = set()
        self.channel_notes[channel].add(key_id)
        
        if Constants.DEBUG:
            print(f"Added note: key={key_id}, note={midi_note}, channel={channel}, velocity={velocity}")
        return note_state

    def _release_note(self, key_id):
        """Internal method to handle note release and cleanup"""
        if key_id in self.active_notes:
            note_state = self.active_notes[key_id]
            note_state.active = False
            channel = note_state.channel
            
            # Clean up channel tracking
            if channel in self.channel_notes:
                self.channel_notes[channel].discard(key_id)
                if Constants.DEBUG:
                    print(f"Released channel {channel} from key {key_id}")

    def release_note(self, key_id):
        self._release_note(key_id)

    def get_note_state(self, key_id):
        note_state = self.active_notes.get(key_id)
        return note_state if note_state and note_state.active else None

    def get_active_notes(self):
        return [note for note in self.active_notes.values() if note.active]

class MPENoteProcessor:
    """Memory-efficient MPE note processing for CircuitPython"""
    def __init__(self, channel_manager):
        self.channel_manager = channel_manager
        self.octave_shift = 0
        self.base_root_note = 60  # Middle C
        self.active_notes = set()

    def process_key_changes(self, changed_keys, config):
        midi_events = []
        
        for key_id, position, pressure, strike_velocity in changed_keys:
            note_state = self.channel_manager.get_note_state(key_id)
            
            if pressure > 0.01:  # Key is active
                midi_note = self.base_root_note + self.octave_shift * 12 + key_id
                
                if not note_state:  # New note
                    velocity = int(strike_velocity * 127) if strike_velocity is not None else int(pressure * 127)
                    # Proper MPE order: CC74 → Pressure → Pitch Bend → Note On
                    midi_events.extend([
                        ('timbre_init', key_id),           # Y-axis
                        ('pressure_init', key_id, pressure),  # Z-axis
                        ('pitch_bend_init', key_id, position),  # X-axis
                        ('note_on', midi_note, velocity, key_id)
                    ])
                    self.active_notes.add(key_id)
                    if Constants.DEBUG:
                        print(f"New note: key={key_id}, note={midi_note}, velocity={velocity}")
                
                elif note_state.active:
                    midi_events.extend([
                        ('timbre_update', key_id, position),  # Using position for timbre calculation
                        ('pressure_update', key_id, pressure),
                        ('pitch_bend_update', key_id, position)
                    ])
                
            else:  # Key released
                if key_id in self.active_notes and note_state and note_state.active:
                    midi_note = note_state.midi_note
                    midi_events.extend([
                        ('pressure_update', key_id, 0),  # Final pressure of 0
                        ('note_off', midi_note, 0, key_id)
                    ])
                    self.active_notes.remove(key_id)
                    if Constants.DEBUG:
                        print(f"Note off: key={key_id}, note={midi_note}")

        return midi_events

    def handle_octave_shift(self, direction):
        midi_events = []
        new_octave = max(-2, min(2, self.octave_shift + direction))
        
        if new_octave != self.octave_shift:
            if Constants.DEBUG:
                print(f"Octave shift: {self.octave_shift} -> {new_octave}")
            self.octave_shift = new_octave
            
            for note_state in self.channel_manager.get_active_notes():
                old_note = note_state.midi_note
                new_note = self.base_root_note + self.octave_shift * 12 + note_state.key_id
                
                # Use stored values from note_state
                position = (note_state.pitch_bend - Constants.PITCH_BEND_CENTER) / (Constants.PITCH_BEND_MAX / 2)
                
                midi_events.extend([
                    ('timbre_init', note_state.key_id),
                    ('pressure_init', note_state.key_id, note_state.pressure),
                    ('pitch_bend_init', note_state.key_id, position),
                    ('note_off', old_note, 0, note_state.key_id),
                    ('note_on', new_note, note_state.velocity, note_state.key_id)
                ])
                
                if note_state.active and note_state.pressure > 0:
                    midi_events.extend([
                        ('timbre_update', note_state.key_id, position),
                        ('pressure_update', note_state.key_id, note_state.pressure),
                        ('pitch_bend_update', note_state.key_id, position)
                    ])
            
        return midi_events

class MidiControlProcessor:
    """Handles MIDI control change processing with configurable assignments"""
    def __init__(self):
        self.controller_config = ControllerManager()  # Updated to new name

    def process_controller_changes(self, changed_pots):  # Renamed from process_pot_changes
        """Process controller changes and generate MIDI events"""
        midi_events = []
        for pot_index, old_value, new_value in changed_pots:
            controller_number = self.controller_config.get_controller_for_pot(pot_index)  # Updated method name
            midi_value = int(new_value * 127)
            midi_events.append(('control_change', controller_number, midi_value))
            if Constants.DEBUG:
                print(f"Controller {pot_index} changed: CC{controller_number}={midi_value}")
        return midi_events

    def handle_config_message(self, message):
        """Process configuration message from Candide"""
        return self.controller_config.handle_config_message(message)

    def reset_to_defaults(self):
        """Reset controller assignments to defaults"""
        self.controller_config.reset_to_defaults()

class MPEConfigurator:
    """Handles MPE-specific configuration and setup"""
    def __init__(self, message_sender):
        self.message_sender = message_sender

    def configure_mpe(self):
        """Configure MPE zones and pitch bend ranges"""
        if Constants.DEBUG:
            print("Configuring MPE zones and pitch bend ranges")
            
        # Reset all channels first
        self.message_sender.send_message([0xB0, 121, 0])  # Reset all controllers
        self.message_sender.send_message([0xB0, 123, 0])  # All notes off
        
        # Configure MPE zone (RPN 6)
        self.message_sender.send_message([0xB0, 101, 0])  # RPN MSB
        self.message_sender.send_message([0xB0, 100, 6])  # RPN LSB (MCM)
        zone_size = Constants.ZONE_END - Constants.ZONE_START + 1
        self.message_sender.send_message([0xB0, 6, zone_size])
        if Constants.DEBUG:
            print(f"MPE zone configured: {zone_size} channels")
        
        # Configure Manager Channel pitch bend range
        self.message_sender.send_message([0xB0, 101, 0])  # RPN MSB
        self.message_sender.send_message([0xB0, 100, 0])  # RPN LSB (pitch bend)
        self.message_sender.send_message([0xB0, 6, Constants.MPE_MASTER_PITCH_BEND_RANGE])
        if Constants.DEBUG:
            print(f"Manager channel pitch bend range: {Constants.MPE_MASTER_PITCH_BEND_RANGE} semitones")
        
        # Configure Member Channel pitch bend range
        for channel in range(Constants.ZONE_START, Constants.ZONE_END + 1):
            self.message_sender.send_message([0xB0 | channel, 101, 0])  # RPN MSB
            self.message_sender.send_message([0xB0 | channel, 100, 0])  # RPN LSB (pitch bend)
            self.message_sender.send_message([0xB0 | channel, 6, Constants.MPE_MEMBER_PITCH_BEND_RANGE])
        if Constants.DEBUG:
            print(f"Member channels pitch bend range: {Constants.MPE_MEMBER_PITCH_BEND_RANGE} semitones")

class MidiMessageSender:
    """Handles the actual sending of MIDI messages"""
    def __init__(self, transport):
        self.transport = transport
        self.ready_for_midi = False

    def send_message(self, message):
        """Send a MIDI message if the system is ready or it's a system message"""
        if self.ready_for_midi or message[0] & 0xF0 in (0xB0, 0xF0) or not self.ready_for_midi:
            self.transport.send_message(message)

    def set_ready(self, ready):
        self.ready_for_midi = ready
        if Constants.DEBUG and ready:
            print("MIDI message sender ready")

class MidiSystemInitializer:
    """Handles system initialization and greeting sequence"""
    def __init__(self, message_sender, channel_manager):
        self.message_sender = message_sender
        self.channel_manager = channel_manager

    def play_greeting(self):
        """Play greeting chime using MPE"""
        if Constants.DEBUG:
            print("Playing MPE greeting sequence")
            
        base_key_id = -1
        base_pressure = 0.75
        
        greeting_notes = [60, 64, 67, 72]
        velocities = [0.6, 0.7, 0.8, 0.9]
        durations = [0.2, 0.2, 0.2, 0.4]
        
        for idx, (note, velocity, duration) in enumerate(zip(greeting_notes, velocities, durations)):
            key_id = base_key_id - idx
            channel = self.channel_manager.allocate_channel(key_id)
            note_state = self.channel_manager.add_note(key_id, note, channel, int(velocity * 127))
            
            # Send in MPE order: CC74 → Pressure → Pitch Bend → Note On
            self.message_sender.send_message([0xB0 | channel, Constants.CC_TIMBRE, Constants.TIMBRE_CENTER])
            self.message_sender.send_message([0xD0 | channel, int(base_pressure * 127)])
            self.message_sender.send_message([0xE0 | channel, 0x00, 0x40])  # Center pitch bend
            self.message_sender.send_message([0x90 | channel, note, int(velocity * 127)])
            
            time.sleep(duration)
            
            self.message_sender.send_message([0xD0 | channel, 0])  # Zero pressure
            self.message_sender.send_message([0x80 | channel, note, 0])
            self.channel_manager.release_note(key_id)
            
            time.sleep(0.05)

class MidiEventRouter:
    """Routes and processes MIDI events"""
    def __init__(self, message_sender, channel_manager):
        self.message_sender = message_sender
        self.channel_manager = channel_manager

    def handle_event(self, event):  # Renamed from route_event to match Candide style
        """Handle a MIDI event"""
        if not self.message_sender.ready_for_midi:
            return
            
        event_type = event[0]
        params = event[1:]
        
        if event_type == 'timbre_init':
            self._handle_timbre_init(*params)
        elif event_type == 'timbre_update':
            self._handle_timbre_update(*params)
        elif event_type == 'pressure_init':
            self._handle_pressure_init(*params)
        elif event_type == 'pressure_update':
            self._handle_pressure_update(*params)
        elif event_type == 'pitch_bend_init':
            self._handle_pitch_bend_init(*params)
        elif event_type == 'pitch_bend_update':
            self._handle_pitch_bend_update(*params)
        elif event_type == 'note_on':
            self._handle_note_on(*params)
        elif event_type == 'note_off':
            self._handle_note_off(*params)
        elif event_type == 'control_change':
            self._handle_control_change(*params)

    def _handle_timbre_init(self, key_id):
        channel = self.channel_manager.allocate_channel(key_id)
        self.message_sender.send_message([0xB0 | channel, Constants.CC_TIMBRE, Constants.TIMBRE_CENTER])

    def _handle_timbre_update(self, key_id, position):
        note_state = self.channel_manager.get_note_state(key_id)
        if note_state:
            # Map position (-1 to 1) to timbre range (0 to 127)
            timbre_value = int((position + 1) * 63.5)
            self.message_sender.send_message([0xB0 | note_state.channel, Constants.CC_TIMBRE, timbre_value])
            note_state.timbre = timbre_value

    def _handle_pressure_init(self, key_id, pressure):
        channel = self.channel_manager.allocate_channel(key_id)
        pressure_value = int(pressure * 127)
        self.message_sender.send_message([0xD0 | channel, pressure_value])

    def _handle_pressure_update(self, key_id, pressure):
        note_state = self.channel_manager.get_note_state(key_id)
        if note_state:
            pressure_value = int(pressure * 127)
            self.message_sender.send_message([0xD0 | note_state.channel, pressure_value])
            note_state.pressure = pressure

    def _handle_pitch_bend_init(self, key_id, position):
        channel = self.channel_manager.allocate_channel(key_id)
        bend_value = self._calculate_pitch_bend(position)
        lsb = bend_value & 0x7F
        msb = (bend_value >> 7) & 0x7F
        self.message_sender.send_message([0xE0 | channel, lsb, msb])

    def _handle_pitch_bend_update(self, key_id, position):
        note_state = self.channel_manager.get_note_state(key_id)
        if note_state:
            bend_value = self._calculate_pitch_bend(position)
            lsb = bend_value & 0x7F
            msb = (bend_value >> 7) & 0x7F
            self.message_sender.send_message([0xE0 | note_state.channel, lsb, msb])
            note_state.pitch_bend = bend_value

    def _handle_note_on(self, midi_note, velocity, key_id):
        channel = self.channel_manager.allocate_channel(key_id)
        self.channel_manager.add_note(key_id, midi_note, channel, velocity)
        self.message_sender.send_message([0x90 | channel, int(midi_note), velocity])

    def _handle_note_off(self, midi_note, velocity, key_id):
        note_state = self.channel_manager.get_note_state(key_id)
        if note_state:
            self.message_sender.send_message([0x80 | note_state.channel, int(midi_note), velocity])
            self.channel_manager.release_note(key_id)

    def _handle_control_change(self, cc_number, midi_value):
        self.message_sender.send_message([0xB0 | Constants.ZONE_MANAGER, cc_number, midi_value])

    def _calculate_pitch_bend(self, position):
        """Calculate pitch bend value from position (-1 to 1)"""
        normalized = (position + 1) / 2  # Convert -1 to 1 range to 0 to 1
        return int(normalized * Constants.PITCH_BEND_MAX)

class MidiLogic:
    """Main MIDI logic coordinator class"""
    def __init__(self, midi_tx, midi_rx, midi_callback=None):
        # Initialize transport and message sender
        self.transport = MidiTransportManager(midi_tx, midi_rx, midi_callback)
        self.message_sender = MidiMessageSender(self.transport)
        
        # Initialize managers and processors
        self.channel_manager = ZoneManager()  # Updated to new name
        self.note_processor = MPENoteProcessor(self.channel_manager)
        self.control_processor = MidiControlProcessor()
        
        # Initialize specialized components
        self.mpe_configurator = MPEConfigurator(self.message_sender)
        self.system_initializer = MidiSystemInitializer(self.message_sender, self.channel_manager)
        self.event_router = MidiEventRouter(self.message_sender, self.channel_manager)
        
        # Configure system
        self._configure_system()

    def _configure_system(self):
        """Initialize system with MPE configuration and greeting sequence"""
        if Constants.DEBUG:
            print("\nInitializing MIDI system...")
        self.mpe_configurator.configure_mpe()
        self.system_initializer.play_greeting()
        self.message_sender.set_ready(True)
        if Constants.DEBUG:
            print("MIDI system initialization complete")

    def handle_config_message(self, message):
        return self.control_processor.handle_config_message(message)

    def reset_controller_defaults(self):  # Renamed from reset_cc_defaults
        self.control_processor.reset_to_defaults()

    def update(self, changed_keys, changed_pots, config):
        if not self.message_sender.ready_for_midi:
            return []
            
        midi_events = []
        
        if changed_keys:
            midi_events.extend(self.note_processor.process_key_changes(changed_keys, config))
        
        if changed_pots:
            midi_events.extend(self.control_processor.process_controller_changes(changed_pots))  # Updated method name
        
        for event in midi_events:
            self.event_router.handle_event(event)  # Updated method name
            
        return midi_events

    def handle_octave_shift(self, direction):
        if not self.message_sender.ready_for_midi:
            return []
        return self.note_processor.handle_octave_shift(direction)

    def reset_cc_defaults(self):
        pass

    def cleanup(self):
        if Constants.DEBUG:
            print("\nCleaning up MIDI system...")
        self.transport.cleanup()
        if Constants.DEBUG:
            print("MIDI system cleanup complete")
