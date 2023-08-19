import logging
import os
import typing as T
from datetime import datetime
from pathlib import Path

from sqlalchemy.sql import exists, func, select

from scrat.db import DBConnector, Nut

from .config import Config, DeletionMethod
from .hasher import Hasher, HashManager
from .serializer import Serializer

logger = logging.getLogger(__name__)


class Squirrel:
    """
    Stash manager, in charge of fetching and storing the Nuts.

    Parameters
    ----------
    serializer
        Select a serializer for the function's result, by default a good
        serializer is inferred from the typehint, using `PickleSerializer` as
        the fallback.
    name
        Name that identifies this function, by default the function name is used.
    hashers
        Dictionary specifying hashers used for the arguments, by default hashers
        are selected according to the type of the argument, using `ToStringHasher`
        as the fallback.
    hash_code
        Control if the function's code should be used in the hash, by default True.
    ignore_args
        List of arguments to ignore from the hash, by default None
    watch_functions
        List of functions which code should be included in the hash, by default None
    watch_globals
        List of global variables to include in the hash, by default None
    force
        If set to True the stash is ignored, the function is called and the result
        is saved to the stash, by default the global setting `scrat.Setting.force` is
        used
    disable
        If set to True the stash is ignored, the function called and the result
        is **not** saved, by default the global setting `scrat.Setting.disable` is used

    """

    def __init__(
        self,
        name: str,
        serializer: Serializer,
        hashers: T.Optional[T.Dict[str, Hasher]] = None,
        hash_code: T.Optional[bool] = True,
        ignore_args: T.Optional[T.List[str]] = None,
        watch_functions: T.Optional[T.List[T.Any]] = None,
        watch_globals: T.Optional[T.List[str]] = None,
        force: T.Optional[bool] = None,
        disable: T.Optional[bool] = None,
        max_size: T.Optional[int] = None,
    ) -> None:
        self.config = Config.load()
        self.name = name
        self.force = force if force is not None else self.config.force
        self.disable = disable if disable is not None else self.config.disable
        self.max_size = max_size
        self.db_connector = DBConnector(self.config.db_path)
        self.hash_manager = HashManager(
            hashers=hashers,
            ignore_args=ignore_args,
            hash_code=hash_code,
            watch_functions=watch_functions,
            watch_globals=watch_globals,
        )
        self.serializer = serializer

    def hash(
        self, args: T.List[T.Any], kwargs: T.Dict[str, T.Any], func: T.Callable
    ) -> str:
        """
        Calculate the hash for a function call.

        Parameters
        ----------
        args
            positional arguments.
        kwargs
            keyword arguments.
        func
            the function to be called.

        Returns
        -------
            the hash-string resulting of combining all argument and code hashes.
        """
        hash_key = self.hash_manager.hash(args=args, kwargs=kwargs, func=func)
        logger.debug("Hash key for %s is '%s'", self.name, hash_key)
        return hash_key

    def exists(self, hash_key: str) -> bool:
        """
        Check if the hash exists

        Parameters
        ----------
        hash_key
            The hash-string calculated in `Squirrel.hash`.

        Returns
        -------
            Whether the hash exists or not.
        """
        if self.force or self.disable:
            logger.debug(
                "Forcing the result or scrat is disable, not reusing the result"
            )
            return False

        with self.db_connector.session() as session:
            return session.query(exists().where(Nut.hash == hash_key)).scalar()

    def fetch(self, hash_key: str) -> T.Any:
        """
        Fetch and recover a result from the stash.

        Parameters
        ----------
        hash_key
            The hash-string calculated in `Squirrel.hash`.

        Returns
        -------
            The result loaded into memory.
        """
        logger.debug("Fetching '%s' for %s", hash_key, self.name)

        with self.db_connector.session() as session:
            nut = session.scalar(select(Nut).where(Nut.hash == hash_key))
            result = self.serializer.load(Path(nut.path))
            nut.use_count = nut.use_count + 1
            nut.used_at = datetime.now()
            session.commit()
        return result

    def stash(self, hash_key: str, time_s: int, result: T.Any):
        """
        Stores a result.

        Parameters
        ----------
        hash_key
            The hash-string calculated in `Squirrel.hash`.
        time_s
            Execution time of the underlying function.
        result
            the result of the underlying function.
        """
        if self.disable:
            logger.debug("Scrat is disable, not saving")
            return

        with self.db_connector.session() as session:
            if self.max_size is not None:
                current_size, count = (
                    session.query(func.sum(Nut.size), func.count(Nut.hash))
                    .filter(Nut.name == self.name)
                    .first()
                )
                if count == 0:
                    current_size = 0

                while current_size >= self.max_size:
                    logger.debug("Size limit hit, freeing space")

                    if self.config.deletion_method == DeletionMethod.lru:
                        to_delete = (
                            session.query(Nut)
                            .filter(Nut.name == self.name)
                            .order_by(func.ifnull(Nut.used_at, Nut.created_at))
                            .first()
                        )
                        logger.info("Removing %s", to_delete)

                    elif self.config.deletion_method == DeletionMethod.lru:
                        to_delete = (
                            session.query(Nut)
                            .filter(Nut.name == self.name)
                            .order_by(Nut.use_count)
                            .first()
                        )
                        logger.info("Removing %s", to_delete)
                    else:
                        logger.error(
                            "Incorrect DeletionMethod %s", self.config.deletion_method
                        )
                        break

                    os.remove(to_delete.path)
                    session.delete(to_delete)
                    session.commit()
                    current_size -= to_delete.size

            logger.debug("Storing '%s' for %s", hash_key, self.name)
            path = self.config.cache_path / f"{self.name}_{hash_key}"
            self.serializer.dump(result, path)
            file_size = round(os.stat(path).st_size)

            nut = Nut(
                hash=hash_key,
                name=self.name,
                path=str(path),
                created_at=datetime.now(),
                used_at=None,
                size=file_size,
                use_count=0,
                time_s=time_s,
            )
            session.add(nut)
            session.commit()
