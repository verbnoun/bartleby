"""MIDI message routing and transport management."""

import time
import math
import busio
import adafruit_midi
import usb_midi
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff
from adafruit_midi.pitch_bend import PitchBend
from adafruit_midi.control_change import ControlChange
from adafruit_midi.channel_pressure import ChannelPressure
from constants import (
    UART_BAUDRATE,
    UART_TIMEOUT,
    ZONE_MANAGER,
    PITCH_BEND_MAX,
    PRESSURE_CURVE,
    BEND_CURVE
)
from logging import log, TAG_MESSAGE

class MidiTransportManager:
    """Manages MIDI output streams using both UART and USB MIDI"""
    def __init__(self, transport_manager, midi_callback=None):
        try:
            log(TAG_MESSAGE, "Initializing MIDI transport manager")
            # Initialize UART MIDI
            self.uart = transport_manager.get_uart()
            self.uart_midi = adafruit_midi.MIDI(
                midi_out=self.uart, 
                out_channel=ZONE_MANAGER
            )
            self.uart_initialized = True
            log(TAG_MESSAGE, "UART MIDI initialized")
            
            # Initialize USB MIDI
            try:
                self.usb_midi = adafruit_midi.MIDI(
                    midi_out=usb_midi.ports[1],
                    out_channel=ZONE_MANAGER
                )
                self.usb_initialized = True
                log(TAG_MESSAGE, "USB MIDI initialized")
            except Exception as e:
                log(TAG_MESSAGE, f"USB MIDI initialization failed: {str(e)}", is_error=True)
                self.usb_initialized = False
                
            self.midi_callback = midi_callback
            log(TAG_MESSAGE, "MIDI transport initialization complete")
        except Exception as e:
            log(TAG_MESSAGE, f"Failed to initialize MIDI transport: {str(e)}", is_error=True)
            raise

    def send_message(self, message):
        """Send MIDI message to both UART and USB MIDI outputs"""
        try:
            if isinstance(message, list):
                # Log MIDI message
                log(TAG_MESSAGE, f"Sending MIDI: {[hex(x) for x in message]}")
                
                # Send raw bytes directly to transports
                if self.uart_initialized:
                    self.uart.write(bytes(message))
                if self.usb_initialized:
                    usb_midi.ports[1].write(bytes(message))
            else:
                # Fallback for direct message sending
                if self.uart_initialized:
                    self.uart_midi.send(message)
                if self.usb_initialized:
                    self.usb_midi.send(message)
                    
        except Exception as e:
            log(TAG_MESSAGE, f"Error sending MIDI message: {str(e)}", is_error=True)

    def read(self, size=None):
        """Read from UART"""
        try:
            data = self.uart.read(size)
            if data:
                log(TAG_MESSAGE, f"Read {len(data)} bytes from UART")
            return data
        except Exception as e:
            log(TAG_MESSAGE, f"Error reading from UART: {str(e)}", is_error=True)
            return None

    @property
    def in_waiting(self):
        """Check bytes waiting"""
        try:
            return self.uart.in_waiting
        except Exception as e:
            log(TAG_MESSAGE, f"Error checking in_waiting: {str(e)}", is_error=True)
            return 0

    def cleanup(self):
        """Clean shutdown of MIDI transports"""
        try:
            log(TAG_MESSAGE, "Starting MIDI transport cleanup")
            # Don't deinit UART here since we don't own it
            self.uart_initialized = False
            log(TAG_MESSAGE, "MIDI transport cleanup complete")
        except Exception as e:
            log(TAG_MESSAGE, f"Error during MIDI cleanup: {str(e)}", is_error=True)

class MidiMessageSender:
    """Handles the actual sending of MIDI messages"""
    def __init__(self, transport):
        try:
            log(TAG_MESSAGE, "Initializing MIDI message sender")
            self.transport = transport
        except Exception as e:
            log(TAG_MESSAGE, f"Failed to initialize message sender: {str(e)}", is_error=True)
            raise

    def send_message(self, message):
        """Send a MIDI message directly"""
        self.transport.send_message(message)

class MidiEventRouter:
    """Routes and processes MIDI events"""
    def __init__(self, message_sender, channel_manager):
        try:
            log(TAG_MESSAGE, "Initializing MIDI event router")
            self.message_sender = message_sender
            self.channel_manager = channel_manager
        except Exception as e:
            log(TAG_MESSAGE, f"Failed to initialize event router: {str(e)}", is_error=True)
            raise

    def handle_event(self, event):
        """Handle a MIDI event"""
        try:
            event_type = event[0]
            params = event[1:]
            
            log(TAG_MESSAGE, f"Processing event: {event_type}")
            
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
            else:
                log(TAG_MESSAGE, f"Unknown event type: {event_type}", is_error=True)
                
        except Exception as e:
            log(TAG_MESSAGE, f"Error handling event {event}: {str(e)}", is_error=True)

    def _calculate_pressure(self, pressure):
        """
        pressure: 0.0 to 1.0 (hardware normalized value)
        PRESSURE_CURVE effects:
        0.0: linear mapping (hardware direct)
        1.0: quick changes at extremes, very slow in middle
        """
        try:
            if PRESSURE_CURVE == 0.0:
                scaled = pressure
            else:
                # Shift to -0.5 to 0.5 range
                center_shift = pressure - 0.5
                
                # Calculate curve power (lower = more extreme curve)
                # At PRESSURE_CURVE = 1.0, power = 0.25 for extreme curve
                # At PRESSURE_CURVE = 0.0, power = 1.0 for linear
                curve_power = 1.0 - (PRESSURE_CURVE * 0.75)
                
                # Apply curve and shift back to 0-1
                if center_shift < 0:
                    # For negative shift, curve and invert
                    curved = math.pow(abs(center_shift) * 2, curve_power) * 0.5
                    scaled = 0.5 - curved
                else:
                    # For positive shift, curve and add to center
                    curved = math.pow(center_shift * 2, curve_power) * 0.5
                    scaled = 0.5 + curved
            
            return int(scaled * 127)
        except Exception as e:
            log(TAG_MESSAGE, f"Error calculating pressure: {str(e)}", is_error=True)
            return 0

    def _calculate_pitch_bend(self, position):
        """
        position: -1.0 to 1.0 (hardware normalized position)
        BEND_CURVE effects:
        0.0: linear mapping (hardware direct)
        1.0: quick changes at extremes, very slow in middle
        """
        try:
            normalized = (position + 1) / 2  # Convert to 0-1 range
            
            if BEND_CURVE == 0.0:
                scaled = normalized
            else:
                # Shift to -0.5 to 0.5 range
                center_shift = normalized - 0.5
                
                # Calculate curve power (lower = more extreme curve)
                # At BEND_CURVE = 1.0, power = 0.25 for extreme curve
                # At BEND_CURVE = 0.0, power = 1.0 for linear
                curve_power = 1.0 - (BEND_CURVE * 0.75)
                
                # Apply curve and shift back to 0-1
                if center_shift < 0:
                    # For negative shift, curve and invert
                    curved = math.pow(abs(center_shift) * 2, curve_power) * 0.5
                    scaled = 0.5 - curved
                else:
                    # For positive shift, curve and add to center
                    curved = math.pow(center_shift * 2, curve_power) * 0.5
                    scaled = 0.5 + curved
            
            # Ensure unsigned value between 0 and PITCH_BEND_MAX
            bend_value = int(scaled * PITCH_BEND_MAX) & 0x3FFF
            return bend_value
            
        except Exception as e:
            log(TAG_MESSAGE, f"Error calculating pitch bend: {str(e)}", is_error=True)
            return PITCH_BEND_MAX // 2  # Return center position on error

    def _handle_pressure_init(self, key_id, pressure):
        try:
            channel = self.channel_manager.allocate_channel(key_id)
            pressure_value = self._calculate_pressure(pressure)
            self.message_sender.send_message([0xD0 | channel, pressure_value])
            log(TAG_MESSAGE, f"Initialized pressure: key={key_id}, channel={channel}, value={pressure_value}")
        except Exception as e:
            log(TAG_MESSAGE, f"Error initializing pressure: {str(e)}", is_error=True)

    def _handle_pressure_update(self, key_id, pressure):
        try:
            note_state = self.channel_manager.get_note_state(key_id)
            if note_state:
                pressure_value = self._calculate_pressure(pressure)
                # Only send if pressure has changed
                if pressure_value != note_state.pressure:
                    self.message_sender.send_message([0xD0 | note_state.channel, pressure_value])
                    note_state.pressure = pressure_value
                    log(TAG_MESSAGE, f"Updated pressure: key={key_id}, channel={note_state.channel}, value={pressure_value}")
        except Exception as e:
            log(TAG_MESSAGE, f"Error updating pressure: {str(e)}", is_error=True)

    def _handle_pitch_bend_init(self, key_id, position):
        try:
            channel = self.channel_manager.allocate_channel(key_id)
            bend_value = self._calculate_pitch_bend(position)
            lsb = bend_value & 0x7F
            msb = (bend_value >> 7) & 0x7F
            self.message_sender.send_message([0xE0 | channel, lsb, msb])
            log(TAG_MESSAGE, f"Initialized pitch bend: key={key_id}, channel={channel}, value={bend_value}")
        except Exception as e:
            log(TAG_MESSAGE, f"Error initializing pitch bend: {str(e)}", is_error=True)

    def _handle_pitch_bend_update(self, key_id, position):
        try:
            note_state = self.channel_manager.get_note_state(key_id)
            if note_state:
                bend_value = self._calculate_pitch_bend(position)
                # Only send if pitch bend has changed
                if bend_value != note_state.pitch_bend:
                    lsb = bend_value & 0x7F
                    msb = (bend_value >> 7) & 0x7F
                    self.message_sender.send_message([0xE0 | note_state.channel, lsb, msb])
                    note_state.pitch_bend = bend_value
                    log(TAG_MESSAGE, f"Updated pitch bend: key={key_id}, channel={note_state.channel}, value={bend_value}")
        except Exception as e:
            log(TAG_MESSAGE, f"Error updating pitch bend: {str(e)}", is_error=True)

    def _handle_note_on(self, midi_note, velocity, key_id):
        try:
            channel = self.channel_manager.allocate_channel(key_id)
            self.channel_manager.add_note(key_id, midi_note, channel, velocity)
            self.message_sender.send_message([0x90 | channel, int(midi_note), velocity])
            log(TAG_MESSAGE, f"Note on: key={key_id}, note={midi_note}, channel={channel}, velocity={velocity}")
        except Exception as e:
            log(TAG_MESSAGE, f"Error handling note on: {str(e)}", is_error=True)

    def _handle_note_off(self, midi_note, velocity, key_id):
        try:
            note_state = self.channel_manager.get_note_state(key_id)
            if note_state:
                self.message_sender.send_message([0x80 | note_state.channel, int(midi_note), velocity])
                self.channel_manager.release_note(key_id)
                log(TAG_MESSAGE, f"Note off: key={key_id}, note={midi_note}, channel={note_state.channel}, velocity={velocity}")
        except Exception as e:
            log(TAG_MESSAGE, f"Error handling note off: {str(e)}", is_error=True)

    def _handle_control_change(self, cc_number, midi_value):
        try:
            self.message_sender.send_message([0xB0 | ZONE_MANAGER, cc_number, midi_value])
            log(TAG_MESSAGE, f"Control change: cc={cc_number}, value={midi_value}")
        except Exception as e:
            log(TAG_MESSAGE, f"Error handling control change: {str(e)}", is_error=True)
