from typing import Protocol
from typing_extensions import Never
from dataclasses import dataclass
from abc import ABC, abstractmethod


from stateless.effect import Effect, fail


class Files(ABC):
    @abstractmethod
    def read_file(self, path: str) -> str:
        pass

    @abstractmethod
    def write_file(self, path: str, content: str) -> None:
        pass


def read_file(path: str) -> Effect[Files, FileNotFoundError | PermissionError, str]:
    try:
        files = yield Files
        return files.read_file(path)
    except (FileNotFoundError, PermissionError) as e:
        return (yield from fail(e))


class LiveFiles(Files):
    def read_file(self, path: str) -> str:
        with open(path) as f:
            return f.read()

    def write_file(self, path: str, content: str) -> None:
        with open(path, "w") as f:
            f.write(content)
