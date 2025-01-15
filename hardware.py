"""Hardware component management and coordination."""

import board
import digitalio
from constants import (
    KEYBOARD_L1A_MUX_SIG, KEYBOARD_L1A_MUX_S0, KEYBOARD_L1A_MUX_S1, KEYBOARD_L1A_MUX_S2, KEYBOARD_L1A_MUX_S3,
    KEYBOARD_L1B_MUX_SIG, KEYBOARD_L1B_MUX_S0, KEYBOARD_L1B_MUX_S1, KEYBOARD_L1B_MUX_S2, KEYBOARD_L1B_MUX_S3,
    KEYBOARD_L2_MUX_S0, KEYBOARD_L2_MUX_S1, KEYBOARD_L2_MUX_S2, KEYBOARD_L2_MUX_S3,
    CONTROL_MUX_SIG, CONTROL_MUX_S0, CONTROL_MUX_S1, CONTROL_MUX_S2, CONTROL_MUX_S3,
    OCTAVE_UP_PIN, OCTAVE_DOWN_PIN
)
from logging import log, TAG_HARDWAR
from mux import Multiplexer
from keyboard import KeyboardHandler
from encoder import OctaveButtonHandler
from pots import PotentiometerHandler

class HardwareManager:
    def __init__(self):
        """Initialize all hardware components"""
        try:
            log(TAG_HARDWAR, "Initializing hardware components")
            
            # Initialize multiplexers
            log(TAG_HARDWAR, "Setting up keyboard layer 1A multiplexer")
            self.l1a_mux = Multiplexer(
                KEYBOARD_L1A_MUX_SIG,
                KEYBOARD_L1A_MUX_S0,
                KEYBOARD_L1A_MUX_S1,
                KEYBOARD_L1A_MUX_S2,
                KEYBOARD_L1A_MUX_S3,
                name="L1A"  # Keys 1-12
            )
            
            log(TAG_HARDWAR, "Setting up keyboard layer 1B multiplexer")
            self.l1b_mux = Multiplexer(
                KEYBOARD_L1B_MUX_SIG,
                KEYBOARD_L1B_MUX_S0,
                KEYBOARD_L1B_MUX_S1,
                KEYBOARD_L1B_MUX_S2,
                KEYBOARD_L1B_MUX_S3,
                name="L1B"  # Keys 13-25
            )
            
            log(TAG_HARDWAR, "Setting up control multiplexer")
            self.control_mux = Multiplexer(
                CONTROL_MUX_SIG,
                CONTROL_MUX_S0,
                CONTROL_MUX_S1,
                CONTROL_MUX_S2,
                CONTROL_MUX_S3,
                name="CTRL"  # Potentiometers
            )

            # Initialize keyboard handler
            log(TAG_HARDWAR, "Initializing keyboard handler")
            self.keyboard = KeyboardHandler(
                self.l1a_mux,
                self.l1b_mux,
                KEYBOARD_L2_MUX_S0,
                KEYBOARD_L2_MUX_S1,
                KEYBOARD_L2_MUX_S2,
                KEYBOARD_L2_MUX_S3
            )

            # Initialize octave button handler
            log(TAG_HARDWAR, "Initializing octave button handler")
            self.octave_control = OctaveButtonHandler(
                OCTAVE_UP_PIN,
                OCTAVE_DOWN_PIN
            )

            # Initialize potentiometer handler
            log(TAG_HARDWAR, "Initializing potentiometer handler")
            self.pots = PotentiometerHandler(self.control_mux)
            
            log(TAG_HARDWAR, "Hardware initialization complete")
        except Exception as e:
            log(TAG_HARDWAR, f"Hardware initialization failed: {str(e)}", is_error=True)
            raise

    def read_keyboard(self):
        """Read keyboard state changes"""
        try:
            changes = self.keyboard.read_keys()
            if changes:
                log(TAG_HARDWAR, f"Keyboard changes detected: {len(changes)} events")
            return changes
        except Exception as e:
            log(TAG_HARDWAR, f"Error reading keyboard: {str(e)}", is_error=True)
            return []

    def read_octave_buttons(self):
        """Read octave button state changes"""
        try:
            changes = self.octave_control.read_buttons()
            if changes:
                log(TAG_HARDWAR, f"Octave button changes: {len(changes)} events")
            return changes
        except Exception as e:
            log(TAG_HARDWAR, f"Error reading octave buttons: {str(e)}", is_error=True)
            return []

    def read_pots(self):
        """Read potentiometer changes"""
        try:
            changes = self.pots.read_pots()
            if changes:
                log(TAG_HARDWAR, f"Potentiometer changes: {len(changes)} events")
            return changes
        except Exception as e:
            log(TAG_HARDWAR, f"Error reading potentiometers: {str(e)}", is_error=True)
            return []

    def read_all_pots(self):
        """Read all potentiometer values"""
        try:
            values = self.pots.read_all_pots()
            log(TAG_HARDWAR, f"Read {len(values)} potentiometer values")
            return values
        except Exception as e:
            log(TAG_HARDWAR, f"Error reading all potentiometers: {str(e)}", is_error=True)
            return []

    def get_octave_position(self):
        """Get current octave position"""
        try:
            position = self.octave_control.get_position()
            return position
        except Exception as e:
            log(TAG_HARDWAR, f"Error getting octave position: {str(e)}", is_error=True)
            return 0

    def reset_octave_position(self):
        """Reset octave position"""
        try:
            self.octave_control.reset_position()
            log(TAG_HARDWAR, "Reset octave position")
        except Exception as e:
            log(TAG_HARDWAR, f"Error resetting octave position: {str(e)}", is_error=True)

    def format_key_hardware_data(self):
        """Get formatted hardware data for debugging"""
        try:
            data = self.keyboard.format_key_hardware_data()
            log(TAG_HARDWAR, "Generated key hardware debug data")
            return data
        except Exception as e:
            log(TAG_HARDWAR, f"Error formatting key hardware data: {str(e)}", is_error=True)
            return ""
