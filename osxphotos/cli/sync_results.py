"""SyncResults class for osxphotos sync command"""

from __future__ import annotations

import datetime
import json
from typing import Any, Self

SYNC_PROPERTIES = [
    "albums",
    "description",
    "favorite",
    "keywords",
    "title",
    "location",
]


class SyncResults:
    """Results of sync set/merge"""

    def __init__(self) -> None:
        self._results: dict[str, dict[str, Any]] = {}
        self._datetime = datetime.datetime.now()

    def add_result(
        self,
        uuid: str,
        filename: str,
        fingerprint: str | None,
        property: str | None,
        updated: bool,
        before: Any,
        after: Any,
        error: str | None = None,
    ) -> None:
        """Add result for a single photo"""
        if uuid not in self._results:
            self._results[uuid] = {
                "filename": filename,
                "fingerprint": fingerprint,
                "error": error,
            }
            self._results[uuid]["properties"] = {}
            if property:
                self._results[uuid]["properties"][property] = {
                    "updated": updated,
                    "datetime": datetime.datetime.now().isoformat(),
                    "before": before,
                    "after": after,
                }
        else:
            if property:
                self._results[uuid]["properties"][property] = {
                    "updated": updated,
                    "datetime": datetime.datetime.now().isoformat(),
                    "before": before,
                    "after": after,
                }
            if error:
                if self._results[uuid]["error"]:
                    self._results[uuid]["error"] += f", {error}"
                else:
                    self._results[uuid]["error"] = error

    @property
    def results(self) -> dict[str, dict[str, Any]]:
        """Return results"""
        return self._results

    @property
    def results_list(self) -> list[list[Any]]:
        """Return results as list lists where each sublist is values for a single photo"""
        results: list[list[Any]] = []
        for uuid, record in self._results.items():
            row: list[Any] = [
                uuid,
                record["filename"],
                record["fingerprint"],
                self._any_updated(uuid),
            ]
            for property in SYNC_PROPERTIES:
                if property in record["properties"]:
                    row.extend(
                        record["properties"][property][column]
                        for column in ["updated", "datetime", "before", "after"]
                    )
                else:
                    row.extend([False, "", "", ""])
            row.append(record.get("error", ""))
            results.append(row)
        return results

    @property
    def results_header(self) -> list[str]:
        """Return headers for results_list"""
        header = ["uuid", "filename", "fingerprint", "updated"]
        for property in SYNC_PROPERTIES:
            header.extend(
                f"{property}_{column}"
                for column in ["updated", "datetime", "before", "after"]
            )
        header.append("error")
        return header

    @property
    def results_dict(self) -> dict[str, dict[str, Any]]:
        """Return dictionary of results"""
        results: dict[str, dict[str, Any]] = {}
        for uuid, record in self._results.items():
            results[uuid] = {
                "uuid": uuid,
                "filename": record["filename"],
                "fingerprint": record["fingerprint"],
                "updated": self._any_updated(uuid),
            }
            for property in SYNC_PROPERTIES:
                if property in record["properties"]:
                    results[uuid][property] = record["properties"][property]
                else:
                    results[uuid][property] = {
                        "updated": False,
                        "datetime": None,
                        "before": None,
                        "after": None,
                    }
            results[uuid]["error"] = record.get("error", "")
        return results

    def results_summary(self) -> dict[str, int]:
        """Get summary of results"""
        updated = sum(bool(self._any_updated(uuid)) for uuid in self._results)
        property_updated: dict[str, int] = {}
        for property in SYNC_PROPERTIES:
            property_updated[property] = 0
            for uuid in self._results:
                if self._results[uuid]["properties"].get(property, {"updated": False})[
                    "updated"
                ]:
                    property_updated[property] += 1
        return {
            "total": len(self._results),
            "updated": updated,
        } | property_updated

    def _any_updated(self, uuid: str) -> bool:
        """Return True if any property was updated for this photo"""
        return any(
            self._results[uuid]["properties"].get(property, {"updated": False})[
                "updated"
            ]
            for property in SYNC_PROPERTIES
        )

    def __add__(self, other: SyncResults) -> SyncResults:
        """Add results from another SyncResults (updates and returns self, like +=)"""
        return self.__iadd__(other)

    def __iadd__(self, other: SyncResults) -> Self:
        """Add results from another SyncResults"""
        for uuid in other._results:
            for property, values in other._results[uuid]["properties"].items():
                self.add_result(
                    uuid,
                    other._results[uuid]["filename"],
                    other._results[uuid]["fingerprint"],
                    property,
                    values["updated"],
                    values["before"],
                    values["after"],
                )
            self.add_result(
                uuid,
                other._results[uuid]["filename"],
                other._results[uuid]["fingerprint"],
                None,
                False,
                None,
                None,
                other._results[uuid].get("error", None),
            )
        return self

    def __str__(self) -> str:
        return json.dumps(self._results, indent=2)
