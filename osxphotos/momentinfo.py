"""MomentInfo class with details about photo moments."""

import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .photoinfo import PhotoInfo
    from .photosdb import PhotosDB

__all__ = ["MomentInfo"]


class MomentInfo:
    """Info about a photo moment"""

    def __init__(self, db: PhotosDB, moment_pk: int) -> None:
        """Initialize with a moment PK; returns None if PK not found."""
        self._db = db
        self._pk = moment_pk

        moment = self._db._db_moment_pk.get(moment_pk)
        if not moment:
            raise ValueError(f"No moment with PK {moment_pk}")
        self._moment: dict[str, Any] = moment

    @property
    def pk(self) -> int:
        """Primary key of the moment."""
        return self._pk

    @property
    def location(self) -> tuple[float | None, float | None]:
        """Location of the moment."""
        return (self._moment.get("latitude"), self._moment.get("longitude"))

    @property
    def title(self) -> str | None:
        """Title of the moment."""
        return self._moment.get("title")

    @property
    def subtitle(self) -> str | None:
        """Subtitle of the moment."""
        return self._moment.get("subtitle")

    @property
    def start_date(self) -> datetime.datetime | None:
        """Start date of the moment."""
        return self._moment.get("startDate")

    @property
    def end_date(self) -> datetime.datetime | None:
        """Stop date of the moment."""
        return self._moment.get("endDate")

    @property
    def date(self) -> datetime.datetime | None:
        """Date of the moment."""
        return self._moment.get("representativeDate")

    @property
    def modification_date(self) -> datetime.datetime | None:
        """Modification date of the moment."""
        return self._moment.get("modificationDate")

    @property
    def photos(self) -> list[PhotoInfo]:
        """All photos in this moment"""
        try:
            return self._photos
        except AttributeError:
            photo_uuids = [
                uuid
                for uuid, photo in self._db._dbphotos.items()
                if photo["momentID"] == self._pk
            ]

            self._photos: list[PhotoInfo] = self._db.photos_by_uuid(photo_uuids)
            return self._photos

    def asdict(self) -> dict[str, Any]:
        """Returns all moment info as dictionary"""
        return {
            "pk": self.pk,
            "location": self.location,
            "title": self.title,
            "subtitle": self.subtitle,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "date": self.date.isoformat() if self.date else None,
            "modification_date": (
                self.modification_date.isoformat() if self.modification_date else None
            ),
            "photos": self.photos,
        }
