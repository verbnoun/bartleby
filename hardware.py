import board
import digitalio
from constants import (
    KEYBOARD_L1A_MUX_SIG, KEYBOARD_L1A_MUX_S0, KEYBOARD_L1A_MUX_S1, KEYBOARD_L1A_MUX_S2, KEYBOARD_L1A_MUX_S3,
    KEYBOARD_L1B_MUX_SIG, KEYBOARD_L1B_MUX_S0, KEYBOARD_L1B_MUX_S1, KEYBOARD_L1B_MUX_S2, KEYBOARD_L1B_MUX_S3,
    KEYBOARD_L2_MUX_S0, KEYBOARD_L2_MUX_S1, KEYBOARD_L2_MUX_S2, KEYBOARD_L2_MUX_S3,
    CONTROL_MUX_SIG, CONTROL_MUX_S0, CONTROL_MUX_S1, CONTROL_MUX_S2, CONTROL_MUX_S3,
    OCTAVE_ENC_CLK, OCTAVE_ENC_DT
)

from mux import Multiplexer
from keyboard import KeyboardHandler
from encoder import RotaryEncoderHandler
from pots import PotentiometerHandler

class HardwareManager:
    def __init__(self):
        """Initialize all hardware components"""
        # Initialize multiplexers
        self.l1a_mux = Multiplexer(
            KEYBOARD_L1A_MUX_SIG,
            KEYBOARD_L1A_MUX_S0,
            KEYBOARD_L1A_MUX_S1,
            KEYBOARD_L1A_MUX_S2,
            KEYBOARD_L1A_MUX_S3
        )
        
        self.l1b_mux = Multiplexer(
            KEYBOARD_L1B_MUX_SIG,
            KEYBOARD_L1B_MUX_S0,
            KEYBOARD_L1B_MUX_S1,
            KEYBOARD_L1B_MUX_S2,
            KEYBOARD_L1B_MUX_S3
        )
        
        self.control_mux = Multiplexer(
            CONTROL_MUX_SIG,
            CONTROL_MUX_S0,
            CONTROL_MUX_S1,
            CONTROL_MUX_S2,
            CONTROL_MUX_S3
        )

        # Initialize keyboard handler
        self.keyboard = KeyboardHandler(
            self.l1a_mux,
            self.l1b_mux,
            KEYBOARD_L2_MUX_S0,
            KEYBOARD_L2_MUX_S1,
            KEYBOARD_L2_MUX_S2,
            KEYBOARD_L2_MUX_S3
        )

        # Initialize encoder handler
        self.encoder = RotaryEncoderHandler(
            OCTAVE_ENC_CLK,
            OCTAVE_ENC_DT
        )

        # Initialize potentiometer handler
        self.pots = PotentiometerHandler(self.control_mux)

    def read_keyboard(self):
        """Read keyboard state changes"""
        return self.keyboard.read_keys()

    def read_encoder(self, encoder_num):
        """Read encoder state changes"""
        return self.encoder.read_encoder(encoder_num)

    def read_pots(self):
        """Read potentiometer changes"""
        return self.pots.read_pots()

    def read_all_pots(self):
        """Read all potentiometer values"""
        return self.pots.read_all_pots()

    def get_encoder_position(self, encoder_num):
        """Get current encoder position"""
        return self.encoder.get_encoder_position(encoder_num)

    def reset_encoder_position(self, encoder_num):
        """Reset encoder position"""
        self.encoder.reset_encoder_position(encoder_num)

    def format_key_hardware_data(self):
        """Get formatted hardware data for debugging"""
        return self.keyboard.format_key_hardware_data()
