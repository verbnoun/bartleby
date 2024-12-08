from constants import (
    MPE_MEMBER_PITCH_BEND_RANGE,
    MPE_MASTER_PITCH_BEND_RANGE,
    ZONE_START,
    ZONE_END
)
from logging import log, TAG_CONFIG

class MPEConfigurator:
    """Handles MPE-specific configuration and setup"""
    def __init__(self, message_sender):
        self.message_sender = message_sender

    def configure_mpe(self):
        """Configure MPE zones and pitch bend ranges"""
        log(TAG_CONFIG, "Configuring MPE zones and pitch bend ranges")
            
        # Reset all channels first
        self.message_sender.send_message([0xB0, 121, 0])  # Reset all controllers
        self.message_sender.send_message([0xB0, 123, 0])  # All notes off
        
        # Configure MPE zone (RPN 6)
        self.message_sender.send_message([0xB0, 101, 0])  # RPN MSB
        self.message_sender.send_message([0xB0, 100, 6])  # RPN LSB (MCM)
        zone_size = ZONE_END - ZONE_START + 1
        self.message_sender.send_message([0xB0, 6, zone_size])
        log(TAG_CONFIG, f"MPE zone configured: {zone_size} channels")
        
        # Configure Manager Channel pitch bend range
        self.message_sender.send_message([0xB0, 101, 0])  # RPN MSB
        self.message_sender.send_message([0xB0, 100, 0])  # RPN LSB (pitch bend)
        self.message_sender.send_message([0xB0, 6, MPE_MASTER_PITCH_BEND_RANGE])
        log(TAG_CONFIG, f"Manager channel pitch bend range: {MPE_MASTER_PITCH_BEND_RANGE} semitones")
        
        # Configure Member Channel pitch bend range
        for channel in range(ZONE_START, ZONE_END + 1):
            self.message_sender.send_message([0xB0 | channel, 101, 0])  # RPN MSB
            self.message_sender.send_message([0xB0 | channel, 100, 0])  # RPN LSB (pitch bend)
            self.message_sender.send_message([0xB0 | channel, 6, MPE_MEMBER_PITCH_BEND_RANGE])
        log(TAG_CONFIG, f"Member channels pitch bend range: {MPE_MEMBER_PITCH_BEND_RANGE} semitones")
