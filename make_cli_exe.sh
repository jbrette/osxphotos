#!/bin/sh

# This will build an stand-alone executable called 'osxphotos' in your ./dist directory
# using pyinstaller
# pyinstaller is installed with the dev dependency group (uv sync)

set -e
uv run pyinstaller osxphotos.spec
