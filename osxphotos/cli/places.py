"""places command for osxphotos CLI"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import click
import yaml

import osxphotos
from osxphotos._constants import _UNKNOWN_PLACE

from .cli_params import DB_OPTION, JSON_OPTION
from .common import get_photos_db
from .list import _list_libraries

if TYPE_CHECKING:
    from .cli import CLI_Obj


@click.command()
@DB_OPTION
@JSON_OPTION
@click.pass_obj
@click.pass_context
def places(
    ctx: click.Context, cli_obj: CLI_Obj | None, db: str | None, json_: bool
) -> None:
    """Print out places found in the Photos library."""

    # below needed for to make CliRunner work for testing
    cli_db = cli_obj.db if cli_obj is not None else None
    db = get_photos_db(db, cli_db)
    if db is None:
        click.echo(ctx.obj.group.commands["places"].get_help(ctx), err=True)
        click.echo("\n\nLocated the following Photos library databases: ", err=True)
        _list_libraries()
        return

    photosdb = osxphotos.PhotosDB(dbfile=db)
    place_names: dict[str | None, int] = {}  # a place may have no name
    for photo in photosdb.photos(movies=True):
        if photo.place:
            try:
                place_names[photo.place.name] += 1
            except Exception:
                place_names[photo.place.name] = 1
        else:
            try:
                place_names[_UNKNOWN_PLACE] += 1
            except Exception:
                place_names[_UNKNOWN_PLACE] = 1

    # sort by place count
    places = {
        "places": {
            name: place_names[name]
            for name in sorted(
                place_names.keys(), key=lambda key: place_names[key], reverse=True
            )
        }
    }

    # below needed for to make CliRunner work for testing
    cli_json = cli_obj.json if cli_obj is not None else None
    if json_ or cli_json:
        click.echo(json.dumps(places, ensure_ascii=False))
    else:
        click.echo(yaml.dump(places, sort_keys=False, allow_unicode=True))
