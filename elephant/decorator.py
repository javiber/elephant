import functools
import logging
import os
import typing as T
from datetime import datetime

from .cache import CacheManager
from .hasher import Hasher, HashManager
from .serializer import Serializer, get_default_serializer
from .utils import Timer

logger = logging.getLogger(__name__)


def remember(
    serializer: T.Optional[Serializer] = None,
    name: T.Optional[str] = None,
    hashers: T.Optional[T.Dict[str, Hasher]] = None,
    hash_code: T.Optional[bool] = True,
    ignore_args: T.Optional[T.List[str]] = None,
    watch_functions: T.Optional[T.List[T.Any]] = None,
    watch_globals: T.Optional[T.List[str]] = None,
):
    def deco(func):
        hash_manager = HashManager(
            hashers=hashers,
            name=name if name is not None else func.__name__,
            ignore_args=ignore_args,
            hash_code=hash_code,
            watch_functions=watch_functions,
            watch_globals=watch_globals,
        )
        _serializer = (
            serializer if serializer is not None else get_default_serializer(func)
        )
        cache_manager = CacheManager()

        timer = Timer()

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            hash_key = hash_manager.hash(args, kwargs, func)

            if cache_manager.exists(hash_key):
                logger.info("Cache hit %s", hash_key)
                entry = cache_manager.get(hash_key)
                result = _serializer.load(entry.path)
                cache_manager.update_usage(entry)
                return result

            logger.info("Cache miss %s", hash_key)
            timer.start()
            result = func(*args, **kwargs)
            func_time = timer.end()
            path = cache_manager.new(hash_key)
            _serializer.dump(result, path)

            entry = cache_manager.new_entry(
                hash=hash_key,
                name=hash_manager.name,
                path=str(path),
                time_s=func_time,
            )
            cache_manager.add(entry)

            return result

        return wrapper

    return deco
