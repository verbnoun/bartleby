"""Rotary encoder handling and position tracking."""

import rotaryio
from logging import log, TAG_ENCODER

class RotaryEncoderHandler:
    def __init__(self, octave_clk_pin, octave_dt_pin):
        """Initialize rotary encoder handler"""
        try:
            log(TAG_ENCODER, "Initializing rotary encoder handler")
            
            # Initialize encoders using rotaryio
            self.encoders = [
                rotaryio.IncrementalEncoder(octave_clk_pin, octave_dt_pin, divisor=2)
            ]
            
            self.num_encoders = len(self.encoders)
            self.min_position = -3  # Allow down three octaves
            self.max_position = 3   # Allow up three octaves

            # Initialize state tracking
            self.encoder_positions = [0] * self.num_encoders
            self.last_positions = [encoder.position for encoder in self.encoders]

            self.reset_all_encoder_positions()
            log(TAG_ENCODER, f"Initialized {self.num_encoders} encoder(s)")
            
        except Exception as e:
            log(TAG_ENCODER, f"Encoder initialization failed: {str(e)}", is_error=True)
            raise

    def reset_all_encoder_positions(self):
        """Reset all encoder positions to initial state"""
        try:
            log(TAG_ENCODER, "Resetting all encoder positions")
            for i in range(self.num_encoders):
                self.reset_encoder_position(i)
            log(TAG_ENCODER, "All encoder positions reset to 0")
        except Exception as e:
            log(TAG_ENCODER, f"Error resetting all encoders: {str(e)}", is_error=True)

    def reset_encoder_position(self, encoder_num):
        """Reset specified encoder to initial position"""
        try:
            if 0 <= encoder_num < self.num_encoders:
                self.encoders[encoder_num].position = 0
                self.encoder_positions[encoder_num] = 0
                self.last_positions[encoder_num] = 0
                log(TAG_ENCODER, f"Reset encoder {encoder_num} to position 0")
            else:
                log(TAG_ENCODER, f"Invalid encoder number: {encoder_num}", is_error=True)
        except Exception as e:
            log(TAG_ENCODER, f"Error resetting encoder {encoder_num}: {str(e)}", is_error=True)

    def read_encoder(self, encoder_num):
        """Read encoder and return events if position changed"""
        events = []
        try:
            if not 0 <= encoder_num < self.num_encoders:
                log(TAG_ENCODER, f"Invalid encoder number: {encoder_num}", is_error=True)
                return events
                
            encoder = self.encoders[encoder_num]
            
            # Read current position
            current_position = encoder.position
            last_position = self.last_positions[encoder_num]

            # Check if the encoder position has changed
            if current_position != last_position:
                # Calculate direction (-1 for left, +1 for right)
                direction = 1 if current_position > last_position else -1

                # Update position with bounds checking
                new_pos = max(self.min_position, min(self.max_position, 
                                                     self.encoder_positions[encoder_num] + direction))
                
                # Only generate event if position actually changed within limits
                if new_pos != self.encoder_positions[encoder_num]:
                    old_pos = self.encoder_positions[encoder_num]
                    self.encoder_positions[encoder_num] = new_pos
                    events.append(('rotation', encoder_num, direction, new_pos))
                    
                    # Log position change
                    dir_text = "up" if direction > 0 else "down"
                    log(TAG_ENCODER, f"Encoder {encoder_num} moved {dir_text}: {old_pos} -> {new_pos}")
                elif new_pos == self.encoder_positions[encoder_num]:
                    # Position unchanged due to limits
                    log(TAG_ENCODER, f"Encoder {encoder_num} at limit: {new_pos}")
            
            # Save the current position for the next read
            self.last_positions[encoder_num] = current_position
            
            return events
            
        except Exception as e:
            log(TAG_ENCODER, f"Error reading encoder {encoder_num}: {str(e)}", is_error=True)
            return events

    def get_encoder_position(self, encoder_num):
        """Get current position of specified encoder"""
        try:
            if 0 <= encoder_num < self.num_encoders:
                position = self.encoder_positions[encoder_num]
                log(TAG_ENCODER, f"Encoder {encoder_num} position: {position}")
                return position
            else:
                log(TAG_ENCODER, f"Invalid encoder number: {encoder_num}", is_error=True)
                return 0
        except Exception as e:
            log(TAG_ENCODER, f"Error getting encoder {encoder_num} position: {str(e)}", is_error=True)
            return 0
