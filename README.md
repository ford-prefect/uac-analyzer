# uac-analyzer

A tool to parse the output of `lsusb -v` for USB Audio Class 1.0 and 2.0
devices, and print a more human readable version of the output.

*Caveat emptor: This tool was built primarily using LLM tools, with some human
oversight, and is still very much a work in progress.*

# Usage

The tool uses [uv](https://github.com/astral-sh/uv), so to run the tool:

```sh
$ lsusb -v <vid>:<pid> | uv run uac-analyzer
```
