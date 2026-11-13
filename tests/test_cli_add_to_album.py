"""Test --add-exported-to-album"""

import pytest
from click.testing import CliRunner

from osxphotos.platform import is_macos

if is_macos:
    import photoscript
else:
    pytest.skip(allow_module_level=True)

UUID_EXPORT = {"3DD2C897-F19E-4CA6-8C22-B027D5A71907": {"filename": "IMG_4547.jpg"}}
UUID_MISSING = {
    "8E1D7BC9-9321-44F9-8CFB-4083F6B9232A": {"filename": "IMG_2000.JPGssss"}
}

# photos with matching names
QUERY_NAME = "IMG_"
QUERY_COUNT = 6


@pytest.mark.addalbum
def test_export_add_to_album(addalbum_library):
    from osxphotos.cli import export

    runner = CliRunner()
    with runner.isolated_filesystem():
        export_album = "OSXPhotos Export"
        skip_album = "OSXPhotos Skipped"
        missing_album = "OSXPhotos Missing"

        uuid_opt = [f"--uuid={uuid}" for uuid in UUID_EXPORT]
        uuid_opt += [f"--uuid={uuid}" for uuid in UUID_MISSING]

        result = runner.invoke(
            export,
            [
                ".",
                "-V",
                "--add-exported-to-album",
                export_album,
                "--add-skipped-to-album",
                skip_album,
                *uuid_opt,
            ],
        )
        assert result.exit_code == 0
        assert f"Creating album '{export_album}'" in result.output
        assert f"Creating album '{skip_album}'" in result.output

        photoslib = photoscript.PhotosLibrary()
        album = photoslib.album(export_album)
        assert album is not None

        assert len(album) == len(UUID_EXPORT)
        got_uuids = [p.uuid for p in album.photos()]
        assert sorted(got_uuids) == sorted(UUID_EXPORT.keys())

        skip_album = photoslib.album(skip_album)
        assert skip_album is not None
        assert len(skip_album) == 0

        result = runner.invoke(
            export,
            [
                ".",
                "-V",
                "--add-exported-to-album",
                export_album,
                "--add-skipped-to-album",
                skip_album,
                "--add-missing-to-album",
                missing_album,
                "--update",
                *uuid_opt,
            ],
        )
        assert result.exit_code == 0
        assert f"Creating album '{export_album}'" not in result.output
        assert f"Creating album '{skip_album}'" not in result.output
        assert f"Creating album '{missing_album}'" in result.output

        photoslib = photoscript.PhotosLibrary()
        export_album = photoslib.album(export_album)
        assert export_album is not None
        assert len(export_album) == len(UUID_EXPORT)

        skip_album = photoslib.album(skip_album)
        assert skip_album is not None
        assert len(skip_album) == len(UUID_EXPORT)
        got_uuids = [p.uuid for p in skip_album.photos()]
        assert sorted(got_uuids) == sorted(UUID_EXPORT.keys())

        missing_album = photoslib.album(missing_album)
        assert missing_album is not None
        assert len(missing_album) == len(UUID_MISSING)
        got_uuids = [p.uuid for p in missing_album.photos()]
        assert sorted(got_uuids) == sorted(UUID_MISSING.keys())


@pytest.mark.addalbum
def test_query_add_to_album(addalbum_library):
    from osxphotos.cli import query

    runner = CliRunner()
    with runner.isolated_filesystem():
        query_album = "OSXPhotos Query"

        uuid_opt = [f"--uuid={uuid}" for uuid in UUID_EXPORT]

        result = runner.invoke(query, ["--add-to-album", query_album, *uuid_opt])
        assert result.exit_code == 0

        photoslib = photoscript.PhotosLibrary()
        album = photoslib.album(query_album)
        assert album is not None

        assert len(album) == len(UUID_EXPORT)
        got_uuids = [p.uuid for p in album.photos()]
        assert sorted(got_uuids) == sorted(UUID_EXPORT.keys())


@pytest.mark.addalbum
def test_query_add_to_album_multiple_results(addalbum_library):
    """Test osxphotos query --add-to-album with multiple results, see #848"""
    from osxphotos.cli import query

    runner = CliRunner()
    with runner.isolated_filesystem():
        query_album = "OSXPhotos Query"

        result = runner.invoke(
            query, ["--add-to-album", query_album, "--name", QUERY_NAME]
        )
        assert result.exit_code == 0

        photoslib = photoscript.PhotosLibrary()
        album = photoslib.album(query_album)
        assert album is not None
        assert len(album) == QUERY_COUNT
