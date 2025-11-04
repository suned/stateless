"""Files ability and ability helpers."""

from stateless.effect import Depend, throws
from stateless.need import Need, need


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
def read_file(path: str) -> Depend[Need[Files], str]:
    """
    Read a file.

    Args:
    ----
        path: The path to the file.

    Returns:
    -------
        The contents of the file as an effect.

    """
    files: Files = yield from need(Files)
    return files.read_file(path)
