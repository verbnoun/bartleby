from constants import (
    DEBUG,
    ZONE_START,
    ZONE_END
)

class ZoneManager:
    def __init__(self):
        self.active_notes = {}
        self.channel_notes = {}
        self.pending_channels = {}
        self.available_channels = list(range(
            ZONE_START, 
            ZONE_END + 1
        ))

    def allocate_channel(self, key_id):
        """Get next available channel using robust allocation strategy"""
        # Check pending allocation first
        if key_id in self.pending_channels:
            return self.pending_channels[key_id]
            
        # Check if note already has an active channel
        if key_id in self.active_notes and self.active_notes[key_id].active:
            return self.active_notes[key_id].channel

        # Find completely free channel first
        for channel in self.available_channels:
            if channel not in self.channel_notes or not self.channel_notes[channel]:
                if DEBUG:
                    print(f"Allocated free channel {channel} for key {key_id}")
                self.pending_channels[key_id] = channel
                return channel

        # If no free channels, find channel with fewest active notes
        min_notes = float('inf')
        best_channel = None
        
        for channel in self.available_channels:
            note_count = len(self.channel_notes.get(channel, set()))
            if note_count < min_notes:
                min_notes = note_count
                best_channel = channel

        if best_channel is not None:
            if DEBUG:
                print(f"Allocated least used channel {best_channel} for key {key_id}")
            self.pending_channels[key_id] = best_channel
            return best_channel

        # Fallback to first channel if all else fails
        if DEBUG:
            print(f"No optimal channels available, using first MPE channel for key {key_id}")
        self.pending_channels[key_id] = ZONE_START
        return ZONE_START

    def add_note(self, key_id, midi_note, channel, velocity):
        """Add new note and track its channel allocation"""
        from notes import NoteState  # Import here to avoid circular dependency
        note_state = NoteState(key_id, midi_note, channel, velocity)
        self.active_notes[key_id] = note_state
        
        # Track channel usage
        if channel not in self.channel_notes:
            self.channel_notes[channel] = set()
        self.channel_notes[channel].add(key_id)
        
        # Clear pending allocation
        self.pending_channels.pop(key_id, None)
        
        if DEBUG:
            print(f"Added note: key={key_id}, note={midi_note}, channel={channel}, velocity={velocity}")
        return note_state

    def _release_note(self, key_id):
        """Internal method to handle note release and cleanup"""
        if key_id in self.active_notes:
            note_state = self.active_notes[key_id]
            note_state.active = False
            channel = note_state.channel
            
            # Clean up channel tracking
            if channel in self.channel_notes:
                self.channel_notes[channel].discard(key_id)
                if DEBUG:
                    print(f"Released channel {channel} from key {key_id}")
                    
            # Clear any pending allocation
            self.pending_channels.pop(key_id, None)

    def release_note(self, key_id):
        self._release_note(key_id)

    def get_note_state(self, key_id):
        note_state = self.active_notes.get(key_id)
        return note_state if note_state and note_state.active else None

    def get_active_notes(self):
        return [note for note in self.active_notes.values() if note.active]
