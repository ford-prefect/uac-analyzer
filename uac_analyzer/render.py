"""
ASCII topology diagram and report generation.

This module renders USB Audio Class device information as human-readable
ASCII art diagrams and structured text reports.
"""

from typing import Optional

from .model import (
    USBAudioDevice,
    UACVersion,
    get_terminal_type_name,
)
from .topology import (
    TopologyGraph,
    TopologyNode,
    NodeType,
    SignalPath,
    get_playback_paths,
    get_capture_paths,
    build_topology,
)
from .bandwidth import (
    DeviceBandwidthAnalysis,
    analyze_bandwidth,
    format_bandwidth_table,
)


def render_topology(graph: TopologyGraph, width: int = 80) -> str:
    """
    Render the topology graph as an ASCII diagram.

    Args:
        graph: The topology graph to render
        width: Maximum width of the output

    Returns:
        ASCII art representation of the topology
    """
    lines = []

    lines.append("=" * width)
    lines.append("AUDIO TOPOLOGY")
    lines.append("=" * width)
    lines.append("")

    # Render playback paths (USB -> Speakers)
    playback_paths = get_playback_paths(graph)
    if playback_paths:
        lines.append("PLAYBACK PATHS (Host -> Device)")
        lines.append("-" * 40)
        for i, path in enumerate(playback_paths, 1):
            path_diagram = _render_signal_path(path)
            lines.append(f"Path {i}:")
            lines.extend(path_diagram)
            lines.append("")

    # Render capture paths (Microphones -> USB)
    capture_paths = get_capture_paths(graph)
    if capture_paths:
        lines.append("CAPTURE PATHS (Device -> Host)")
        lines.append("-" * 40)
        for i, path in enumerate(capture_paths, 1):
            path_diagram = _render_signal_path(path)
            lines.append(f"Path {i}:")
            lines.extend(path_diagram)
            lines.append("")

    # Render clock topology if present
    if graph.clock_entities:
        lines.append("CLOCK TOPOLOGY")
        lines.append("-" * 40)
        lines.extend(_render_clock_entities(graph))
        lines.append("")

    # If no paths found, show raw nodes
    if not playback_paths and not capture_paths:
        lines.append("ENTITIES")
        lines.append("-" * 40)
        lines.extend(_render_all_nodes(graph))
        lines.append("")

    return "\n".join(lines)


def _render_signal_path(path: SignalPath) -> list[str]:
    """Render a single signal path as ASCII art."""
    lines = []

    if not path.nodes:
        return ["  (empty path)"]

    # Build horizontal flow diagram
    boxes = []
    for node in path.nodes:
        box = _node_to_box(node)
        boxes.append(box)

    # Calculate maximum box height
    max_height = max(len(box) for box in boxes)

    # Pad boxes to same height
    for box in boxes:
        while len(box) < max_height:
            width = len(box[0]) if box else 10
            box.append(" " * width)

    # Render boxes side by side with arrows
    for row in range(max_height):
        line_parts = []
        for i, box in enumerate(boxes):
            line_parts.append(box[row])
            if i < len(boxes) - 1:
                # Add arrow between boxes (only on middle row)
                if row == max_height // 2:
                    line_parts.append(" --> ")
                else:
                    line_parts.append("     ")
        lines.append("  " + "".join(line_parts))

    return lines


def _node_to_box(node: TopologyNode) -> list[str]:
    """Convert a topology node to an ASCII box."""
    # Determine box content
    if node.node_type == NodeType.INPUT_TERMINAL:
        if node.is_usb_streaming:
            label = "USB OUT"
            sublabel = "(from host)"
        else:
            label = node.description[:15]
            sublabel = f"{node.channels}ch" if node.channels else ""
    elif node.node_type == NodeType.OUTPUT_TERMINAL:
        if node.is_usb_streaming:
            label = "USB IN"
            sublabel = "(to host)"
        else:
            label = node.description[:15]
            sublabel = ""
    elif node.node_type == NodeType.FEATURE_UNIT:
        label = "Feature"
        if node.controls:
            sublabel = ", ".join(node.controls[:2])
            if len(node.controls) > 2:
                sublabel += "..."
        else:
            sublabel = f"ID {node.id}"
    elif node.node_type == NodeType.MIXER_UNIT:
        label = "Mixer"
        sublabel = node.description
    elif node.node_type == NodeType.SELECTOR_UNIT:
        label = "Selector"
        sublabel = node.description
    elif node.node_type == NodeType.PROCESSING_UNIT:
        label = "Process"
        sublabel = node.description[:12]
    elif node.node_type == NodeType.EXTENSION_UNIT:
        label = "Extension"
        sublabel = f"ID {node.id}"
    else:
        label = node.name[:12]
        sublabel = ""

    # Build box
    width = max(len(label), len(sublabel)) + 4
    width = max(width, 12)

    box = []
    box.append("+" + "-" * (width - 2) + "+")
    box.append("|" + label.center(width - 2) + "|")
    if sublabel:
        box.append("|" + sublabel.center(width - 2) + "|")
    box.append("+" + "-" * (width - 2) + "+")

    return box


def _render_clock_entities(graph: TopologyGraph) -> list[str]:
    """Render clock entities as a simple list."""
    lines = []

    for clock in graph.clock_entities:
        if clock.node_type == NodeType.CLOCK_SOURCE:
            lines.append(f"  [Clock Source {clock.id}] {clock.name}")
            lines.append(f"    Type: {clock.description}")
        elif clock.node_type == NodeType.CLOCK_SELECTOR:
            lines.append(f"  [Clock Selector {clock.id}] {clock.name}")
        elif clock.node_type == NodeType.CLOCK_MULTIPLIER:
            lines.append(f"  [Clock Multiplier {clock.id}] {clock.name}")

    return lines


def _render_all_nodes(graph: TopologyGraph) -> list[str]:
    """Render all nodes when no paths are found."""
    lines = []

    if graph.input_terminals:
        lines.append("  Input Terminals:")
        for node in graph.input_terminals:
            usb = " (USB Streaming)" if node.is_usb_streaming else ""
            lines.append(f"    [{node.id}] {node.description}{usb}")

    if graph.output_terminals:
        lines.append("  Output Terminals:")
        for node in graph.output_terminals:
            usb = " (USB Streaming)" if node.is_usb_streaming else ""
            lines.append(f"    [{node.id}] {node.description}{usb}")

    if graph.units:
        lines.append("  Units:")
        for node in graph.units:
            lines.append(f"    [{node.id}] {node.node_type.value}: {node.name}")

    return lines


def render_report(device: USBAudioDevice, graph: Optional[TopologyGraph] = None,
                  analysis: Optional[DeviceBandwidthAnalysis] = None) -> str:
    """
    Render a structured text report for the device.

    Args:
        device: The parsed USB audio device
        graph: Optional pre-built topology graph
        analysis: Optional pre-computed bandwidth analysis

    Returns:
        Formatted text report
    """
    lines = []
    width = 80

    # Build graph and analysis if not provided
    if graph is None:
        graph = build_topology(device)
    if analysis is None:
        analysis = analyze_bandwidth(device)

    # Device Summary
    lines.append("=" * width)
    lines.append("USB AUDIO DEVICE REPORT")
    lines.append("=" * width)
    lines.append("")

    lines.append("DEVICE SUMMARY")
    lines.append("-" * 40)
    lines.append(f"  Product:      {device.device_name}")
    lines.append(f"  Manufacturer: {device.manufacturer_name}")
    lines.append(f"  VID:PID:      {device.device.vendor_id:04X}:{device.device.product_id:04X}")
    lines.append(f"  USB Version:  {device.device.usb_version}")
    lines.append(f"  UAC Version:  {device.uac_version.value}")

    # Show note if device supports multiple UAC versions
    if len(device.available_uac_versions) > 1:
        current = device.uac_version
        other_versions = sorted(
            [v for v in device.available_uac_versions if v != current],
            key=lambda v: v.value,
            reverse=True
        )
        if other_versions:
            other_str = ", ".join(v.value for v in other_versions)
            note = f"  Note: Device also supports UAC {other_str}. Use --uac-version to select."
            if UACVersion.UAC_3_0 in other_versions:
                note += " (UAC 3.0 support is incomplete)"
            lines.append(note)

    lines.append("")

    # Topology Description
    if graph.signal_paths:
        lines.append("SIGNAL FLOW SUMMARY")
        lines.append("-" * 40)

        playback_paths = get_playback_paths(graph)
        capture_paths = get_capture_paths(graph)

        if playback_paths:
            lines.append("  Playback:")
            for path in playback_paths:
                if path.output_node:
                    lines.append(f"    -> {path.output_node.description}")

        if capture_paths:
            lines.append("  Capture:")
            for path in capture_paths:
                if path.input_node:
                    lines.append(f"    <- {path.input_node.description}")

        lines.append("")

    # Input Terminals
    if graph.input_terminals:
        lines.append("INPUT TERMINALS")
        lines.append("-" * 40)
        for node in graph.input_terminals:
            usb_flag = " [USB]" if node.is_usb_streaming else ""
            channels = f" ({node.channels}ch)" if node.channels else ""
            lines.append(f"  ID {node.id}: {node.description}{channels}{usb_flag}")
        lines.append("")

    # Output Terminals
    if graph.output_terminals:
        lines.append("OUTPUT TERMINALS")
        lines.append("-" * 40)
        for node in graph.output_terminals:
            usb_flag = " [USB]" if node.is_usb_streaming else ""
            lines.append(f"  ID {node.id}: {node.description}{usb_flag}")
        lines.append("")

    # Units
    if graph.units:
        lines.append("PROCESSING UNITS")
        lines.append("-" * 40)
        for node in graph.units:
            type_name = node.node_type.value.replace("_", " ").title()
            extra = ""
            if node.controls:
                extra = f" - Controls: {', '.join(node.controls)}"
            lines.append(f"  ID {node.id}: {type_name}{extra}")
        lines.append("")

    # Clock Entities (UAC 2.0)
    if graph.clock_entities:
        lines.append("CLOCK ENTITIES (UAC 2.0)")
        lines.append("-" * 40)
        for node in graph.clock_entities:
            type_name = node.node_type.value.replace("_", " ").title()
            lines.append(f"  ID {node.id}: {type_name} - {node.description}")
        lines.append("")

    # Streaming Interfaces
    if analysis.interfaces:
        lines.append("STREAMING INTERFACES")
        lines.append("-" * 40)

        for iface in analysis.interfaces:
            direction = "Playback" if iface.direction == "OUT" else "Capture"
            lines.append(f"  Interface {iface.interface_number}: {direction}")
            lines.append(f"    Terminal: {iface.terminal_type}")

            formats = iface.available_formats
            if formats:
                lines.append("    Formats:")
                for fmt in formats:
                    lines.append(f"      - {fmt.format_str} @ {fmt.sample_rate_str}")

            lines.append("")

    return "\n".join(lines)


def render_summary(device: USBAudioDevice) -> str:
    """
    Render a brief summary of the device.

    Args:
        device: The parsed USB audio device

    Returns:
        Brief summary string
    """
    lines = []

    lines.append(f"Device: {device.device_name}")
    lines.append(f"Manufacturer: {device.manufacturer_name}")
    lines.append(f"UAC Version: {device.uac_version.value}")

    # Show note if device supports multiple UAC versions
    if len(device.available_uac_versions) > 1:
        current = device.uac_version
        other_versions = sorted(
            [v for v in device.available_uac_versions if v != current],
            key=lambda v: v.value,
            reverse=True
        )
        if other_versions:
            other_str = ", ".join(v.value for v in other_versions)
            note = f"Note: Device also supports UAC {other_str}. Use --uac-version to select."
            if UACVersion.UAC_3_0 in other_versions:
                note += " (UAC 3.0 support is incomplete)"
            lines.append(note)

    graph = build_topology(device)

    # Count capabilities
    playback = len(get_playback_paths(graph))
    capture = len(get_capture_paths(graph))

    caps = []
    if playback:
        caps.append(f"{playback} playback path(s)")
    if capture:
        caps.append(f"{capture} capture path(s)")

    if caps:
        lines.append(f"Capabilities: {', '.join(caps)}")

    # Feature controls
    controls = set()
    for node in graph.units:
        controls.update(node.controls)
    if controls:
        lines.append(f"Controls: {', '.join(sorted(controls))}")

    return "\n".join(lines)


def render_full(device: USBAudioDevice) -> str:
    """
    Render complete analysis including topology diagram, report, and bandwidth table.

    Args:
        device: The parsed USB audio device

    Returns:
        Complete formatted output
    """
    graph = build_topology(device)
    analysis = analyze_bandwidth(device)

    sections = []

    # Topology diagram
    sections.append(render_topology(graph))

    # Structured report
    sections.append(render_report(device, graph, analysis))

    # Bandwidth table
    sections.append(format_bandwidth_table(analysis))

    return "\n".join(sections)


def render_topology_only(device: USBAudioDevice) -> str:
    """
    Render only the topology diagram.

    Args:
        device: The parsed USB audio device

    Returns:
        Topology diagram
    """
    graph = build_topology(device)
    return render_topology(graph)
