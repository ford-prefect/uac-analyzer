"""
Command-line interface for the USB Audio Class Descriptor Analyzer.

Usage:
    uac-analyzer [options] [file]
    lsusb -v | uac-analyzer [options]
"""

import argparse
import sys
from typing import Optional

from .parser import parse_lsusb, ParseError
from .topology import build_topology
from .bandwidth import analyze_bandwidth, format_bandwidth_table
from .render import render_full, render_topology_only, render_report, render_summary


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="uac-analyzer",
        description="Analyze USB Audio Class device descriptors from lsusb -v output.",
        epilog="Example: lsusb -v -d 1234:5678 | uac-analyzer",
    )

    parser.add_argument(
        "file",
        nargs="?",
        help="Input file containing lsusb -v output (default: stdin)",
    )

    parser.add_argument(
        "-f", "--format",
        choices=["full", "topology", "report", "bandwidth", "summary"],
        default="full",
        help="Output format (default: full)",
    )

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress warnings and non-essential output",
    )

    parser.add_argument(
        "-v", "--version",
        action="store_true",
        help="Show version and exit",
    )

    return parser


def read_input(file_path: Optional[str]) -> str:
    """Read input from file or stdin."""
    if file_path:
        try:
            with open(file_path, "r") as f:
                return f.read()
        except FileNotFoundError:
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        except IOError as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Check if stdin has data
        if sys.stdin.isatty():
            print("Error: No input provided. Pipe lsusb -v output or specify a file.",
                  file=sys.stderr)
            print("Usage: lsusb -v | uac-analyzer", file=sys.stderr)
            print("       uac-analyzer input.txt", file=sys.stderr)
            sys.exit(1)
        return sys.stdin.read()


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.version:
        from . import __version__
        print(f"uac-analyzer {__version__}")
        return 0

    # Read input
    text = read_input(args.file)

    if not text.strip():
        print("Error: Empty input", file=sys.stderr)
        return 1

    # Parse the lsusb output
    try:
        device = parse_lsusb(text)
    except ParseError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error parsing input: {e}", file=sys.stderr)
        if not args.quiet:
            import traceback
            traceback.print_exc()
        return 1

    # Check if we found any audio content
    if not device.audio_control and not device.streaming_interfaces:
        if not args.quiet:
            print("Warning: No USB Audio Class descriptors found in input.",
                  file=sys.stderr)
            print("Make sure the input is from a USB audio device.",
                  file=sys.stderr)

    # Generate output based on format
    try:
        if args.format == "full":
            output = render_full(device)
        elif args.format == "topology":
            output = render_topology_only(device)
        elif args.format == "report":
            graph = build_topology(device)
            analysis = analyze_bandwidth(device)
            output = render_report(device, graph, analysis)
        elif args.format == "bandwidth":
            analysis = analyze_bandwidth(device)
            output = format_bandwidth_table(analysis)
        elif args.format == "summary":
            output = render_summary(device)
        else:
            output = render_full(device)

        print(output)

    except Exception as e:
        print(f"Error generating output: {e}", file=sys.stderr)
        if not args.quiet:
            import traceback
            traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
