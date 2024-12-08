import rotaryio
from constants import DEBUG

class RotaryEncoderHandler:
    def __init__(self, octave_clk_pin, octave_dt_pin):
        """Initialize rotary encoder handler"""
        # Initialize encoders using rotaryio
        self.encoders = [
            rotaryio.IncrementalEncoder(octave_clk_pin, octave_dt_pin, divisor=2)
        ]
        
        self.num_encoders = len(self.encoders)
        self.min_position = -3  # Changed from 0 to -3 to allow down three octaves
        self.max_position = 3   # Allow up three octaves

        # Initialize state tracking
        self.encoder_positions = [0] * self.num_encoders
        self.last_positions = [encoder.position for encoder in self.encoders]

        self.reset_all_encoder_positions()

    def reset_all_encoder_positions(self):
        """Reset all encoder positions to initial state"""
        for i in range(self.num_encoders):
            self.reset_encoder_position(i)

    def reset_encoder_position(self, encoder_num):
        """Reset specified encoder to initial position"""
        if 0 <= encoder_num < self.num_encoders:
            self.encoders[encoder_num].position = 0
            self.encoder_positions[encoder_num] = 0
            self.last_positions[encoder_num] = 0

    def read_encoder(self, encoder_num):
        """Read encoder and return events if position changed"""
        events = []
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
                self.encoder_positions[encoder_num] = new_pos
                events.append(('rotation', encoder_num, direction, new_pos))
                
                if DEBUG:
                    print(f"E{encoder_num}: Position: {self.encoder_positions[encoder_num]} -> {new_pos}")
        
        # Save the current position for the next read
        self.last_positions[encoder_num] = current_position
        
        return events

    def get_encoder_position(self, encoder_num):
        """Get current position of specified encoder"""
        if 0 <= encoder_num < self.num_encoders:
            return self.encoder_positions[encoder_num]
        return 0
