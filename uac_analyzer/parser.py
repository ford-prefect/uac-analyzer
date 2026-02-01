"""
Parser for lsusb -v output.

This module parses the text output of `lsusb -v` and populates the USB Audio
Class data model.
"""

import re
from typing import Optional, TextIO, Iterator
from io import StringIO

from .model import (
    UACVersion,
    SyncType,
    UsageType,
    DeviceDescriptor,
    ConfigurationDescriptor,
    InterfaceDescriptor,
    EndpointDescriptor,
    AudioControlHeader,
    InputTerminal,
    OutputTerminal,
    FeatureUnit,
    MixerUnit,
    SelectorUnit,
    ProcessingUnit,
    ExtensionUnit,
    ClockSource,
    ClockSelector,
    ClockMultiplier,
    AudioStreamingInterface,
    FormatTypeDescriptor,
    AlternateSetting,
    AudioControlInterface,
    USBAudioDevice,
)


class ParseError(Exception):
    """Exception raised when parsing fails."""
    pass


class LsusbLine:
    """Represents a parsed line from lsusb output with indentation tracking."""

    def __init__(self, raw_line: str, line_number: int):
        self.raw = raw_line
        self.line_number = line_number
        self.indent = len(raw_line) - len(raw_line.lstrip())
        self.content = raw_line.strip()

    def __repr__(self) -> str:
        return f"LsusbLine({self.line_number}: indent={self.indent}, {self.content!r})"


class LsusbParser:
    """Parser for lsusb -v text output."""

    # Interface class codes
    AUDIO_CLASS = 0x01
    AUDIO_CONTROL_SUBCLASS = 0x01
    AUDIO_STREAMING_SUBCLASS = 0x02
    MIDI_STREAMING_SUBCLASS = 0x03

    # Audio Control descriptor subtypes (UAC 1.0)
    AC_HEADER = 0x01
    AC_INPUT_TERMINAL = 0x02
    AC_OUTPUT_TERMINAL = 0x03
    AC_MIXER_UNIT = 0x04
    AC_SELECTOR_UNIT = 0x05
    AC_FEATURE_UNIT = 0x06
    AC_PROCESSING_UNIT = 0x07
    AC_EXTENSION_UNIT = 0x08
    # UAC 2.0 additions
    AC_CLOCK_SOURCE = 0x0A
    AC_CLOCK_SELECTOR = 0x0B
    AC_CLOCK_MULTIPLIER = 0x0C
    AC_SAMPLE_RATE_CONVERTER = 0x0D

    # Audio Streaming descriptor subtypes
    AS_GENERAL = 0x01
    AS_FORMAT_TYPE = 0x02
    AS_FORMAT_SPECIFIC = 0x03

    def __init__(self, text: str):
        """Initialize parser with lsusb -v text output."""
        self.text = text
        self.lines: list[LsusbLine] = []
        self.pos = 0
        self._tokenize()

    def _tokenize(self) -> None:
        """Tokenize input text into lines with indentation tracking."""
        for i, line in enumerate(self.text.splitlines(), 1):
            if line.strip():  # Skip empty lines
                self.lines.append(LsusbLine(line, i))

    def _current(self) -> Optional[LsusbLine]:
        """Get current line or None if at end."""
        if self.pos < len(self.lines):
            return self.lines[self.pos]
        return None

    def _advance(self) -> Optional[LsusbLine]:
        """Advance to next line and return it."""
        self.pos += 1
        return self._current()

    def _peek(self, offset: int = 1) -> Optional[LsusbLine]:
        """Peek at a line without advancing."""
        pos = self.pos + offset
        if 0 <= pos < len(self.lines):
            return self.lines[pos]
        return None

    def _parse_hex_value(self, text: str) -> int:
        """Parse a hex value from text like '0x1234' or just '1234'."""
        text = text.strip()
        # First try explicit 0x prefix
        match = re.search(r'0x([0-9a-fA-F]+)', text)
        if match:
            return int(match.group(1), 16)
        # Try to find value after field name (after whitespace)
        # Look for pattern: fieldName  value
        parts = text.split()
        if len(parts) >= 2:
            value_part = parts[1]
            # Check if it looks like a hex number (all hex digits)
            if re.match(r'^[0-9a-fA-F]+$', value_part):
                try:
                    return int(value_part, 16)
                except ValueError:
                    pass
        return 0

    def _parse_bcd_value(self, text: str) -> int:
        """Parse a BCD version value like '1.00' or '2.00' to 0x0100 or 0x0200."""
        # Match patterns like "1.00", "2.00", "1.10"
        match = re.search(r'(\d+)\.(\d+)', text)
        if match:
            major = int(match.group(1))
            minor = int(match.group(2))
            return (major << 8) | minor
        return 0

    def _parse_int_value(self, text: str) -> int:
        """Parse an integer value from text."""
        match = re.search(r'\b(\d+)\b', text)
        if match:
            return int(match.group(1))
        return 0

    def _parse_field(self, line: str, field_name: str) -> str:
        """Extract value after a field name."""
        # Handle formats like "bLength  18" or "idVendor  0x1234 Company"
        pattern = rf'{re.escape(field_name)}\s+(.+)'
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    def _collect_block(self, start_indent: int) -> list[LsusbLine]:
        """Collect all lines belonging to a block at greater indentation."""
        block = []
        while self._current() and self._current().indent > start_indent:
            block.append(self._current())
            self._advance()
        return block

    def parse(self) -> USBAudioDevice:
        """Parse the lsusb output and return a USBAudioDevice."""
        device = USBAudioDevice()

        while self._current():
            line = self._current()

            if line.content.startswith("Bus "):
                # Start of device - parse bus/device info if needed
                self._advance()
            elif line.content.startswith("Device Descriptor:"):
                device.device = self._parse_device_descriptor()
            elif line.content.startswith("Configuration Descriptor:"):
                device.configuration = self._parse_configuration_descriptor(device)
            else:
                self._advance()

        # Build alternate settings list from streaming interfaces
        device.alternate_settings = self._build_alternate_settings(device)

        return device

    def _parse_device_descriptor(self) -> DeviceDescriptor:
        """Parse Device Descriptor block."""
        desc = DeviceDescriptor()
        start_indent = self._current().indent
        self._advance()

        while self._current() and self._current().indent > start_indent:
            line = self._current()
            content = line.content

            if content.startswith("bcdUSB"):
                desc.usb_version = self._parse_field(content, "bcdUSB").split()[0]
            elif content.startswith("bDeviceClass"):
                desc.device_class = self._parse_int_value(content)
            elif content.startswith("bDeviceSubClass"):
                desc.device_subclass = self._parse_int_value(content)
            elif content.startswith("bDeviceProtocol"):
                desc.device_protocol = self._parse_int_value(content)
            elif content.startswith("bMaxPacketSize0"):
                desc.max_packet_size_0 = self._parse_int_value(content)
            elif content.startswith("idVendor"):
                desc.vendor_id = self._parse_hex_value(content)
                # Extract vendor name after hex ID
                match = re.search(r'0x[0-9a-fA-F]+\s+(.+)', content)
                if match:
                    desc.manufacturer = match.group(1).strip()
            elif content.startswith("idProduct"):
                desc.product_id = self._parse_hex_value(content)
                # Extract product name after hex ID
                match = re.search(r'0x[0-9a-fA-F]+\s+(.+)', content)
                if match:
                    desc.product = match.group(1).strip()
            elif content.startswith("bcdDevice"):
                desc.bcd_device = self._parse_hex_value(content)
            elif content.startswith("iManufacturer"):
                # Format: "iManufacturer  1 Company Name"
                match = re.search(r'iManufacturer\s+\d+\s+(.+)', content)
                if match:
                    desc.manufacturer = match.group(1).strip()
            elif content.startswith("iProduct"):
                match = re.search(r'iProduct\s+\d+\s+(.+)', content)
                if match:
                    desc.product = match.group(1).strip()
            elif content.startswith("iSerial"):
                match = re.search(r'iSerial\s+\d+\s+(.+)', content)
                if match:
                    desc.serial_number = match.group(1).strip()
            elif content.startswith("bNumConfigurations"):
                desc.num_configurations = self._parse_int_value(content)
            elif content.startswith("Configuration Descriptor:"):
                # Configuration is nested in lsusb output but should be parsed separately
                break

            self._advance()

        return desc

    def _parse_configuration_descriptor(self, device: USBAudioDevice) -> ConfigurationDescriptor:
        """Parse Configuration Descriptor block."""
        config = ConfigurationDescriptor()
        start_indent = self._current().indent
        self._advance()

        while self._current() and self._current().indent > start_indent:
            line = self._current()
            content = line.content

            if content.startswith("bConfigurationValue"):
                config.config_value = self._parse_int_value(content)
                self._advance()
            elif content.startswith("bNumInterfaces"):
                config.num_interfaces = self._parse_int_value(content)
                self._advance()
            elif content.startswith("iConfiguration"):
                match = re.search(r'iConfiguration\s+\d+\s+(.+)', content)
                if match:
                    config.config_name = match.group(1).strip()
                self._advance()
            elif content.startswith("bmAttributes"):
                config.attributes = self._parse_hex_value(content)
                self._advance()
            elif content.startswith("MaxPower"):
                config.max_power_ma = self._parse_int_value(content)
                self._advance()
            elif content.startswith("Interface Descriptor:"):
                iface = self._parse_interface_descriptor(device)
                config.interfaces.append(iface)
            else:
                self._advance()

        return config

    def _parse_interface_descriptor(self, device: USBAudioDevice) -> InterfaceDescriptor:
        """Parse Interface Descriptor block."""
        iface = InterfaceDescriptor()
        start_indent = self._current().indent
        self._advance()

        while self._current() and self._current().indent > start_indent:
            line = self._current()
            content = line.content

            if content.startswith("bInterfaceNumber"):
                iface.interface_number = self._parse_int_value(content)
                self._advance()
            elif content.startswith("bAlternateSetting"):
                iface.alternate_setting = self._parse_int_value(content)
                self._advance()
            elif content.startswith("bNumEndpoints"):
                iface.num_endpoints = self._parse_int_value(content)
                self._advance()
            elif content.startswith("bInterfaceClass"):
                iface.interface_class = self._parse_int_value(content)
                self._advance()
            elif content.startswith("bInterfaceSubClass"):
                iface.interface_subclass = self._parse_int_value(content)
                self._advance()
            elif content.startswith("bInterfaceProtocol"):
                iface.interface_protocol = self._parse_int_value(content)
                self._advance()
            elif content.startswith("iInterface"):
                match = re.search(r'iInterface\s+\d+\s+(.+)', content)
                if match:
                    iface.interface_name = match.group(1).strip()
                self._advance()
            elif content.startswith("Endpoint Descriptor:"):
                ep = self._parse_endpoint_descriptor()
                iface.endpoints.append(ep)
            elif content.startswith("AudioControl Interface Descriptor:"):
                self._parse_audio_control_descriptor(device)
            elif content.startswith("AudioStreaming Interface Descriptor:"):
                self._parse_audio_streaming_descriptor(device, iface)
            else:
                self._advance()

        return iface

    def _parse_endpoint_descriptor(self) -> EndpointDescriptor:
        """Parse Endpoint Descriptor block."""
        ep = EndpointDescriptor()
        start_indent = self._current().indent
        self._advance()

        while self._current() and self._current().indent > start_indent:
            line = self._current()
            content = line.content

            if content.startswith("bEndpointAddress"):
                ep.address = self._parse_hex_value(content)
                ep.direction = "IN" if (ep.address & 0x80) else "OUT"
                self._advance()
            elif content.startswith("bmAttributes"):
                attrs = self._parse_int_value(content)
                # Transfer type (bits 0-1)
                transfer_types = ["Control", "Isochronous", "Bulk", "Interrupt"]
                ep.transfer_type = transfer_types[attrs & 0x03]

                # Sync type (bits 2-3) for isochronous
                if ep.transfer_type == "Isochronous":
                    sync_types = [SyncType.NONE, SyncType.ASYNC, SyncType.ADAPTIVE, SyncType.SYNC]
                    ep.sync_type = sync_types[(attrs >> 2) & 0x03]

                    # Usage type (bits 4-5)
                    usage_types = [UsageType.DATA, UsageType.FEEDBACK, UsageType.IMPLICIT_FEEDBACK, UsageType.DATA]
                    ep.usage_type = usage_types[(attrs >> 4) & 0x03]
                self._advance()
            elif content.startswith("wMaxPacketSize"):
                # Format may include transactions: "0x0200  1x 512 bytes"
                match = re.search(r'0x([0-9a-fA-F]+)', content)
                if match:
                    ep.max_packet_size = int(match.group(1), 16) & 0x7FF  # Lower 11 bits
                self._advance()
            elif content.startswith("bInterval"):
                ep.interval = self._parse_int_value(content)
                self._advance()
            elif content.startswith("bRefresh"):
                ep.refresh = self._parse_int_value(content)
                self._advance()
            elif content.startswith("bSynchAddress"):
                ep.synch_address = self._parse_hex_value(content)
                self._advance()
            elif content.startswith("AudioControl Endpoint Descriptor:"):
                # Parse audio-specific endpoint extensions
                self._parse_audio_endpoint_descriptor(ep)
            else:
                self._advance()

        return ep

    def _parse_audio_endpoint_descriptor(self, ep: EndpointDescriptor) -> None:
        """Parse audio-specific endpoint descriptor extensions."""
        start_indent = self._current().indent
        self._advance()

        while self._current() and self._current().indent > start_indent:
            line = self._current()
            content = line.content

            if content.startswith("bmAttributes"):
                attrs = self._parse_hex_value(content)
                ep.max_packets_only = bool(attrs & 0x80)
            elif content.startswith("bLockDelayUnits"):
                ep.lock_delay_units = self._parse_int_value(content)
            elif content.startswith("wLockDelay"):
                ep.lock_delay = self._parse_int_value(content)

            self._advance()

    def _parse_audio_control_descriptor(self, device: USBAudioDevice) -> None:
        """Parse AudioControl Interface Descriptor."""
        if not device.audio_control:
            device.audio_control = AudioControlInterface()

        start_indent = self._current().indent
        self._advance()

        # Read descriptor subtype
        subtype = 0
        while self._current() and self._current().indent > start_indent:
            line = self._current()
            content = line.content

            if content.startswith("bDescriptorSubtype"):
                subtype = self._parse_int_value(content)
                break
            self._advance()

        # Reset to parse full descriptor based on subtype
        # Continue from current position
        if subtype == self.AC_HEADER:
            self._parse_ac_header(device.audio_control, start_indent)
        elif subtype == self.AC_INPUT_TERMINAL:
            self._parse_input_terminal(device.audio_control, start_indent)
        elif subtype == self.AC_OUTPUT_TERMINAL:
            self._parse_output_terminal(device.audio_control, start_indent)
        elif subtype == self.AC_FEATURE_UNIT:
            self._parse_feature_unit(device.audio_control, start_indent)
        elif subtype == self.AC_MIXER_UNIT:
            self._parse_mixer_unit(device.audio_control, start_indent)
        elif subtype == self.AC_SELECTOR_UNIT:
            self._parse_selector_unit(device.audio_control, start_indent)
        elif subtype == self.AC_PROCESSING_UNIT:
            self._parse_processing_unit(device.audio_control, start_indent)
        elif subtype == self.AC_EXTENSION_UNIT:
            self._parse_extension_unit(device.audio_control, start_indent)
        elif subtype == self.AC_CLOCK_SOURCE:
            self._parse_clock_source(device.audio_control, start_indent)
        elif subtype == self.AC_CLOCK_SELECTOR:
            self._parse_clock_selector(device.audio_control, start_indent)
        elif subtype == self.AC_CLOCK_MULTIPLIER:
            self._parse_clock_multiplier(device.audio_control, start_indent)
        else:
            # Skip unknown descriptor
            while self._current() and self._current().indent > start_indent:
                self._advance()

    def _parse_ac_header(self, ac: AudioControlInterface, start_indent: int) -> None:
        """Parse AudioControl Header descriptor."""
        header = AudioControlHeader()

        while self._current() and self._current().indent > start_indent:
            line = self._current()
            content = line.content

            if content.startswith("bcdADC"):
                header.bcd_adc = self._parse_bcd_value(content)
                # Determine UAC version from bcdADC
                if header.bcd_adc >= 0x0200:
                    header.uac_version = UACVersion.UAC_2_0
                else:
                    header.uac_version = UACVersion.UAC_1_0
            elif content.startswith("wTotalLength"):
                header.total_length = self._parse_int_value(content)
            elif content.startswith("bInCollection"):
                header.in_collection = self._parse_int_value(content)
            elif content.startswith("baInterfaceNr"):
                # UAC 1.0 interface numbers - format: baInterfaceNr(0)  1
                match = re.search(r'baInterfaceNr\(\d+\)\s+(\d+)', content)
                if match:
                    iface_nr = int(match.group(1))
                    header.interface_numbers.append(iface_nr)
            elif content.startswith("bCategory"):
                header.category = self._parse_hex_value(content)
            elif content.startswith("bmControls"):
                header.controls = self._parse_hex_value(content)

            self._advance()

        ac.header = header

    def _parse_input_terminal(self, ac: AudioControlInterface, start_indent: int) -> None:
        """Parse Input Terminal descriptor."""
        terminal = InputTerminal()

        while self._current() and self._current().indent > start_indent:
            line = self._current()
            content = line.content

            if content.startswith("bTerminalID"):
                terminal.terminal_id = self._parse_int_value(content)
            elif content.startswith("wTerminalType"):
                terminal.terminal_type = self._parse_hex_value(content)
            elif content.startswith("bAssocTerminal"):
                terminal.assoc_terminal = self._parse_int_value(content)
            elif content.startswith("bNrChannels"):
                terminal.nr_channels = self._parse_int_value(content)
            elif content.startswith("wChannelConfig"):
                terminal.channel_config = self._parse_hex_value(content)
            elif content.startswith("iChannelNames"):
                match = re.search(r'iChannelNames\s+\d+\s+(.+)', content)
                if match:
                    terminal.channel_names = match.group(1).strip()
            elif content.startswith("iTerminal"):
                match = re.search(r'iTerminal\s+\d+\s+(.+)', content)
                if match:
                    terminal.terminal_name = match.group(1).strip()
            elif content.startswith("bCSourceID"):
                terminal.clock_source_id = self._parse_int_value(content)
            elif content.startswith("bmControls"):
                terminal.controls = self._parse_hex_value(content)

            self._advance()

        ac.input_terminals.append(terminal)

    def _parse_output_terminal(self, ac: AudioControlInterface, start_indent: int) -> None:
        """Parse Output Terminal descriptor."""
        terminal = OutputTerminal()

        while self._current() and self._current().indent > start_indent:
            line = self._current()
            content = line.content

            if content.startswith("bTerminalID"):
                terminal.terminal_id = self._parse_int_value(content)
            elif content.startswith("wTerminalType"):
                terminal.terminal_type = self._parse_hex_value(content)
            elif content.startswith("bAssocTerminal"):
                terminal.assoc_terminal = self._parse_int_value(content)
            elif content.startswith("bSourceID"):
                terminal.source_id = self._parse_int_value(content)
            elif content.startswith("iTerminal"):
                match = re.search(r'iTerminal\s+\d+\s+(.+)', content)
                if match:
                    terminal.terminal_name = match.group(1).strip()
            elif content.startswith("bCSourceID"):
                terminal.clock_source_id = self._parse_int_value(content)
            elif content.startswith("bmControls"):
                terminal.controls = self._parse_hex_value(content)

            self._advance()

        ac.output_terminals.append(terminal)

    def _parse_feature_unit(self, ac: AudioControlInterface, start_indent: int) -> None:
        """Parse Feature Unit descriptor."""
        unit = FeatureUnit()

        while self._current() and self._current().indent > start_indent:
            line = self._current()
            content = line.content

            if content.startswith("bUnitID"):
                unit.unit_id = self._parse_int_value(content)
            elif content.startswith("bSourceID"):
                unit.source_id = self._parse_int_value(content)
            elif content.startswith("bControlSize"):
                # UAC 1.0 control size
                pass
            elif re.match(r'bmaControls\(\s*\d+\)', content):
                # Format: bmaControls( 0)  0x03
                ctrl = self._parse_hex_value(content)
                unit.controls.append(ctrl)
            elif content.startswith("iFeature"):
                match = re.search(r'iFeature\s+\d+\s+(.+)', content)
                if match:
                    unit.unit_name = match.group(1).strip()

            self._advance()

        ac.feature_units.append(unit)

    def _parse_mixer_unit(self, ac: AudioControlInterface, start_indent: int) -> None:
        """Parse Mixer Unit descriptor."""
        unit = MixerUnit()

        while self._current() and self._current().indent > start_indent:
            line = self._current()
            content = line.content

            if content.startswith("bUnitID"):
                unit.unit_id = self._parse_int_value(content)
            elif content.startswith("bNrInPins"):
                unit.nr_in_pins = self._parse_int_value(content)
            elif re.match(r'baSourceID\(\s*\d+\)', content):
                src_id = self._parse_int_value(content.split(')')[-1])
                unit.source_ids.append(src_id)
            elif content.startswith("bNrChannels"):
                unit.nr_channels = self._parse_int_value(content)
            elif content.startswith("wChannelConfig"):
                unit.channel_config = self._parse_hex_value(content)
            elif content.startswith("iChannelNames"):
                match = re.search(r'iChannelNames\s+\d+\s+(.+)', content)
                if match:
                    unit.channel_names = match.group(1).strip()
            elif content.startswith("iMixer"):
                match = re.search(r'iMixer\s+\d+\s+(.+)', content)
                if match:
                    unit.unit_name = match.group(1).strip()

            self._advance()

        ac.mixer_units.append(unit)

    def _parse_selector_unit(self, ac: AudioControlInterface, start_indent: int) -> None:
        """Parse Selector Unit descriptor."""
        unit = SelectorUnit()

        while self._current() and self._current().indent > start_indent:
            line = self._current()
            content = line.content

            if content.startswith("bUnitID"):
                unit.unit_id = self._parse_int_value(content)
            elif content.startswith("bNrInPins"):
                unit.nr_in_pins = self._parse_int_value(content)
            elif re.match(r'baSourceID\(\s*\d+\)', content):
                src_id = self._parse_int_value(content.split(')')[-1])
                unit.source_ids.append(src_id)
            elif content.startswith("iSelector"):
                match = re.search(r'iSelector\s+\d+\s+(.+)', content)
                if match:
                    unit.selector_name = match.group(1).strip()

            self._advance()

        ac.selector_units.append(unit)

    def _parse_processing_unit(self, ac: AudioControlInterface, start_indent: int) -> None:
        """Parse Processing Unit descriptor."""
        unit = ProcessingUnit()

        while self._current() and self._current().indent > start_indent:
            line = self._current()
            content = line.content

            if content.startswith("bUnitID"):
                unit.unit_id = self._parse_int_value(content)
            elif content.startswith("wProcessType"):
                unit.process_type = self._parse_hex_value(content)
            elif content.startswith("bNrInPins"):
                unit.nr_in_pins = self._parse_int_value(content)
            elif re.match(r'baSourceID\(\s*\d+\)', content):
                src_id = self._parse_int_value(content.split(')')[-1])
                unit.source_ids.append(src_id)
            elif content.startswith("bNrChannels"):
                unit.nr_channels = self._parse_int_value(content)
            elif content.startswith("wChannelConfig"):
                unit.channel_config = self._parse_hex_value(content)
            elif content.startswith("iChannelNames"):
                match = re.search(r'iChannelNames\s+\d+\s+(.+)', content)
                if match:
                    unit.channel_names = match.group(1).strip()
            elif content.startswith("bmControls"):
                unit.controls = self._parse_hex_value(content)
            elif content.startswith("iProcessing"):
                match = re.search(r'iProcessing\s+\d+\s+(.+)', content)
                if match:
                    unit.unit_name = match.group(1).strip()

            self._advance()

        ac.processing_units.append(unit)

    def _parse_extension_unit(self, ac: AudioControlInterface, start_indent: int) -> None:
        """Parse Extension Unit descriptor."""
        unit = ExtensionUnit()

        while self._current() and self._current().indent > start_indent:
            line = self._current()
            content = line.content

            if content.startswith("bUnitID"):
                unit.unit_id = self._parse_int_value(content)
            elif content.startswith("wExtensionCode"):
                unit.extension_code = self._parse_hex_value(content)
            elif content.startswith("bNrInPins"):
                unit.nr_in_pins = self._parse_int_value(content)
            elif re.match(r'baSourceID\(\s*\d+\)', content):
                src_id = self._parse_int_value(content.split(')')[-1])
                unit.source_ids.append(src_id)
            elif content.startswith("bNrChannels"):
                unit.nr_channels = self._parse_int_value(content)
            elif content.startswith("wChannelConfig"):
                unit.channel_config = self._parse_hex_value(content)
            elif content.startswith("iChannelNames"):
                match = re.search(r'iChannelNames\s+\d+\s+(.+)', content)
                if match:
                    unit.channel_names = match.group(1).strip()
            elif content.startswith("bmControls"):
                unit.controls = self._parse_hex_value(content)
            elif content.startswith("iExtension"):
                match = re.search(r'iExtension\s+\d+\s+(.+)', content)
                if match:
                    unit.unit_name = match.group(1).strip()

            self._advance()

        ac.extension_units.append(unit)

    def _parse_clock_source(self, ac: AudioControlInterface, start_indent: int) -> None:
        """Parse Clock Source descriptor (UAC 2.0)."""
        clock = ClockSource()

        while self._current() and self._current().indent > start_indent:
            line = self._current()
            content = line.content

            if content.startswith("bClockID"):
                clock.clock_id = self._parse_int_value(content)
            elif content.startswith("bmAttributes"):
                clock.attributes = self._parse_hex_value(content)
            elif content.startswith("bmControls"):
                clock.controls = self._parse_hex_value(content)
            elif content.startswith("bAssocTerminal"):
                clock.assoc_terminal = self._parse_int_value(content)
            elif content.startswith("iClockSource"):
                match = re.search(r'iClockSource\s+\d+\s+(.+)', content)
                if match:
                    clock.clock_source_name = match.group(1).strip()

            self._advance()

        ac.clock_sources.append(clock)

    def _parse_clock_selector(self, ac: AudioControlInterface, start_indent: int) -> None:
        """Parse Clock Selector descriptor (UAC 2.0)."""
        clock = ClockSelector()

        while self._current() and self._current().indent > start_indent:
            line = self._current()
            content = line.content

            if content.startswith("bClockID"):
                clock.clock_id = self._parse_int_value(content)
            elif content.startswith("bNrInPins"):
                clock.nr_in_pins = self._parse_int_value(content)
            elif re.match(r'baCSourceID\(\s*\d+\)', content):
                src_id = self._parse_int_value(content.split(')')[-1])
                clock.clock_pin_ids.append(src_id)
            elif content.startswith("bmControls"):
                clock.controls = self._parse_hex_value(content)
            elif content.startswith("iClockSelector"):
                match = re.search(r'iClockSelector\s+\d+\s+(.+)', content)
                if match:
                    clock.clock_selector_name = match.group(1).strip()

            self._advance()

        ac.clock_selectors.append(clock)

    def _parse_clock_multiplier(self, ac: AudioControlInterface, start_indent: int) -> None:
        """Parse Clock Multiplier descriptor (UAC 2.0)."""
        clock = ClockMultiplier()

        while self._current() and self._current().indent > start_indent:
            line = self._current()
            content = line.content

            if content.startswith("bClockID"):
                clock.clock_id = self._parse_int_value(content)
            elif content.startswith("bCSourceID"):
                clock.clock_source_id = self._parse_int_value(content)
            elif content.startswith("bmControls"):
                clock.controls = self._parse_hex_value(content)
            elif content.startswith("iClockMultiplier"):
                match = re.search(r'iClockMultiplier\s+\d+\s+(.+)', content)
                if match:
                    clock.clock_multiplier_name = match.group(1).strip()

            self._advance()

        ac.clock_multipliers.append(clock)

    def _parse_audio_streaming_descriptor(self, device: USBAudioDevice, iface: InterfaceDescriptor) -> None:
        """Parse AudioStreaming Interface Descriptor."""
        start_indent = self._current().indent
        self._advance()

        # Check first field to determine descriptor type
        subtype = 0
        while self._current() and self._current().indent > start_indent:
            content = self._current().content

            if content.startswith("bDescriptorSubtype"):
                subtype = self._parse_int_value(content)
                break
            self._advance()

        if subtype == self.AS_GENERAL:
            self._parse_as_general(device, iface, start_indent)
        elif subtype == self.AS_FORMAT_TYPE:
            self._parse_as_format_type(device, start_indent)
        else:
            # Skip unknown descriptor
            while self._current() and self._current().indent > start_indent:
                self._advance()

    def _parse_as_general(self, device: USBAudioDevice, iface: InterfaceDescriptor, start_indent: int) -> None:
        """Parse AS General descriptor."""
        streaming = AudioStreamingInterface()
        streaming.interface_number = iface.interface_number
        streaming.alternate_setting = iface.alternate_setting

        while self._current() and self._current().indent > start_indent:
            line = self._current()
            content = line.content

            if content.startswith("bTerminalLink"):
                streaming.terminal_link = self._parse_int_value(content)
            elif content.startswith("bDelay"):
                streaming.delay = self._parse_int_value(content)
            elif content.startswith("wFormatTag"):
                streaming.format_tag = self._parse_hex_value(content)
            elif content.startswith("bmControls"):
                streaming.controls = self._parse_hex_value(content)
            elif content.startswith("bFormatType"):
                # UAC 2.0 format type in AS general
                pass
            elif content.startswith("bNrChannels"):
                # UAC 2.0: channel count is in AS General, store temporarily
                streaming._nr_channels = self._parse_int_value(content)
            elif content.startswith("bClockSourceID"):
                streaming.clock_source_id = self._parse_int_value(content)

            self._advance()

        device.streaming_interfaces.append(streaming)

    def _parse_as_format_type(self, device: USBAudioDevice, start_indent: int) -> None:
        """Parse AS Format Type descriptor."""
        fmt = FormatTypeDescriptor()

        while self._current() and self._current().indent > start_indent:
            line = self._current()
            content = line.content

            if content.startswith("bFormatType"):
                fmt.format_type = self._parse_int_value(content)
            elif content.startswith("bNrChannels"):
                fmt.nr_channels = self._parse_int_value(content)
            elif content.startswith("bSubframeSize"):
                fmt.subframe_size = self._parse_int_value(content)
            elif content.startswith("bBitResolution"):
                fmt.bit_resolution = self._parse_int_value(content)
            elif content.startswith("bSubslotSize"):
                # UAC 2.0 uses this instead of bSubframeSize
                fmt.subframe_size = self._parse_int_value(content)
            elif content.startswith("bSamFreqType"):
                # Number of discrete sample frequencies (UAC 1.0)
                pass
            elif re.match(r'tSamFreq\[\s*\d+\]', content):
                # Discrete sample frequencies
                freq = self._parse_int_value(content.split(']')[-1])
                fmt.sample_frequencies.append(freq)
            elif content.startswith("tLowerSamFreq"):
                fmt.freq_min = self._parse_int_value(content)
            elif content.startswith("tUpperSamFreq"):
                fmt.freq_max = self._parse_int_value(content)

            self._advance()

        # Attach format to most recent streaming interface
        if device.streaming_interfaces:
            streaming = device.streaming_interfaces[-1]
            streaming.format = fmt
            # UAC 2.0: copy channel count from AS General to format if not set
            if fmt.nr_channels == 0 and hasattr(streaming, '_nr_channels'):
                fmt.nr_channels = streaming._nr_channels

    def _build_alternate_settings(self, device: USBAudioDevice) -> list[AlternateSetting]:
        """Build alternate settings from parsed streaming interfaces."""
        alt_settings = []

        # Map streaming interfaces to their endpoints
        if not device.configuration:
            return alt_settings

        for streaming in device.streaming_interfaces:
            alt = AlternateSetting()
            alt.interface_number = streaming.interface_number
            alt.alternate_setting = streaming.alternate_setting
            alt.streaming_interface = streaming
            alt.format = streaming.format

            # Find matching interface descriptor for endpoint
            for iface in device.configuration.interfaces:
                if (iface.interface_number == streaming.interface_number and
                    iface.alternate_setting == streaming.alternate_setting):
                    if iface.endpoints:
                        # Find data endpoint (not feedback)
                        for ep in iface.endpoints:
                            if ep.usage_type == UsageType.DATA:
                                alt.endpoint = ep
                                streaming.endpoint = ep
                                break
                        if not alt.endpoint and iface.endpoints:
                            alt.endpoint = iface.endpoints[0]
                            streaming.endpoint = iface.endpoints[0]
                    break

            alt_settings.append(alt)

        return alt_settings


def parse_lsusb(text: str) -> USBAudioDevice:
    """
    Parse lsusb -v output and return a USBAudioDevice.

    Args:
        text: The text output from `lsusb -v`

    Returns:
        USBAudioDevice populated with parsed descriptor data

    Raises:
        ParseError: If parsing fails
    """
    parser = LsusbParser(text)
    return parser.parse()


def parse_lsusb_file(file_path: str) -> USBAudioDevice:
    """
    Parse lsusb -v output from a file.

    Args:
        file_path: Path to file containing lsusb -v output

    Returns:
        USBAudioDevice populated with parsed descriptor data
    """
    with open(file_path, 'r') as f:
        return parse_lsusb(f.read())


def parse_lsusb_stream(stream: TextIO) -> USBAudioDevice:
    """
    Parse lsusb -v output from a text stream.

    Args:
        stream: Text stream (e.g., sys.stdin)

    Returns:
        USBAudioDevice populated with parsed descriptor data
    """
    return parse_lsusb(stream.read())
