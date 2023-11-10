from typing import Protocol
from typing_extensions import Never
from dataclasses import dataclass
from abc import ABC, abstractmethod


from stateless.effect import Effect, throws, Depend


class Files:
    def read_file(self, path: str) -> str:
        with open(path) as f:
            return f.read()

    def write_file(self, path: str, content: str) -> None:
        with open(path, "w") as f:
            f.write(content)


@throws(FileNotFoundError, PermissionError)
def read_file(path: str) -> Depend[Files, str]:
    files = yield Files
    return files.read_file(path)
