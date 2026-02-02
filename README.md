# uac-analyzer

A tool to parse the output of `lsusb -v` for USB Audio Class 1.0 and 2.0
devices, and print a more human readable version of the output.

*Caveat emptor: This tool was built primarily using LLM tools, with some human
oversight, and is still very much a work in progress.*

## Usage

The tool uses [uv](https://github.com/astral-sh/uv), so to run the tool:

```sh
$ lsusb -v <vid>:<pid> | uv run uac-analyzer
```

## Example

This is the output for the Apple USB-C to 3.5mm dongle.


```
================================================================================
AUDIO TOPOLOGY
================================================================================

PLAYBACK PATHS (Host -> Device)
----------------------------------------
Path 1:
  +-------------+     +------------------+     +--------------+     +----------+
  |   USB OUT   |     |      Mixer       |     |   Feature    |     | Headset  |
  | (from host) | --> | Mixer (2 inputs) | --> | Mute, Volume | --> +----------+
  +-------------+     +------------------+     +--------------+                 

CAPTURE PATHS (Device -> Host)
----------------------------------------
Path 1:
  +----------+     +--------------+     +-----------+
  | Headset  |     |   Feature    |     |   USB IN  |
  |   1ch    | --> | Mute, Volume | --> | (to host) |
  +----------+     +--------------+     +-----------+

CLOCK TOPOLOGY
----------------------------------------
  [Clock Source 9] Clock Source 9
    Type: Internal Programmable
  [Clock Source 10] Clock Source 10
    Type: Internal Programmable

================================================================================
USB AUDIO DEVICE REPORT
================================================================================

DEVICE SUMMARY
----------------------------------------
  Product:      USB-C to 3.5mm Headphone Jack Adapter
  Manufacturer: Apple, Inc.
  VID:PID:      05AC:110A
  USB Version:  2.01
  UAC Version:  2.0
  Note: Device also supports UAC 3.0. Use --uac-version to select. (UAC 3.0 support is incomplete)

SIGNAL FLOW SUMMARY
----------------------------------------
  Playback:
    -> Headset
  Capture:
    <- Headset

INPUT TERMINALS
----------------------------------------
  ID 1: USB Streaming (2ch) [USB]
  ID 4: Headset (1ch)

OUTPUT TERMINALS
----------------------------------------
  ID 3: Headset
  ID 6: USB Streaming [USB]

PROCESSING UNITS
----------------------------------------
  ID 2: Feature Unit - Controls: Mute, Volume
  ID 5: Feature Unit - Controls: Mute, Volume
  ID 7: Feature Unit - Controls: Mute, Volume
  ID 8: Mixer Unit

CLOCK ENTITIES (UAC 2.0)
----------------------------------------
  ID 9: Clock Source - Internal Programmable
  ID 10: Clock Source - Internal Programmable

STREAMING INTERFACES
----------------------------------------
  Interface 1: Playback
    Terminal: USB Streaming
    Formats:
      - 2ch 24-bit PCM @ Unknown
      - 2ch 16-bit PCM @ Unknown

  Interface 2: Capture
    Terminal: USB Streaming
    Formats:
      - 1ch 16-bit PCM @ Unknown
      - 1ch 24-bit PCM @ Unknown

=====================================================================================
STREAMING INTERFACES AND BANDWIDTH
=====================================================================================

Interface 1: Playback
  Terminal: USB Streaming (ID 1)
-------------------------------------------------------------------------------------
 Alt | Format                    | Sample Rate          | Sync         | Bandwidth   
-------------------------------------------------------------------------------------
   1 | 2ch 24-bit PCM            | Unknown              | Synchronous  | 2.30 MB/s   
   2 | 2ch 16-bit PCM            | Unknown              | Synchronous  | 1.54 MB/s   

Interface 2: Capture
  Terminal: USB Streaming (ID 6)
-------------------------------------------------------------------------------------
 Alt | Format                    | Sample Rate          | Sync         | Bandwidth   
-------------------------------------------------------------------------------------
   1 | 1ch 16-bit PCM            | Unknown              | Synchronous  | 768.0 KB/s  
   2 | 1ch 24-bit PCM            | Unknown              | Synchronous  | 1.15 MB/s   

=====================================================================================
BANDWIDTH SUMMARY
-------------------------------------------------------------------------------------
Max Playback Bandwidth: 2.30 MB/s
Max Capture Bandwidth:  1.15 MB/s
Max Total Bandwidth:    3.46 MB/s
```
