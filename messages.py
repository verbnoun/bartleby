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
            # Track last message type per channel in stream
            self.channels_in_stream = {}
            log(TAG_MESSAGE, "MIDI transport initialization complete")
        except Exception as e:
            log(TAG_MESSAGE, f"Failed to initialize MIDI transport: {str(e)}", is_error=True)
            raise

    def send_message(self, message):
        """Send MIDI message to both UART and USB MIDI outputs"""
        try:
            if isinstance(message, list):
                # Track message type for channel
                status_byte = message[0]
                message_type = status_byte & 0xF0
                channel = status_byte & 0x0F
                self.channels_in_stream[channel] = message_type
                
                if self.uart_initialized:
                    self.uart.write(bytes(message))
                if self.usb_initialized:
                    usb_midi.ports[1].write(bytes(message))
                
                log(TAG_MESSAGE, f"Message type 0x{message_type:02X} in stream for channel {channel}")
            else:
                if self.uart_initialized:
                    self.uart_midi.send(message)
                if self.usb_initialized:
                    self.usb_midi.send(message)
                    
        except Exception as e:
            log(TAG_MESSAGE, f"Error sending MIDI message: {str(e)}", is_error=True)

    def is_note_off_in_stream(self, channel):
        """Check if Note Off is the last message in stream for channel"""
        return self.channels_in_stream.get(channel) == 0x80

    def read(self, size=None):
        """Read from UART"""
        try:
            data = self.uart.read(size)
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
            self.channels_in_stream.clear()
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

    def is_note_off_in_stream(self, channel):
        """Check if Note Off is in stream for channel"""
        return self.transport.is_note_off_in_stream(channel)

class MidiEventRouter:
    """Routes and processes MIDI events"""
    def __init__(self, message_sender, channel_manager):
        try:
            log(TAG_MESSAGE, "Initializing MIDI event router")
            self.message_sender = message_sender
            self.channel_manager = channel_manager
            # Initialize message statistics
            self.message_stats = {
                'pitch_bend': {'allowed': 0, 'filtered': 0},
                'pressure': {'allowed': 0, 'filtered': 0},
                'timbre': {'allowed': 0, 'filtered': 0}
            }
        except Exception as e:
            log(TAG_MESSAGE, f"Failed to initialize event router: {str(e)}", is_error=True)
            raise

    def handle_event(self, event):
        """Handle a MIDI event"""
        try:
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
            
            pressure_value = int(scaled * 127)
            log(TAG_MESSAGE, f"Pressure: {pressure_value}")
            return pressure_value
            
        except Exception as e:
            log(TAG_MESSAGE, f"Error calculating pressure: {str(e)}", is_error=True)
            return 0

    def _calculate_pitch_bend(self, position, initial_position=None):
        """
        position: -1.0 to 1.0 (from pressure.calculate_position)
        initial_position: Position at key press, or None if outside dead zone
        BEND_CURVE effects:
        0.0: tiny dead zone, mostly variable range
        1.0: large dead zone, tiny variable range
        """
        try:
            # Dead zone size based on BEND_CURVE (0.0 = tiny, 1.0 = huge)
            dead_zone_size = BEND_CURVE * 0.5  # Adjust multiplier as needed
            
            # If no initial position set, check if we're within allowed center range
            if initial_position is None:
                if abs(position) <= dead_zone_size:
                    # Within allowed range - use this as center
                    initial_position = position
                else:
                    # Outside allowed range - use hardware center
                    initial_position = 0
                    
            # Calculate relative position from initial position
            relative_pos = position - initial_position
            
            # If within dead zone of initial position, return center
            if abs(relative_pos) <= dead_zone_size:
                return PITCH_BEND_MAX // 2  # 8192
                
            # Calculate smooth curve outside dead zone
            if relative_pos < 0:
                # Map -1.0 to dead_zone to 0 to 8192
                normalized = (relative_pos + 1.0) / (1.0 - dead_zone_size)
                bend_value = int(normalized * (PITCH_BEND_MAX // 2))
            else:
                # Map dead_zone to 1.0 to 8192 to 16383
                normalized = (relative_pos - dead_zone_size) / (1.0 - dead_zone_size)
                bend_value = int(8192 + (normalized * (PITCH_BEND_MAX // 2)))
                
            # Clamp to valid range
            bend_value = max(0, min(PITCH_BEND_MAX, bend_value))
            
            log(TAG_MESSAGE, f"Bend: {bend_value}")
            return bend_value
            
        except Exception as e:
            log(TAG_MESSAGE, f"Error calculating pitch bend: {str(e)}", is_error=True)
            return PITCH_BEND_MAX // 2  # Return center on error

    def _handle_pressure_init(self, key_id, pressure):
        try:
            channel = self.channel_manager.allocate_channel(key_id)
            if channel is not None:  # Only proceed if we got a valid channel
                pressure_value = self._calculate_pressure(pressure)
                self.message_sender.send_message([0xD0 | channel, pressure_value])
                log(TAG_MESSAGE, f"Created Channel Pressure: ch={channel} pressure={pressure_value}")
                log(TAG_MESSAGE, f"MPE Pressure: zone=lower ch={channel} pressure={pressure_value}")
                self.message_stats['pressure']['allowed'] += 1
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
                    log(TAG_MESSAGE, f"Created Channel Pressure: ch={note_state.channel} pressure={pressure_value}")
                    log(TAG_MESSAGE, f"MPE Pressure: zone=lower ch={note_state.channel} pressure={pressure_value}")
                    note_state.pressure = pressure_value
                    self.message_stats['pressure']['allowed'] += 1
        except Exception as e:
            log(TAG_MESSAGE, f"Error updating pressure: {str(e)}", is_error=True)

    def _handle_pitch_bend_init(self, key_id, position):
        try:
            channel = self.channel_manager.allocate_channel(key_id)
            if channel is not None:  # Only proceed if we got a valid channel
                note_state = self.channel_manager.get_note_state(key_id)
                if note_state:
                    note_state.initial_position = position  # Store initial position
                bend_value = self._calculate_pitch_bend(position, None)  # Pass None to check initial position
                lsb = bend_value & 0x7F
                msb = (bend_value >> 7) & 0x7F
                self.message_sender.send_message([0xE0 | channel, lsb, msb])
                log(TAG_MESSAGE, f"Created Pitch Bend: ch={channel} value={bend_value}")
                log(TAG_MESSAGE, f"MPE Pitch Bend: zone=lower ch={channel} value={bend_value}")
                self.message_stats['pitch_bend']['allowed'] += 1
        except Exception as e:
            log(TAG_MESSAGE, f"Error initializing pitch bend: {str(e)}", is_error=True)

    def _handle_pitch_bend_update(self, key_id, position):
        try:
            note_state = self.channel_manager.get_note_state(key_id)
            if note_state:
                bend_value = self._calculate_pitch_bend(position, note_state.initial_position)
                if bend_value != note_state.pitch_bend:
                    lsb = bend_value & 0x7F
                    msb = (bend_value >> 7) & 0x7F
                    self.message_sender.send_message([0xE0 | note_state.channel, lsb, msb])
                    log(TAG_MESSAGE, f"Created Pitch Bend: ch={note_state.channel} value={bend_value}")
                    log(TAG_MESSAGE, f"MPE Pitch Bend: zone=lower ch={note_state.channel} value={bend_value}")
                    note_state.pitch_bend = bend_value
                    self.message_stats['pitch_bend']['allowed'] += 1
        except Exception as e:
            log(TAG_MESSAGE, f"Error updating pitch bend: {str(e)}", is_error=True)

    def _handle_note_on(self, midi_note, velocity, key_id):
        try:
            channel = self.channel_manager.allocate_channel(key_id)
            if channel is not None:  # Only proceed if we got a valid channel
                self.channel_manager.add_note(key_id, midi_note, channel, velocity)
                self.message_sender.send_message([0x90 | channel, int(midi_note), velocity])
                log(TAG_MESSAGE, f"Created Note note_on: ch={channel} note={midi_note} vel={velocity}")
                log(TAG_MESSAGE, f"MPE Note On: zone=lower ch={channel} note={midi_note} vel={velocity}")
        except Exception as e:
            log(TAG_MESSAGE, f"Error handling note on: {str(e)}", is_error=True)

    def _handle_note_off(self, midi_note, velocity, key_id):
        try:
            note_state = self.channel_manager.get_note_state(key_id)
            if note_state:
                channel = note_state.channel
                # Send Note Off
                self.message_sender.send_message([0x80 | channel, int(midi_note), velocity])
                log(TAG_MESSAGE, f"Created Note Off: ch={channel} note={midi_note} vel={velocity}")
                log(TAG_MESSAGE, f"MPE Note Off: zone=lower ch={channel} note={midi_note} vel={velocity}")
                
                # Only release channel once Note Off is in stream
                if self.message_sender.is_note_off_in_stream(channel):
                    self.channel_manager.release_note(key_id)
                    log(TAG_MESSAGE, f"Channel {channel} released after Note Off confirmed in stream")
        except Exception as e:
            log(TAG_MESSAGE, f"Error handling note off: {str(e)}", is_error=True)

    def _handle_control_change(self, cc_number, midi_value):
        try:
            self.message_sender.send_message([0xB0 | ZONE_MANAGER, cc_number, midi_value])
            log(TAG_MESSAGE, f"Created Control Change: ch={ZONE_MANAGER} cc={cc_number} value={midi_value}")
            log(TAG_MESSAGE, f"MPE Control Change: zone=lower ch={ZONE_MANAGER} cc={cc_number} value={midi_value}")
        except Exception as e:
            log(TAG_MESSAGE, f"Error handling control change: {str(e)}", is_error=True)
