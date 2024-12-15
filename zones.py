"""MPE zone and channel management."""

from constants import (
    ZONE_START,
    ZONE_END
)
from logging import log, TAG_ZONES

class ZoneManager:
    def __init__(self):
        try:
            log(TAG_ZONES, f"Initializing zone manager for channels {ZONE_START}-{ZONE_END}")
            self.active_notes = {}
            self.channel_notes = {}
            self.pending_channels = {}
            self.available_channels = list(range(
                ZONE_START, 
                ZONE_END + 1
            ))
            log(TAG_ZONES, f"Zone manager initialized with {len(self.available_channels)} channels")
        except Exception as e:
            log(TAG_ZONES, f"Failed to initialize zone manager: {str(e)}", is_error=True)
            raise

    def allocate_channel(self, key_id):
        """Get next available channel using robust allocation strategy"""
        try:
            # Check pending allocation first
            if key_id in self.pending_channels:
                channel = self.pending_channels[key_id]
                log(TAG_ZONES, f"Using pending channel {channel} for key {key_id}")
                return channel
                
            # Check if note already has an active channel
            if key_id in self.active_notes and self.active_notes[key_id].active:
                channel = self.active_notes[key_id].channel
                log(TAG_ZONES, f"Reusing active channel {channel} for key {key_id}")
                return channel

            # Find completely free channel first
            for channel in self.available_channels:
                if channel not in self.channel_notes or not self.channel_notes[channel]:
                    log(TAG_ZONES, f"Allocated free channel {channel} for key {key_id}")
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
                log(TAG_ZONES, f"Allocated least used channel {best_channel} (notes: {min_notes}) for key {key_id}")
                self.pending_channels[key_id] = best_channel
                return best_channel

            # Fallback to first channel if all else fails
            log(TAG_ZONES, f"No optimal channels available, using first MPE channel for key {key_id}", is_error=True)
            self.pending_channels[key_id] = ZONE_START
            return ZONE_START
            
        except Exception as e:
            log(TAG_ZONES, f"Error allocating channel for key {key_id}: {str(e)}", is_error=True)
            return ZONE_START

    def add_note(self, key_id, midi_note, channel, velocity):
        """Add new note and track its channel allocation"""
        try:
            from notes import NoteState  # Import here to avoid circular dependency
            note_state = NoteState(key_id, midi_note, channel, velocity)
            self.active_notes[key_id] = note_state
            
            # Track channel usage
            if channel not in self.channel_notes:
                self.channel_notes[channel] = set()
            self.channel_notes[channel].add(key_id)
            
            # Clear pending allocation
            self.pending_channels.pop(key_id, None)
            
            log(TAG_ZONES, f"Added note: key={key_id}, note={midi_note}, channel={channel}, velocity={velocity}")
            
            # Log channel usage statistics
            for ch in self.channel_notes:
                if self.channel_notes[ch]:
                    log(TAG_ZONES, f"Channel {ch} has {len(self.channel_notes[ch])} active notes")
                    
            return note_state
            
        except Exception as e:
            log(TAG_ZONES, f"Error adding note for key {key_id}: {str(e)}", is_error=True)
            return None

    def _release_note(self, key_id):
        """Internal method to handle note release and cleanup"""
        try:
            if key_id in self.active_notes:
                note_state = self.active_notes[key_id]
                note_state.active = False
                channel = note_state.channel
                
                # Clean up channel tracking
                if channel in self.channel_notes:
                    self.channel_notes[channel].discard(key_id)
                    log(TAG_ZONES, f"Released channel {channel} from key {key_id}")
                    
                # Clear any pending allocation
                self.pending_channels.pop(key_id, None)
                
                # Remove inactive note from active_notes to prevent ghost notes
                del self.active_notes[key_id]
                log(TAG_ZONES, f"Removed inactive note {key_id} from active_notes")
                
                # Log remaining channel usage
                active_channels = sum(1 for ch in self.channel_notes if self.channel_notes[ch])
                log(TAG_ZONES, f"Channels in use after release: {active_channels}")
                
        except Exception as e:
            log(TAG_ZONES, f"Error releasing note for key {key_id}: {str(e)}", is_error=True)

    def release_note(self, key_id):
        """Release a note and its channel allocation"""
        self._release_note(key_id)

    def get_note_state(self, key_id):
        """Get the active note state for a key"""
        try:
            note_state = self.active_notes.get(key_id)
            return note_state if note_state and note_state.active else None
        except Exception as e:
            log(TAG_ZONES, f"Error getting note state for key {key_id}: {str(e)}", is_error=True)
            return None

    def get_active_notes(self):
        """Get all currently active notes"""
        try:
            active_notes = [note for note in self.active_notes.values() if note.active]
            log(TAG_ZONES, f"Current active notes: {len(active_notes)}")
            return active_notes
        except Exception as e:
            log(TAG_ZONES, f"Error getting active notes: {str(e)}", is_error=True)
            return []
