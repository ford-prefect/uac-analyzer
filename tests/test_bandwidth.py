"""Tests for bandwidth analysis."""

import pytest
from pathlib import Path

from uac_analyzer.parser import parse_lsusb
from uac_analyzer.bandwidth import (
    analyze_bandwidth,
    DeviceBandwidthAnalysis,
    format_bandwidth_table,
)
from uac_analyzer.model import SyncType


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestBandwidthAnalysis:
    """Tests for bandwidth calculation."""

    @pytest.fixture
    def uac1_analysis(self):
        """Analyze bandwidth from UAC 1.0 headset fixture."""
        fixture_path = FIXTURES_DIR / "uac1_stereo_headset.txt"
        with open(fixture_path) as f:
            device = parse_lsusb(f.read())
        return analyze_bandwidth(device)

    @pytest.fixture
    def uac2_analysis(self):
        """Analyze bandwidth from UAC 2.0 audio interface fixture."""
        fixture_path = FIXTURES_DIR / "uac2_audio_interface.txt"
        with open(fixture_path) as f:
            device = parse_lsusb(f.read())
        return analyze_bandwidth(device)

    def test_interfaces_found(self, uac1_analysis):
        """Test that streaming interfaces are found."""
        assert len(uac1_analysis.interfaces) == 2
        assert len(uac1_analysis.playback_interfaces) == 1
        assert len(uac1_analysis.capture_interfaces) == 1

    def test_playback_bandwidth(self, uac1_analysis):
        """Test playback bandwidth calculation."""
        playback = uac1_analysis.playback_interfaces[0]
        assert playback.direction == "OUT"

        # Get active (non-zero bandwidth) setting
        max_setting = playback.max_bandwidth_setting
        assert max_setting is not None
        assert not max_setting.is_zero_bandwidth

        # Max packet size is 192 bytes
        assert max_setting.max_packet_size == 192

        # Bandwidth should be positive
        assert max_setting.bytes_per_second > 0

    def test_capture_bandwidth(self, uac1_analysis):
        """Test capture bandwidth calculation."""
        capture = uac1_analysis.capture_interfaces[0]
        assert capture.direction == "IN"

        max_setting = capture.max_bandwidth_setting
        assert max_setting is not None
        assert max_setting.max_packet_size == 96  # Mono 16-bit 48kHz

    def test_format_info(self, uac1_analysis):
        """Test format information extraction."""
        playback = uac1_analysis.playback_interfaces[0]
        max_setting = playback.max_bandwidth_setting

        assert max_setting.format is not None
        assert max_setting.format.channels == 2
        assert max_setting.format.bit_depth == 16
        assert 48000 in max_setting.format.sample_rates

    def test_sync_type(self, uac1_analysis):
        """Test sync type extraction."""
        playback = uac1_analysis.playback_interfaces[0]
        max_setting = playback.max_bandwidth_setting

        assert max_setting.sync_type == SyncType.ADAPTIVE

    def test_total_bandwidth(self, uac1_analysis):
        """Test total bandwidth calculation."""
        assert uac1_analysis.max_playback_bandwidth > 0
        assert uac1_analysis.max_capture_bandwidth > 0
        assert uac1_analysis.max_total_bandwidth == (
            uac1_analysis.max_playback_bandwidth +
            uac1_analysis.max_capture_bandwidth
        )


class TestUAC2Bandwidth:
    """Tests specific to UAC 2.0 bandwidth analysis."""

    @pytest.fixture
    def uac2_analysis(self):
        """Analyze bandwidth from UAC 2.0 audio interface fixture."""
        fixture_path = FIXTURES_DIR / "uac2_audio_interface.txt"
        with open(fixture_path) as f:
            device = parse_lsusb(f.read())
        return analyze_bandwidth(device)

    def test_uac2_format(self, uac2_analysis):
        """Test UAC 2.0 format extraction."""
        playback = uac2_analysis.playback_interfaces[0]
        max_setting = playback.max_bandwidth_setting

        assert max_setting.format is not None
        # UAC 2.0 Scarlett uses 24-bit in 4-byte slots
        assert max_setting.format.bit_depth == 24
        assert max_setting.format.channels == 2

    def test_async_sync_type(self, uac2_analysis):
        """Test async endpoint detection."""
        playback = uac2_analysis.playback_interfaces[0]
        max_setting = playback.max_bandwidth_setting

        assert max_setting.sync_type == SyncType.ASYNC

    def test_high_bandwidth(self, uac2_analysis):
        """Test high-bandwidth calculation for 24-bit audio."""
        # 24-bit in 4-byte slots, stereo at high sample rate
        # Should have higher bandwidth than 16-bit
        playback = uac2_analysis.playback_interfaces[0]
        max_setting = playback.max_bandwidth_setting

        assert max_setting.max_packet_size == 392
        assert max_setting.bytes_per_second > 0


class TestBandwidthTable:
    """Tests for bandwidth table formatting."""

    @pytest.fixture
    def uac1_analysis(self):
        """Analyze bandwidth from UAC 1.0 headset fixture."""
        fixture_path = FIXTURES_DIR / "uac1_stereo_headset.txt"
        with open(fixture_path) as f:
            device = parse_lsusb(f.read())
        return analyze_bandwidth(device)

    def test_table_generation(self, uac1_analysis):
        """Test bandwidth table is generated."""
        table = format_bandwidth_table(uac1_analysis)
        assert len(table) > 0

    def test_table_content(self, uac1_analysis):
        """Test bandwidth table contains expected content."""
        table = format_bandwidth_table(uac1_analysis)

        # Should contain headers
        assert "STREAMING INTERFACES" in table
        assert "BANDWIDTH" in table

        # Should contain interface info
        assert "Playback" in table
        assert "Capture" in table

        # Should contain format info
        assert "16-bit" in table or "16" in table

    def test_table_summary(self, uac1_analysis):
        """Test bandwidth table summary section."""
        table = format_bandwidth_table(uac1_analysis)

        assert "BANDWIDTH SUMMARY" in table
        assert "Max" in table


class TestFormatInfo:
    """Tests for format info class."""

    def test_sample_rate_str_single(self):
        """Test sample rate string for single rate."""
        from uac_analyzer.bandwidth import FormatInfo

        info = FormatInfo(channels=2, bit_depth=16, sample_rates=[48000])
        assert "48.0 kHz" in info.sample_rate_str

    def test_sample_rate_str_multiple(self):
        """Test sample rate string for multiple rates."""
        from uac_analyzer.bandwidth import FormatInfo

        info = FormatInfo(channels=2, bit_depth=16,
                          sample_rates=[44100, 48000, 96000])
        rate_str = info.sample_rate_str
        assert "44.1" in rate_str
        assert "48.0" in rate_str
        assert "96.0" in rate_str

    def test_sample_rate_str_range(self):
        """Test sample rate string for continuous range."""
        from uac_analyzer.bandwidth import FormatInfo

        info = FormatInfo(channels=2, bit_depth=24,
                          sample_rate_range=(44100, 192000))
        rate_str = info.sample_rate_str
        assert "44.1" in rate_str
        assert "192.0" in rate_str

    def test_format_str(self):
        """Test format string generation."""
        from uac_analyzer.bandwidth import FormatInfo

        info = FormatInfo(channels=2, bit_depth=24, format_name="PCM")
        assert info.format_str == "2ch 24-bit PCM"


class TestBandwidthInfo:
    """Tests for bandwidth info class."""

    def test_bandwidth_str_kb(self):
        """Test bandwidth string in KB/s."""
        from uac_analyzer.bandwidth import BandwidthInfo

        info = BandwidthInfo(bytes_per_second=192000)
        assert "KB/s" in info.bandwidth_str

    def test_bandwidth_str_mb(self):
        """Test bandwidth string in MB/s."""
        from uac_analyzer.bandwidth import BandwidthInfo

        info = BandwidthInfo(bytes_per_second=3_000_000)
        assert "MB/s" in info.bandwidth_str

    def test_zero_bandwidth(self):
        """Test zero bandwidth detection."""
        from uac_analyzer.bandwidth import BandwidthInfo

        info = BandwidthInfo(max_packet_size=0)
        assert info.is_zero_bandwidth

        info = BandwidthInfo(max_packet_size=192)
        assert not info.is_zero_bandwidth


class TestEmptyAnalysis:
    """Tests for empty or minimal analysis cases."""

    def test_empty_device(self):
        """Test analysis of device with no streaming interfaces."""
        device = parse_lsusb("")
        analysis = analyze_bandwidth(device)

        assert len(analysis.interfaces) == 0
        assert analysis.max_total_bandwidth == 0

    def test_empty_table(self):
        """Test table for device with no interfaces."""
        device = parse_lsusb("")
        analysis = analyze_bandwidth(device)
        table = format_bandwidth_table(analysis)

        assert "No streaming interfaces" in table
