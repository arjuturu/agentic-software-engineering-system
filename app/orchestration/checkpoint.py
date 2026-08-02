import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from app.config import Settings
from app.core.exceptions import ApplicationError


class CheckpointManager:
    def __init__(self, settings: Settings) -> None:
        prefix = "sqlite:///"
        url = settings.LANGGRAPH_DATABASE_URL
        if not url.startswith(prefix) or url == prefix:
            raise ApplicationError("The checkpoint database is invalid.", "CHECKPOINT_FAILURE", 500)
        raw_path = url.removeprefix(prefix)
        path = Path(raw_path)
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.checkpointer = SqliteSaver(self.connection)
        self.checkpointer.setup()

    def close(self) -> None:
        self.connection.close()
