import time
import math
import usb_midi
import busio
from collections import deque

class Constants:
	DEBUG = True
	WELCOME_SEQUENCE = "mpe_demo"

	# MIDI Transport Settings
	MIDI_BAUDRATE = 31250
	UART_TIMEOUT = 0.001
	SEE_HEARTBEAT = False
	
	# MPE Configuration
	MPE_MASTER_CHANNEL = 0      # MIDI channel 1 (zero-based)
	MPE_ZONE_START = 1          # MIDI channel 2 (zero-based)
	MPE_ZONE_END = 11           # MIDI channel 15 (leaving channel 16 free per MPE spec)

	# MIDI CC Numbers - Standard Controls
	CC_MODULATION = 1
	CC_VOLUME = 7
	CC_FILTER_RESONANCE = 71
	CC_RELEASE_TIME = 72
	CC_ATTACK_TIME = 73
	CC_FILTER_CUTOFF = 74
	CC_DECAY_TIME = 75
	CC_SUSTAIN_LEVEL = 76

	# MIDI CC Numbers - MPE Specific
	CC_LEFT_PRESSURE = 78       # Left sensor pressure
	CC_RIGHT_PRESSURE = 79      # Right sensor pressure
	CC_CHANNEL_PRESSURE = 74    # Standard MPE channel pressure
	
	# MIDI RPN Messages
	RPN_MSB = 0
	RPN_LSB_MPE = 6
	
	# MIDI Pitch Bend
	PITCH_BEND_CENTER = 8192
	PITCH_BEND_MAX = 16383
	
	# Note Management
	MAX_ACTIVE_NOTES = 14       # Maximum concurrent notes (matches available MPE channels)
	
	# MPE Settings
	MPE_PITCH_BEND_RANGE = 48   # Default to 48 semitones for MPE

	# Default CC Assignments for Pots
	DEFAULT_CC_ASSIGNMENTS = {
		0: CC_FILTER_CUTOFF,     # Pot 0: Filter Cutoff
		1: CC_FILTER_RESONANCE,  # Pot 1: Filter Resonance
		2: CC_ATTACK_TIME,       # Pot 2: Attack
		3: CC_DECAY_TIME,        # Pot 3: Decay
		4: CC_SUSTAIN_LEVEL,     # Pot 4: Sustain
		5: CC_RELEASE_TIME,      # Pot 5: Release
		6: CC_VOLUME,            # Pot 6: Volume
		7: CC_MODULATION,        # Pot 7: Modulation
		8: 20,                   # Pot 8: Unassigned (CC20)
		9: 21,                   # Pot 9: Unassigned (CC21)
		10: 22,                  # Pot 10: Unassigned (CC22)
		11: 23,                  # Pot 11: Unassigned (CC23)
		12: 24,                  # Pot 12: Unassigned (CC24)
		13: 25,                  # Pot 13: Unassigned (CC25)
	}

class WelcomeSequence:
	"""Handles musical greeting sequences using MPE capabilities"""
	
	def __init__(self, midi_logic):
		self.midi = midi_logic
		self.base_key_id = -100  # Use negative IDs to avoid conflicts with real keys
		
	def play_connection_greeting(self):
		"""Play selected greeting sequence"""
		if Constants.WELCOME_SEQUENCE == "classic":
			self._play_classic_greeting()
		else:
			self._play_mpe_demo()

	def _play_classic_greeting(self):
		"""Original simple greeting sequence"""
		# Greeting sequence: C E G C (ascending)
		greeting_notes = [60, 64, 67, 72]  # MIDI notes
		velocities = [0.6, 0.7, 0.8, 0.9]  # Normalized velocities
		durations = [0.2, 0.2, 0.2, 0.4]   # Note durations in seconds
		
		for idx, (note, velocity, duration) in enumerate(zip(greeting_notes, velocities, durations)):
			key_id = self.base_key_id - idx
			# Send pitch bend (centered)
			bend_value = Constants.PITCH_BEND_CENTER
			lsb = bend_value & 0x7F
			msb = (bend_value >> 7) & 0x7F
			self.midi._send_message([0xE0, lsb, msb])
			
			# Send initial pressure
			pressure_value = int(0.75 * 127)  # Default pressure
			self.midi._send_message([0xD0, pressure_value, 0])
			
			# Send note on
			self.midi._send_message([0x90, note, int(velocity * 127)])
			
			# Hold note
			time.sleep(duration)
			
			# Note off
			self.midi._send_message([0x80, note, 0])
			
			# Small gap between notes
			time.sleep(0.05)

	def _play_mpe_demo(self):
		"""MPE demo sequence with expressive controls"""
		"""
		An MPE greeting sequence demonstrating pitch bends, pressure, and timbre.
		Duration: ~2.2 seconds
		Structure: 
		- Chord with increasing pressure and rising pitch bend
		- Quick ascending sequence with varying pressure and CC74
		- Final note with expressive control
		"""
		# Utility function to send MIDI events
		def send_midi_events(events):
			for event in events:
				self.midi.send_midi_event(event)
				
		# Base chord notes (C major 7)
		chord = [60, 64, 67, 71]  # C E G B
		velocities = [0.7, 0.75, 0.8, 0.85]
		
		# Play chord with increasing pressure and rising bend
		for idx, (note, vel) in enumerate(zip(chord, velocities)):
			key_id = self.base_key_id - idx
			# Initial state - no bend, medium pressure
			send_midi_events([
				('pitch_bend_init', key_id, 0.0),
				('pressure_init', key_id, 0.5),
				('note_on', note, int(vel * 127), key_id)
			])
			time.sleep(0.05)
		
		# Gradually increase pressure and add upward bend
		steps = 20
		for i in range(steps):
			pressure = 0.5 + (i/steps * 0.4)  # 0.5 -> 0.9
			bend = i/steps * 0.3  # 0.0 -> 0.3 (about a quarter tone up)
			
			for idx in range(len(chord)):
				key_id = self.base_key_id - idx
				send_midi_events([
					('pressure_update', key_id, pressure, bend)
				])
			time.sleep(0.02)
		
		# Release chord
		for idx, note in enumerate(chord):
			key_id = self.base_key_id - idx
			send_midi_events([
				('note_off', note, 0, key_id)
			])
			
		# Quick ascending sequence with varying timbre
		ascending = [72, 76, 79, 84]  # C E G C
		for idx, note in enumerate(ascending):
			key_id = self.base_key_id - (idx + 10)  # New set of IDs
			timbre = 0.3 + (idx / len(ascending) * 0.6)  # Gradually open filter
			pressure = 0.9 - (idx / len(ascending) * 0.4)  # Gradually decrease pressure
			
			send_midi_events([
				('pitch_bend_init', key_id, 0.0),
				('pressure_init', key_id, pressure),
				('control_change', 74, int(timbre * 127), timbre),
				('note_on', note, int(0.8 * 127), key_id)
			])
			time.sleep(0.12)
			send_midi_events([
				('note_off', note, 0, key_id)
			])
			time.sleep(0.02)
			
		# Final note with expressive flourish
		final_key_id = self.base_key_id - 20
		send_midi_events([
			('pitch_bend_init', final_key_id, -0.2),  # Start slightly flat
			('pressure_init', final_key_id, 0.4),
			('note_on', 84, int(0.85 * 127), final_key_id)  # High C
		])
		
		# Expressive movement
		steps = 30
		for i in range(steps):
			t = i / steps
			# Slide up to pitch then add subtle vibrato
			if t < 0.3:
				bend = -0.2 + (t/0.3 * 0.2)  # Slide up to pitch
			else:
				bend = math.sin((t-0.3) * math.pi * 8) * 0.02  # Subtle vibrato
				
			# Pressure swells then relaxes
			if t < 0.6:
				pressure = 0.4 + (t/0.6 * 0.5)
			else:
				pressure = 0.9 - ((t-0.6)/0.4 * 0.7)
				
			send_midi_events([
				('pressure_update', final_key_id, pressure, bend)
			])
			time.sleep(0.02)
			
		# Gentle release
		send_midi_events([
			('pressure_update', final_key_id, 0.1, 0.0),
			('note_off', 84, 0, final_key_id)
		])

class MidiTransportManager:
	"""Manages both UART and USB MIDI output streams"""
	def __init__(self, tx_pin, rx_pin, midi_callback=None):
		print(f"Initializing MIDI Transport Manager")
		self.midi_callback = midi_callback
		self._setup_uart(tx_pin, rx_pin)
		self._setup_usb()
		
	def _setup_uart(self, tx_pin, rx_pin):
		"""Initialize UART for MIDI communication"""
		try:
			self.uart = busio.UART(
				tx=tx_pin,
				rx=rx_pin,
				baudrate=Constants.MIDI_BAUDRATE,
				bits=8,
				parity=None,
				stop=1,
				timeout=Constants.UART_TIMEOUT
			)
			print("UART MIDI initialized")
		except Exception as e:
			print(f"UART initialization error: {str(e)}")
			raise

	def _setup_usb(self):
		"""Initialize USB MIDI output"""
		try:
			self.usb_midi = usb_midi.ports[1]
			print("USB MIDI initialized")
		except Exception as e:
			print(f"USB MIDI initialization error: {str(e)}")
			raise

	def send_message(self, message):
		"""Send MIDI message to both UART and USB outputs"""
		try:
			# Send via UART
			self.uart.write(bytes(message))
			# Send via USB
			self.usb_midi.write(bytes(message))
		except Exception as e:
			if str(e):  # Only print if there's an actual error message
				print(f"Error sending MIDI: {str(e)}")

	def check_for_messages(self):
		"""Check for incoming MIDI messages on UART"""
		try:
			if self.uart.in_waiting:
				new_bytes = self.uart.read(self.uart.in_waiting)
				if new_bytes:
					try:
						# Try to decode as UTF-8 and strip any whitespace/newlines
						message = new_bytes.decode('utf-8').strip()
						
						if message.startswith("cc:"):  # Configuration message
							if self.midi_callback:
								self.midi_callback(message)
							if Constants.DEBUG:
								print(f"Received config: {message}")
						elif message == "hello from candide":
							if Constants.DEBUG:
								print(f"Received message: {message}")
							return "hello"  # Special return value for hello message
						elif Constants.DEBUG:
							if message.strip() == "♡":
								if Constants.SEE_HEARTBEAT:
									print(f"Cart {message}")
							else:
								print(f"Received message: {message}")
						return True
					except UnicodeDecodeError:
						if Constants.DEBUG:
							print(f"Received non-text data: {new_bytes.hex()}")
				return False
		except Exception as e:
			if str(e):
				print(f"Error reading UART: {str(e)}")
			return False

	def cleanup(self):
		"""Clean shutdown of MIDI transport"""
		try:
			self.uart.deinit()
			print("MIDI transport cleaned up")
		except Exception as e:
			if str(e):
				print(f"Error during cleanup: {str(e)}")

class MPEConfiguration:
	"""Handles MPE configuration and CC assignments"""
	def __init__(self):
		self.cc_assignments = Constants.DEFAULT_CC_ASSIGNMENTS.copy()
		self.ready_for_midi = False

	def _configure_system(self, transport):
		"""Initialize system with MPE configuration"""
		# Reset all channels first
		transport._send_message([0xB0, 121, 0])  # Reset all controllers
		transport._send_message([0xB0, 123, 0])  # All notes off
		
		# Configure MPE zone
		transport._send_message([0xB0, 101, Constants.RPN_MSB])       # RPN MSB
		transport._send_message([0xB0, 100, Constants.RPN_LSB_MPE])   # RPN LSB (MCM message)
		transport._send_message([0xB0, 6, Constants.MPE_ZONE_END])    # Number of member channels
		
		# Configure pitch bend range
		transport._send_message([0xB0, 101, 0])  # RPN MSB
		transport._send_message([0xB0, 100, 0])  # RPN LSB (pitch bend range)
		transport._send_message([0xB0, 6, Constants.MPE_PITCH_BEND_RANGE])  # Set pitch bend range
		transport._send_message([0xB0, 38, 0])   # LSB (always 0 for pitch bend range)
		
		self.ready_for_midi = True
		if Constants.DEBUG:
			print("MIDI system ready for input")

	def handle_config_message(self, message):
		"""Parse and handle configuration message from Candide"""
		try:
			if not message.startswith("cc:"):
				return False

			assignments = message[3:].split(',')
			for assignment in assignments:
				if '=' not in assignment:
					continue
				pot, cc = assignment.split('=')
				pot_num = int(pot)
				cc_num = int(cc)
				if 0 <= pot_num <= 13 and 0 <= cc_num <= 127:
					self.cc_assignments[pot_num] = cc_num
					if Constants.DEBUG:
						print(f"Assigned Pot {pot_num} to CC {cc_num}")

			return True

		except Exception as e:
			print(f"Error parsing CC config: {str(e)}")
			return False

	def reset_cc_defaults(self):
		"""Reset CC assignments to defaults"""
		self.cc_assignments = Constants.DEFAULT_CC_ASSIGNMENTS.copy()
		if Constants.DEBUG:
			print("CC assignments reset to defaults")

	def get_cc_for_pot(self, pot_number):
		"""Get the CC number assigned to a pot"""
		return self.cc_assignments.get(pot_number, pot_number)

class NoteState:
	"""Memory-efficient note state tracking"""
	__slots__ = ['key_id', 'midi_note', 'channel', 'velocity', 'timestamp', 
				 'left_pressure', 'right_pressure', 'pitch_bend', 'active']
	
	def __init__(self, key_id, midi_note, channel, velocity):
		self.key_id = key_id
		self.midi_note = midi_note
		self.channel = channel
		self.velocity = velocity
		self.timestamp = time.monotonic()
		self.left_pressure = 0
		self.right_pressure = 0
		self.pitch_bend = Constants.PITCH_BEND_CENTER
		self.active = True

class MPEChannelManager:
	"""Manages MPE channel allocation and note states"""
	def __init__(self):
		self.active_notes = {}
		self.note_queue = deque((), Constants.MAX_ACTIVE_NOTES)
		self.available_channels = list(range(
			Constants.MPE_ZONE_START, 
			Constants.MPE_ZONE_END + 1
		))

	def allocate_channel(self, key_id):
		if key_id in self.active_notes and self.active_notes[key_id].active:
			return self.active_notes[key_id].channel

		if self.available_channels:
			return self.available_channels.pop(0)
			
		# Steal channel from oldest note if queue not empty
		if len(self.note_queue):
			oldest_key_id = self.note_queue.popleft()
			channel = self.active_notes[oldest_key_id].channel
			self._release_note(oldest_key_id)
			return channel
			
		return Constants.MPE_ZONE_START  # Fallback

	def add_note(self, key_id, midi_note, channel, velocity):
		note_state = NoteState(key_id, midi_note, channel, velocity)
		self.active_notes[key_id] = note_state
		self.note_queue.append(key_id)
		return note_state

	def _release_note(self, key_id):
		if key_id in self.active_notes:
			note_state = self.active_notes[key_id]
			note_state.active = False
			channel = note_state.channel
			if channel not in self.available_channels:
				self.available_channels.append(channel)

	def release_note(self, key_id):
		self._release_note(key_id)

	def get_note_state(self, key_id):
		note_state = self.active_notes.get(key_id)
		return note_state if note_state and note_state.active else None

	def get_active_notes(self):
		return [note for note in self.active_notes.values() if note.active]

class MPENoteProcessor:
	"""Handles MPE note processing and message generation"""
	def __init__(self, channel_manager):
		self.channel_manager = channel_manager
		self.octave_shift = 0
		self.base_root_note = 60  # Middle C
		self.active_notes = set()
		self.pending_notes = {}

	def process_key_changes(self, key_events, config):
		"""Process key events into MPE messages"""
		midi_events = []
		
		for key_id, event_type, values in key_events:
			if event_type == 'contact':
				self.pending_notes[key_id] = values['strike']
				
			elif event_type == 'active':
				if key_id not in self.active_notes:
					# New note - send full note-on sequence
					strike = self.pending_notes.pop(key_id, 0.7)
					midi_note = self.base_root_note + self.octave_shift * 12 + key_id
					velocity = int(strike * 127)
					
					midi_events.extend([
						('pitch_bend_init', key_id, values['position']),
						('pressure_init', key_id, values['pressure']),
						('note_on', midi_note, velocity, key_id)
					])
					self.active_notes.add(key_id)
					
				else:
					midi_events.append(
						('pressure_update', key_id, values['pressure'], values['position'])
					)
					
			elif event_type == 'release':
				if key_id in self.active_notes:
					note_state = self.channel_manager.get_note_state(key_id)
					if note_state:
						midi_note = note_state.midi_note
						midi_events.extend([
							('pressure_update', key_id, 0.0, 0.0),
							('note_off', midi_note, 0, key_id)
						])
						self.active_notes.remove(key_id)

		return midi_events

	def handle_octave_shift(self, direction):
		"""Process octave shift and update all active notes"""
		midi_events = []
		new_octave = max(-2, min(2, self.octave_shift + direction))
		
		if new_octave != self.octave_shift:
			self.octave_shift = new_octave
			
			for note_state in self.channel_manager.get_active_notes():
				old_note = note_state.midi_note
				new_note = self.base_root_note + self.octave_shift * 12 + note_state.key_id
				
				midi_events.extend([
					('pitch_bend_init', note_state.key_id, 
					 note_state.position if hasattr(note_state, 'position') else 0),
					('pressure_init', note_state.key_id, 
					 note_state.pressure if hasattr(note_state, 'pressure') else 0),
					('note_off', old_note, 0, note_state.key_id),
					('note_on', new_note, note_state.velocity, note_state.key_id)
				])
				
				if note_state.active and hasattr(note_state, 'pressure') and note_state.pressure > 0:
					midi_events.append((
						'pressure_update',
						note_state.key_id,
						note_state.pressure,
						getattr(note_state, 'position', 0)
					))
			
		return midi_events

class MidiLogic:
	"""Main MPE MIDI controller logic"""
	def __init__(self, midi_tx, midi_rx, midi_callback=None):
		self.channel_manager = MPEChannelManager()
		self.note_processor = MPENoteProcessor(self.channel_manager)
		self.config = MPEConfiguration()
		self.transport = MidiTransportManager(midi_tx, midi_rx, self.handle_config_message)
		self.config._configure_system(self)
		self.welcome = WelcomeSequence(self)
		self.config._configure_system(self)
		
	def _send_message(self, message):
		"""Send raw MIDI message via transport"""
		if self.config.ready_for_midi or message[0] & 0xF0 in (0xB0, 0xF0):
			self.transport.send_message(message)

	def check_for_messages(self):
		"""Check for incoming MIDI messages"""
		return self.transport.check_for_messages()

	def handle_config_message(self, message):
		"""Handle configuration message from Candide"""
		return self.config.handle_config_message(message)

	def update(self, key_events, pot_events, config):
		"""Process hardware changes and send appropriate MIDI messages"""
		if not self.config.ready_for_midi:
			return []
			
		midi_events = []
		
		# Process key changes first
		if key_events:
			key_midi_events = self.note_processor.process_key_changes(key_events, config)
			
			# Sort events to ensure proper MPE order
			init_events = []
			note_events = []
			update_events = []
			
			for event in key_midi_events:
				if event[0] in ('pitch_bend_init', 'pressure_init'):
					init_events.append(event)
				elif event[0] in ('note_on', 'note_off'):
					note_events.append(event)
				else:
					update_events.append(event)
			
			midi_events.extend(init_events)
			midi_events.extend(note_events)
			midi_events.extend(update_events)
		
		# Process pot changes
		if pot_events:
			for pot_index, old_value, new_value in pot_events:
				cc_number = self.config.get_cc_for_pot(pot_index)
				midi_value = int(new_value * 127)
				midi_events.append(('control_change', cc_number, midi_value, new_value))
		
		# Send all events in order
		for event in midi_events:
			self.send_midi_event(event)
			
		return midi_events

	def send_midi_event(self, event):
		"""Handle different types of MIDI events and send via transport"""
		if not self.config.ready_for_midi:
			return
			
		event_type = event[0]
		params = event[1:]
		
		if event_type == 'pitch_bend_init':
			key_id, position = params
			channel = self.channel_manager.allocate_channel(key_id)
			bend_value = int((position + 1) * Constants.PITCH_BEND_MAX / 2)
			lsb = bend_value & 0x7F
			msb = (bend_value >> 7) & 0x7F
			if Constants.DEBUG:
				print(f"\nKey {key_id} Initial Pitch Bend:")
				print(f"  Channel: {channel + 1}")
				print(f"  Position: {position:+.3f}")
			self._send_message([0xE0 | channel, lsb, msb])
			
		elif event_type == 'pressure_init':
			key_id, pressure = params
			channel = self.channel_manager.allocate_channel(key_id)
			pressure_value = int(pressure * 127)
			if Constants.DEBUG:
				print(f"\nKey {key_id} Initial Pressure:")
				print(f"  Channel: {channel + 1}")
				print(f"  Pressure: {pressure_value}")
			self._send_message([0xD0 | channel, pressure_value, 0])
				
		elif event_type == 'note_on':
			midi_note, velocity, key_id = params
			channel = self.channel_manager.allocate_channel(key_id)
			note_state = self.channel_manager.add_note(key_id, midi_note, channel, velocity)
			if Constants.DEBUG:
				print(f"\nKey {key_id} Note ON:")
				print(f"  Channel: {channel + 1}")
				print(f"  Note: {midi_note}")
				print(f"  Velocity: {velocity}")
			self._send_message([0x90 | channel, int(midi_note), velocity])
				
		elif event_type == 'note_off':
			midi_note, velocity, key_id = params
			note_state = self.channel_manager.get_note_state(key_id)
			if note_state:
				if Constants.DEBUG:
					print(f"\nKey {key_id} Note OFF:")
					print(f"  Channel: {note_state.channel + 1}")
					print(f"  Note: {midi_note}")
				self._send_message([0x80 | note_state.channel, int(midi_note), velocity])
				self.channel_manager.release_note(key_id)
					
		elif event_type == 'pressure_update':
			key_id, pressure, position = params
			note_state = self.channel_manager.get_note_state(key_id)
			if note_state:
				pressure_value = int(pressure * 127)
				bend_value = int((position + 1) * Constants.PITCH_BEND_MAX / 2)
				lsb = bend_value & 0x7F
				msb = (bend_value >> 7) & 0x7F
				
				if Constants.DEBUG:
					print(f"\nKey {key_id} Updates:")
					print(f"  Channel: {note_state.channel + 1}")
					print(f"  Pressure: {pressure_value}")
					print(f"  Position: {position:+.3f}")
				
				# Send pressure (Z-axis)
				self._send_message([0xD0 | note_state.channel, pressure_value, 0])
				
				# Send position as pitch bend (X-axis)
				self._send_message([0xE0 | note_state.channel, lsb, msb])
				
				# Store current values
				note_state.pressure = pressure
				note_state.position = position
					
		elif event_type == 'control_change':
			cc_number, midi_value, _ = params
			if Constants.DEBUG:
				print(f"\nControl Change:")
				print(f"  CC Number: {cc_number}")
				print(f"  Value: {midi_value}")
			self._send_message([0xB0 | Constants.MPE_MASTER_CHANNEL, cc_number, midi_value])

	def handle_octave_shift(self, direction):
		"""Process octave shift and return MIDI events"""
		if not self.config.ready_for_midi:
			return []
		return self.note_processor.handle_octave_shift(direction)
	
	def reset_cc_defaults(self):
		"""Reset CC assignments to defaults"""
		self.config.reset_cc_defaults()

	def cleanup(self):
		"""Clean shutdown"""
		self.transport.cleanup()