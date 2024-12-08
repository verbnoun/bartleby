"""Main MIDI logic and coordination for Bartleby synthesizer."""

import time
from constants import (
    CC_TIMBRE,
    TIMBRE_CENTER,
    ZONE_MANAGER
)
from notes import MPENoteProcessor
from zones import ZoneManager
from controls import MidiControlProcessor
from messages import MidiTransportManager, MidiMessageSender, MidiEventRouter
from config import MPEConfigurator
from logging import log, TAG_MIDI

class MidiLogic:
    """Main MIDI logic coordinator class"""
    def __init__(self, transport_manager, midi_callback=None):
        log(TAG_MIDI, "Initializing MIDI Logic")
        try:
            # Initialize transport and message sender
            self.transport = MidiTransportManager(transport_manager, midi_callback)
            self.message_sender = MidiMessageSender(self.transport)
            log(TAG_MIDI, "Transport and message sender initialized")
            
            # Initialize managers and processors
            self.channel_manager = ZoneManager()
            self.note_processor = MPENoteProcessor(self.channel_manager)
            self.control_processor = MidiControlProcessor()
            log(TAG_MIDI, "Managers and processors initialized")
            
            # Initialize specialized components
            self.mpe_configurator = MPEConfigurator(self.message_sender)
            self.event_router = MidiEventRouter(self.message_sender, self.channel_manager)
            log(TAG_MIDI, "Specialized components initialized")
            
            # Configure system
            self._configure_system()
        except Exception as e:
            log(TAG_MIDI, f"Failed to initialize MIDI Logic: {str(e)}", is_error=True)
            raise

    def _configure_system(self):
        """Initialize system with MPE configuration"""
        log(TAG_MIDI, "Configuring MPE system...")
        try:
            self.mpe_configurator.configure_mpe()
            log(TAG_MIDI, "MPE configuration complete")
        except Exception as e:
            log(TAG_MIDI, f"MPE configuration failed: {str(e)}", is_error=True)
            raise

    def handle_config_message(self, message):
        log(TAG_MIDI, f"Processing config message: {message}")
        return self.control_processor.handle_config_message(message)

    def reset_controller_defaults(self):
        log(TAG_MIDI, "Resetting controller defaults")
        self.control_processor.reset_to_defaults()

    def update(self, changed_keys, changed_pots, config):
        midi_events = []
        
        if changed_keys:
            log(TAG_MIDI, f"Processing {len(changed_keys)} key changes")
            midi_events.extend(self.note_processor.process_key_changes(changed_keys, config))
        
        if changed_pots:
            log(TAG_MIDI, f"Processing {len(changed_pots)} controller changes")
            midi_events.extend(self.control_processor.process_controller_changes(changed_pots))
        
        for event in midi_events:
            self.event_router.handle_event(event)
            
        return midi_events

    def handle_octave_shift(self, direction):
        log(TAG_MIDI, f"Handling octave shift: {direction}")
        midi_events = self.note_processor.handle_octave_shift(direction)
        for event in midi_events:
            self.event_router.handle_event(event)
        return midi_events

    def play_greeting(self):
        """Play greeting chime using MPE"""
        log(TAG_MIDI, "Playing MPE greeting sequence")
            
        base_key_id = -1
        base_pressure = 0.75
        
        greeting_notes = [60, 64, 67, 72]
        velocities = [0.6, 0.7, 0.8, 0.9]
        durations = [0.2, 0.2, 0.2, 0.4]
        
        try:
            for idx, (note, velocity, duration) in enumerate(zip(greeting_notes, velocities, durations)):
                key_id = base_key_id - idx
                channel = self.channel_manager.allocate_channel(key_id)
                note_state = self.channel_manager.add_note(key_id, note, channel, int(velocity * 127))
                
                # Send in MPE order: CC74 → Pressure → Pitch Bend → Note On
                self.message_sender.send_message([0xB0 | channel, CC_TIMBRE, TIMBRE_CENTER])
                self.message_sender.send_message([0xD0 | channel, int(base_pressure * 127)])
                self.message_sender.send_message([0xE0 | channel, 0x00, 0x40])  # Center pitch bend
                self.message_sender.send_message([0x90 | channel, note, int(velocity * 127)])
                
                time.sleep(duration)
                
                self.message_sender.send_message([0xD0 | channel, 0])  # Zero pressure
                self.message_sender.send_message([0x80 | channel, note, 0])
                self.channel_manager.release_note(key_id)
                
                time.sleep(0.05)
                
                log(TAG_MIDI, f"Played greeting note {idx+1}/4: {note}")
        except Exception as e:
            log(TAG_MIDI, f"Error during greeting sequence: {str(e)}", is_error=True)

    def cleanup(self):
        log(TAG_MIDI, "Starting MIDI system cleanup")
        try:
            self.transport.cleanup()
            log(TAG_MIDI, "MIDI system cleanup complete")
        except Exception as e:
            log(TAG_MIDI, f"Error during cleanup: {str(e)}", is_error=True)
