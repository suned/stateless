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
