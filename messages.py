import time
import busio
import adafruit_midi
import usb_midi
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff
from adafruit_midi.pitch_bend import PitchBend
from adafruit_midi.control_change import ControlChange
from adafruit_midi.channel_pressure import ChannelPressure
from constants import (
    DEBUG,
    UART_BAUDRATE,
    UART_TIMEOUT,
    ZONE_MANAGER,
    PITCH_BEND_MAX
)

class MidiTransportManager:
    """Manages MIDI output streams using both UART and USB MIDI"""
    def __init__(self, transport_manager, midi_callback=None):
        # Initialize UART MIDI
        self.uart = transport_manager.get_uart()
        self.uart_midi = adafruit_midi.MIDI(
            midi_out=self.uart, 
            out_channel=ZONE_MANAGER
        )
        self.uart_initialized = True
        
        # Initialize USB MIDI
        try:
            self.usb_midi = adafruit_midi.MIDI(
                midi_out=usb_midi.ports[1],
                out_channel=ZONE_MANAGER
            )
            self.usb_initialized = True
            print("USB MIDI initialized")
        except Exception as e:
            print(f"USB MIDI initialization failed: {str(e)}")
            self.usb_initialized = False
            
        self.midi_callback = midi_callback
        print("MIDI transport initialized (UART + USB)")

    def send_message(self, message):
        """Send MIDI message to both UART and USB MIDI outputs"""
        try:
            if isinstance(message, list):
                # Debug logging for raw MIDI message
                if DEBUG:
                    print(f"Raw MIDI Message: {[hex(x) for x in message]}")
                
                # Send raw bytes directly to transports
                if self.uart_initialized:
                    self.uart.write(bytes(message))
                if self.usb_initialized:
                    usb_midi.ports[1].write(bytes(message))
            else:
                # Fallback for direct message sending (though this path might need revision)
                if self.uart_initialized:
                    self.uart_midi.send(message)
                if self.usb_initialized:
                    self.usb_midi.send(message)
                    
        except Exception as e:
            print(f"Error sending MIDI message: {str(e)}")

    def read(self, size=None):
        """Read from UART"""
        return self.uart.read(size)

    @property
    def in_waiting(self):
        """Check bytes waiting"""
        return self.uart.in_waiting

    def cleanup(self):
        """Clean shutdown of MIDI transports"""
        if self.uart and self.uart_initialized:
            self.uart.deinit()
            self.uart_initialized = False
        print("MIDI transport cleaned up")

class MidiMessageSender:
    """Handles the actual sending of MIDI messages"""
    def __init__(self, transport):
        self.transport = transport

    def send_message(self, message):
        """Send a MIDI message directly"""
        self.transport.send_message(message)

class MidiEventRouter:
    """Routes and processes MIDI events"""
    def __init__(self, message_sender, channel_manager):
        self.message_sender = message_sender
        self.channel_manager = channel_manager

    def handle_event(self, event):
        """Handle a MIDI event"""
        event_type = event[0]
        params = event[1:]
        
        if event_type == 'pressure_init':
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

    def _handle_pressure_init(self, key_id, pressure):
        channel = self.channel_manager.allocate_channel(key_id)
        pressure_value = int(pressure * 127)
        self.message_sender.send_message([0xD0 | channel, pressure_value])

    def _handle_pressure_update(self, key_id, pressure):
        note_state = self.channel_manager.get_note_state(key_id)
        if note_state:
            pressure_value = int(pressure * 127)
            # Only send if pressure has changed
            if pressure_value != note_state.pressure:
                self.message_sender.send_message([0xD0 | note_state.channel, pressure_value])
                note_state.pressure = pressure_value

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
            # Only send if pitch bend has changed
            if bend_value != note_state.pitch_bend:
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
        self.message_sender.send_message([0xB0 | ZONE_MANAGER, cc_number, midi_value])

    def _calculate_pitch_bend(self, position):
        """Calculate pitch bend value from position (-1 to 1)"""
        normalized = (position + 1) / 2  # Convert -1 to 1 range to 0 to 1
        return int(normalized * PITCH_BEND_MAX)
