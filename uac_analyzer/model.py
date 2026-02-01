"""
Data model for USB Audio Class descriptors.

This module defines dataclasses representing the USB Audio Class descriptor hierarchy
for both UAC 1.0 and UAC 2.0 specifications.
"""

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Optional, Union


class UACVersion(Enum):
    """USB Audio Class specification version."""
    UAC_1_0 = "1.0"
    UAC_2_0 = "2.0"
    UAC_3_0 = "3.0"
    UNKNOWN = "unknown"


class SyncType(Enum):
    """Endpoint synchronization type."""
    NONE = "none"
    ASYNC = "async"
    ADAPTIVE = "adaptive"
    SYNC = "sync"


class UsageType(Enum):
    """Endpoint usage type."""
    DATA = "data"
    FEEDBACK = "feedback"
    IMPLICIT_FEEDBACK = "implicit_feedback"


class TerminalType(IntEnum):
    """USB Audio Terminal Type codes (partial list of common types)."""
    # USB Terminal Types
    USB_UNDEFINED = 0x0100
    USB_STREAMING = 0x0101
    USB_VENDOR_SPECIFIC = 0x01FF

    # Input Terminal Types
    INPUT_UNDEFINED = 0x0200
    MICROPHONE = 0x0201
    DESKTOP_MICROPHONE = 0x0202
    PERSONAL_MICROPHONE = 0x0203
    OMNI_DIRECTIONAL_MICROPHONE = 0x0204
    MICROPHONE_ARRAY = 0x0205
    PROCESSING_MICROPHONE_ARRAY = 0x0206

    # Output Terminal Types
    OUTPUT_UNDEFINED = 0x0300
    SPEAKER = 0x0301
    HEADPHONES = 0x0302
    HEAD_MOUNTED_DISPLAY = 0x0303
    DESKTOP_SPEAKER = 0x0304
    ROOM_SPEAKER = 0x0305
    COMMUNICATION_SPEAKER = 0x0306
    LOW_FREQUENCY_EFFECTS_SPEAKER = 0x0307

    # Bi-directional Terminal Types
    BIDIRECTIONAL_UNDEFINED = 0x0400
    HANDSET = 0x0401
    HEADSET = 0x0402
    SPEAKERPHONE = 0x0403
    ECHO_SUPPRESSING_SPEAKERPHONE = 0x0404
    ECHO_CANCELING_SPEAKERPHONE = 0x0405

    # Telephony Terminal Types
    TELEPHONY_UNDEFINED = 0x0500
    PHONE_LINE = 0x0501
    TELEPHONE = 0x0502
    DOWN_LINE_PHONE = 0x0503

    # External Terminal Types
    EXTERNAL_UNDEFINED = 0x0600
    ANALOG_CONNECTOR = 0x0601
    DIGITAL_AUDIO_INTERFACE = 0x0602
    LINE_CONNECTOR = 0x0603
    LEGACY_AUDIO_CONNECTOR = 0x0604
    SPDIF_INTERFACE = 0x0605
    DA_STREAM = 0x0606
    DV_STREAM = 0x0607

    # Embedded Function Terminal Types
    EMBEDDED_UNDEFINED = 0x0700
    LEVEL_CALIBRATION_NOISE_SOURCE = 0x0701
    EQUALIZATION_NOISE = 0x0702
    CD_PLAYER = 0x0703
    DAT = 0x0704
    DCC = 0x0705
    MINIDISK = 0x0706
    ANALOG_TAPE = 0x0707
    PHONOGRAPH = 0x0708
    VCR_AUDIO = 0x0709
    VIDEO_DISC_AUDIO = 0x070A
    DVD_AUDIO = 0x070B
    TV_TUNER_AUDIO = 0x070C
    SATELLITE_RECEIVER_AUDIO = 0x070D
    CABLE_TUNER_AUDIO = 0x070E
    DSS_AUDIO = 0x070F
    RADIO_RECEIVER = 0x0710
    RADIO_TRANSMITTER = 0x0711
    MULTI_TRACK_RECORDER = 0x0712
    SYNTHESIZER = 0x0713
    PIANO = 0x0714
    GUITAR = 0x0715
    DRUMS = 0x0716
    OTHER_INSTRUMENT = 0x0717


# Mapping of terminal type codes to human-readable descriptions
TERMINAL_TYPE_NAMES: dict[int, str] = {
    0x0100: "USB Undefined",
    0x0101: "USB Streaming",
    0x01FF: "USB Vendor Specific",
    0x0200: "Input Undefined",
    0x0201: "Microphone",
    0x0202: "Desktop Microphone",
    0x0203: "Personal Microphone",
    0x0204: "Omni-directional Microphone",
    0x0205: "Microphone Array",
    0x0206: "Processing Microphone Array",
    0x0300: "Output Undefined",
    0x0301: "Speaker",
    0x0302: "Headphones",
    0x0303: "Head Mounted Display Audio",
    0x0304: "Desktop Speaker",
    0x0305: "Room Speaker",
    0x0306: "Communication Speaker",
    0x0307: "Low Frequency Effects Speaker",
    0x0400: "Bi-directional Undefined",
    0x0401: "Handset",
    0x0402: "Headset",
    0x0403: "Speakerphone (no echo reduction)",
    0x0404: "Echo-suppressing Speakerphone",
    0x0405: "Echo-canceling Speakerphone",
    0x0500: "Telephony Undefined",
    0x0501: "Phone Line",
    0x0502: "Telephone",
    0x0503: "Down Line Phone",
    0x0600: "External Undefined",
    0x0601: "Analog Connector",
    0x0602: "Digital Audio Interface",
    0x0603: "Line Connector",
    0x0604: "Legacy Audio Connector",
    0x0605: "S/PDIF Interface",
    0x0606: "1394 DA Stream",
    0x0607: "1394 DV Stream",
    0x0700: "Embedded Undefined",
    0x0701: "Level Calibration Noise Source",
    0x0702: "Equalization Noise",
    0x0703: "CD Player",
    0x0704: "DAT",
    0x0705: "DCC",
    0x0706: "MiniDisk",
    0x0707: "Analog Tape",
    0x0708: "Phonograph",
    0x0709: "VCR Audio",
    0x070A: "Video Disc Audio",
    0x070B: "DVD Audio",
    0x070C: "TV Tuner Audio",
    0x070D: "Satellite Receiver Audio",
    0x070E: "Cable Tuner Audio",
    0x070F: "DSS Audio",
    0x0710: "Radio Receiver",
    0x0711: "Radio Transmitter",
    0x0712: "Multi-track Recorder",
    0x0713: "Synthesizer",
    0x0714: "Piano",
    0x0715: "Guitar",
    0x0716: "Drums/Rhythm",
    0x0717: "Other Musical Instrument",
}


def get_terminal_type_name(type_code: int) -> str:
    """Get human-readable name for a terminal type code."""
    if type_code in TERMINAL_TYPE_NAMES:
        return TERMINAL_TYPE_NAMES[type_code]
    # Categorize by high byte
    category = (type_code >> 8) & 0xFF
    categories = {
        0x01: "USB",
        0x02: "Input",
        0x03: "Output",
        0x04: "Bi-directional",
        0x05: "Telephony",
        0x06: "External",
        0x07: "Embedded",
    }
    cat_name = categories.get(category, "Unknown")
    return f"{cat_name} (0x{type_code:04X})"


# ============================================================================
# Basic USB Descriptors
# ============================================================================

@dataclass
class DeviceDescriptor:
    """USB Device Descriptor."""
    vendor_id: int = 0
    product_id: int = 0
    bcd_device: int = 0
    manufacturer: str = ""
    product: str = ""
    serial_number: str = ""
    device_class: int = 0
    device_subclass: int = 0
    device_protocol: int = 0
    max_packet_size_0: int = 0
    num_configurations: int = 0
    usb_version: str = ""


@dataclass
class EndpointDescriptor:
    """USB Endpoint Descriptor with audio extensions."""
    address: int = 0
    direction: str = ""  # "IN" or "OUT"
    transfer_type: str = ""  # "Isochronous", "Bulk", "Interrupt", "Control"
    sync_type: SyncType = SyncType.NONE
    usage_type: UsageType = UsageType.DATA
    max_packet_size: int = 0
    interval: int = 0
    refresh: int = 0  # For feedback endpoints
    synch_address: int = 0  # Sync endpoint address

    # Audio-specific extensions (from audio endpoint descriptor)
    lock_delay_units: int = 0
    lock_delay: int = 0
    max_packets_only: bool = False

    @property
    def endpoint_number(self) -> int:
        """Get endpoint number (address without direction bit)."""
        return self.address & 0x0F

    @property
    def is_input(self) -> bool:
        """Check if endpoint is input (device to host)."""
        return (self.address & 0x80) != 0


@dataclass
class InterfaceDescriptor:
    """USB Interface Descriptor."""
    interface_number: int = 0
    alternate_setting: int = 0
    num_endpoints: int = 0
    interface_class: int = 0
    interface_subclass: int = 0
    interface_protocol: int = 0
    interface_name: str = ""
    endpoints: list[EndpointDescriptor] = field(default_factory=list)


@dataclass
class ConfigurationDescriptor:
    """USB Configuration Descriptor."""
    config_value: int = 0
    num_interfaces: int = 0
    config_name: str = ""
    attributes: int = 0
    max_power_ma: int = 0
    interfaces: list[InterfaceDescriptor] = field(default_factory=list)


# ============================================================================
# Audio Control Interface Descriptors
# ============================================================================

@dataclass
class AudioControlHeader:
    """AudioControl Interface Header Descriptor."""
    uac_version: UACVersion = UACVersion.UNKNOWN
    bcd_adc: int = 0  # Audio Device Class specification release number
    total_length: int = 0
    in_collection: int = 0  # Number of AudioStreaming interfaces (UAC 1.0)
    interface_numbers: list[int] = field(default_factory=list)  # UAC 1.0
    category: int = 0  # Function category (UAC 2.0)
    controls: int = 0  # UAC 2.0


@dataclass
class InputTerminal:
    """Input Terminal Descriptor."""
    terminal_id: int = 0
    terminal_type: int = 0
    assoc_terminal: int = 0
    nr_channels: int = 0
    channel_config: int = 0
    channel_names: str = ""
    terminal_name: str = ""
    # UAC 2.0 specific
    clock_source_id: int = 0
    controls: int = 0

    @property
    def terminal_type_name(self) -> str:
        """Get human-readable terminal type name."""
        return get_terminal_type_name(self.terminal_type)

    @property
    def is_usb_streaming(self) -> bool:
        """Check if this is a USB streaming terminal."""
        return self.terminal_type == 0x0101


@dataclass
class OutputTerminal:
    """Output Terminal Descriptor."""
    terminal_id: int = 0
    terminal_type: int = 0
    assoc_terminal: int = 0
    source_id: int = 0
    terminal_name: str = ""
    # UAC 2.0 specific
    clock_source_id: int = 0
    controls: int = 0

    @property
    def terminal_type_name(self) -> str:
        """Get human-readable terminal type name."""
        return get_terminal_type_name(self.terminal_type)

    @property
    def is_usb_streaming(self) -> bool:
        """Check if this is a USB streaming terminal."""
        return self.terminal_type == 0x0101


@dataclass
class FeatureUnit:
    """Feature Unit Descriptor."""
    unit_id: int = 0
    source_id: int = 0
    nr_channels: int = 0
    # Controls per channel - list of control bitmasks
    # Index 0 = master, 1..n = per-channel
    controls: list[int] = field(default_factory=list)
    unit_name: str = ""

    # Control bit definitions (UAC 1.0)
    MUTE = 0x01
    VOLUME = 0x02
    BASS = 0x04
    MID = 0x08
    TREBLE = 0x10
    GRAPHIC_EQ = 0x20
    AUTO_GAIN = 0x40
    DELAY = 0x80
    BASS_BOOST = 0x100
    LOUDNESS = 0x200

    @property
    def has_mute(self) -> bool:
        """Check if master mute control is available."""
        return bool(self.controls and (self.controls[0] & self.MUTE))

    @property
    def has_volume(self) -> bool:
        """Check if master volume control is available."""
        return bool(self.controls and (self.controls[0] & self.VOLUME))

    def get_control_names(self) -> list[str]:
        """Get list of available control names."""
        if not self.controls:
            return []
        master = self.controls[0]
        names = []
        if master & self.MUTE:
            names.append("Mute")
        if master & self.VOLUME:
            names.append("Volume")
        if master & self.BASS:
            names.append("Bass")
        if master & self.MID:
            names.append("Mid")
        if master & self.TREBLE:
            names.append("Treble")
        if master & self.GRAPHIC_EQ:
            names.append("Graphic EQ")
        if master & self.AUTO_GAIN:
            names.append("AGC")
        if master & self.DELAY:
            names.append("Delay")
        if master & self.BASS_BOOST:
            names.append("Bass Boost")
        if master & self.LOUDNESS:
            names.append("Loudness")
        return names


@dataclass
class MixerUnit:
    """Mixer Unit Descriptor."""
    unit_id: int = 0
    nr_in_pins: int = 0
    source_ids: list[int] = field(default_factory=list)
    nr_channels: int = 0
    channel_config: int = 0
    channel_names: str = ""
    controls: bytes = b""  # Programmable mixing controls bitmap
    unit_name: str = ""


@dataclass
class SelectorUnit:
    """Selector Unit Descriptor."""
    unit_id: int = 0
    nr_in_pins: int = 0
    source_ids: list[int] = field(default_factory=list)
    selector_name: str = ""


@dataclass
class ProcessingUnit:
    """Processing Unit Descriptor."""
    unit_id: int = 0
    process_type: int = 0
    nr_in_pins: int = 0
    source_ids: list[int] = field(default_factory=list)
    nr_channels: int = 0
    channel_config: int = 0
    channel_names: str = ""
    controls: int = 0
    unit_name: str = ""

    # Process types
    UNDEFINED = 0x00
    UP_DOWNMIX = 0x01
    DOLBY_PROLOGIC = 0x02
    STEREO_EXTENDER = 0x03


@dataclass
class ExtensionUnit:
    """Extension Unit Descriptor."""
    unit_id: int = 0
    extension_code: int = 0
    nr_in_pins: int = 0
    source_ids: list[int] = field(default_factory=list)
    nr_channels: int = 0
    channel_config: int = 0
    channel_names: str = ""
    controls: int = 0
    unit_name: str = ""


# ============================================================================
# UAC 2.0 Clock Entities
# ============================================================================

@dataclass
class ClockSource:
    """Clock Source Descriptor (UAC 2.0)."""
    clock_id: int = 0
    attributes: int = 0
    controls: int = 0
    assoc_terminal: int = 0
    clock_source_name: str = ""

    @property
    def clock_type(self) -> str:
        """Get clock type from attributes."""
        clock_types = {
            0b00: "External",
            0b01: "Internal Fixed",
            0b10: "Internal Variable",
            0b11: "Internal Programmable",
        }
        return clock_types.get(self.attributes & 0x03, "Unknown")

    @property
    def is_synced_to_sof(self) -> bool:
        """Check if clock is synchronized to USB SOF."""
        return bool(self.attributes & 0x04)


@dataclass
class ClockSelector:
    """Clock Selector Descriptor (UAC 2.0)."""
    clock_id: int = 0
    nr_in_pins: int = 0
    clock_pin_ids: list[int] = field(default_factory=list)
    controls: int = 0
    clock_selector_name: str = ""


@dataclass
class ClockMultiplier:
    """Clock Multiplier Descriptor (UAC 2.0)."""
    clock_id: int = 0
    clock_source_id: int = 0
    controls: int = 0
    clock_multiplier_name: str = ""


# ============================================================================
# Audio Streaming Interface Descriptors
# ============================================================================

@dataclass
class FormatTypeDescriptor:
    """Format Type Descriptor."""
    format_type: int = 0  # Usually TYPE_I
    nr_channels: int = 0
    subframe_size: int = 0  # Bytes per audio subframe
    bit_resolution: int = 0
    # UAC 1.0: discrete sample frequencies
    sample_frequencies: list[int] = field(default_factory=list)
    # UAC 1.0: continuous range (min, max)
    freq_min: int = 0
    freq_max: int = 0

    # Format type codes
    TYPE_I = 0x01
    TYPE_II = 0x02
    TYPE_III = 0x03

    @property
    def sample_rate_range(self) -> tuple[int, int]:
        """Get sample rate range (min, max)."""
        if self.sample_frequencies:
            return (min(self.sample_frequencies), max(self.sample_frequencies))
        elif self.freq_min and self.freq_max:
            return (self.freq_min, self.freq_max)
        return (0, 0)


@dataclass
class AudioStreamingInterface:
    """Audio Streaming Interface Descriptor."""
    interface_number: int = 0
    alternate_setting: int = 0
    terminal_link: int = 0  # ID of connected terminal
    delay: int = 0  # Interface delay
    format_tag: int = 0  # Audio data format (UAC 1.0)

    # UAC 2.0 specific
    controls: int = 0
    clock_source_id: int = 0
    bm_formats: int = 0  # UAC 2.0 format bitmask

    # Format descriptor
    format: Optional[FormatTypeDescriptor] = None

    # Endpoint
    endpoint: Optional[EndpointDescriptor] = None

    # Audio format codes (UAC 1.0)
    FORMAT_TYPE_I_UNDEFINED = 0x0000
    FORMAT_PCM = 0x0001
    FORMAT_PCM8 = 0x0002
    FORMAT_IEEE_FLOAT = 0x0003
    FORMAT_ALAW = 0x0004
    FORMAT_MULAW = 0x0005

    # UAC 2.0 bmFormats bit definitions (Type I)
    UAC2_FORMAT_PCM = 0x00000001
    UAC2_FORMAT_PCM8 = 0x00000002
    UAC2_FORMAT_IEEE_FLOAT = 0x00000004
    UAC2_FORMAT_ALAW = 0x00000008
    UAC2_FORMAT_MULAW = 0x00000010
    UAC2_FORMAT_RAW_DATA = 0x80000000

    @property
    def format_name(self) -> str:
        """Get human-readable format name."""
        # UAC 2.0: use bmFormats bitmask
        if self.bm_formats:
            formats = []
            if self.bm_formats & self.UAC2_FORMAT_PCM:
                formats.append("PCM")
            if self.bm_formats & self.UAC2_FORMAT_PCM8:
                formats.append("PCM8")
            if self.bm_formats & self.UAC2_FORMAT_IEEE_FLOAT:
                formats.append("IEEE Float")
            if self.bm_formats & self.UAC2_FORMAT_ALAW:
                formats.append("A-Law")
            if self.bm_formats & self.UAC2_FORMAT_MULAW:
                formats.append("μ-Law")
            if self.bm_formats & self.UAC2_FORMAT_RAW_DATA:
                formats.append("Raw Data")
            if formats:
                return "/".join(formats)
            return f"Unknown (0x{self.bm_formats:08X})"

        # UAC 1.0: use format_tag
        formats = {
            0x0000: "Undefined",
            0x0001: "PCM",
            0x0002: "PCM8",
            0x0003: "IEEE Float",
            0x0004: "A-Law",
            0x0005: "μ-Law",
        }
        return formats.get(self.format_tag, f"Unknown (0x{self.format_tag:04X})")


@dataclass
class AlternateSetting:
    """Grouped alternate setting information for analysis."""
    interface_number: int = 0
    alternate_setting: int = 0
    streaming_interface: Optional[AudioStreamingInterface] = None
    format: Optional[FormatTypeDescriptor] = None
    endpoint: Optional[EndpointDescriptor] = None

    @property
    def is_zero_bandwidth(self) -> bool:
        """Check if this is a zero-bandwidth (disabled) setting."""
        return self.endpoint is None or self.endpoint.max_packet_size == 0

    @property
    def bandwidth_bytes_per_frame(self) -> int:
        """Calculate bandwidth in bytes per USB frame (1ms for FS, 125μs for HS)."""
        if not self.endpoint:
            return 0
        return self.endpoint.max_packet_size


# ============================================================================
# Top-Level Device Model
# ============================================================================

# Type alias for any unit type
AudioUnit = Union[FeatureUnit, MixerUnit, SelectorUnit, ProcessingUnit, ExtensionUnit]
ClockEntity = Union[ClockSource, ClockSelector, ClockMultiplier]


@dataclass
class AudioControlInterface:
    """Complete Audio Control interface with all entities."""
    header: Optional[AudioControlHeader] = None
    input_terminals: list[InputTerminal] = field(default_factory=list)
    output_terminals: list[OutputTerminal] = field(default_factory=list)
    feature_units: list[FeatureUnit] = field(default_factory=list)
    mixer_units: list[MixerUnit] = field(default_factory=list)
    selector_units: list[SelectorUnit] = field(default_factory=list)
    processing_units: list[ProcessingUnit] = field(default_factory=list)
    extension_units: list[ExtensionUnit] = field(default_factory=list)
    # UAC 2.0
    clock_sources: list[ClockSource] = field(default_factory=list)
    clock_selectors: list[ClockSelector] = field(default_factory=list)
    clock_multipliers: list[ClockMultiplier] = field(default_factory=list)

    def get_entity_by_id(self, entity_id: int) -> Optional[Union[InputTerminal, OutputTerminal, AudioUnit, ClockEntity]]:
        """Look up any entity (terminal, unit, or clock) by its ID."""
        for terminal in self.input_terminals:
            if terminal.terminal_id == entity_id:
                return terminal
        for terminal in self.output_terminals:
            if terminal.terminal_id == entity_id:
                return terminal
        for unit in self.feature_units:
            if unit.unit_id == entity_id:
                return unit
        for unit in self.mixer_units:
            if unit.unit_id == entity_id:
                return unit
        for unit in self.selector_units:
            if unit.unit_id == entity_id:
                return unit
        for unit in self.processing_units:
            if unit.unit_id == entity_id:
                return unit
        for unit in self.extension_units:
            if unit.unit_id == entity_id:
                return unit
        for clock in self.clock_sources:
            if clock.clock_id == entity_id:
                return clock
        for clock in self.clock_selectors:
            if clock.clock_id == entity_id:
                return clock
        for clock in self.clock_multipliers:
            if clock.clock_id == entity_id:
                return clock
        return None


@dataclass
class USBAudioDevice:
    """Complete USB Audio Device model."""
    device: DeviceDescriptor = field(default_factory=DeviceDescriptor)
    configuration: Optional[ConfigurationDescriptor] = None
    audio_control: Optional[AudioControlInterface] = None
    streaming_interfaces: list[AudioStreamingInterface] = field(default_factory=list)
    alternate_settings: list[AlternateSetting] = field(default_factory=list)

    @property
    def uac_version(self) -> UACVersion:
        """Get UAC version from audio control header."""
        if self.audio_control and self.audio_control.header:
            return self.audio_control.header.uac_version
        return UACVersion.UNKNOWN

    @property
    def device_name(self) -> str:
        """Get device name (product or fallback to IDs)."""
        if self.device.product:
            return self.device.product
        return f"USB Audio Device {self.device.vendor_id:04X}:{self.device.product_id:04X}"

    @property
    def manufacturer_name(self) -> str:
        """Get manufacturer name."""
        return self.device.manufacturer or "Unknown"
