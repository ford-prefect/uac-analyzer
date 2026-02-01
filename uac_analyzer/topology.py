"""
Topology graph analysis for USB Audio Class devices.

This module builds and analyzes the signal flow graph from AudioControl
interface descriptors.
"""

from dataclasses import dataclass, field
from typing import Optional, Union
from enum import Enum

from .model import (
    USBAudioDevice,
    AudioControlInterface,
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
    AudioUnit,
    ClockEntity,
    get_terminal_type_name,
)


class NodeType(Enum):
    """Type of node in the topology graph."""
    INPUT_TERMINAL = "input_terminal"
    OUTPUT_TERMINAL = "output_terminal"
    FEATURE_UNIT = "feature_unit"
    MIXER_UNIT = "mixer_unit"
    SELECTOR_UNIT = "selector_unit"
    PROCESSING_UNIT = "processing_unit"
    EXTENSION_UNIT = "extension_unit"
    CLOCK_SOURCE = "clock_source"
    CLOCK_SELECTOR = "clock_selector"
    CLOCK_MULTIPLIER = "clock_multiplier"


@dataclass
class TopologyNode:
    """A node in the topology graph."""
    id: int
    node_type: NodeType
    name: str = ""
    description: str = ""
    channels: int = 0
    entity: Optional[Union[InputTerminal, OutputTerminal, AudioUnit, ClockEntity]] = None

    # For rendering
    is_usb_streaming: bool = False
    controls: list[str] = field(default_factory=list)


@dataclass
class TopologyEdge:
    """An edge (connection) in the topology graph."""
    source_id: int
    target_id: int
    channels: int = 0
    is_clock: bool = False  # True for clock connections


@dataclass
class SignalPath:
    """A complete signal path from input to output."""
    nodes: list[TopologyNode] = field(default_factory=list)
    description: str = ""

    @property
    def input_node(self) -> Optional[TopologyNode]:
        """Get the input terminal node."""
        return self.nodes[0] if self.nodes else None

    @property
    def output_node(self) -> Optional[TopologyNode]:
        """Get the output terminal node."""
        return self.nodes[-1] if self.nodes else None


@dataclass
class TopologyGraph:
    """Complete topology graph for a USB audio device."""
    nodes: dict[int, TopologyNode] = field(default_factory=dict)
    edges: list[TopologyEdge] = field(default_factory=list)
    signal_paths: list[SignalPath] = field(default_factory=list)

    # Categorized nodes for easy access
    input_terminals: list[TopologyNode] = field(default_factory=list)
    output_terminals: list[TopologyNode] = field(default_factory=list)
    units: list[TopologyNode] = field(default_factory=list)
    clock_entities: list[TopologyNode] = field(default_factory=list)

    # USB streaming terminals (important for understanding data flow)
    usb_input_terminals: list[TopologyNode] = field(default_factory=list)  # USB OUT (host to device)
    usb_output_terminals: list[TopologyNode] = field(default_factory=list)  # USB IN (device to host)

    def get_node(self, node_id: int) -> Optional[TopologyNode]:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def get_sources(self, node_id: int) -> list[TopologyNode]:
        """Get all nodes that feed into the given node."""
        sources = []
        for edge in self.edges:
            if edge.target_id == node_id and not edge.is_clock:
                if edge.source_id in self.nodes:
                    sources.append(self.nodes[edge.source_id])
        return sources

    def get_targets(self, node_id: int) -> list[TopologyNode]:
        """Get all nodes that the given node feeds into."""
        targets = []
        for edge in self.edges:
            if edge.source_id == node_id and not edge.is_clock:
                if edge.target_id in self.nodes:
                    targets.append(self.nodes[edge.target_id])
        return targets


def build_topology(device: USBAudioDevice) -> TopologyGraph:
    """
    Build a topology graph from a USB audio device's AudioControl interface.

    Args:
        device: The parsed USB audio device

    Returns:
        TopologyGraph representing the audio signal flow
    """
    graph = TopologyGraph()

    if not device.audio_control:
        return graph

    ac = device.audio_control

    # Create nodes for all entities
    _add_input_terminals(graph, ac)
    _add_output_terminals(graph, ac)
    _add_feature_units(graph, ac)
    _add_mixer_units(graph, ac)
    _add_selector_units(graph, ac)
    _add_processing_units(graph, ac)
    _add_extension_units(graph, ac)
    _add_clock_entities(graph, ac)

    # Build edges from source IDs
    _build_edges(graph, ac)

    # Find all signal paths
    graph.signal_paths = _find_signal_paths(graph)

    return graph


def _add_input_terminals(graph: TopologyGraph, ac: AudioControlInterface) -> None:
    """Add input terminal nodes to the graph."""
    for terminal in ac.input_terminals:
        node = TopologyNode(
            id=terminal.terminal_id,
            node_type=NodeType.INPUT_TERMINAL,
            name=terminal.terminal_name or get_terminal_type_name(terminal.terminal_type),
            description=get_terminal_type_name(terminal.terminal_type),
            channels=terminal.nr_channels,
            entity=terminal,
            is_usb_streaming=terminal.is_usb_streaming,
        )
        graph.nodes[terminal.terminal_id] = node
        graph.input_terminals.append(node)

        if terminal.is_usb_streaming:
            # USB streaming input terminal = host OUT to device (playback)
            graph.usb_input_terminals.append(node)


def _add_output_terminals(graph: TopologyGraph, ac: AudioControlInterface) -> None:
    """Add output terminal nodes to the graph."""
    for terminal in ac.output_terminals:
        node = TopologyNode(
            id=terminal.terminal_id,
            node_type=NodeType.OUTPUT_TERMINAL,
            name=terminal.terminal_name or get_terminal_type_name(terminal.terminal_type),
            description=get_terminal_type_name(terminal.terminal_type),
            channels=0,  # Output terminals don't specify channels directly
            entity=terminal,
            is_usb_streaming=terminal.is_usb_streaming,
        )
        graph.nodes[terminal.terminal_id] = node
        graph.output_terminals.append(node)

        if terminal.is_usb_streaming:
            # USB streaming output terminal = device to host IN (capture)
            graph.usb_output_terminals.append(node)


def _add_feature_units(graph: TopologyGraph, ac: AudioControlInterface) -> None:
    """Add feature unit nodes to the graph."""
    for unit in ac.feature_units:
        node = TopologyNode(
            id=unit.unit_id,
            node_type=NodeType.FEATURE_UNIT,
            name=unit.unit_name or f"Feature Unit {unit.unit_id}",
            description="Feature Unit",
            channels=unit.nr_channels,
            entity=unit,
            controls=unit.get_control_names(),
        )
        graph.nodes[unit.unit_id] = node
        graph.units.append(node)


def _add_mixer_units(graph: TopologyGraph, ac: AudioControlInterface) -> None:
    """Add mixer unit nodes to the graph."""
    for unit in ac.mixer_units:
        node = TopologyNode(
            id=unit.unit_id,
            node_type=NodeType.MIXER_UNIT,
            name=unit.unit_name or f"Mixer Unit {unit.unit_id}",
            description=f"Mixer ({unit.nr_in_pins} inputs)",
            channels=unit.nr_channels,
            entity=unit,
        )
        graph.nodes[unit.unit_id] = node
        graph.units.append(node)


def _add_selector_units(graph: TopologyGraph, ac: AudioControlInterface) -> None:
    """Add selector unit nodes to the graph."""
    for unit in ac.selector_units:
        node = TopologyNode(
            id=unit.unit_id,
            node_type=NodeType.SELECTOR_UNIT,
            name=unit.selector_name or f"Selector Unit {unit.unit_id}",
            description=f"Selector ({unit.nr_in_pins} inputs)",
            channels=0,
            entity=unit,
        )
        graph.nodes[unit.unit_id] = node
        graph.units.append(node)


def _add_processing_units(graph: TopologyGraph, ac: AudioControlInterface) -> None:
    """Add processing unit nodes to the graph."""
    process_types = {
        0x00: "Undefined",
        0x01: "Up/Downmix",
        0x02: "Dolby Prologic",
        0x03: "Stereo Extender",
    }
    for unit in ac.processing_units:
        process_name = process_types.get(unit.process_type, f"Process 0x{unit.process_type:02X}")
        node = TopologyNode(
            id=unit.unit_id,
            node_type=NodeType.PROCESSING_UNIT,
            name=unit.unit_name or f"Processing Unit {unit.unit_id}",
            description=process_name,
            channels=unit.nr_channels,
            entity=unit,
        )
        graph.nodes[unit.unit_id] = node
        graph.units.append(node)


def _add_extension_units(graph: TopologyGraph, ac: AudioControlInterface) -> None:
    """Add extension unit nodes to the graph."""
    for unit in ac.extension_units:
        node = TopologyNode(
            id=unit.unit_id,
            node_type=NodeType.EXTENSION_UNIT,
            name=unit.unit_name or f"Extension Unit {unit.unit_id}",
            description=f"Extension (0x{unit.extension_code:04X})",
            channels=unit.nr_channels,
            entity=unit,
        )
        graph.nodes[unit.unit_id] = node
        graph.units.append(node)


def _add_clock_entities(graph: TopologyGraph, ac: AudioControlInterface) -> None:
    """Add clock entity nodes to the graph (UAC 2.0)."""
    for clock in ac.clock_sources:
        node = TopologyNode(
            id=clock.clock_id,
            node_type=NodeType.CLOCK_SOURCE,
            name=clock.clock_source_name or f"Clock Source {clock.clock_id}",
            description=clock.clock_type,
            entity=clock,
        )
        graph.nodes[clock.clock_id] = node
        graph.clock_entities.append(node)

    for clock in ac.clock_selectors:
        node = TopologyNode(
            id=clock.clock_id,
            node_type=NodeType.CLOCK_SELECTOR,
            name=clock.clock_selector_name or f"Clock Selector {clock.clock_id}",
            description=f"Clock Selector ({clock.nr_in_pins} inputs)",
            entity=clock,
        )
        graph.nodes[clock.clock_id] = node
        graph.clock_entities.append(node)

    for clock in ac.clock_multipliers:
        node = TopologyNode(
            id=clock.clock_id,
            node_type=NodeType.CLOCK_MULTIPLIER,
            name=clock.clock_multiplier_name or f"Clock Multiplier {clock.clock_id}",
            description="Clock Multiplier",
            entity=clock,
        )
        graph.nodes[clock.clock_id] = node
        graph.clock_entities.append(node)


def _build_edges(graph: TopologyGraph, ac: AudioControlInterface) -> None:
    """Build edges from source ID references in entities."""
    # Output terminals have a source_id
    for terminal in ac.output_terminals:
        if terminal.source_id and terminal.source_id in graph.nodes:
            source_node = graph.nodes.get(terminal.source_id)
            edge = TopologyEdge(
                source_id=terminal.source_id,
                target_id=terminal.terminal_id,
                channels=source_node.channels if source_node else 0,
            )
            graph.edges.append(edge)

    # Feature units have a source_id
    for unit in ac.feature_units:
        if unit.source_id and unit.source_id in graph.nodes:
            source_node = graph.nodes.get(unit.source_id)
            edge = TopologyEdge(
                source_id=unit.source_id,
                target_id=unit.unit_id,
                channels=source_node.channels if source_node else 0,
            )
            graph.edges.append(edge)

    # Mixer units have multiple source_ids
    for unit in ac.mixer_units:
        for source_id in unit.source_ids:
            if source_id in graph.nodes:
                source_node = graph.nodes.get(source_id)
                edge = TopologyEdge(
                    source_id=source_id,
                    target_id=unit.unit_id,
                    channels=source_node.channels if source_node else 0,
                )
                graph.edges.append(edge)

    # Selector units have multiple source_ids
    for unit in ac.selector_units:
        for source_id in unit.source_ids:
            if source_id in graph.nodes:
                source_node = graph.nodes.get(source_id)
                edge = TopologyEdge(
                    source_id=source_id,
                    target_id=unit.unit_id,
                    channels=source_node.channels if source_node else 0,
                )
                graph.edges.append(edge)

    # Processing units have multiple source_ids
    for unit in ac.processing_units:
        for source_id in unit.source_ids:
            if source_id in graph.nodes:
                source_node = graph.nodes.get(source_id)
                edge = TopologyEdge(
                    source_id=source_id,
                    target_id=unit.unit_id,
                    channels=source_node.channels if source_node else 0,
                )
                graph.edges.append(edge)

    # Extension units have multiple source_ids
    for unit in ac.extension_units:
        for source_id in unit.source_ids:
            if source_id in graph.nodes:
                source_node = graph.nodes.get(source_id)
                edge = TopologyEdge(
                    source_id=source_id,
                    target_id=unit.unit_id,
                    channels=source_node.channels if source_node else 0,
                )
                graph.edges.append(edge)

    # Clock selector has clock source inputs
    for clock in ac.clock_selectors:
        for source_id in clock.clock_pin_ids:
            if source_id in graph.nodes:
                edge = TopologyEdge(
                    source_id=source_id,
                    target_id=clock.clock_id,
                    is_clock=True,
                )
                graph.edges.append(edge)

    # Clock multiplier has a clock source input
    for clock in ac.clock_multipliers:
        if clock.clock_source_id and clock.clock_source_id in graph.nodes:
            edge = TopologyEdge(
                source_id=clock.clock_source_id,
                target_id=clock.clock_id,
                is_clock=True,
            )
            graph.edges.append(edge)


def _find_signal_paths(graph: TopologyGraph) -> list[SignalPath]:
    """Find all signal paths from input terminals to output terminals."""
    paths = []

    for output_terminal in graph.output_terminals:
        # Trace back from each output terminal
        found_paths = _trace_back(graph, output_terminal.id, [], set())
        for node_ids in found_paths:
            nodes = [graph.nodes[nid] for nid in node_ids if nid in graph.nodes]
            if nodes:
                path = SignalPath(nodes=nodes)
                path.description = _describe_path(path)
                paths.append(path)

    return paths


def _trace_back(graph: TopologyGraph, node_id: int, current_path: list[int],
                visited: set[int]) -> list[list[int]]:
    """
    Trace back from a node to find all paths to input terminals.

    Returns list of paths, where each path is a list of node IDs from
    input terminal to output terminal.
    """
    if node_id in visited:
        # Cycle detected
        return []

    visited = visited | {node_id}
    current_path = [node_id] + current_path

    node = graph.nodes.get(node_id)
    if not node:
        return []

    # If this is an input terminal, we've found a complete path
    if node.node_type == NodeType.INPUT_TERMINAL:
        return [current_path]

    # Find all sources of this node
    sources = graph.get_sources(node_id)

    if not sources:
        # Dead end - no sources
        return []

    # Recursively trace back through all sources
    all_paths = []
    for source in sources:
        paths = _trace_back(graph, source.id, current_path, visited)
        all_paths.extend(paths)

    return all_paths


def _describe_path(path: SignalPath) -> str:
    """Generate a text description of a signal path."""
    if not path.nodes:
        return ""

    parts = []
    for node in path.nodes:
        if node.node_type == NodeType.INPUT_TERMINAL:
            parts.append(node.description)
        elif node.node_type == NodeType.OUTPUT_TERMINAL:
            parts.append(node.description)
        elif node.node_type == NodeType.FEATURE_UNIT:
            if node.controls:
                parts.append(f"Feature ({', '.join(node.controls)})")
            else:
                parts.append("Feature")
        elif node.node_type == NodeType.MIXER_UNIT:
            parts.append("Mixer")
        elif node.node_type == NodeType.SELECTOR_UNIT:
            parts.append("Selector")
        elif node.node_type == NodeType.PROCESSING_UNIT:
            parts.append(node.description)
        elif node.node_type == NodeType.EXTENSION_UNIT:
            parts.append("Extension")

    return " -> ".join(parts)


def get_playback_paths(graph: TopologyGraph) -> list[SignalPath]:
    """
    Get signal paths for playback (USB OUT from host to speakers/outputs).

    These are paths that start from USB streaming input terminals.
    """
    return [
        path for path in graph.signal_paths
        if path.input_node and path.input_node.is_usb_streaming
    ]


def get_capture_paths(graph: TopologyGraph) -> list[SignalPath]:
    """
    Get signal paths for capture (microphones/inputs to USB IN to host).

    These are paths that end at USB streaming output terminals.
    """
    return [
        path for path in graph.signal_paths
        if path.output_node and path.output_node.is_usb_streaming
    ]


def get_internal_paths(graph: TopologyGraph) -> list[SignalPath]:
    """
    Get internal signal paths (not involving USB streaming).

    These might be monitoring paths or internal routing.
    """
    return [
        path for path in graph.signal_paths
        if (path.input_node and not path.input_node.is_usb_streaming and
            path.output_node and not path.output_node.is_usb_streaming)
    ]
