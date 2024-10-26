import board
import math
import array
import time
import synthio
import audiobusio
import audiomixer
from hardware import (
    Multiplexer, KeyMultiplexer, RotaryEncoderHandler, 
    PotentiometerHandler, KeyboardHandler, Constants as HWConstants)
from instruments import Piano, ElectricOrgan, BendableOrgan, Instrument
from midi import MidiLogic 

class Constants:
    # System Constants
    DEBUG = False
    LOG_GLOBAL = True
    LOG_HARDWARE = True
    LOG_MIDI = True
    LOG_SYNTH = True
    LOG_MISC = True

    # Hardware Setup Delay
    SETUP_DELAY = 0.1
    
    # PCM5102A DAC Pins
    I2S_DATA = board.GP0
    I2S_BIT_CLOCK = board.GP1
    I2S_WORD_SELECT = board.GP2

    # Synthesizer Constants
    AUDIO_BUFFER_SIZE = 4096 #8,192
    SAMPLE_RATE = 44100

    # Scan Intervals (in seconds)
    POT_SCAN_INTERVAL = 0.02
    ENCODER_SCAN_INTERVAL = 0.001  # Fast scan for direct GPIO
    MAIN_LOOP_INTERVAL = 0.001
    

class SynthVoiceManager:
    def __init__(self):
        self.active_notes = {}  # Maps key_id to Note objects

    def allocate_voice(self, key_id, frequency, velocity, envelope, waveform):
        if key_id in self.active_notes:
            note = self.active_notes[key_id]
            note.frequency = frequency
            note.amplitude = velocity / 127.0
            note.envelope = envelope
            note.waveform = waveform
        else:
            note = synthio.Note(
                frequency=frequency,
                envelope=envelope,
                amplitude=velocity / 127.0,
                waveform=waveform
            )
            self.active_notes[key_id] = note
        
        return note

    def change_note_waveform(self, key_id, new_waveform):
        if key_id in self.active_notes:
            self.active_notes[key_id].waveform = new_waveform

    def release_voice(self, key_id):
        if key_id in self.active_notes:
            note = self.active_notes.pop(key_id)
            return note
        return None

    def get_note_by_key_id(self, key_id):
        return self.active_notes.get(key_id)

    def update_all_envelopes(self, new_envelope):
        for note in self.active_notes.values():
            note.envelope = new_envelope

    def release_all_voices(self):
        self.active_notes.clear()

    def get_active_note_count(self):
        return len(self.active_notes)
    
    def get_active_notes(self):
        return list(self.active_notes.values())


class SynthEngine:
    def __init__(self):
        self.lfos = []
        self.modulation_matrix = {}
        self.effects = []
        self.envelope_settings = {}
        self.instrument = None
        self.detune = 0
        self.filter = None
        self.waveforms = {}
        self.filter_config = {'type': 'low_pass', 'cutoff': 1000, 'resonance': 0.5}
        self.current_waveform = 'sine'
        self.pitch_bend_enabled = False
        self.pitch_bend_range = 2
        self.pitch_bend_curve = 2

    def set_instrument(self, instrument):
        self.instrument = instrument
        self._configure_from_instrument()

    def _configure_from_instrument(self):
        if self.instrument:
            config = self.instrument.get_configuration()
            if 'envelope' in config:
                self.set_envelope(config['envelope'])
            if 'oscillator' in config:
                self.configure_oscillator(config['oscillator'])
            if 'filter' in config:
                self.set_filter(config['filter'])
            if 'pitch_bend' in config:
                self.pitch_bend_enabled = config['pitch_bend'].get('enabled', False)
                self.pitch_bend_range = config['pitch_bend'].get('range', 2)
                self.pitch_bend_curve = config['pitch_bend'].get('curve', 2)

    def configure_oscillator(self, osc_config):
        if 'detune' in osc_config:
            self.set_detune(osc_config['detune'])
        if 'waveform' in osc_config:
            self.set_waveform(osc_config['waveform'])

    def set_filter(self, filter_config):
        self.filter_config.update(filter_config)
        self._update_filter()

    def set_filter_resonance(self, resonance):
        self.filter_config['resonance'] = resonance
        self._update_filter()

    def set_filter_cutoff(self, cutoff):
        safe_cutoff = max(20, min(20000, float(cutoff)))
        self.filter_config['cutoff'] = safe_cutoff
        self._update_filter()

    def _update_filter(self):
        if self.filter_config['type'] == 'low_pass':
            self.filter = lambda synth: synth.low_pass_filter(
                self.filter_config['cutoff'], 
                self.filter_config['resonance']
            )
        elif self.filter_config['type'] == 'high_pass':
            self.filter = lambda synth: synth.high_pass_filter(
                self.filter_config['cutoff'],
                self.filter_config['resonance']
            )
        elif self.filter_config['type'] == 'band_pass':
            self.filter = lambda synth: synth.band_pass_filter(
                self.filter_config['cutoff'],
                self.filter_config['resonance']
            )
        else:
            self.filter = None

    def set_detune(self, detune):
        self.detune = detune

    def set_envelope(self, env_config):
        self.envelope_settings.update(env_config)

    def set_envelope_param(self, param, value):
        if param in self.envelope_settings:
            self.envelope_settings[param] = value
    
    def create_envelope(self):
        return synthio.Envelope(
            attack_time=self.envelope_settings.get('attack', 0.01),
            decay_time=self.envelope_settings.get('decay', 0.1),
            release_time=self.envelope_settings.get('release', 0.1),
            attack_level=1.0,
            sustain_level=self.envelope_settings.get('sustain', 0.8)
        )

    def set_waveform(self, waveform_type):
        self.current_waveform = waveform_type
        self.generate_waveform(waveform_type)

    def generate_waveform(self, waveform_type, sample_size=256):
        if waveform_type not in self.waveforms:
            if waveform_type == 'sine':
                self.waveforms[waveform_type] = self.generate_sine_wave(sample_size)
            elif waveform_type == 'saw':
                self.waveforms[waveform_type] = self.generate_saw_wave(sample_size)
            elif waveform_type == 'square':
                self.waveforms[waveform_type] = self.generate_square_wave(sample_size)
            elif waveform_type == 'triangle':
                self.waveforms[waveform_type] = self.generate_triangle_wave(sample_size)
            else:
                self.waveforms[waveform_type] = self.generate_sine_wave(sample_size)

    def get_waveform(self, waveform_type):
        if waveform_type not in self.waveforms:
            self.generate_waveform(waveform_type)
        return self.waveforms[waveform_type]

    def generate_sine_wave(self, sample_size=256):
        return array.array("h", 
            [int(math.sin(math.pi * 2 * i / sample_size) * 32767) 
             for i in range(sample_size)])

    def generate_saw_wave(self, sample_size=256):
        return array.array("h", 
            [int((i / sample_size * 2 - 1) * 32767) 
             for i in range(sample_size)])

    def generate_square_wave(self, sample_size=256, duty_cycle=0.5):
        return array.array("h", 
            [32767 if i / sample_size < duty_cycle else -32767 
             for i in range(sample_size)])

    def generate_triangle_wave(self, sample_size=256):
        return array.array("h", 
            [int(((2 * i / sample_size - 1) if i < sample_size / 2 
                 else (2 - 2 * i / sample_size) - 1) * 32767) 
             for i in range(sample_size)])

    def create_lfo(self, rate, scale=1.0, offset=0.0, waveform=None):
        lfo = synthio.LFO(rate=rate, scale=scale, offset=offset, waveform=waveform)
        self.lfos.append(lfo)
        return lfo

    def update(self, synth):
        self.update_modulation()
        self.process_effects(synth)

    def update_modulation(self):
        for target, modulations in self.modulation_matrix.items():
            total_modulation = 0
            for source, amount in modulations:
                if isinstance(source, synthio.LFO):
                    total_modulation += source.value * amount
            if hasattr(target, 'value'):
                target.value += total_modulation

    def process_effects(self, synth):
        for effect in self.effects:
            effect.process(synth)

class SynthAudioOutputManager:
    def __init__(self):
        self.mixer = audiomixer.Mixer(
            sample_rate=Constants.SAMPLE_RATE,
            buffer_size=Constants.AUDIO_BUFFER_SIZE,
            channel_count=1
        )
        self.audio = audiobusio.I2SOut(
            bit_clock=Constants.I2S_BIT_CLOCK,
            word_select=Constants.I2S_WORD_SELECT,
            data=Constants.I2S_DATA
        )
        self.synth = synthio.Synthesizer(sample_rate=Constants.SAMPLE_RATE)
        self.volume = 1.0
        self._setup_audio()

    def _setup_audio(self):
        self.audio.play(self.mixer)
        self.mixer.voice[0].play(self.synth)
        self.set_volume(self.volume)

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, volume))
        self.mixer.voice[0].level = self.volume

    def get_volume(self):
        return self.volume

    def get_synth(self):
        return self.synth

    def stop(self):
        self.audio.stop()

    def update_volume(self, pot_value):
        old_volume = self.volume
        self.set_volume(pot_value)
        
        print(f"P0: Volume: {old_volume:.2f} -> {pot_value:.2f}")

class Synthesizer:
    def __init__(self, audio_output_manager):
        self.voice_manager = SynthVoiceManager()
        self.synth_engine = SynthEngine()
        self.audio_output_manager = audio_output_manager
        self.synth = self.audio_output_manager.get_synth()
        self.max_amplitude = 0.9
        self.instrument = None
        self.current_midi_values = {}

    def set_instrument(self, instrument):
        self.instrument = instrument
        self.synth_engine.set_instrument(instrument)
        self._configure_synthesizer()
        self._re_evaluate_midi_values()

    def _configure_synthesizer(self):
        if self.instrument:
            config = self.instrument.get_configuration()
            if 'oscillator' in config:
                self.synth_engine.configure_oscillator(config['oscillator'])
            if 'filter' in config:
                self.synth_engine.set_filter(config['filter'])

    def _re_evaluate_midi_values(self):
        for cc_number, midi_value in self.current_midi_values.items():
            self.handle_control_change(cc_number, midi_value, midi_value / 127.0)

    def process_midi_event(self, event):
        event_type, *params = event
        if event_type == 'note_on':
            self.play_note(*params)
        elif event_type == 'note_off':
            self.stop_note(*params)
        elif event_type == 'note_update':
            self.update_note(*params)
        elif event_type == 'pitch_bend':
            self.apply_pitch_bend(*params)
        elif event_type == 'control_change':
            self.handle_control_change(*params)

    def play_note(self, midi_note, velocity, key_id):
        frequency = self._fractional_midi_to_hz(midi_note)
        envelope = self.synth_engine.create_envelope()
        waveform = self.synth_engine.get_waveform(self.instrument.oscillator['waveform'])
        note = self.voice_manager.allocate_voice(key_id, frequency, velocity, envelope, waveform)
        
        if note is not None:
            if self.synth_engine.filter:
                note.filter = self.synth_engine.filter(self.synth)
            self.synth.press(note)
            self._apply_amplitude_scaling()

    def stop_note(self, midi_note, velocity, key_id):
        note = self.voice_manager.release_voice(key_id)
        if note:
            self.synth.release(note)
            self._apply_amplitude_scaling()

    def update_note(self, midi_note, velocity, key_id):
        note = self.voice_manager.get_note_by_key_id(key_id)
        if note:
            frequency = self._fractional_midi_to_hz(midi_note)
            note.frequency = frequency
            self._apply_amplitude_scaling()

    def apply_pitch_bend(self, key_id, bend_value):
        if self.instrument.pitch_bend['enabled']:
            note = self.voice_manager.get_note_by_key_id(key_id)
            if note:
                normalized_bend = (bend_value - 8192) / 8192
                bend_range = self.instrument.pitch_bend['range']
                bend_multiplier = 2 ** (normalized_bend * bend_range / 12)
                note.bend = bend_multiplier

    def handle_control_change(self, cc_number, midi_value, normalized_value):
        self.current_midi_values[cc_number] = midi_value
        pots_config = self.instrument.pots
        for pot_index, pot_config in pots_config.items():
            if pot_config['cc'] == cc_number:
                param_name = pot_config['name']
                min_val = pot_config['min']
                max_val = pot_config['max']
                scaled_value = min_val + normalized_value * (max_val - min_val)
                
                # Print pot change information
                print(f"P{pot_index}: {param_name}: {self.current_midi_values.get(cc_number, 0)/127.0:.2f} -> {normalized_value:.2f}")
                
                if param_name == 'Filter Cutoff':
                    self.synth_engine.set_filter_cutoff(scaled_value)
                elif param_name == 'Filter Resonance':
                    self.synth_engine.set_filter_resonance(scaled_value)
                elif param_name == 'Detune Amount':
                    self.synth_engine.set_detune(scaled_value)
                elif param_name == 'Attack Time':
                    self.synth_engine.set_envelope_param('attack', scaled_value)
                elif param_name == 'Decay Time':
                    self.synth_engine.set_envelope_param('decay', scaled_value)
                elif param_name == 'Sustain Level':
                    self.synth_engine.set_envelope_param('sustain', scaled_value)
                elif param_name == 'Release Time':
                    self.synth_engine.set_envelope_param('release', scaled_value)
                elif param_name == 'Bend Range':
                    self.instrument.pitch_bend['range'] = scaled_value
                elif param_name == 'Bend Curve':
                    self.instrument.pitch_bend['curve'] = scaled_value
                
                break
        
        self._update_active_notes()

    def _update_active_notes(self):
        active_notes = self.voice_manager.get_active_notes()
        for note in active_notes:
            if self.synth_engine.filter:
                note.filter = self.synth_engine.filter(self.synth)
            note.envelope = self.synth_engine.create_envelope()

    def _apply_amplitude_scaling(self):
        active_notes = self.voice_manager.get_active_notes()
        if not active_notes:
            return

        total_amplitude = sum(note.amplitude for note in active_notes)
        if total_amplitude > self.max_amplitude:
            scale_factor = self.max_amplitude / total_amplitude
            for note in active_notes:
                note.amplitude *= scale_factor

    def update(self, midi_events):
        for event in midi_events:
            self.process_midi_event(event)
        self.synth_engine.update(self.synth)

    def stop(self):
        self.voice_manager.release_all_voices()
        self.audio_output_manager.stop()

    def _fractional_midi_to_hz(self, midi_note):
        return 440 * (2 ** ((midi_note - 69) / 12))

class Bartleby:
    def __init__(self):
        # System components (initialized in setup)
        self.hardware = None
        self.audio = None
        self.midi = None
        self.synth = None
        self.current_instrument = None
        
        # Timing state
        self.current_time = 0
        self.last_pot_scan = 0
        self.last_encoder_scan = 0
        
        # Run setup
        self._setup_hardware()
        self._setup_audio()
        self._setup_instruments()
        self._setup_initial_state()
        
    def _setup_hardware(self):
        """Initialize all hardware components"""
        self.hardware = {
            'control_mux': Multiplexer(
                HWConstants.CONTROL_MUX_SIG,
                HWConstants.CONTROL_MUX_S0,
                HWConstants.CONTROL_MUX_S1,
                HWConstants.CONTROL_MUX_S2,
                HWConstants.CONTROL_MUX_S3
            ),
            'keyboard': self._setup_keyboard(),
            'encoders': RotaryEncoderHandler(
                HWConstants.OCTAVE_ENC_CLK,
                HWConstants.OCTAVE_ENC_DT,
                HWConstants.INSTRUMENT_ENC_CLK,
                HWConstants.INSTRUMENT_ENC_DT
            )
        }
        
        # Create pot handler after mux is ready
        self.hardware['pots'] = PotentiometerHandler(self.hardware['control_mux'])
        time.sleep(Constants.SETUP_DELAY)  # Allow hardware to stabilize

    def _setup_keyboard(self):
        """Initialize keyboard multiplexers and handler"""
        keyboard_l1a = Multiplexer(
            HWConstants.KEYBOARD_L1A_MUX_SIG,
            HWConstants.KEYBOARD_L1A_MUX_S0,
            HWConstants.KEYBOARD_L1A_MUX_S1,
            HWConstants.KEYBOARD_L1A_MUX_S2,
            HWConstants.KEYBOARD_L1A_MUX_S3
        )
        
        keyboard_l1b = Multiplexer(
            HWConstants.KEYBOARD_L1B_MUX_SIG,
            HWConstants.KEYBOARD_L1B_MUX_S0,
            HWConstants.KEYBOARD_L1B_MUX_S1,
            HWConstants.KEYBOARD_L1B_MUX_S2,
            HWConstants.KEYBOARD_L1B_MUX_S3
        )
        
        return KeyboardHandler(
            keyboard_l1a,
            keyboard_l1b,
            HWConstants.KEYBOARD_L2_MUX_S0,
            HWConstants.KEYBOARD_L2_MUX_S1,
            HWConstants.KEYBOARD_L2_MUX_S2,
            HWConstants.KEYBOARD_L2_MUX_S3
        )

    def _setup_audio(self):
        """Initialize audio and synthesis components"""
        
        self.audio = SynthAudioOutputManager()
        self.synth = Synthesizer(self.audio)
        self.midi = MidiLogic()

    def _setup_instruments(self):
        """Initialize instrument templates and set default"""
        # Create instruments in specific order for rotary selection
        self.current_instrument = ElectricOrgan()  # Default instrument
        Piano()  # Add to available instruments
        BendableOrgan()  # Add to available instruments
        
        # Configure systems with initial instrument
        self.synth.set_instrument(self.current_instrument)
        self.midi.note_processor.set_instrument(self.current_instrument)

    def _setup_initial_state(self):
        """Set initial system state"""
        # Reset all encoders
        self.hardware['encoders'].reset_all_encoder_positions()
        
        # Set initial octave
        self.midi.note_processor.set_octave(0)
        
        # Set initial volume from pot 0
        initial_volume = self.hardware['pots'].normalize_value(
            self.hardware['control_mux'].read_channel(0)
        )
        self.audio.set_volume(initial_volume)
        
        print("\nBartleby (v1.0) is awake... (◕‿◕✿)")

    def _handle_encoder_events(self, encoder_events):
        """Process encoder state changes"""
        for event in encoder_events:
            if event[0] == 'rotation':
                encoder_id, direction = event[1:3]
                if encoder_id == 0:  # Octave control
                    self.midi.handle_octave_shift(direction)
                    print(f"Octave shifted {direction}: new position {self.hardware['encoders'].get_encoder_position(0)}")
                elif encoder_id == 1:  # Instrument selection
                    # Get new instrument and update all systems
                    from instruments import Instrument
                    self.current_instrument = Instrument.handle_instrument_change(direction)
                    self.synth.set_instrument(self.current_instrument)
                    print(f"Instrument changed to {self.current_instrument.name}")

    def process_hardware(self):
        """Read and process all hardware inputs"""
        self.current_time = time.monotonic()
        changes = {
            'keys': [],
            'pots': [],
            'encoders': []
        }
        
        # Always read keys at full speed
        changes['keys'] = self.hardware['keyboard'].read_keys()
        
        # Read pots at medium interval
        if self.current_time - self.last_pot_scan >= Constants.POT_SCAN_INTERVAL:
            changes['pots'] = self.hardware['pots'].read_pots()
            if changes['pots']:
                # Handle volume pot (pot 0) separately
                for pot_id, old_value, new_value in changes['pots'][:]:
                    if pot_id == 0:
                        self.audio.update_volume(new_value)
                        changes['pots'].remove((pot_id, old_value, new_value))
            self.last_pot_scan = self.current_time
        
        # Read encoders at fastest interval
        if self.current_time - self.last_encoder_scan >= Constants.ENCODER_SCAN_INTERVAL:
            for i in range(self.hardware['encoders'].num_encoders):
                new_events = self.hardware['encoders'].read_encoder(i)
                if new_events:
                    changes['encoders'].extend(new_events)
            if changes['encoders']:
                self._handle_encoder_events(changes['encoders'])
            self.last_encoder_scan = self.current_time
            
        return changes

    def update(self):
        """Main update loop - returns False if should stop"""
        try:
            # Process all hardware
            changes = self.process_hardware()
            
            # Only process MIDI/synth if we have changes
            if any(changes.values()):
                # Generate MIDI events
                midi_events = self.midi.update(
                    changes['keys'],
                    changes['pots'],
                    self.current_instrument.get_configuration()
                )
                
                # Process MIDI events
                processed_events = self.midi.process_and_send_midi_events(midi_events)
                
                # Update synthesizer
                for event in processed_events:
                    self.synth.process_midi_event(event)
                self.synth.update(processed_events)
            
            return True
            
        except KeyboardInterrupt:
            return False
        except Exception as e:
            print(f"Error in main loop: {str(e)}")
            return False

    def run(self):
        """Main run loop"""
        try:
            while self.update():
                time.sleep(Constants.MAIN_LOOP_INTERVAL)
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean shutdown of all systems"""
        if self.synth:
            self.synth.stop()
        print("\nBartleby goes to sleep... ( ◡_◡)ᶻ 𝗓 𐰁")

def main():
    synth = Bartleby()
    synth.run()

if __name__ == "__main__":
    main()
