from __future__ import annotations

import atexit
import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver


def create_sqlite_checkpointer(path: str | Path) -> SqliteSaver:
    checkpoint_path = Path(path)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(checkpoint_path, check_same_thread=False)
    atexit.register(connection.close)
    checkpointer = SqliteSaver(connection)
    checkpointer.setup()
    return checkpointer
