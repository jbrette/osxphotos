"""Auto-update the installed version"""

from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
import urllib.request
from collections.abc import Iterable

from packaging.version import parse as version_parse
from uv import find_uv_bin

VERSION_INFO_URL = "https://pypi.org/pypi/{}/json"


def pyapp() -> bool:
    """Check if we are running in a pyapp environment."""
    return os.environ.get("PYAPP") == "1"


def uv_pip(args: Iterable[str]) -> int:
    """Run a `uv pip` subcommand against the Python environment osxphotos is running in.

    Args:
        args: The `uv pip` subcommand and its arguments, e.g. ["install", "requests"].

    Returns: The exit code of the uv command.
    """
    command = [find_uv_bin(), "pip", *args, "--python", sys.executable]
    return subprocess.run(command, check=False).returncode


def install(packages: Iterable[str], upgrade: bool = False) -> int:
    """Install Python packages into the same environment as the current script using uv.

    Args:
        packages: The names of the packages to install.
        upgrade: Whether to upgrade the packages if they are already installed.

    Returns: The exit code of the uv command.
    """
    args = ["install"]
    if upgrade:
        args += ["--upgrade"]
    args += list(packages)
    return uv_pip(args)


def update(package: str, version: str, pyapp_binary: str) -> None:
    """Update the installation to the latest version.

    Args:
        package: The name of the package to update.
        version: The current version of the package.
        pyapp_binary: The name of the package binary built with PyApp to use for updating.

    Note:
        Updating PyApp package requires the pyapp_binary to be available in the PATH.
        This will work for most users but may fail if the binary is not in the path and
        was instead invoked using an absolute path, e.g. /path/to/pyapp_binary.
        I am not aware of a way to get the absolute path of the binary from the package
        itself as the PyApp binary will execute python, replacing the current process.
    """
    if pyapp():
        # let pyapp handle the update
        command = [pyapp_binary, "self", "update"]
        subprocess.run(command, check=True)
        return
    else:
        # otherwise let's update in place
        # check if there is a newer version of the package
        latest_version = get_latest_version(package)
        if version_parse(latest_version) > version_parse(version):
            print(f"Updating from version {version} to {latest_version}.")
            install([package], upgrade=True)
            print(f"Updated {package} to version {latest_version}.")
        else:
            print(f"{package} is already up to date: {version}.")


def get_latest_version(package_name: str) -> str:
    """Get latest version of package_name from PyPI

    Note: This uses the standard library instead of 'requests'
    to avoid adding a dependency to the project.
    """
    try:
        url = VERSION_INFO_URL.format(package_name)
        ssl_context = ssl._create_unverified_context()
        response = urllib.request.urlopen(url, context=ssl_context)
        data = json.load(response)
        return data["info"]["version"]
    except Exception as e:
        raise ValueError(f"Error retrieving version for {package_name}: {e}") from e
