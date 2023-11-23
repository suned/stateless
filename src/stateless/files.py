"""Files ability and ability helpers."""

from stateless.effect import Depend, throws


class Files:
    """The Files ability."""

    def read_file(self, path: str) -> str:
        """
        Read a file.

        Args:
        ----
            path: The path to the file.

        Returns:
        -------
            The contents of the file.
        """
        with open(path) as f:
            return f.read()

    def write_file(self, path: str, content: str) -> None:
        """
        Write a file.

        Args:
        ----
            path: The path to the file.
            content: The contents of the file.
        """
        with open(path, "w") as f:
            f.write(content)


@throws(FileNotFoundError, PermissionError)
def read_file(path: str) -> Depend[Files, str]:
    """
    Read a file.

    Args:
    ----
        path: The path to the file.

    Returns:
    -------
        The contents of the file as an effect.
    """
    files: Files = yield Files
    return files.read_file(path)
