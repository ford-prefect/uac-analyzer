"""
Bandwidth analysis for USB Audio Class devices.

This module analyzes alternate settings, calculates bandwidth reservations,
and provides format information for audio streaming interfaces.
"""

from dataclasses import dataclass, field
from typing import Optional

from .model import (
    USBAudioDevice,
    AlternateSetting,
    AudioStreamingInterface,
    FormatTypeDescriptor,
    EndpointDescriptor,
    SyncType,
    UsageType,
    get_terminal_type_name,
)


@dataclass
class FormatInfo:
    """Human-readable format information."""
    channels: int = 0
    bit_depth: int = 0
    sample_rates: list[int] = field(default_factory=list)
    sample_rate_range: tuple[int, int] = (0, 0)
    format_name: str = "PCM"

    @property
    def sample_rate_str(self) -> str:
        """Get sample rate as human-readable string."""
        if self.sample_rates:
            if len(self.sample_rates) == 1:
                return f"{self.sample_rates[0] / 1000:.1f} kHz"
            else:
                rates = [f"{r / 1000:.1f}" for r in sorted(self.sample_rates)]
                return f"{', '.join(rates)} kHz"
        elif self.sample_rate_range[0] and self.sample_rate_range[1]:
            return f"{self.sample_rate_range[0] / 1000:.1f}-{self.sample_rate_range[1] / 1000:.1f} kHz"
        return "Unknown"

    @property
    def format_str(self) -> str:
        """Get format as human-readable string."""
        return f"{self.channels}ch {self.bit_depth}-bit {self.format_name}"


@dataclass
class BandwidthInfo:
    """Bandwidth information for an alternate setting."""
    interface_number: int = 0
    alternate_setting: int = 0
    direction: str = ""  # "IN" (capture) or "OUT" (playback)

    # Format details
    format: Optional[FormatInfo] = None

    # Endpoint details
    endpoint_address: int = 0
    max_packet_size: int = 0
    sync_type: SyncType = SyncType.NONE
    usage_type: UsageType = UsageType.DATA

    # Bandwidth calculations
    bytes_per_frame: int = 0  # USB frame (1ms for FS, 125μs for HS)
    bytes_per_second: int = 0
    bandwidth_percent: float = 0.0  # Percentage of USB bandwidth

    # Associated terminal
    terminal_id: int = 0
    terminal_type: str = ""

    @property
    def is_zero_bandwidth(self) -> bool:
        """Check if this is a zero-bandwidth (disabled) setting."""
        return self.max_packet_size == 0

    @property
    def sync_type_str(self) -> str:
        """Get sync type as human-readable string."""
        return {
            SyncType.NONE: "None",
            SyncType.ASYNC: "Asynchronous",
            SyncType.ADAPTIVE: "Adaptive",
            SyncType.SYNC: "Synchronous",
        }.get(self.sync_type, "Unknown")

    @property
    def bandwidth_str(self) -> str:
        """Get bandwidth as human-readable string."""
        if self.bytes_per_second == 0:
            return "0 (disabled)"

        if self.bytes_per_second >= 1_000_000:
            return f"{self.bytes_per_second / 1_000_000:.2f} MB/s"
        elif self.bytes_per_second >= 1_000:
            return f"{self.bytes_per_second / 1_000:.1f} KB/s"
        else:
            return f"{self.bytes_per_second} B/s"


@dataclass
class InterfaceBandwidthSummary:
    """Summary of all alternate settings for an interface."""
    interface_number: int = 0
    direction: str = ""
    terminal_id: int = 0
    terminal_type: str = ""
    alternate_settings: list[BandwidthInfo] = field(default_factory=list)

    @property
    def max_bandwidth_setting(self) -> Optional[BandwidthInfo]:
        """Get the alternate setting with maximum bandwidth."""
        active = [s for s in self.alternate_settings if not s.is_zero_bandwidth]
        if not active:
            return None
        return max(active, key=lambda s: s.bytes_per_second)

    @property
    def available_formats(self) -> list[FormatInfo]:
        """Get all unique formats available on this interface."""
        formats = []
        seen = set()
        for setting in self.alternate_settings:
            if setting.format and not setting.is_zero_bandwidth:
                key = (setting.format.channels, setting.format.bit_depth,
                       tuple(setting.format.sample_rates))
                if key not in seen:
                    seen.add(key)
                    formats.append(setting.format)
        return formats


@dataclass
class DeviceBandwidthAnalysis:
    """Complete bandwidth analysis for a USB audio device."""
    interfaces: list[InterfaceBandwidthSummary] = field(default_factory=list)
    playback_interfaces: list[InterfaceBandwidthSummary] = field(default_factory=list)
    capture_interfaces: list[InterfaceBandwidthSummary] = field(default_factory=list)

    # Totals
    max_playback_bandwidth: int = 0
    max_capture_bandwidth: int = 0
    max_total_bandwidth: int = 0

    @property
    def total_bandwidth_str(self) -> str:
        """Get total bandwidth as human-readable string."""
        total = self.max_total_bandwidth
        if total >= 1_000_000:
            return f"{total / 1_000_000:.2f} MB/s"
        elif total >= 1_000:
            return f"{total / 1_000:.1f} KB/s"
        else:
            return f"{total} B/s"


def analyze_bandwidth(device: USBAudioDevice) -> DeviceBandwidthAnalysis:
    """
    Analyze bandwidth for all streaming interfaces in a USB audio device.

    Args:
        device: The parsed USB audio device

    Returns:
        DeviceBandwidthAnalysis with complete bandwidth information
    """
    analysis = DeviceBandwidthAnalysis()

    # Group alternate settings by interface number
    interface_settings: dict[int, list[BandwidthInfo]] = {}

    for alt in device.alternate_settings:
        if alt.streaming_interface:
            bw_info = _analyze_alternate_setting(device, alt)
            if alt.interface_number not in interface_settings:
                interface_settings[alt.interface_number] = []
            interface_settings[alt.interface_number].append(bw_info)

    # Build interface summaries
    for iface_num, settings in sorted(interface_settings.items()):
        summary = InterfaceBandwidthSummary(
            interface_number=iface_num,
            alternate_settings=sorted(settings, key=lambda s: s.alternate_setting),
        )

        # Get direction and terminal info from first non-zero setting
        for setting in settings:
            if not setting.is_zero_bandwidth:
                summary.direction = setting.direction
                summary.terminal_id = setting.terminal_id
                summary.terminal_type = setting.terminal_type
                break

        analysis.interfaces.append(summary)

        if summary.direction == "OUT":
            analysis.playback_interfaces.append(summary)
        elif summary.direction == "IN":
            analysis.capture_interfaces.append(summary)

    # Calculate max bandwidth totals
    for iface in analysis.playback_interfaces:
        max_setting = iface.max_bandwidth_setting
        if max_setting:
            analysis.max_playback_bandwidth += max_setting.bytes_per_second

    for iface in analysis.capture_interfaces:
        max_setting = iface.max_bandwidth_setting
        if max_setting:
            analysis.max_capture_bandwidth += max_setting.bytes_per_second

    analysis.max_total_bandwidth = (analysis.max_playback_bandwidth +
                                     analysis.max_capture_bandwidth)

    return analysis


def _analyze_alternate_setting(device: USBAudioDevice, alt: AlternateSetting) -> BandwidthInfo:
    """Analyze a single alternate setting."""
    bw = BandwidthInfo(
        interface_number=alt.interface_number,
        alternate_setting=alt.alternate_setting,
    )

    streaming = alt.streaming_interface
    if not streaming:
        return bw

    # Get terminal info
    bw.terminal_id = streaming.terminal_link
    if device.audio_control:
        entity = device.audio_control.get_entity_by_id(streaming.terminal_link)
        if entity:
            if hasattr(entity, 'terminal_type'):
                bw.terminal_type = get_terminal_type_name(entity.terminal_type)

    # Get format info
    if alt.format:
        bw.format = _extract_format_info(streaming, alt.format)

    # Get endpoint info
    if alt.endpoint:
        ep = alt.endpoint
        bw.endpoint_address = ep.address
        bw.direction = ep.direction
        bw.max_packet_size = ep.max_packet_size
        bw.sync_type = ep.sync_type
        bw.usage_type = ep.usage_type

        # Calculate bandwidth
        # For USB Audio, typically 1 packet per (micro)frame
        # Full Speed: 1 frame = 1ms, so 1000 packets/sec
        # High Speed: 1 microframe = 125μs, so 8000 packets/sec
        # Use max packet size as the reservation

        bw.bytes_per_frame = ep.max_packet_size

        # Assume high-speed (most common for audio devices)
        # For FS devices, interval would typically indicate 1ms framing
        # This is a simplification - real bandwidth depends on USB speed
        if ep.interval <= 1:
            # High-speed: 8000 microframes per second
            bw.bytes_per_second = ep.max_packet_size * 8000
        else:
            # Full-speed: 1000 frames per second
            bw.bytes_per_second = ep.max_packet_size * 1000

        # Calculate bandwidth percentage (of USB 2.0 high-speed 480 Mbps)
        usb_hs_bandwidth = 480_000_000 // 8  # 60 MB/s
        bw.bandwidth_percent = (bw.bytes_per_second / usb_hs_bandwidth) * 100

    return bw


def _extract_format_info(streaming: AudioStreamingInterface,
                         fmt: FormatTypeDescriptor) -> FormatInfo:
    """Extract format information from descriptors."""
    info = FormatInfo(
        channels=fmt.nr_channels,
        bit_depth=fmt.bit_resolution,
        sample_rates=list(fmt.sample_frequencies) if fmt.sample_frequencies else [],
        sample_rate_range=fmt.sample_rate_range,
        format_name=streaming.format_name,
    )
    return info


def format_bandwidth_table(analysis: DeviceBandwidthAnalysis) -> str:
    """
    Format bandwidth analysis as an ASCII table.

    Args:
        analysis: The device bandwidth analysis

    Returns:
        Formatted ASCII table string
    """
    lines = []

    if not analysis.interfaces:
        return "No streaming interfaces found.\n"

    # Header
    lines.append("=" * 85)
    lines.append("STREAMING INTERFACES AND BANDWIDTH")
    lines.append("=" * 85)

    for iface in analysis.interfaces:
        lines.append("")
        direction_str = "Playback" if iface.direction == "OUT" else "Capture"
        lines.append(f"Interface {iface.interface_number}: {direction_str}")
        if iface.terminal_type:
            lines.append(f"  Terminal: {iface.terminal_type} (ID {iface.terminal_id})")
        lines.append("-" * 85)

        # Table header
        lines.append(f"{'Alt':>4} | {'Format':<25} | {'Sample Rate':<20} | {'Sync':<12} | {'Bandwidth':<12}")
        lines.append("-" * 85)

        for setting in iface.alternate_settings:
            if setting.is_zero_bandwidth:
                lines.append(f"{setting.alternate_setting:>4} | {'(zero bandwidth - disabled)':<25} | {'':<20} | {'':<12} | {'0':<12}")
            else:
                fmt_str = setting.format.format_str if setting.format else "Unknown"
                rate_str = setting.format.sample_rate_str if setting.format else "Unknown"
                sync_str = setting.sync_type_str
                bw_str = setting.bandwidth_str

                lines.append(f"{setting.alternate_setting:>4} | {fmt_str:<25} | {rate_str:<20} | {sync_str:<12} | {bw_str:<12}")

    lines.append("")
    lines.append("=" * 85)
    lines.append("BANDWIDTH SUMMARY")
    lines.append("-" * 85)

    if analysis.max_playback_bandwidth:
        bw = analysis.max_playback_bandwidth
        if bw >= 1_000_000:
            bw_str = f"{bw / 1_000_000:.2f} MB/s"
        else:
            bw_str = f"{bw / 1_000:.1f} KB/s"
        lines.append(f"Max Playback Bandwidth: {bw_str}")

    if analysis.max_capture_bandwidth:
        bw = analysis.max_capture_bandwidth
        if bw >= 1_000_000:
            bw_str = f"{bw / 1_000_000:.2f} MB/s"
        else:
            bw_str = f"{bw / 1_000:.1f} KB/s"
        lines.append(f"Max Capture Bandwidth:  {bw_str}")

    lines.append(f"Max Total Bandwidth:    {analysis.total_bandwidth_str}")
    lines.append("")

    return "\n".join(lines)
