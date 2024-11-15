# Bartleby MPE Controller
##A CircuitPython MPE controller implementation

Bartleby is a MIDI controller program designed for CircuitPython microcontrollers. It implements an MPE (MIDI Polyphonic Expression) control system that processes input from a 25-key pressure-sensitive keyboard and 14 potentiometers, translating physical interactions into expressive MIDI data.

The system uses multiplexed inputs to handle multiple analog sensors, implementing dual-phase key detection for velocity and pressure sensing. Each key supports independent pitch bend, pressure, and timbre control through MPE, while the potentiometers provide control over various MIDI parameters. The program manages MIDI communication through UART, handling both text-based configuration messages and MIDI data on a shared transport.

## System Architecture

### Core Components

- **Hardware Layer**
  - Multiplexer management for key scanning and control inputs
  - Keyboard handling with dual-phase detection
  - Rotary encoder support for octave shifting
  - Potentiometer handling with noise reduction
  - ADC (Analog-Digital Converter) interfacing

- **MIDI Layer**
  - MPE zone management and configuration
  - Channel allocation and management
  - Note state tracking
  - MIDI message generation and routing
  - Controller (CC) message handling

- **Transport Layer**
  - UART communication management
  - Shared transport handling for both text and MIDI data
  - Buffer management and cleanup

### Key Features

- **MPE Support**
  - Per-note pitch bend
  - Pressure sensitivity
  - Timbre control
  - Configurable pitch bend ranges
  - 15 member channels (2-16) with channel 1 as zone manager

- **Hardware Capabilities**
  - 25-key keyboard with pressure sensitivity
  - 14 assignable potentiometers
  - Octave shift encoder
  - Multiplexed input scanning
  - Dual-phase key detection

- **Control Features**
  - Configurable CC assignments
  - Real-time parameter control
  - Octave shifting
  - Velocity sensitivity
  - Pressure tracking

## Technical Specifications

- **Hardware Interface**
  - UART TX: GP16
  - UART RX: GP17
  - Detect Pin: GP22
  - Multiple multiplexed inputs for keyboard and controls

- **MIDI Implementation**
  - MIDI baudrate: 31250
  - MPE member pitch bend range: 48 semitones
  - MPE master pitch bend range: 2 semitones
  - Support for standard MIDI CC messages
  - Configurable CC assignments for potentiometers

- **Performance Parameters**
  - Main loop interval: 0.001s
  - Potentiometer scan interval: 0.02s
  - Encoder scan interval: 0.001s
  - Communication timeout: 2.0s

## Dependencies

- CircuitPython
- `board` module
- `busio` module
- `digitalio` module
- `rotaryio` module
- `analogio` module
- `time` module

## System Requirements

- CircuitPython-compatible microcontroller
- Hardware configured according to pin specifications
- MPE-compatible synthesizer/sound engine for full feature utilization
