"""
ASCII topology diagram and report generation.

This module renders USB Audio Class device information as human-readable
ASCII art diagrams and structured text reports.
"""

from collections import defaultdict
from typing import Optional

from .model import (
    USBAudioDevice,
    UACVersion,
    get_terminal_type_name,
)
from .topology import (
    TopologyGraph,
    TopologyNode,
    TopologyEdge,
    NodeType,
    SignalPath,
    get_playback_paths,
    get_capture_paths,
    get_internal_paths,
    build_topology,
)
from .bandwidth import (
    DeviceBandwidthAnalysis,
    analyze_bandwidth,
    format_bandwidth_table,
)


def render_topology(graph: TopologyGraph, width: int = 80) -> str:
    """
    Render the topology graph as a unified ASCII DAG diagram.

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

    # Try unified graph rendering
    playback_paths = get_playback_paths(graph)
    capture_paths = get_capture_paths(graph)
    internal_paths = get_internal_paths(graph)

    if playback_paths or capture_paths or internal_paths:
        lines.extend(_render_unified_graph(graph))
        lines.append("")
        lines.extend(_render_path_legend(graph))
        lines.append("")
    else:
        # No paths found, show raw nodes
        lines.append("ENTITIES")
        lines.append("-" * 40)
        lines.extend(_render_all_nodes(graph))
        lines.append("")

    # Render clock topology if present
    if graph.clock_entities:
        lines.append("CLOCK TOPOLOGY")
        lines.append("-" * 40)
        lines.extend(_render_clock_entities(graph))
        lines.append("")

    return "\n".join(lines)


def _assign_layers(graph: TopologyGraph) -> dict[int, int]:
    """Assign each audio node to a layer using longest-path from sources."""
    # Filter to audio-only edges
    audio_edges = [e for e in graph.edges if not e.is_clock]
    audio_node_ids = set()
    for node in graph.input_terminals + graph.output_terminals + graph.units:
        audio_node_ids.add(node.id)

    # Build adjacency: target -> list of source ids
    predecessors: dict[int, list[int]] = defaultdict(list)
    for edge in audio_edges:
        if edge.source_id in audio_node_ids and edge.target_id in audio_node_ids:
            predecessors[edge.target_id].append(edge.source_id)

    # Source nodes: no incoming audio edges
    sources = [nid for nid in audio_node_ids if not predecessors[nid]]

    # Longest-path BFS
    layers: dict[int, int] = {}
    for nid in sources:
        layers[nid] = 0

    changed = True
    while changed:
        changed = False
        for nid in audio_node_ids:
            preds = [p for p in predecessors[nid] if p in layers]
            if preds:
                new_layer = max(layers[p] for p in preds) + 1
                if nid not in layers or new_layer > layers[nid]:
                    layers[nid] = new_layer
                    changed = True

    # Any remaining nodes (disconnected) get layer 0
    for nid in audio_node_ids:
        if nid not in layers:
            layers[nid] = 0

    return layers


def _order_within_layers(
    graph: TopologyGraph,
    layers: dict[int, int],
    audio_edges: list[TopologyEdge],
) -> list[list[int]]:
    """Order nodes within each layer to minimize edge crossings."""
    # Group nodes by layer
    max_layer = max(layers.values()) if layers else 0
    layer_lists: list[list[int]] = [[] for _ in range(max_layer + 1)]
    for nid, layer in layers.items():
        layer_lists[layer].append(nid)

    # Sort layer 0: USB streaming terminals first, then physical, by ID
    def layer0_key(nid: int) -> tuple[int, int]:
        node = graph.nodes.get(nid)
        if node and node.is_usb_streaming:
            return (0, nid)
        return (1, nid)

    layer_lists[0].sort(key=layer0_key)

    # Build predecessor map from audio edges
    predecessors: dict[int, list[int]] = defaultdict(list)
    for edge in audio_edges:
        if edge.source_id in layers and edge.target_id in layers:
            predecessors[edge.target_id].append(edge.source_id)

    # Barycenter ordering for subsequent layers
    for layer_idx in range(1, max_layer + 1):
        prev_layer = layer_lists[layer_idx - 1]
        # Map from node id to row position in previous layer
        prev_pos = {nid: i for i, nid in enumerate(prev_layer)}

        def barycenter(nid: int) -> float:
            preds = [p for p in predecessors[nid] if p in prev_pos]
            if not preds:
                return float('inf')
            return sum(prev_pos[p] for p in preds) / len(preds)

        layer_lists[layer_idx].sort(key=lambda nid: (barycenter(nid), nid))

    return layer_lists


def _render_unified_graph(graph: TopologyGraph) -> list[str]:
    """Render a unified DAG diagram of the audio topology."""
    layers = _assign_layers(graph)
    audio_edges = [e for e in graph.edges if not e.is_clock]

    # Filter to only nodes that are in layers
    audio_edges = [
        e for e in audio_edges
        if e.source_id in layers and e.target_id in layers
    ]

    layer_order = _order_within_layers(graph, layers, audio_edges)
    return _render_canvas(graph, layer_order, audio_edges)


def _render_canvas(
    graph: TopologyGraph,
    layer_order: list[list[int]],
    edges: list[TopologyEdge],
) -> list[str]:
    """Place boxes on a 2D character canvas and route edges."""
    if not layer_order or not any(layer_order):
        return []

    # Build boxes for each node
    node_boxes: dict[int, list[str]] = {}
    for layer in layer_order:
        for nid in layer:
            node = graph.nodes.get(nid)
            if node:
                node_boxes[nid] = _node_to_box(node)

    # Calculate column widths (max box width per layer)
    col_widths: list[int] = []
    for layer in layer_order:
        w = 0
        for nid in layer:
            if nid in node_boxes:
                box_w = max(len(line) for line in node_boxes[nid])
                w = max(w, box_w)
        col_widths.append(w)

    # Calculate row heights: for each row index, max box height across all layers
    max_rows = max(len(layer) for layer in layer_order) if layer_order else 0
    row_heights: list[int] = []
    for row_idx in range(max_rows):
        h = 0
        for layer in layer_order:
            if row_idx < len(layer):
                nid = layer[row_idx]
                if nid in node_boxes:
                    h = max(h, len(node_boxes[nid]))
        row_heights.append(h)

    # Node grid: nid -> (layer_idx, row_idx)
    node_grid: dict[int, tuple[int, int]] = {}
    for layer_idx, layer in enumerate(layer_order):
        for row_idx, nid in enumerate(layer):
            node_grid[nid] = (layer_idx, row_idx)

    # Classify edges: which need vertical routing in which gap column
    source_edge_map: dict[int, list[TopologyEdge]] = defaultdict(list)
    target_edge_map: dict[int, list[TopologyEdge]] = defaultdict(list)
    for edge in edges:
        source_edge_map[edge.source_id].append(edge)
        target_edge_map[edge.target_id].append(edge)

    # Count vertical segments needed per gap column
    gap_vert_count: dict[int, int] = defaultdict(int)
    for edge in edges:
        if edge.source_id in node_grid and edge.target_id in node_grid:
            _, sr = node_grid[edge.source_id]
            sl, _ = node_grid[edge.source_id]
            _, tr = node_grid[edge.target_id]
            if sr != tr:
                gap_vert_count[sl] += 1

    # Calculate per-gap widths: need room for arrow chars + vertical routing
    gap_widths: list[int] = []
    for i in range(len(col_widths)):
        verts = gap_vert_count.get(i, 0)
        gap_widths.append(max(5, 5 + verts * 2))

    # Pad boxes to row height
    for layer in layer_order:
        for row_idx, nid in enumerate(layer):
            if nid not in node_boxes:
                continue
            box = node_boxes[nid]
            target_h = row_heights[row_idx]
            while len(box) < target_h:
                width = len(box[0]) if box else 12
                box.append(" " * width)

    # Compute X positions for each layer
    layer_x: list[int] = []
    x = 0
    for i, w in enumerate(col_widths):
        layer_x.append(x)
        gw = gap_widths[i] if i < len(gap_widths) else 5
        x += w + gw
    total_width = x

    # Compute Y positions for each row
    row_gap = 2
    row_y: list[int] = []
    y = 0
    for i, h in enumerate(row_heights):
        row_y.append(y)
        y += h + row_gap
    total_height = y - row_gap if row_y else 0

    # Create canvas
    canvas = [[' '] * total_width for _ in range(total_height)]

    # Place boxes on canvas
    node_positions: dict[int, tuple[int, int, int, int]] = {}
    for layer_idx, layer in enumerate(layer_order):
        for row_idx, nid in enumerate(layer):
            if nid not in node_boxes:
                continue
            box = node_boxes[nid]
            bx = layer_x[layer_idx]
            by = row_y[row_idx]
            bw = max(len(line) for line in box)
            bh = len(box)
            node_positions[nid] = (bx, by, bw, bh)

            for line_idx, line in enumerate(box):
                for ch_idx, ch in enumerate(line):
                    cy = by + line_idx
                    cx = bx + ch_idx
                    if 0 <= cy < len(canvas) and 0 <= cx < len(canvas[0]):
                        canvas[cy][cx] = ch

    # Pre-compute connection Y for each edge endpoint
    # For fan-out/fan-in, sort edges so same-row connections get the mid Y
    edge_src_y: dict[tuple[int, int], int] = {}
    edge_tgt_y: dict[tuple[int, int], int] = {}

    for nid, out_edges in source_edge_map.items():
        if nid not in node_grid:
            continue
        _, src_row = node_grid[nid]
        src_mid = row_y[src_row] + (row_heights[src_row] - 1) // 2
        if len(out_edges) == 1:
            edge_src_y[(out_edges[0].source_id, out_edges[0].target_id)] = src_mid
        else:
            # Sort: same-row edges first (they get mid Y)
            same = [e for e in out_edges if e.target_id in node_grid and node_grid[e.target_id][1] == src_row]
            diff = [e for e in out_edges if e.target_id in node_grid and node_grid[e.target_id][1] != src_row]
            ordered = same + diff
            _, by, _, bh = node_positions.get(nid, (0, 0, 0, 4))
            for i, e in enumerate(ordered):
                if i == 0:
                    edge_src_y[(e.source_id, e.target_id)] = src_mid
                else:
                    edge_src_y[(e.source_id, e.target_id)] = by + min(bh - 1, (bh - 1) // 2 + i)

    for nid, in_edges in target_edge_map.items():
        if nid not in node_grid:
            continue
        _, tgt_row = node_grid[nid]
        tgt_mid = row_y[tgt_row] + (row_heights[tgt_row] - 1) // 2
        if len(in_edges) == 1:
            edge_tgt_y[(in_edges[0].source_id, in_edges[0].target_id)] = tgt_mid
        else:
            # Sort: same-row edges first
            same = [e for e in in_edges if e.source_id in node_grid and node_grid[e.source_id][1] == tgt_row]
            diff = [e for e in in_edges if e.source_id in node_grid and node_grid[e.source_id][1] != tgt_row]
            ordered = same + diff
            _, by, _, bh = node_positions.get(nid, (0, 0, 0, 4))
            for i, e in enumerate(ordered):
                if i == 0:
                    edge_tgt_y[(e.source_id, e.target_id)] = tgt_mid
                else:
                    edge_tgt_y[(e.source_id, e.target_id)] = by + min(bh - 1, (bh - 1) // 2 + i)

    # Track next available vert X per gap column
    gap_x_next: dict[int, int] = {}
    for i in range(len(col_widths)):
        gap_x_next[i] = layer_x[i] + col_widths[i] + 2

    # Sort edges: straight (same-row) first, then by crossing distance
    def edge_sort_key(e: TopologyEdge) -> tuple:
        if e.source_id in node_grid and e.target_id in node_grid:
            _, sr = node_grid[e.source_id]
            _, tr = node_grid[e.target_id]
            return (abs(tr - sr), e.source_id, e.target_id)
        return (0, 0, 0)

    sorted_edges = sorted(edges, key=edge_sort_key)

    for edge in sorted_edges:
        src_id = edge.source_id
        tgt_id = edge.target_id
        if src_id not in node_positions or tgt_id not in node_positions:
            continue

        src_x, src_y, src_w, src_h = node_positions[src_id]
        tgt_x, tgt_y, tgt_w, tgt_h = node_positions[tgt_id]
        src_layer = node_grid[src_id][0]
        tgt_layer = node_grid[tgt_id][0]

        arrow_start_x = src_x + src_w
        arrow_end_x = tgt_x - 1

        src_connect_y = edge_src_y.get((src_id, tgt_id), src_y + (src_h - 1) // 2)
        tgt_connect_y = edge_tgt_y.get((src_id, tgt_id), tgt_y + (tgt_h - 1) // 2)

        if src_connect_y == tgt_connect_y and tgt_layer == src_layer + 1:
            # Same row, adjacent layers: straight horizontal arrow
            _draw_horizontal(canvas, src_connect_y, arrow_start_x, arrow_end_x, arrow=True)
        elif src_connect_y == tgt_connect_y and tgt_layer > src_layer + 1:
            # Same row but skip-layer: route through gap columns only
            # Draw horizontal segments through gaps, skipping over intermediate box areas
            _draw_skip_layer_horizontal(
                canvas, src_connect_y, arrow_start_x, arrow_end_x,
                src_layer, tgt_layer, layer_x, col_widths, gap_widths
            )
        else:
            # Different rows: route through gap column after source layer
            vert_x = gap_x_next[src_layer]
            gap_x_next[src_layer] += 2

            # For skip-layer edges, route target horizontal through gaps only
            if tgt_layer > src_layer + 1:
                _draw_horizontal(canvas, src_connect_y, arrow_start_x, vert_x)
                _draw_skip_layer_horizontal(
                    canvas, tgt_connect_y, vert_x, arrow_end_x,
                    src_layer, tgt_layer, layer_x, col_widths, gap_widths
                )
                _draw_vertical(canvas, vert_x, src_connect_y, tgt_connect_y)
            else:
                _draw_horizontal(canvas, src_connect_y, arrow_start_x, vert_x)
                _draw_horizontal(canvas, tgt_connect_y, vert_x, arrow_end_x, arrow=True)
                _draw_vertical(canvas, vert_x, src_connect_y, tgt_connect_y)

    # Convert canvas to strings, trimming trailing whitespace
    result = []
    for row in canvas:
        line = ''.join(row).rstrip()
        result.append(line)

    # Remove trailing empty lines
    while result and not result[-1].strip():
        result.pop()

    # Remove leading empty lines
    while result and not result[0].strip():
        result.pop(0)

    return result


def _draw_skip_layer_horizontal(
    canvas: list[list[str]], y: int, x_start: int, x_end: int,
    src_layer: int, tgt_layer: int,
    layer_x: list[int], col_widths: list[int], gap_widths: list[int],
) -> None:
    """Draw a horizontal line that skips over intermediate layer boxes.

    Only draws in gap regions between layers, not through box columns.
    """
    width = len(canvas[0]) if canvas else 0
    if y < 0 or y >= len(canvas):
        return

    for x in range(min(x_start, x_end), max(x_start, x_end) + 1):
        if x < 0 or x >= width:
            continue

        # Check if x is in a box column (inside a layer's box area)
        in_box = False
        for layer_idx in range(src_layer + 1, tgt_layer):
            lx = layer_x[layer_idx]
            lw = col_widths[layer_idx]
            if lx <= x < lx + lw:
                in_box = True
                break

        if not in_box:
            ch = canvas[y][x]
            if ch in ('│', '┌', '└', '┐', '┘', '┼'):
                pass
            else:
                canvas[y][x] = '─'

    # Arrow at end
    end_x = max(x_start, x_end)
    if 0 <= end_x < width:
        canvas[y][end_x] = '>'


def _draw_horizontal(
    canvas: list[list[str]], y: int, x1: int, x2: int, arrow: bool = False
) -> None:
    """Draw a horizontal line on the canvas from x1 to x2 at row y."""
    if y < 0 or y >= len(canvas):
        return
    width = len(canvas[0]) if canvas else 0
    start = min(x1, x2)
    end = max(x1, x2)
    for x in range(start, end + 1):
        if 0 <= x < width:
            ch = canvas[y][x]
            if ch in ('│', '┌', '└', '┐', '┘', '┼'):
                pass  # Don't overwrite vertical/corner chars
            else:
                canvas[y][x] = '─'
    if arrow and 0 <= end < width:
        canvas[y][end] = '>'


def _draw_vertical(
    canvas: list[list[str]], x: int, y_src: int, y_tgt: int
) -> None:
    """Draw a vertical line from y_src (source side) to y_tgt (target side).

    y_src is where the horizontal FROM the source meets the vertical.
    y_tgt is where the vertical meets the horizontal TO the target.
    The horizontal from source comes from the left into the corner.
    The horizontal to target goes from the corner to the right.
    """
    if x < 0 or (canvas and x >= len(canvas[0])):
        return
    top = min(y_src, y_tgt)
    bottom = max(y_src, y_tgt)

    for y in range(top, bottom + 1):
        if y < 0 or y >= len(canvas):
            continue
        ch = canvas[y][x]

        if y == y_src:
            # Source end: horizontal comes from left, vertical goes up or down
            if ch == '─':
                # Horizontal line already here from source; add corner
                if y_tgt > y_src:
                    canvas[y][x] = '┐'  # going down: ─┐
                else:
                    canvas[y][x] = '┘'  # going up: ─┘
            elif ch not in ('│', '┌', '└', '┐', '┘', '┼'):
                canvas[y][x] = '│'
        elif y == y_tgt:
            # Target end: vertical arrives, horizontal goes right to target
            if ch == '─':
                if y_src < y_tgt:
                    canvas[y][x] = '└'  # came from above: └─
                else:
                    canvas[y][x] = '┌'  # came from below: ┌─
            elif ch not in ('│', '┌', '└', '┐', '┘', '┼'):
                canvas[y][x] = '│'
        else:
            # Middle segment
            if ch == '─':
                canvas[y][x] = '┼'
            elif ch not in ('│', '┌', '└', '┐', '┘', '┼'):
                canvas[y][x] = '│'


def _render_path_legend(graph: TopologyGraph) -> list[str]:
    """Render the path legend below the diagram."""
    lines = []
    lines.append("Paths:")

    playback_paths = get_playback_paths(graph)
    capture_paths = get_capture_paths(graph)
    internal_paths = get_internal_paths(graph)

    def _node_short_name(node: TopologyNode) -> str:
        if node.node_type == NodeType.INPUT_TERMINAL:
            if node.is_usb_streaming:
                return f"USB OUT({node.id})"
            return f"{node.description}({node.id})"
        elif node.node_type == NodeType.OUTPUT_TERMINAL:
            if node.is_usb_streaming:
                return f"USB IN({node.id})"
            return f"{node.description}({node.id})"
        elif node.node_type == NodeType.FEATURE_UNIT:
            return f"Feature({node.id})"
        elif node.node_type == NodeType.MIXER_UNIT:
            return f"Mixer({node.id})"
        elif node.node_type == NodeType.SELECTOR_UNIT:
            return f"Selector({node.id})"
        elif node.node_type == NodeType.PROCESSING_UNIT:
            return f"Process({node.id})"
        elif node.node_type == NodeType.EXTENSION_UNIT:
            return f"Extension({node.id})"
        return f"{node.name}({node.id})"

    for i, path in enumerate(playback_paths, 1):
        chain = " -> ".join(_node_short_name(n) for n in path.nodes)
        label = "Playback" if len(playback_paths) == 1 else f"Playback {i}"
        lines.append(f"  {label}: {chain}")

    for i, path in enumerate(capture_paths, 1):
        chain = " -> ".join(_node_short_name(n) for n in path.nodes)
        label = "Capture" if len(capture_paths) == 1 else f"Capture {i}"
        lines.append(f"  {label}:  {chain}")

    for i, path in enumerate(internal_paths, 1):
        chain = " -> ".join(_node_short_name(n) for n in path.nodes)
        label = "Internal" if len(internal_paths) == 1 else f"Internal {i}"
        lines.append(f"  {label}: {chain}")

    return lines


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

        internal_paths = get_internal_paths(graph)
        if internal_paths:
            lines.append("  Internal:")
            for path in internal_paths:
                if path.input_node and path.output_node:
                    lines.append(f"    {path.input_node.description} -> {path.output_node.description}")

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
