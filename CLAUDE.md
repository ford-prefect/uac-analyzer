# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

USB Audio Class Descriptor Analyzer - A Python tool for parsing and analyzing USB audio device descriptors from `lsusb -v` output. It converts raw USB descriptor information into human-readable formats with topology diagrams, bandwidth analysis, and detailed device capabilities reporting.

## Build and Test Commands

This project uses `uv` for dependency management.

```bash
# Sync dependencies
uv sync

# Run the tool
uv run uac-analyzer <file>              # Analyze from file
cat lsusb_output.txt | uv run uac-analyzer  # Analyze from stdin

# Run tests
uv run pytest tests/                    # Run all tests
uv run pytest tests/test_parser.py      # Run specific test file
uv run pytest tests/ -v                 # Verbose output
uv run pytest tests/ --cov              # With coverage
```

## Architecture

The codebase follows a pipeline architecture:

```
lsusb -v output → Parser → Model Objects → Analysis → Rendering
```

### Module Responsibilities

| Module | Purpose |
|--------|---------|
| `model.py` | Dataclasses for USB Audio Class descriptors (UAC 1.0 and 2.0): terminals, units, clock entities |
| `parser.py` | LsusbParser class - indentation-based tokenization and recursive descent parsing of lsusb output |
| `topology.py` | Signal flow graph construction - traces paths from input terminals through units to output terminals |
| `bandwidth.py` | Bandwidth calculations per alternate setting, format information extraction |
| `render.py` | ASCII diagram generation and formatted text output |
| `cli.py` | Entry point, argument parsing, module orchestration |

### Data Flow

1. `LsusbParser` tokenizes lines with indentation tracking
2. Parser extracts device/configuration/interface/audio descriptors into model objects
3. `build_topology()` creates signal flow graph from parsed descriptors
4. `analyze_bandwidth()` calculates bandwidth per interface
5. `render_*()` functions generate human-readable output

### Key Classes

- `USBAudioDevice` - Top-level container for all parsed device data
- `AudioControlInterface` - Contains audio processing units and terminals
- `TopologyGraph` - Signal flow representation with nodes and edges

## Parser Notes

The parser (`parser.py`) is the most complex module:
- Uses indentation depth as structural information
- Handles BCD version parsing (e.g., "1.00" → 0x0100)
- Supports both UAC 1.0 and UAC 2.0 descriptor structures
- Requires `_advance()` calls after processing each line to prevent infinite loops

## Topology Renderer (`render.py`)

The topology diagram uses a unified DAG layout (simplified Sugiyama) where each audio node appears exactly once:

1. **Layer assignment** (`_assign_layers`): longest-path from source nodes
2. **Row ordering** (`_order_within_layers`): barycenter sort to reduce crossings
3. **Canvas rendering** (`_render_canvas`): 2D character grid with box-drawing edge routing

Edge routing categories:
- **Same-row adjacent**: straight horizontal `────>`
- **Cross-row adjacent**: vertical segment through gap column between layers, with `┐└` corners
- **Skip-layer same-row**: `_draw_skip_layer_horizontal` — draws `─` only in gap regions, skipping intermediate box columns (with 1-char margin)
- **Skip-layer cross-row**: 5-segment path through the inter-row gap — avoids routing through intermediate boxes entirely. Inter-row gaps expand dynamically to accommodate these routing lines.

Fan-out/fan-in: edges from the same node are sorted so same-row connections get the midpoint Y; cross-row connections get offset Y positions.

### Known visual artifacts
- Adjacent-layer cross-row verticals can produce `┌─┐` or `┼` where they cross a straight horizontal from the same source node (e.g. Anker dongle USB OUT line). Correct but slightly cluttered.

## Test Fixtures

Sample device outputs for testing are in `tests/fixtures/`:
- `uac1_stereo_headset.txt` - UAC 1.0 simple headset (2 independent chains)
- `uac2_audio_interface.txt` - UAC 2.0 audio interface with clock entities
- `apple-dongle.txt` - UAC 2.0, shared nodes (Mixer/FU in both playback and sidetone)
- `anker-dongle.txt` - UAC 1.0, mixer with internal monitoring path
- `smsl-d6s.txt` - UAC 2.0, playback-only DAC with clock selector
- `steelseries-arctis7.txt` - UAC 1.0, dual playback (game + chat) + capture
- `sennheiser-gsx120.txt` - UAC 1.0, dual playback + capture with selector unit
- `jbl-quantum-810wireless.txt` - UAC 1.0, dual playback + capture with selector unit
