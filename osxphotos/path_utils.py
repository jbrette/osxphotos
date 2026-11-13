"""utility functions for validating/sanitizing path components

This module also performs Unicode normalization. For a quick summary, there are
multiple ways to write more complex characters in Unicode. This causes problems
when e.g. checking if a file already exists and you have multiple sources for
the same string with different encodings. This sadly happens in Photos, but
isn't a problem on macOS, since macOS does normalization behind-the-scenes (see
https://eclecticlight.co/2021/05/08/explainer-unicode-normalization-and-apfs/).
This causes problems on other platforms, so we normalize as part of filename
sanitization functions and rely on them being called every time a unique
filename is needed.
"""

import pathlib

import pathvalidate

from osxphotos.unicode import normalize_unicode

from ._constants import MAX_DIRNAME_LEN, MAX_FILENAME_LEN

__all__ = [
    "is_valid_filepath",
    "sanitize_dirname",
    "sanitize_filename",
    "sanitize_filepath",
    "sanitize_pathpart",
]


def sanitize_filepath[PathT: (str, pathlib.Path)](filepath: PathT) -> PathT:
    """sanitize a filepath"""
    return pathvalidate.sanitize_filepath(filepath, platform="macos")


def is_valid_filepath[PathT: (str, pathlib.Path)](filepath: PathT) -> bool:
    """returns True if a filepath is valid otherwise False"""
    return pathvalidate.is_valid_filepath(filepath, platform="macos")


def sanitize_filename[NameT: (str, None)](
    filename: NameT, replacement: str = ":"
) -> NameT:
    """replace any illegal characters in a filename, truncate filename if needed and normalize Unicode to NFC form

    Args:
        filename: str, filename to sanitze
        replacement: str, value to replace any illegal characters with; default = ":"

    Returns:
        filename with any illegal characters replaced by replacement and truncated if necessary
    """

    if filename:
        filename = normalize_unicode(filename)
        filename = filename.replace("/", replacement)
        if len(filename) > MAX_FILENAME_LEN:
            parts = filename.split(".")
            drop = len(filename) - MAX_FILENAME_LEN
            if len(parts) > 1:
                # has an extension
                ext = parts.pop(-1)
                stem = ".".join(parts)
                if drop > len(stem):
                    ext = ext[:-drop]
                else:
                    stem = stem[:-drop]
                filename = f"{stem}.{ext}"
            else:
                filename = filename[:-drop]
    return filename


def sanitize_dirname[NameT: (str, None)](
    dirname: NameT, replacement: str | None = ":"
) -> NameT:
    """replace any illegal characters in a directory name, truncate directory name if needed, and normalize Unicode to NFC form

    Args:
        dirname: str, directory name to sanitize
        replacement: str, value to replace any illegal characters with; default = ":"; if None, no replacement occurs

    Returns:
        dirname with any illegal characters replaced by replacement and truncated if necessary
    """
    if dirname:
        dirname = sanitize_pathpart(dirname, replacement=replacement)
    return dirname


def sanitize_pathpart[NameT: (str, None)](
    pathpart: NameT, replacement: str | None = ":"
) -> NameT:
    """replace any illegal characters in a path part (either directory or filename without extension), truncate name if needed, and normalize Unicode to NFC form

    Args:
        pathpart: str, path part to sanitize
        replacement: str, value to replace any illegal characters with; default = ":"; if None, no replacement occurs

    Returns:
        pathpart with any illegal characters replaced by replacement and truncated if necessary
    """
    if pathpart:
        pathpart = (
            pathpart.replace("/", replacement) if replacement is not None else pathpart
        )
        pathpart = normalize_unicode(pathpart)
        if len(pathpart) > MAX_DIRNAME_LEN:
            drop = len(pathpart) - MAX_DIRNAME_LEN
            pathpart = pathpart[:-drop]
    return pathpart
