"""Yet another simple exiftool wrapper
I rolled my own for following reasons:
1. I wanted something under MIT license (best alternative was licensed under GPL/BSD)
2. I wanted singleton behavior so only a single exiftool process was ever running
3. When used as a context manager, I wanted the operations to batch until exiting the context (improved performance)
If these aren't important to you, I recommend you consider Sven Marnach's excellent
pyexiftool: https://github.com/smarnach/pyexiftool which provides more functionality"""

from __future__ import annotations

import atexit
import contextlib
import html
import json
import logging
import os
import pathlib
import re
import shutil
import subprocess
import threading
from functools import lru_cache  # pylint: disable=syntax-error
from types import TracebackType
from typing import Any, ClassVar, Self, cast, overload

logger = logging.getLogger("osxphotos")

__all__ = [
    "ExifTool",
    "ExifToolCaching",
    "escape_str",
    "exiftool_can_write",
    "get_exiftool_path",
    "terminate_exiftool",
    "unescape_str",
]

# exiftool -stay_open commands outputs this EOF marker after command is run
EXIFTOOL_STAYOPEN_EOF = "{ready}"
EXIFTOOL_STAYOPEN_EOF_LEN = len(EXIFTOOL_STAYOPEN_EOF)

# timeout in seconds for starting exiftool process
EXIFTOOL_STARTUP_TIMEOUT = 30

# list of exiftool processes to cleanup when exiting or when terminate is called
EXIFTOOL_PROCESSES: list[_ExifToolProc] = []

# exiftool supported file types, created by utils/exiftool_supported_types.py
EXIFTOOL_FILETYPES_JSON = "exiftool_filetypes.json"
with (pathlib.Path(__file__).parent / EXIFTOOL_FILETYPES_JSON).open("r") as f:
    EXIFTOOL_SUPPORTED_FILETYPES: dict[str, dict[str, bool]] = json.load(f)


def exiftool_can_write(suffix: str) -> bool:
    """Return True if exiftool supports writing to a file with the given suffix, otherwise False"""
    if not suffix:
        return False
    suffix = suffix.lower()
    if suffix[0] == ".":
        suffix = suffix[1:]
    return (
        suffix in EXIFTOOL_SUPPORTED_FILETYPES
        and EXIFTOOL_SUPPORTED_FILETYPES[suffix]["write"]
    )


@overload
def escape_str(s: str) -> str: ...


@overload
def escape_str[T](s: T) -> T: ...


def escape_str(s: Any) -> Any:
    """escape string for use with exiftool -E"""
    if not isinstance(s, str):
        return s
    s = html.escape(s)
    s = s.replace("\n", "&#xa;")
    s = s.replace("\t", "&#x9;")
    s = s.replace("\r", "&#xd;")
    return s


@overload
def unescape_str(s: str) -> str: ...


@overload
def unescape_str[T](s: T) -> T: ...


def unescape_str(s: Any) -> Any:
    """unescape an HTML string returned by exiftool -E"""
    if not isinstance(s, str):
        return s
    # avoid " in values which result in json.loads() throwing an exception, #636
    s = s.replace("&quot;", '\\"')
    return html.unescape(s)


@atexit.register
def terminate_exiftool() -> None:
    """Terminate any running ExifTool subprocesses; call this to cleanup when done using ExifTool"""
    for proc in EXIFTOOL_PROCESSES:
        proc._stop_proc()


@lru_cache(maxsize=1)
def get_exiftool_path() -> str:
    """return path of exiftool, cache result"""
    if exiftool_path := shutil.which("exiftool"):
        return exiftool_path.rstrip()
    else:
        raise FileNotFoundError(
            "Could not find exiftool. Please download and install from "
            "https://exiftool.org/"
        )


def _start_process_with_timeout(
    args: list[str], timeout: float, **kwargs: Any
) -> subprocess.Popen[bytes]:
    """Start a subprocess with a timeout on the Popen call itself.

    Args:
        args: Arguments to pass to subprocess.Popen
        timeout: Timeout in seconds
        **kwargs: Additional keyword arguments for subprocess.Popen

    Returns:
        subprocess.Popen object

    Raises:
        TimeoutError: If process startup times out
        Other exceptions from subprocess.Popen as normal
    """
    process: subprocess.Popen[bytes] | None = None
    exception: Exception | None = None

    def target() -> None:
        nonlocal process, exception
        try:
            process = subprocess.Popen(args, **kwargs)
        except Exception as e:
            exception = e

    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        # Thread is still running, startup timed out
        # Note: We can't easily kill the thread, but the daemon flag
        # means it will be cleaned up when the main process exits
        raise TimeoutError(f"process startup timed out after {timeout} seconds")

    if exception:
        raise exception

    if process is None:
        raise RuntimeError("Failed to start process for unknown reason")

    return process


class _ExifToolProc:
    """Runs exiftool in a subprocess via Popen
    Creates a singleton object"""

    instance: ClassVar[_ExifToolProc]
    _process_running: bool
    _large_file_support: bool
    _exiftool: str
    _process: subprocess.Popen[bytes]

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        """create new object or return instance of already created singleton"""
        if not hasattr(cls, "instance") or not cls.instance:
            cls.instance = super().__new__(cls)

        # the singleton was created above by this class (_ExifToolProc has no subclasses)
        return cast(Self, cls.instance)

    def __init__(
        self, exiftool: str | None = None, large_file_support: bool = True
    ) -> None:
        """construct _ExifToolProc singleton object or return instance of already created object

        Args:
            exiftool: optional path to exiftool binary (if not provided, will search path to find it)
            large_file_support: if True, enables large file support (>4GB) via '-api largefilesupport=1'
        """

        if hasattr(self, "_process_running") and self._process_running:
            # already running
            if exiftool is not None and exiftool != self._exiftool:
                logger.warning(
                    f"exiftool subprocess already running, ignoring exiftool={exiftool}"
                )
            return
        self._process_running = False
        self._large_file_support = large_file_support
        self._exiftool = exiftool or get_exiftool_path()
        self._start_proc(large_file_support=large_file_support)

    @property
    def process(self) -> subprocess.Popen[bytes]:
        """return the exiftool subprocess"""
        if not self._process_running:
            self._start_proc(large_file_support=self._large_file_support)
        return self._process

    @property
    def pid(self) -> int:
        """return process id (PID) of the exiftool process"""
        return self._process.pid

    @property
    def exiftool(self) -> str:
        """return path to exiftool process"""
        return self._exiftool

    def _start_proc(self, large_file_support: bool) -> None:
        """start exiftool in batch mode"""

        if self._process_running:
            logger.warning("exiftool already running: {self._process}")
            return

        # open exiftool procGess
        # make sure /usr/bin at start of path so exiftool can find xattr (see #636)
        env = os.environ.copy()
        env["PATH"] = f"/usr/bin/:{env['PATH']}"
        large_file_args = ["-api", "largefilesupport=1"] if large_file_support else []

        try:
            self._process = _start_process_with_timeout(
                [
                    self._exiftool,
                    "-stay_open",  # keep process open in batch mode
                    "True",  # -stay_open=True, keep process open in batch mode
                    *large_file_args,
                    "-@",  # read command-line arguments from file
                    "-",  # read from stdin
                    "-common_args",  # specifies args common to all commands subsequently run
                    "-n",  # no print conversion (e.g. print tag values in machine readable format)
                    "-P",  # Preserve file modification date/time
                    "-G",  # print group name for each tag
                    "-E",  # escape tag values for HTML (allows use of HTML &#xa; for newlines)
                ],
                timeout=EXIFTOOL_STARTUP_TIMEOUT,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
            )
        except (TimeoutError, RuntimeError) as e:
            raise RuntimeError(f"Failed to start exiftool process: {e}") from e

        self._process_running = True
        EXIFTOOL_PROCESSES.append(self)

    def _stop_proc(self) -> None:
        """stop the exiftool process if it's running, otherwise, do nothing"""

        if not self._process_running:
            return

        with contextlib.suppress(Exception):
            # stdin is never None: the process is started with stdin=PIPE
            stdin = self._process.stdin
            assert stdin is not None
            stdin.write(b"-stay_open\n")
            stdin.write(b"False\n")
            stdin.flush()
        try:
            self._process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.communicate()

        del self._process
        self._process_running = False


class ExifTool:
    """Basic exiftool interface for reading and writing EXIF tags"""

    def __init__(
        self,
        filepath: str | os.PathLike[str],
        exiftool: str | None = None,
        overwrite: bool = True,
        flags: list[str] | None = None,
        large_file_support: bool = True,
    ) -> None:
        """Create ExifTool object

        Args:
            file: path to image file
            exiftool: path to exiftool, if not specified will look in path
            overwrite: if True, will overwrite image file without creating backup, default=False
            flags: optional list of exiftool flags to prepend to exiftool command when writing metadata (e.g. -m or -F)
            large_file_support: if True, enables large file support in exiftool ('-api largefilesupport=1')

        Returns:
            ExifTool instance
        """
        self.file = filepath if isinstance(filepath, str) else str(filepath)
        self.overwrite = overwrite
        self.flags = flags or []
        self.warning: str | None = None
        self.error: str | None = None
        # if running as a context manager, self._context_mgr will be True
        self._context_mgr = False
        self._exiftoolproc = _ExifToolProc(
            exiftool=exiftool, large_file_support=large_file_support
        )
        self.data = self._read_exif()
        self.is_png = self.data.get("File:FileType") == "PNG"  # 1031

    @property
    def _process(self) -> subprocess.Popen[bytes]:
        return self._exiftoolproc.process

    def setvalue(self, tag: str, value: Any) -> bool:
        """Set tag to value(s); if value is None, will delete tag

        Args:
            tag: str; name of tag to set
            value: Any; value to set tag to

        Returns:
            True if success otherwise False

            If error generated by exiftool, returns False and sets self.error to error string
            If warning generated by exiftool, returns True (unless there was also an error) and sets self.warning to warning string
            If called in context manager, returns True (execution is delayed until exiting context manager)
        """

        if value is None:
            value = ""
        value = escape_str(value)
        if isinstance(value, dict):
            # need to convert structs to a format exiftool expects
            # exiftool's format is basically JSON where keys are unquoted
            value = convert_dict_to_unquoted_json(value)
        command = [f"-{tag}={value}"]
        if self.overwrite and not self._context_mgr:
            command.append("-overwrite_original")

        # avoid "Warning: Some character(s) could not be encoded in Latin" warning #393
        if not self.is_png:
            command.append("-iptc:codedcharacterset=utf8")

        if self._context_mgr:
            self._commands.extend(command)
            return True
        else:
            _, _, error = self.run_commands(*command)
            return error == ""

    def addvalues(self, tag: str, *values: Any) -> bool:
        """Add one or more value(s) to tag
            If more than one value is passed, each value will be added to the tag

        Args:
            tag: str; tag to set
            *values: str; one or more values to set

        Returns:
            True if success otherwise False

            If error generated by exiftool, returns False and sets self.error to error string
            If warning generated by exiftool, returns True (unless there was also an error) and sets self.warning to warning string
            If called in context manager, returns True (execution is delayed until exiting context manager)

        Notes: exiftool may add duplicate values for some tags so the caller must ensure
               the values being added are not already in the EXIF data
               For some tags, such as IPTC:Keywords, this will add a new value to the list of keywords,
               but for others, such as EXIF:ISO, this will literally add a value to the existing value.
               It's up to the caller to know what exiftool will do for each tag
               If setvalue called before addvalues, exiftool does not appear to add duplicates,
               but if addvalues called without first calling setvalue, exiftool will add duplicate values
        """
        if not values:
            raise ValueError("Must pass at least one value")

        command: list[str] = []
        for value in values:
            if value is None:
                raise ValueError("Can't add None value to tag")
            value = escape_str(value)
            command.append(f"-{tag}+={value}")

        if self.overwrite and not self._context_mgr:
            command.append("-overwrite_original")

        if self._context_mgr:
            self._commands.extend(command)
            return True
        else:
            _, _, error = self.run_commands(*command)
            return error == ""

    def run_commands(
        self, *commands: str, no_file: bool = False
    ) -> tuple[bytes, str, str]:
        """Run commands in the exiftool process and return result.

        Args:
                *commands: exiftool commands to run
                no_file: (bool) do not pass the filename to exiftool (default=False)
                        by default, all commands will be run against self.file
                        use no_file=True to run a command without passing the filename
        Returns:
            (output, warning, error)
            output: bytes is containing output of exiftool commands
            warning: if exiftool generated warnings, string containing warning otherwise empty string
            error: if exiftool generated errors, string containing otherwise empty string

        Note: Also sets self.warning and self.error if warning or error generated.
        """
        if not (hasattr(self, "_process") and self._process):
            raise ValueError("exiftool process is not running")

        if not commands:
            raise TypeError("must provide one or more command to run")

        command_list = list(commands)
        if self._context_mgr and self.overwrite:
            command_list.append("-overwrite_original")

        filename = b"" if no_file else os.fsencode(self.file)

        if self.flags:
            # need to split flags, e.g. so "--ext AVI" becomes ["--ext", "AVI"]
            flags = []
            for f in self.flags:
                flags.extend(f.split())
            command_str = b"\n".join([f.encode("utf-8") for f in flags])
            command_str += b"\n"
        else:
            command_str = b""

        command_str += (
            b"\n".join([c.encode("utf-8") for c in command_list])
            + b"\n"
            + filename
            + b"\n"
            + b"-execute\n"
        )

        # stdin and stdout are never None: the process is started with PIPEs
        process = self._process
        stdin, stdout = process.stdin, process.stdout
        assert stdin is not None
        assert stdout is not None

        # send the command
        stdin.write(command_str)
        stdin.flush()

        # read the output
        output = b""
        warning_bytes = b""
        error_bytes = b""
        while EXIFTOOL_STAYOPEN_EOF not in str(output):
            line = stdout.readline()
            if line.startswith(b"Warning"):
                warning_bytes += line.strip()
            elif line.startswith(b"Error"):
                error_bytes += line.strip()
            else:
                output += line.strip()
        warning = "" if warning_bytes == b"" else warning_bytes.decode("utf-8")
        error = "" if error_bytes == b"" else error_bytes.decode("utf-8")
        self.warning = warning
        self.error = error

        return output[:-EXIFTOOL_STAYOPEN_EOF_LEN], warning, error

    @property
    def pid(self) -> int:
        """return process id (PID) of the exiftool process"""
        return self._process.pid

    @property
    def version(self) -> str:
        """returns exiftool version"""
        ver, _, _ = self.run_commands("-ver", no_file=True)
        return ver.decode("utf-8")

    def asdict(
        self, tag_groups: bool = True, normalized: bool = False
    ) -> dict[str, Any]:
        """return dictionary of all EXIF tags and values from exiftool
        returns empty dict if no tags

        Args:
            tag_groups: if True (default), dict keys have tag groups, e.g. "IPTC:Keywords"; if False, drops groups from keys, e.g. "Keywords"
            normalized: if True, dict keys are all normalized to lower case (default is False)
        """
        json_bytes, _, _ = self.run_commands("-json")
        if not json_bytes:
            return {}
        json_str = unescape_str(json_bytes.decode("utf-8"))

        try:
            exif_list = json.loads(json_str)
        except Exception as e:
            # will fail with some commands, e.g --ext AVI which produces
            # 'No file with specified extension' instead of json
            logger.warning(f"error loading json returned by exiftool: {e} {json_str}")
            return {}
        exifdict: dict[str, Any] = exif_list[0]
        if not tag_groups:
            # strip tag groups
            exif_new: dict[str, Any] = {}
            for k, v in exifdict.items():
                k = re.sub(r".*:", "", k)
                exif_new[k] = v
            exifdict = exif_new

        if normalized:
            exifdict = {k.lower(): v for (k, v) in exifdict.items()}

        return exifdict

    def json(self) -> str:
        """returns JSON string containing all EXIF tags and values from exiftool"""
        json_bytes, _, _ = self.run_commands("-json")
        return unescape_str(json_bytes.decode("utf-8"))

    def _read_exif(self) -> dict[str, Any]:
        """read exif data from file"""
        self.data = self.asdict().copy()
        return self.data

    def __str__(self) -> str:
        return f"file: {self.file}\nexiftool: {self._exiftoolproc._exiftool}"

    def __enter__(self) -> Self:
        self._context_mgr = True
        self._commands: list[str] = []
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if exc_type:
            return False
        elif self._commands:
            # run_commands sets self.warning and self.error as needed
            self.run_commands(*self._commands)
        return None


class ExifToolCaching(ExifTool):
    """Basic exiftool interface for reading and writing EXIF tags, with caching.
    Use this only when you know the file's EXIF data will not be changed by any external process.

    Creates a singleton cached ExifTool instance"""

    _singletons: ClassVar[dict[str | os.PathLike[str], _ExifToolCaching]] = {}

    # __new__ deliberately returns a cached _ExifToolCaching, which is an ExifTool
    # but not an ExifToolCaching (so ExifToolCaching.__init__ is never run)
    def __new__(  # type: ignore[misc]  # returns a sibling class, see above
        cls, filepath: str | os.PathLike[str], exiftool: str | None = None
    ) -> _ExifToolCaching:
        """create new object or return instance of already created singleton"""
        if filepath not in cls._singletons:
            cls._singletons[filepath] = _ExifToolCaching(filepath, exiftool=exiftool)
        return cls._singletons[filepath]


class _ExifToolCaching(ExifTool):
    def __init__(
        self, filepath: str | os.PathLike[str], exiftool: str | None = None
    ) -> None:
        """Create read-only ExifTool object that caches values

        Args:
            file: path to image file
            exiftool: path to exiftool, if not specified will look in path

        Returns:
            ExifTool instance
        """
        self._json_cache: str | None = None
        self._asdict_cache: dict[bool, dict[bool, dict[str, Any]]] = {}
        super().__init__(filepath, exiftool=exiftool, overwrite=False, flags=None)

    def run_commands(
        self, *commands: str, no_file: bool = False
    ) -> tuple[bytes, str, str]:
        if commands[0] not in ["-json", "-ver"]:
            raise NotImplementedError(f"{self.__class__} is read-only")
        return super().run_commands(*commands, no_file=no_file)

    def setvalue(self, tag: str, value: Any) -> bool:
        raise NotImplementedError(f"{self.__class__} is read-only")

    def addvalues(self, tag: str, *values: Any) -> bool:
        raise NotImplementedError(f"{self.__class__} is read-only")

    def json(self) -> str:
        if not self._json_cache:
            self._json_cache = super().json()
        return self._json_cache

    def asdict(
        self, tag_groups: bool = True, normalized: bool = False
    ) -> dict[str, Any]:
        """return dictionary of all EXIF tags and values from exiftool
        returns empty dict if no tags

        Args:
            tag_groups: if True (default), dict keys have tag groups, e.g. "IPTC:Keywords"; if False, drops groups from keys, e.g. "Keywords"
            normalized: if True, dict keys are all normalized to lower case (default is False)
        """
        try:
            return self._asdict_cache[tag_groups][normalized]
        except KeyError:
            if tag_groups not in self._asdict_cache:
                self._asdict_cache[tag_groups] = {}
            self._asdict_cache[tag_groups][normalized] = super().asdict(
                tag_groups=tag_groups, normalized=normalized
            )
            return self._asdict_cache[tag_groups][normalized]

    def flush_cache(self) -> None:
        """Clear cached data so that calls to json or asdict return fresh data"""
        self._json_cache = None
        self._asdict_cache = {}


def convert_dict_to_unquoted_json(data: dict[Any, Any] | list[Any]) -> str:
    """Convert a dict to a JSON-like format where keys are unquoted. This is needed to feed structs to exiftool.

    Reference: https://exiftool.org/forum/index.php?topic=15629.msg83986#msg83986
    """

    def process_value(v: Any) -> str:
        if isinstance(v, (dict, list)):
            return convert_dict_to_unquoted_json(v)
        elif isinstance(v, str):
            return v
        else:
            return str(v)

    if isinstance(data, dict):
        items = [f"{k}={process_value(v)}" for k, v in data.items()]
        return "{" + ",".join(items) + "}"
    elif isinstance(data, list):
        items = [process_value(v) for v in data]
        return "[" + ",".join(items) + "]"
    else:
        return str(data)
