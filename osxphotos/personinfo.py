"""PhotoInfo and FaceInfo classes to expose info about persons and faces in the Photos library"""

from __future__ import annotations

import json
import logging
import math
from collections import namedtuple
from functools import cached_property
from typing import TYPE_CHECKING, Any, cast

import osxphotos

if TYPE_CHECKING:
    from .photoinfo import PhotoInfo

logger = logging.getLogger("osxphotos")

__all__ = ["FaceInfo", "PersonInfo", "rotate_image_point"]

MWG_RS_Area = namedtuple("MWG_RS_Area", ["x", "y", "h", "w"])
MPRI_Reg_Rect = namedtuple("MPRI_Reg_Rect", ["x", "y", "h", "w"])


class PersonInfo:
    """Info about a person in the Photos library"""

    # set lazily by keyphoto; absent until first access
    _keyphoto: PhotoInfo | None

    def __init__(self, db: osxphotos.PhotosDB, pk: int) -> None:
        """Creates a new PersonInfo instance

        Arguments:
            db: instance of PhotosDB object
            pk: primary key value of person to initialize PersonInfo with

        Returns:
            PersonInfo instance
        """
        self._db: osxphotos.PhotosDB = db
        self._pk: int = pk

        person = self._db._dbpersons_pk[pk]
        self.uuid: str = person["uuid"]
        self.name: str = person["fullname"]
        self.display_name: str | None = person["displayname"]
        self.keyface = person["keyface"]
        self.facecount = person["facecount"]

    @property
    def keyphoto(self) -> PhotoInfo | None:
        try:
            return self._keyphoto
        except AttributeError:
            person = self._db._dbpersons_pk[self._pk]
            if person["photo_uuid"]:
                try:
                    key_photo: PhotoInfo | None = self._db.get_photo(
                        person["photo_uuid"]
                    )
                except IndexError:
                    key_photo = None
            else:
                key_photo = None
            self._keyphoto = key_photo
            return self._keyphoto

    @property
    def photos(self) -> list[PhotoInfo]:
        """Returns list of PhotoInfo objects associated with this person"""
        try:
            return self._db.photos_by_uuid(self._db._dbfaces_pk[self._pk])
        except KeyError:
            # A person may have no photos (e.g. if all photos were deleted from the library)
            return []

    @property
    def face_info(self) -> list[FaceInfo]:
        """Returns a list of FaceInfo objects associated with this person sorted by quality score
        Highest quality face is result[0] and lowest quality face is result[n]
        """
        try:
            faces = self._db._db_faceinfo_person[self._pk]
            return sorted(
                [FaceInfo(db=self._db, pk=face) for face in faces],
                key=lambda face: face.quality,
                reverse=True,
            )
        except KeyError:
            # no faces
            return []

    @property
    def favorite(self) -> bool:
        """Returns True if person is a favorite, False otherwise; Photos 5+ only; returns False on Photos <= 4"""
        return bool(self._db._dbpersons_pk[self._pk]["type"] == 1)

    @property
    def sort_order(self) -> int:
        """Returns sort order of person; favorite persons are sorted before non-favorite persons"; Photos 5+ only; returns 0 on Photos <= 4"""
        return cast(int, self._db._dbpersons_pk[self._pk]["manualorder"])

    @cached_property
    def feature_less(self) -> bool:
        """Returns True if person has been marked as "Feature This Person Less" in Photos, False otherwise; Photos 8+ only; returns False on Photos <= 7"""
        if self._db.photos_version < 8:
            return False

        if results := self._db.execute(
            """
            SELECT ZTYPE
            FROM ZUSERFEEDBACK
            WHERE ZPERSON = ?
            """,
            (self._pk,),
        ).fetchone():
            return bool(results[0])
        return False

    def asdict(self) -> dict[str, Any]:
        """Returns dictionary representation of class instance"""
        keyphoto = self.keyphoto.uuid if self.keyphoto is not None else None
        return {
            "uuid": self.uuid,
            "name": self.name,
            "displayname": self.display_name,
            "keyface": self.keyface,
            "facecount": self.facecount,
            "keyphoto": keyphoto,
            "favorite": self.favorite,
            "sort_order": self.sort_order,
            "feature_less": self.feature_less,
        }

    def json(self) -> str:
        """Returns JSON representation of class instance"""
        return json.dumps(self.asdict())

    def __str__(self) -> str:
        return f"PersonInfo(name={self.name}, display_name={self.display_name}, uuid={self.uuid}, facecount={self.facecount})"

    def __eq__(self, other: object) -> bool:
        return (
            all(
                getattr(self, field) == getattr(other, field)
                for field in ["_db", "_pk"]
            )
            if isinstance(other, type(self))
            else False
        )

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)


class FaceInfo:
    """Info about a face in the Photos library"""

    # set lazily by person_info and photo; absent until first access
    _person: PersonInfo
    _photo: PhotoInfo | None

    def __init__(
        self, db: osxphotos.PhotosDB | None = None, pk: int | None = None
    ) -> None:
        """Creates a new FaceInfo instance

        Arguments:
            db: instance of PhotosDB object
            pk: primary key value of face to init the object with

        Returns:
            FaceInfo instance
        """
        # db and pk default to None only for signature compatibility; both are required
        self._db: osxphotos.PhotosDB = cast("osxphotos.PhotosDB", db)
        self._pk: int = cast(int, pk)

        face = self._db._db_faceinfo_pk[self._pk]
        self._info = face
        self.uuid: str = face["uuid"]
        self.name: str | None = face["fullname"]
        self.asset_uuid: str = face["asset_uuid"]
        self._person_pk: int = face["person"]
        self.center_x: float = face["centerx"]
        self.center_y: float = face["centery"]
        self.size: float = face["size"]
        self.quality = face["quality"]
        self.source_width = face["sourcewidth"]
        self.source_height = face["sourceheight"]
        self.has_smile = face["has_smile"]
        self.manual = face["manual"]
        self.face_type = face["facetype"]
        self.age_type = face["agetype"]
        self.eye_makeup_type = face["eyemakeuptype"]
        self.eye_state = face["eyestate"]
        self.facial_hair_type = face["facialhairtype"]
        self.gender_type = face["gendertype"]
        self.glasses_type = face["glassestype"]
        self.hair_color_type = face["haircolortype"]
        self.intrash = face["intrash"]
        self.lip_makeup_type = face["lipmakeuptype"]
        self.smile_type = face["smiletype"]

    @property
    def center(self) -> tuple[int, int]:
        """Coordinates, in PIL format, for center of face

        Returns:
            tuple of coordinates in form (x, y)
        """
        return self._make_point((self.center_x, self.center_y))

    @property
    def size_pixels(self) -> float:
        """Size of face in pixels (centered around center_x, center_y)

        Returns:
            size, in int pixels, of a circle drawn around the center of the face
        """
        photo = self._photo_info
        size_reference = max(photo.height, photo.width)
        return self.size * size_reference

    @property
    def person_info(self) -> PersonInfo:
        """PersonInfo instance for person associated with this face"""
        try:
            return self._person
        except AttributeError:
            self._person = PersonInfo(db=self._db, pk=self._person_pk)
            return self._person

    @property
    def photo(self) -> PhotoInfo | None:
        """PhotoInfo instance associated with this face"""
        try:
            return self._photo
        except AttributeError:
            self._photo = self._db.get_photo(self.asset_uuid)
            if self._photo is None:
                logger.warning(f"Could not get photo for uuid: {self.asset_uuid}")
            return self._photo

    @property
    def _photo_info(self) -> PhotoInfo:
        """photo, for the internal geometry code which needs the photo to exist"""
        return cast("PhotoInfo", self.photo)

    @property
    def mwg_rs_area(self) -> MWG_RS_Area:
        """Get coordinates for Metadata Working Group Region Area.

        Returns:
            MWG_RS_Area named tuple with x, y, h, w where:
            x = stArea:x
            y = stArea:y
            h = stArea:h
            w = stArea:w

        Reference:
            https://photo.stackexchange.com/questions/106410/how-does-xmp-define-the-face-region
        """
        x, y = self.center_x, self.center_y
        x, y = self._fix_orientation((x, y))

        # there are some rare cases where width or height is zero (#1810)
        # in this case return a zero rectangle which doesn't make sense but neither does a zero width or height
        if self._photo_info.width == 0 or self._photo_info.height == 0:
            return MWG_RS_Area(0, 0, 0, 0)

        if self._photo_info.orientation in [5, 6, 7, 8]:
            w = self.size_pixels / self._photo_info.height
            h = self.size_pixels / self._photo_info.width
        else:
            h = self.size_pixels / self._photo_info.height
            w = self.size_pixels / self._photo_info.width

        return MWG_RS_Area(x, y, h, w)

    @property
    def mpri_reg_rect(self) -> MPRI_Reg_Rect:
        """Get coordinates for Microsoft Photo Region Rectangle.

        Returns:
            MPRI_Reg_Rect named tuple with x, y, h, w where:
            x = x coordinate of top left corner of rectangle
            y = y coordinate of top left corner of rectangle
            h = height of rectangle
            w = width of rectangle

        Reference:
            https://docs.microsoft.com/en-us/windows/win32/wic/-wic-people-tagging
        """
        x, y = self.center_x, self.center_y
        x, y = self._fix_orientation((x, y))

        # there are some rare cases where width or height is zero (#1810)
        # in this case return a zero rectangle which doesn't make sense but neither does a zero width or height
        if self._photo_info.width == 0 or self._photo_info.height == 0:
            return MPRI_Reg_Rect(0, 0, 0, 0)

        if self._photo_info.orientation in [5, 6, 7, 8]:
            w = self.size_pixels / self._photo_info.width
            h = self.size_pixels / self._photo_info.height
            x = x - self.size_pixels / self._photo_info.height / 2
            y = y - self.size_pixels / self._photo_info.width / 2
        else:
            h = self.size_pixels / self._photo_info.width
            w = self.size_pixels / self._photo_info.height
            x = x - self.size_pixels / self._photo_info.width / 2
            y = y - self.size_pixels / self._photo_info.height / 2

        return MPRI_Reg_Rect(x, y, h, w)

    def face_rect(self) -> list[tuple[float, float]]:
        """Get face rectangle coordinates for current version of the associated image
            If image has been edited, rectangle applies to edited version, otherwise original version
            Coordinates in format and reference frame used by PIL

        Returns:
            list [(x0, x1), (y0, y1)] of coordinates in reference frame used by PIL
        """
        photo = self._photo_info
        size_reference = max(photo.height, photo.width)
        radius = (self.size / 2) * size_reference
        x, y = self._make_point((self.center_x, self.center_y))
        x0, y0 = x - radius, y - radius
        x1, y1 = x + radius, y + radius
        return [(x0, y0), (x1, y1)]

    def roll_pitch_yaw(self) -> tuple[float, float, float]:
        """Roll, pitch, yaw of face in radians as tuple"""
        info = self._info
        roll = 0 if info["roll"] is None else info["roll"]
        pitch = 0 if info["pitch"] is None else info["pitch"]
        yaw = 0 if info["yaw"] is None else info["yaw"]

        return (roll, pitch, yaw)

    @property
    def roll(self) -> float:
        """Return roll angle in radians of the face region"""
        roll, _, _ = self.roll_pitch_yaw()
        return roll

    @property
    def pitch(self) -> float:
        """Return pitch angle in radians of the face region"""
        _, pitch, _ = self.roll_pitch_yaw()
        return pitch

    @property
    def yaw(self) -> float:
        """Return yaw angle in radians of the face region"""
        _, _, yaw = self.roll_pitch_yaw()
        return yaw

    def _fix_orientation(self, xy: tuple[float, float]) -> tuple[float, float]:
        """Translate an (x, y) tuple based on image orientation

        Arguments:
            xy: tuple of (x, y) coordinates for point to translate
                in format used by Photos (percent of height/width)

        Returns:
            (x, y) tuple of translated coordinates
        """
        # Reference: https://github.com/neilpa/phace/blob/7594776480505d0c389688a42099c94ac5d34f3f/cmd/phace/draw.go#L79-L94

        orientation = self._photo_info.orientation
        x, y = xy
        if orientation == 1:
            y = 1.0 - y
        elif orientation == 2:
            y = 1.0 - y
            x = 1.0 - x
        elif orientation == 3:
            x = 1.0 - x
        elif orientation == 4:
            pass
        elif orientation == 5:
            x, y = 1.0 - y, x
        elif orientation == 6:
            x, y = 1.0 - y, 1.0 - x
        elif orientation == 7:
            x, y = y, x
            y = 1.0 - y
        elif orientation == 8:
            x, y = y, x
        elif orientation == 0:
            # set by osxphotos if adjusted orientation cannot be read, assume it's 1
            y = 1.0 - y
        else:
            logger.warning(f"Unhandled orientation: {orientation}")

        return (x, y)

    def _make_point(self, xy: tuple[float, float]) -> tuple[int, int]:
        """Translate an (x, y) tuple based on image orientation
            and convert to image coordinates

        Arguments:
            xy: tuple of (x, y) coordinates for point to translate
                in format used by Photos (percent of height/width)

        Returns:
            (x, y) tuple of translated coordinates in pixels in PIL format/reference frame
        """
        # Reference: https://github.com/neilpa/phace/blob/7594776480505d0c389688a42099c94ac5d34f3f/cmd/phace/draw.go#L79-L94

        photo = self._photo_info
        orientation = photo.orientation
        x, y = self._fix_orientation(xy)
        dx = photo.width
        dy = photo.height
        if orientation in [5, 6, 7, 8]:
            dx, dy = dy, dx
        return (int(x * dx), int(y * dy))

    def _make_point_with_rotation(self, xy: tuple[float, float]) -> tuple[int, int]:
        """Translate an (x, y) tuple based on image orientation and rotation
            and convert to image coordinates

        Arguments:
            xy: tuple of (x, y) coordinates for point to translate
                in format used by Photos (percent of height/width)

        Returns:
            (x, y) tuple of translated coordinates in pixels in PIL format/reference frame
        """

        # convert to image coordinates
        x, y = self._make_point(xy)

        # rotate about center
        xmid, ymid = self.center
        roll, _, _ = self.roll_pitch_yaw()
        xr, yr = rotate_image_point(x, y, xmid, ymid, roll)

        return (int(xr), int(yr))

    def asdict(self) -> dict[str, Any]:
        """Returns dict representation of class instance"""
        roll, pitch, yaw = self.roll_pitch_yaw()
        return {
            "_pk": self._pk,
            "uuid": self.uuid,
            "name": self.name,
            "asset_uuid": self.asset_uuid,
            "_person_pk": self._person_pk,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "center": self.center,
            "size": self.size,
            "face_rect": self.face_rect(),
            "mpri_reg_rect": self.mpri_reg_rect._asdict(),
            "mwg_rs_area": self.mwg_rs_area._asdict(),
            "roll": roll,
            "pitch": pitch,
            "yaw": yaw,
            "quality": self.quality,
            "source_width": self.source_width,
            "source_height": self.source_height,
            "has_smile": self.has_smile,
            "manual": self.manual,
            "face_type": self.face_type,
            "age_type": self.age_type,
            "eye_makeup_type": self.eye_makeup_type,
            "eye_state": self.eye_state,
            "facial_hair_type": self.facial_hair_type,
            "gender_type": self.gender_type,
            "glasses_type": self.glasses_type,
            "hair_color_type": self.hair_color_type,
            "intrash": self.intrash,
            "lip_makeup_type": self.lip_makeup_type,
            "smile_type": self.smile_type,
        }

    def json(self) -> str:
        """Return JSON representation of FaceInfo instance"""
        return json.dumps(self.asdict())

    def __str__(self) -> str:
        return f"FaceInfo(uuid={self.uuid}, center_x={self.center_x}, center_y = {self.center_y}, size={self.size}, person={self.name}, asset_uuid={self.asset_uuid})"

    def __repr__(self) -> str:
        return f"FaceInfo(db={self._db}, pk={self._pk})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return False

        return all(
            getattr(self, field) == getattr(other, field) for field in ["_db", "_pk"]
        )

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)


def rotate_image_point(
    x: float, y: float, xmid: float, ymid: float, angle: float
) -> tuple[float, float]:
    """rotate image point about xm, ym by angle in radians

    Arguments:
        x: x coordinate of point to rotate
        y: y coordinate of point to rotate
        xmid: x coordinate of center point to rotate about
        ymid: y coordinate of center point to rotate about
        angle: angle in radians about which to coordinate,
            counter-clockwise is positive

    Returns:
        tuple of rotated points (xr, yr)
    """
    # translate point relative to the mid point
    x = x - xmid
    y = y - ymid

    # rotate by angle and translate back
    # the photo coordinate system is downwards y is positive so
    # need to adjust the rotation accordingly
    cos_angle = math.cos(angle)
    sin_angle = math.sin(angle)
    xr = x * cos_angle + y * sin_angle + xmid
    yr = -x * sin_angle + y * cos_angle + ymid

    return (xr, yr)
