"""ConfigOptions class to load/save config settings for osxphotos CLI"""

import datetime
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any, Self

import bitmath
import toml

__all__ = [
    "ConfigOptions",
    "ConfigOptionsException",
    "ConfigOptionsInvalidError",
    "ConfigOptionsLoadError",
]


class ConfigOptionsException(Exception):  # noqa: N818  (public name)
    """Invalid combination of options."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class ConfigOptionsInvalidError(ConfigOptionsException):
    pass


class ConfigOptionsLoadError(ConfigOptionsException):
    pass


class ConfigOptions:
    """data class to store and load options for osxphotos commands"""

    if TYPE_CHECKING:
        # option attributes are set dynamically from the command's parameters
        def __getattr__(self, name: str) -> Any: ...

    def __init__(
        self,
        name: str,
        attrs: Mapping[str, Any],
        ignore: Iterable[str] | None = None,
    ) -> None:
        """init ConfigOptions class

        Args:
            name: name for these options, will be used for section heading in TOML file when saving/loading from file
            attrs: dict with name and default value for all allowed attributes
            ignore: optional list of strings of keys to ignore from attrs dict
        """
        self._name = name
        self._attrs: dict[str, Any] = dict(attrs)
        if ignore:
            for attrname in ignore:
                self._attrs.pop(attrname, None)

        self.set_attributes(attrs)

    def set_attributes(self, args: Mapping[str, Any]) -> None:
        for attr in self._attrs:
            try:
                arg = args[attr]
                # don't test 'not arg'; need to handle empty strings as valid values
                if arg is None or arg is False:
                    if type(self._attrs[attr]) is tuple:
                        setattr(self, attr, ())
                    else:
                        setattr(self, attr, self._attrs[attr])
                else:
                    setattr(self, attr, arg)
            except KeyError as e:
                raise KeyError(f"Missing argument: {attr}") from e

    def validate(
        self,
        exclusive: Iterable[tuple[str, str]] | None = None,
        inclusive: Iterable[tuple[str, str]] | None = None,
        dependent: Iterable[tuple[str, str | tuple[str, ...]]] | None = None,
        cli: bool = False,
    ) -> bool:
        """validate combinations of otions

        Args:
            exclusive: list of tuples in form [("option_1", "option_2")...] which are exclusive;
                       ie. either option_1 can be set or option_2 but not both;
            inclusive: list of tuples in form [("option_1", "option_2")...] which are inclusive;
                       ie. if either option_1 or option_2 is set, the other must be set
            dependent: list of tuples in form [("option_1", ("option_2", "option_3"))...]
                       where if option_1 is set, then at least one of the options in the second tuple must also be set
            cli: bool, set to True if called to validate CLI options;
                       will prepend '--' to option names in InvalidOptions.message and change _ to - in option names

        Returns:
            True if all options valid

        Raises:
            InvalidOption if any combination of options is invalid
            InvalidOption.message will be descriptive message of invalid options
        """
        if not any([exclusive, inclusive, dependent]):
            return True

        prefix = "--" if cli else ""
        if exclusive:
            for a, b in exclusive:
                vala = getattr(self, a)
                valb = getattr(self, b)
                vala = any(vala) if isinstance(vala, tuple) else vala
                valb = any(valb) if isinstance(valb, tuple) else valb
                if vala and valb:
                    stra = a.replace("_", "-") if cli else a
                    strb = b.replace("_", "-") if cli else b
                    raise ConfigOptionsInvalidError(
                        f"{prefix}{stra} and {prefix}{strb} options cannot be used together."
                    )
        if inclusive:
            for a, b in inclusive:
                vala = getattr(self, a)
                valb = getattr(self, b)
                vala = any(vala) if isinstance(vala, tuple) else vala
                valb = any(valb) if isinstance(valb, tuple) else valb
                if any([vala, valb]) and not all([vala, valb]):
                    stra = a.replace("_", "-") if cli else a
                    strb = b.replace("_", "-") if cli else b
                    raise ConfigOptionsInvalidError(
                        f"{prefix}{stra} and {prefix}{strb} options must be used together."
                    )
        if dependent:
            for a, deps in dependent:
                vala = getattr(self, a)
                # python unrolls the tuple if there's a single element
                dep_names = deps if isinstance(deps, tuple) else (deps,)
                valb = [getattr(self, x) for x in dep_names]
                valb = [any(x) if isinstance(x, tuple) else x for x in valb]
                if vala and not any(valb):
                    if cli:
                        stra = prefix + a.replace("_", "-")
                        strb = ", ".join(
                            prefix + x.replace("_", "-") for x in dep_names
                        )
                    else:
                        stra = a
                        strb = ", ".join(dep_names)
                    raise ConfigOptionsInvalidError(
                        f"{stra} must be used with at least one of: {strb}."
                    )
        return True

    def write_to_file(self, filename: str) -> None:
        """Write self to TOML file

        Args:
            filename: full path to TOML file to write; filename will be overwritten if it exists
        """
        # todo: add overwrite and option to merge contents already in TOML file (under different [section] with new content)
        with open(filename, "w") as fd:
            toml.dump(self._get_toml_dict(), fd)

    def write_to_str(self) -> str:
        """Write self to TOML str"""
        return toml.dumps(self._get_toml_dict())

    def load_from_file(self, filename: str, override: bool = False) -> Self:
        """Load options from a TOML file.

        Args:
            filename: full path to TOML file
            override: bool; if True, values in the TOML file will override values already set in the instance

        Raises:
            ConfigOptionsLoadError if there are any errors during the parsing of the TOML file
        """
        loaded = toml.load(filename)
        return self._load_from_toml_dict(loaded, override)

    def load_from_str(self, str: str, override: bool = False) -> Self:
        """Load options from a TOML str.

        Args:
            str: TOML str
            override: bool; if True, values in the TOML str will override values already set in the instance

        Raises:
            ConfigOptionsLoadError if there are any errors during the parsing of the TOML str
        """
        loaded = toml.loads(str)
        return self._load_from_toml_dict(loaded, override)

    def _load_from_toml_dict(self, loaded: dict[str, Any], override: bool) -> Self:
        """Load options from a TOML dict (as returned by toml.load or toml.loads)"""
        name = self._name
        if name not in loaded:
            raise ConfigOptionsLoadError(f"[{name}] section missing from config file")

        for attr in loaded[name]:
            if attr not in self._attrs:
                raise ConfigOptionsLoadError(
                    f"Unknown option: {attr} = {loaded[name][attr]}"
                )
            val = loaded[name][attr]
            if not override:
                # use value from self if set
                val = getattr(self, attr) or val
            if type(self._attrs[attr]) is tuple:
                val = tuple(val)
            # TOML parser converts date strings to datetime.date objects
            # but osxphotos expects datetime.datetime objects, so convert them
            if isinstance(val, datetime.date) and not isinstance(
                val, datetime.datetime
            ):
                val = datetime.datetime(val.year, val.month, val.day)
            setattr(self, attr, val)
        return self

    def asdict(self) -> dict[str, Any]:
        return {attr: getattr(self, attr) for attr in sorted(self._attrs.keys())}

    def _get_toml_dict(self) -> dict[str, dict[str, Any]]:
        """Return dict for writing to TOML file"""
        data: dict[str, Any] = {}
        for attr in sorted(self._attrs.keys()):
            val = getattr(self, attr)

            if isinstance(val, bitmath.Bitmath):
                val = int(val.to_Byte())

            if val in [False, ()]:
                val = None
            else:
                val = list(val) if type(val) is tuple else val

            data[attr] = val

        return {self._name: data}
