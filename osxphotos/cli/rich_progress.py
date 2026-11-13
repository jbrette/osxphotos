"""rich Progress bar factory that can return a rich Progress bar or a mock Progress bar"""

import os
from types import TracebackType
from typing import Any, Self

from rich.console import Console
from rich.progress import GetTimeCallable, Progress, ProgressColumn, TaskID

# set to 1 if running tests
OSXPHOTOS_IS_TESTING = bool(os.getenv("OSXPHOTOS_IS_TESTING"))


class MockTask:
    """A mock task object similar to rich.progress.Task."""

    def __init__(
        self, task_id: TaskID, description: str = "", total: float | None = 100
    ) -> None:
        self.id = task_id
        self.description = description
        self.total = total
        self.completed: float = 0
        self.finished = False

    def advance(self, advance: float) -> None:
        """Advance completed by advance steps"""
        self.completed += advance


class MockProgress:
    """A mock version of rich.Progress for testing purposes."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.tasks: list[MockTask | None] = []
        self.live = False
        self.console: Console | None = kwargs.get("console")
        self.auto_refresh: bool = kwargs.get("auto_refresh", True)
        self.transient: bool = kwargs.get("transient", False)

    # --- Context manager methods ---
    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.stop()

    # --- Lifecycle methods ---
    def start(self) -> None:
        self.live = True

    def stop(self) -> None:
        self.live = False

    def refresh(self) -> None:
        pass  # dummy method, does nothing

    # --- Task management ---
    def _active_task(self, task_id: TaskID) -> MockTask:
        """Return task for task_id; raise KeyError if the task was removed"""
        task = self.tasks[task_id]
        if task is None:
            raise KeyError(task_id)
        return task

    def add_task(
        self, description: str = "", total: float | None = 100, **kwargs: Any
    ) -> TaskID:
        task_id = TaskID(len(self.tasks))
        task = MockTask(task_id, description, total)
        self.tasks.append(task)
        return task_id

    def update(
        self,
        task_id: TaskID,
        advance: float | None = 0,
        completed: float | None = None,
        total: float | None = None,
        **kwargs: Any,
    ) -> MockTask:
        task = self._active_task(task_id)
        if completed is not None:
            task.completed = completed
        if total is not None:
            task.total = total
        if advance:
            task.advance(advance)
        return task

    def advance(self, task_id: TaskID, advance: float = 1) -> None:
        pass
        # task = self.tasks[task_id]
        # task.advance(advance)

    def remove_task(self, task_id: TaskID) -> None:
        self.tasks[task_id] = None  # keep index stable

    def get_task(self, task_id: TaskID) -> MockTask | None:
        return self.tasks[task_id]

    # --- Output simulation ---
    def print(self, *args: Any, **kwargs: Any) -> None:
        # mimic console.print()
        if self.console:
            self.console.print(*args, **kwargs)
        else:
            print(*args, **kwargs)

    # --- Misc / dummy API methods ---
    def __getitem__(self, task_id: TaskID) -> MockTask | None:
        return self.tasks[task_id]

    def __len__(self) -> int:
        return len(self.tasks)

    def reset(self, task_id: TaskID, total: float | None = None) -> None:
        task = self._active_task(task_id)
        task.completed = 0
        if total is not None:
            task.total = total
        task.finished = False

    def stop_task(self, task_id: TaskID) -> None:
        task = self._active_task(task_id)
        task.finished = True


def rich_progress(
    *columns: str | ProgressColumn,
    console: Console | None = None,
    auto_refresh: bool = True,
    refresh_per_second: float = 10,
    speed_estimate_period: float = 30.0,
    transient: bool = False,
    redirect_stdout: bool = True,
    redirect_stderr: bool = True,
    get_time: GetTimeCallable | None = None,
    disable: bool = False,
    expand: bool = False,
    mock: bool = False,
) -> Progress | MockProgress:
    """Return a rich.progress.Progress object unless mock=True or os.getenv("OSXPHOTOS_IS_TESTING") is set"""
    # if OSXPHOTOS_IS_TESTING is set or mock=True, return a MockProgress object
    if mock or OSXPHOTOS_IS_TESTING:
        return MockProgress()
    return Progress(
        *columns,
        console=console,
        auto_refresh=auto_refresh,
        refresh_per_second=refresh_per_second,
        speed_estimate_period=speed_estimate_period,
        transient=transient,
        redirect_stdout=redirect_stdout,
        redirect_stderr=redirect_stderr,
        get_time=get_time,
        disable=disable,
        expand=expand,
    )
