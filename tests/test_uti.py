"""test uti.py"""

import logging

import pytest

import osxphotos.uti
from osxphotos.platform import is_macos
from osxphotos.uti import (
    _get_uti_from_mdls,
    get_preferred_uti_extension,
    get_uti_for_extension,
)

EXT_DICT = {"heic": "public.heic", "jpg": "public.jpeg", ".jpg": "public.jpeg"}
UTI_DICT = {"public.heic": "heic", "public.jpeg": "jpeg"}


def test_get_preferred_uti_extension():
    """test get_preferred_uti_extension"""
    for uti, value in UTI_DICT.items():
        assert get_preferred_uti_extension(uti) == value


def test_get_preferred_uti_extension_unknown(caplog):
    """test get_preferred_uti_extension for unknown UTI #1643"""
    caplog.set_level(logging.WARNING)
    assert get_preferred_uti_extension("com.OSXPHOTOS.UNKNOWN.FOOBAR") == ""
    assert "Could not determine extension for UTI" in caplog.text


def test_get_uti_for_extension():
    """get get_uti_for_extension"""
    for ext, value in EXT_DICT.items():
        assert get_uti_for_extension(ext) == value


def test_get_preferred_uti_extension_no_objc():
    """test get_preferred_uti_extension when running on macOS >= 12"""
    old_ver = osxphotos.uti.OS_VER
    osxphotos.uti.OS_VER = 12
    for uti, value in UTI_DICT.items():
        assert get_preferred_uti_extension(uti) == value
    osxphotos.uti.OS_VER = old_ver


def test_get_uti_for_extension_no_objc():
    """get get_uti_for_extension when running on macOS >= 12"""
    old_ver = osxphotos.uti.OS_VER
    osxphotos.uti.OS_VER = 12
    for ext, value in EXT_DICT.items():
        assert get_uti_for_extension(ext) == value
    osxphotos.uti.OS_VER = old_ver


def test_get_uti_for_path():
    """test get_uti_for_path"""
    for ext, value in EXT_DICT.items():
        assert osxphotos.uti.get_uti_for_path(f"test.{ext}") == value


@pytest.mark.skipif(not is_macos, reason="Only works on macOS")
def test_get_uti_from_mdls():
    """get _get_uti_from_mdls"""
    for ext, value in EXT_DICT.items():
        assert _get_uti_from_mdls(ext) == value


@pytest.mark.skipif(not is_macos, reason="Only works on macOS")
def test_get_uti_not_in_dict():
    """get UTI when objc is not available and it's not in the EXT_UTI_DICT"""
    # monkey patch the EXT_UTI_DICT
    old_ver = osxphotos.uti.OS_VER
    osxphotos.uti.OS_VER = 12
    osxphotos.uti.EXT_UTI_DICT = {}
    osxphotos.uti.UTI_EXT_DICT = {}
    for ext, value in EXT_DICT.items():
        assert get_uti_for_extension(ext) == value
    osxphotos.uti.OS_VER = old_ver

    # re-initialize the cached dicts
    osxphotos.uti._load_uti_dict()
