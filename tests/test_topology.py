"""Tests for topology graph analysis."""

import pytest
from pathlib import Path

from uac_analyzer.parser import parse_lsusb
from uac_analyzer.topology import (
    build_topology,
    TopologyGraph,
    NodeType,
    get_playback_paths,
    get_capture_paths,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestTopologyBuilding:
    """Tests for building topology graphs."""

    @pytest.fixture
    def uac1_graph(self):
        """Build topology from UAC 1.0 headset fixture."""
        fixture_path = FIXTURES_DIR / "uac1_stereo_headset.txt"
        with open(fixture_path) as f:
            device = parse_lsusb(f.read())
        return build_topology(device)

    @pytest.fixture
    def uac2_graph(self):
        """Build topology from UAC 2.0 audio interface fixture."""
        fixture_path = FIXTURES_DIR / "uac2_audio_interface.txt"
        with open(fixture_path) as f:
            device = parse_lsusb(f.read())
        return build_topology(device)

    def test_nodes_created(self, uac1_graph):
        """Test that all nodes are created."""
        # Should have 2 input terminals, 2 output terminals, 2 feature units
        assert len(uac1_graph.nodes) == 6
        assert len(uac1_graph.input_terminals) == 2
        assert len(uac1_graph.output_terminals) == 2
        assert len(uac1_graph.units) == 2

    def test_edges_created(self, uac1_graph):
        """Test that edges are created from source IDs."""
        # Feature unit 5 <- Input terminal 1
        # Feature unit 4 <- Input terminal 2
        # Output terminal 6 <- Feature unit 5
        # Output terminal 7 <- Feature unit 4
        assert len(uac1_graph.edges) == 4

    def test_usb_streaming_terminals(self, uac1_graph):
        """Test USB streaming terminal identification."""
        assert len(uac1_graph.usb_input_terminals) == 1  # USB OUT (playback)
        assert len(uac1_graph.usb_output_terminals) == 1  # USB IN (capture)

        usb_in = uac1_graph.usb_input_terminals[0]
        assert usb_in.is_usb_streaming
        assert usb_in.id == 1  # Terminal ID 1

        usb_out = uac1_graph.usb_output_terminals[0]
        assert usb_out.is_usb_streaming
        assert usb_out.id == 7  # Terminal ID 7

    def test_node_types(self, uac1_graph):
        """Test node type assignments."""
        for node in uac1_graph.input_terminals:
            assert node.node_type == NodeType.INPUT_TERMINAL

        for node in uac1_graph.output_terminals:
            assert node.node_type == NodeType.OUTPUT_TERMINAL

        for node in uac1_graph.units:
            assert node.node_type == NodeType.FEATURE_UNIT


class TestSignalPaths:
    """Tests for signal path tracing."""

    @pytest.fixture
    def uac1_graph(self):
        """Build topology from UAC 1.0 headset fixture."""
        fixture_path = FIXTURES_DIR / "uac1_stereo_headset.txt"
        with open(fixture_path) as f:
            device = parse_lsusb(f.read())
        return build_topology(device)

    def test_signal_paths_found(self, uac1_graph):
        """Test that signal paths are traced."""
        assert len(uac1_graph.signal_paths) == 2  # Playback and capture

    def test_playback_path(self, uac1_graph):
        """Test playback path tracing."""
        playback_paths = get_playback_paths(uac1_graph)
        assert len(playback_paths) == 1

        path = playback_paths[0]
        # Should be: USB Streaming (1) -> Feature Unit (5) -> Speaker (6)
        assert len(path.nodes) == 3
        assert path.nodes[0].id == 1  # USB streaming input
        assert path.nodes[1].id == 5  # Feature unit
        assert path.nodes[2].id == 6  # Speaker output

        assert path.input_node.is_usb_streaming
        assert not path.output_node.is_usb_streaming

    def test_capture_path(self, uac1_graph):
        """Test capture path tracing."""
        capture_paths = get_capture_paths(uac1_graph)
        assert len(capture_paths) == 1

        path = capture_paths[0]
        # Should be: Microphone (2) -> Feature Unit (4) -> USB Streaming (7)
        assert len(path.nodes) == 3
        assert path.nodes[0].id == 2  # Microphone input
        assert path.nodes[1].id == 4  # Feature unit
        assert path.nodes[2].id == 7  # USB streaming output

        assert not path.input_node.is_usb_streaming
        assert path.output_node.is_usb_streaming

    def test_path_description(self, uac1_graph):
        """Test path description generation."""
        playback_paths = get_playback_paths(uac1_graph)
        path = playback_paths[0]

        # Description should include the components
        desc = path.description
        assert "USB Streaming" in desc
        assert "Feature" in desc
        assert "Speaker" in desc


class TestUAC2Topology:
    """Tests specific to UAC 2.0 topology."""

    @pytest.fixture
    def uac2_graph(self):
        """Build topology from UAC 2.0 audio interface fixture."""
        fixture_path = FIXTURES_DIR / "uac2_audio_interface.txt"
        with open(fixture_path) as f:
            device = parse_lsusb(f.read())
        return build_topology(device)

    def test_clock_entities(self, uac2_graph):
        """Test clock entity handling."""
        assert len(uac2_graph.clock_entities) == 1

        clock = uac2_graph.clock_entities[0]
        assert clock.node_type == NodeType.CLOCK_SOURCE
        assert clock.id == 41

    def test_uac2_paths(self, uac2_graph):
        """Test UAC 2.0 signal paths."""
        playback_paths = get_playback_paths(uac2_graph)
        capture_paths = get_capture_paths(uac2_graph)

        assert len(playback_paths) == 1
        assert len(capture_paths) == 1

    def test_feature_unit_controls(self, uac2_graph):
        """Test feature unit control extraction."""
        feature_units = [n for n in uac2_graph.units
                         if n.node_type == NodeType.FEATURE_UNIT]
        assert len(feature_units) == 2

        for fu in feature_units:
            assert "Mute" in fu.controls
            assert "Volume" in fu.controls


class TestGraphQueries:
    """Tests for graph query methods."""

    @pytest.fixture
    def uac1_graph(self):
        """Build topology from UAC 1.0 headset fixture."""
        fixture_path = FIXTURES_DIR / "uac1_stereo_headset.txt"
        with open(fixture_path) as f:
            device = parse_lsusb(f.read())
        return build_topology(device)

    def test_get_node(self, uac1_graph):
        """Test node lookup by ID."""
        node = uac1_graph.get_node(1)
        assert node is not None
        assert node.id == 1
        assert node.node_type == NodeType.INPUT_TERMINAL

        # Non-existent node
        assert uac1_graph.get_node(999) is None

    def test_get_sources(self, uac1_graph):
        """Test getting source nodes."""
        # Feature unit 5 should have USB streaming terminal 1 as source
        sources = uac1_graph.get_sources(5)
        assert len(sources) == 1
        assert sources[0].id == 1

        # Input terminal has no sources
        sources = uac1_graph.get_sources(1)
        assert len(sources) == 0

    def test_get_targets(self, uac1_graph):
        """Test getting target nodes."""
        # Feature unit 5 should feed into output terminal 6
        targets = uac1_graph.get_targets(5)
        assert len(targets) == 1
        assert targets[0].id == 6

        # Output terminal has no targets
        targets = uac1_graph.get_targets(6)
        assert len(targets) == 0


class TestEmptyTopology:
    """Tests for empty or minimal topology cases."""

    def test_empty_device(self):
        """Test topology of device with no audio control."""
        device = parse_lsusb("")
        graph = build_topology(device)

        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0
        assert len(graph.signal_paths) == 0

    def test_header_only_device(self):
        """Test topology of device with only AC header."""
        text = """
Bus 001 Device 002: ID 0123:4567 Some Company
Device Descriptor:
  bLength                18
  bDescriptorType         1
  bNumConfigurations      1
  Configuration Descriptor:
    Interface Descriptor:
      bInterfaceClass         1 Audio
      bInterfaceSubClass      1 Control Device
      AudioControl Interface Descriptor:
        bDescriptorSubtype      1 (HEADER)
        bcdADC               1.00
        """
        device = parse_lsusb(text)
        graph = build_topology(device)

        assert len(graph.nodes) == 0
        assert len(graph.signal_paths) == 0
