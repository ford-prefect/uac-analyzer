"""Tests for the lsusb parser."""

import pytest
from pathlib import Path

from uac_analyzer.parser import parse_lsusb, LsusbParser
from uac_analyzer.model import UACVersion, SyncType


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestUAC1Parser:
    """Tests for parsing UAC 1.0 device descriptors."""

    @pytest.fixture
    def uac1_device(self):
        """Load and parse UAC 1.0 headset fixture."""
        fixture_path = FIXTURES_DIR / "uac1_stereo_headset.txt"
        with open(fixture_path) as f:
            return parse_lsusb(f.read())

    def test_device_descriptor(self, uac1_device):
        """Test parsing of device descriptor."""
        device = uac1_device.device
        assert device.vendor_id == 0x0d8c
        assert device.product_id == 0x0014
        assert device.manufacturer == "C-Media Electronics Inc."
        assert device.product == "USB Audio Device"
        assert device.usb_version == "1.10"

    def test_uac_version(self, uac1_device):
        """Test UAC version detection."""
        assert uac1_device.uac_version == UACVersion.UAC_1_0

    def test_audio_control_header(self, uac1_device):
        """Test parsing of AudioControl header."""
        ac = uac1_device.audio_control
        assert ac is not None
        assert ac.header is not None
        assert ac.header.bcd_adc == 0x0100
        assert ac.header.in_collection == 2
        assert 1 in ac.header.interface_numbers
        assert 2 in ac.header.interface_numbers

    def test_input_terminals(self, uac1_device):
        """Test parsing of input terminals."""
        ac = uac1_device.audio_control
        assert len(ac.input_terminals) == 2

        # USB streaming terminal (playback)
        usb_term = next(t for t in ac.input_terminals if t.terminal_id == 1)
        assert usb_term.terminal_type == 0x0101
        assert usb_term.is_usb_streaming
        assert usb_term.nr_channels == 2

        # Microphone terminal
        mic_term = next(t for t in ac.input_terminals if t.terminal_id == 2)
        assert mic_term.terminal_type == 0x0201
        assert not mic_term.is_usb_streaming
        assert mic_term.nr_channels == 1

    def test_output_terminals(self, uac1_device):
        """Test parsing of output terminals."""
        ac = uac1_device.audio_control
        assert len(ac.output_terminals) == 2

        # Speaker terminal
        spk_term = next(t for t in ac.output_terminals if t.terminal_id == 6)
        assert spk_term.terminal_type == 0x0301
        assert not spk_term.is_usb_streaming
        assert spk_term.source_id == 5

        # USB streaming terminal (capture)
        usb_term = next(t for t in ac.output_terminals if t.terminal_id == 7)
        assert usb_term.terminal_type == 0x0101
        assert usb_term.is_usb_streaming
        assert usb_term.source_id == 4

    def test_feature_units(self, uac1_device):
        """Test parsing of feature units."""
        ac = uac1_device.audio_control
        assert len(ac.feature_units) == 2

        # Playback feature unit
        fu_play = next(u for u in ac.feature_units if u.unit_id == 5)
        assert fu_play.source_id == 1
        assert fu_play.has_mute
        assert fu_play.has_volume

        # Capture feature unit
        fu_cap = next(u for u in ac.feature_units if u.unit_id == 4)
        assert fu_cap.source_id == 2
        assert fu_cap.has_mute
        assert fu_cap.has_volume

    def test_streaming_interfaces(self, uac1_device):
        """Test parsing of streaming interfaces."""
        assert len(uac1_device.streaming_interfaces) == 2

        # Playback interface
        playback = next(s for s in uac1_device.streaming_interfaces
                        if s.terminal_link == 1)
        assert playback.interface_number == 1
        assert playback.alternate_setting == 1
        assert playback.format_tag == 0x0001  # PCM
        assert playback.format is not None
        assert playback.format.nr_channels == 2
        assert playback.format.bit_resolution == 16
        assert 48000 in playback.format.sample_frequencies

        # Capture interface
        capture = next(s for s in uac1_device.streaming_interfaces
                       if s.terminal_link == 7)
        assert capture.interface_number == 2
        assert capture.format.nr_channels == 1

    def test_alternate_settings(self, uac1_device):
        """Test building of alternate settings."""
        # Should have alt settings for both interfaces
        alt_settings = uac1_device.alternate_settings
        assert len(alt_settings) >= 2

        # Check playback endpoint
        playback_alt = next(a for a in alt_settings
                            if a.interface_number == 1 and not a.is_zero_bandwidth)
        assert playback_alt.endpoint is not None
        assert playback_alt.endpoint.direction == "OUT"
        assert playback_alt.endpoint.sync_type == SyncType.ADAPTIVE
        assert playback_alt.endpoint.max_packet_size == 192


class TestUAC2Parser:
    """Tests for parsing UAC 2.0 device descriptors."""

    @pytest.fixture
    def uac2_device(self):
        """Load and parse UAC 2.0 audio interface fixture."""
        fixture_path = FIXTURES_DIR / "uac2_audio_interface.txt"
        with open(fixture_path) as f:
            return parse_lsusb(f.read())

    def test_device_descriptor(self, uac2_device):
        """Test parsing of device descriptor."""
        device = uac2_device.device
        assert device.vendor_id == 0x1235
        assert device.product_id == 0x8211
        assert device.manufacturer == "Focusrite"
        assert device.product == "Scarlett 2i2 USB"
        assert device.serial_number == "ABC123XYZ"

    def test_uac_version(self, uac2_device):
        """Test UAC version detection."""
        assert uac2_device.uac_version == UACVersion.UAC_2_0

    def test_clock_source(self, uac2_device):
        """Test parsing of clock source (UAC 2.0)."""
        ac = uac2_device.audio_control
        assert len(ac.clock_sources) == 1

        clock = ac.clock_sources[0]
        assert clock.clock_id == 41
        assert clock.clock_source_name == "Internal Clock"
        assert clock.clock_type == "Internal Programmable"

    def test_input_terminals_uac2(self, uac2_device):
        """Test parsing of UAC 2.0 input terminals."""
        ac = uac2_device.audio_control
        assert len(ac.input_terminals) == 2

        # USB streaming terminal
        usb_term = next(t for t in ac.input_terminals if t.terminal_id == 1)
        assert usb_term.clock_source_id == 41
        assert usb_term.nr_channels == 2

        # Microphone terminal
        mic_term = next(t for t in ac.input_terminals if t.terminal_id == 2)
        assert mic_term.terminal_type == 0x0201

    def test_feature_units_uac2(self, uac2_device):
        """Test parsing of UAC 2.0 feature units."""
        ac = uac2_device.audio_control
        assert len(ac.feature_units) == 2

        # Both should have mute and volume
        for fu in ac.feature_units:
            assert fu.has_mute
            assert fu.has_volume

    def test_streaming_interface_uac2(self, uac2_device):
        """Test parsing of UAC 2.0 streaming interfaces."""
        playback = next(s for s in uac2_device.streaming_interfaces
                        if s.terminal_link == 1)
        assert playback.format is not None
        assert playback.format.subframe_size == 4  # 24-bit in 4 bytes
        assert playback.format.bit_resolution == 24

    def test_async_endpoint(self, uac2_device):
        """Test async endpoint with feedback."""
        alt_settings = uac2_device.alternate_settings
        playback_alt = next(a for a in alt_settings
                            if a.interface_number == 1 and not a.is_zero_bandwidth)

        assert playback_alt.endpoint is not None
        assert playback_alt.endpoint.sync_type == SyncType.ASYNC
        assert playback_alt.endpoint.max_packet_size == 392


class TestParserEdgeCases:
    """Tests for parser edge cases."""

    def test_empty_input(self):
        """Test handling of empty input."""
        device = parse_lsusb("")
        assert device.audio_control is None

    def test_non_audio_device(self):
        """Test handling of non-audio device."""
        text = """
Bus 001 Device 002: ID 0123:4567 Some Company
Device Descriptor:
  bLength                18
  bDescriptorType         1
  bcdUSB               2.00
  bDeviceClass            0
  bDeviceSubClass         0
  idVendor           0x0123
  idProduct          0x4567
  iManufacturer           1 Test Manufacturer
  iProduct                2 Test Product
  bNumConfigurations      1
        """
        device = parse_lsusb(text)
        assert device.device.vendor_id == 0x0123
        assert device.audio_control is None

    def test_partial_audio_device(self):
        """Test handling of device with only some audio descriptors."""
        text = """
Bus 001 Device 002: ID 0123:4567 Some Company
Device Descriptor:
  bLength                18
  bDescriptorType         1
  bcdUSB               2.00
  idVendor           0x0123
  idProduct          0x4567
  bNumConfigurations      1
  Configuration Descriptor:
    bLength                 9
    bDescriptorType         2
    bNumInterfaces          1
    Interface Descriptor:
      bLength                 9
      bDescriptorType         4
      bInterfaceNumber        0
      bAlternateSetting       0
      bNumEndpoints           0
      bInterfaceClass         1 Audio
      bInterfaceSubClass      1 Control Device
      AudioControl Interface Descriptor:
        bLength                10
        bDescriptorType        36
        bDescriptorSubtype      1 (HEADER)
        bcdADC               1.00
        wTotalLength       0x0020
        bInCollection           1
        baInterfaceNr(0)        1
        """
        device = parse_lsusb(text)
        assert device.audio_control is not None
        assert device.audio_control.header is not None
        assert device.audio_control.header.uac_version == UACVersion.UAC_1_0


class TestTerminalTypes:
    """Tests for terminal type name resolution."""

    def test_common_terminal_types(self):
        """Test common terminal type name lookups."""
        from uac_analyzer.model import get_terminal_type_name

        assert get_terminal_type_name(0x0101) == "USB Streaming"
        assert get_terminal_type_name(0x0201) == "Microphone"
        assert get_terminal_type_name(0x0301) == "Speaker"
        assert get_terminal_type_name(0x0302) == "Headphones"
        assert get_terminal_type_name(0x0402) == "Headset"

    def test_unknown_terminal_type(self):
        """Test unknown terminal type handling."""
        from uac_analyzer.model import get_terminal_type_name

        # Should return categorized name with hex code
        name = get_terminal_type_name(0x02FF)
        assert "Input" in name
        assert "0x02FF" in name


class TestMultiConfigDevice:
    """Tests for devices with multiple UAC configurations."""

    @pytest.fixture
    def apple_dongle(self):
        """Load and parse Apple dongle with UAC 2.0 and 3.0 configs."""
        fixture_path = FIXTURES_DIR / "apple-dongle.txt"
        with open(fixture_path) as f:
            return parse_lsusb(f.read())

    def test_multiple_configurations_parsed(self, apple_dongle):
        """Test that multiple configurations are parsed."""
        # Apple dongle has 3 configurations (including a third we may not fully parse)
        assert len(apple_dongle.configurations) >= 2

    def test_available_uac_versions(self, apple_dongle):
        """Test detection of available UAC versions."""
        versions = apple_dongle.available_uac_versions
        assert UACVersion.UAC_2_0 in versions
        assert UACVersion.UAC_3_0 in versions

    def test_default_selects_highest_version(self, apple_dongle):
        """Test that highest UAC version is selected by default."""
        # Should select UAC 3.0 by default (highest)
        assert apple_dongle.uac_version == UACVersion.UAC_3_0

    def test_select_configuration_uac2(self, apple_dongle):
        """Test selecting UAC 2.0 configuration."""
        result = apple_dongle.select_configuration(UACVersion.UAC_2_0)
        assert result is True
        assert apple_dongle.uac_version == UACVersion.UAC_2_0
        assert apple_dongle.audio_control is not None

    def test_select_configuration_uac3(self, apple_dongle):
        """Test selecting UAC 3.0 configuration."""
        # First select 2.0
        apple_dongle.select_configuration(UACVersion.UAC_2_0)
        # Then select 3.0
        result = apple_dongle.select_configuration(UACVersion.UAC_3_0)
        assert result is True
        assert apple_dongle.uac_version == UACVersion.UAC_3_0

    def test_select_unavailable_version(self, apple_dongle):
        """Test selecting unavailable UAC version returns False."""
        result = apple_dongle.select_configuration(UACVersion.UAC_1_0)
        assert result is False
        # Should keep current selection
        assert apple_dongle.uac_version in (UACVersion.UAC_2_0, UACVersion.UAC_3_0)

    def test_each_config_has_audio_data(self, apple_dongle):
        """Test that each configuration has its own audio data."""
        for config in apple_dongle.configurations:
            # At least the audio configs should have audio control
            if config.uac_version != UACVersion.UNKNOWN:
                assert config.audio_control is not None
                assert config.audio_control.header is not None
