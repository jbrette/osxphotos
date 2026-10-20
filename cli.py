"""stand alone command line script for use with pyinstaller

To build this into an executable:
- install the dev dependencies (includes pyinstaller): uv sync
- then use make_cli_exe.sh to run pyinstaller

Resulting executable will be in "dist/osxphotos"

Note: This is *not* the cli that installing the osxphotos package would install;
it's merely a wrapper around __main__.py to allow pyinstaller to work

"""

from osxphotos.cli.cli import cli_main

if __name__ == "__main__":
    cli_main()
