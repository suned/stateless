from stateless.effect import Depend, throws


class Files:
    def read_file(self, path: str) -> str:
        with open(path) as f:
            return f.read()

    def write_file(self, path: str, content: str) -> None:
        with open(path, "w") as f:
            f.write(content)


@throws(FileNotFoundError, PermissionError)
def read_file(path: str) -> Depend[Files, str]:
    files: Files = yield Files
    return files.read_file(path)
