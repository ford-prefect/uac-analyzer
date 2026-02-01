"""
USB Audio Class Descriptor Analyzer

A Python tool to parse USB Audio Class device descriptors from lsusb -v output
and present them in a human-understandable format.
"""

__version__ = "0.1.0"

from .model import (
    UACVersion,
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
    USBAudioDevice,
)
from .parser import parse_lsusb
from .topology import build_topology, TopologyGraph
from .bandwidth import analyze_bandwidth, BandwidthInfo
from .render import render_topology, render_report, render_full

__all__ = [
    "UACVersion",
    "DeviceDescriptor",
    "ConfigurationDescriptor",
    "InterfaceDescriptor",
    "EndpointDescriptor",
    "AudioControlHeader",
    "InputTerminal",
    "OutputTerminal",
    "FeatureUnit",
    "MixerUnit",
    "SelectorUnit",
    "ProcessingUnit",
    "ExtensionUnit",
    "ClockSource",
    "ClockSelector",
    "ClockMultiplier",
    "AudioStreamingInterface",
    "FormatTypeDescriptor",
    "USBAudioDevice",
    "parse_lsusb",
    "build_topology",
    "TopologyGraph",
    "analyze_bandwidth",
    "BandwidthInfo",
    "render_topology",
    "render_report",
    "render_full",
]
