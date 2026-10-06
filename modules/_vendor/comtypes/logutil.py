# logutil.py
import functools
import logging
import warnings
import re
from ctypes import WinDLL
from ctypes.wintypes import LPCSTR, LPCWSTR
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

_kernel32 = WinDLL("kernel32")

_OutputDebugStringA = _kernel32.OutputDebugStringA
_OutputDebugStringA.argtypes = [LPCSTR]
_OutputDebugStringA.restype = None

_OutputDebugStringW = _kernel32.OutputDebugStringW
_OutputDebugStringW.argtypes = [LPCWSTR]
_OutputDebugStringW.restype = None


class NTDebugHandler(logging.Handler):
    def emit(
        self,
        record,
        writeW=_OutputDebugStringW,
    ):
        text = self.format(record)
        writeW(text + "\n")


logging.NTDebugHandler = NTDebugHandler


def deprecated(reason: str):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            warnings.warn(reason, category=DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)

        return wrapper

    return decorator


@deprecated("Deprecated. See https://github.com/enthought/comtypes/issues/920.")
def setup_logging(*pathnames):
    import configparser

    parser = configparser.ConfigParser()
    parser.optionxform = str  # use case sensitive option names!

    parser.read(pathnames)

    DEFAULTS = {
        "handler": "StreamHandler()",
        "format": "%(levelname)s:%(name)s:%(message)s",
        "level": "WARNING",
    }

    # Безопасный словарь разрешенных хендлеров
    SAFE_HANDLERS = {
        "StreamHandler": logging.StreamHandler,
        "FileHandler": logging.FileHandler,
        "NullHandler": logging.NullHandler,
        "RotatingFileHandler": RotatingFileHandler,
        "TimedRotatingFileHandler": TimedRotatingFileHandler,
    }

    def get(section, option):
        try:
            return parser.get(section, option, True)
        except (configparser.NoOptionError, configparser.NoSectionError):
            return DEFAULTS[option]

    levelname = get("logging", "level")
    format = get("logging", "format")
    handlerclass = get("logging", "handler")

    # convert level name to level value
    level = getattr(logging, levelname)
    
    # ИСПРАВЛЕНО: безопасное создание хендлера без eval
    # Извлекаем имя класса из строки вроде "FileHandler('log.txt')"
    # Используем регулярное выражение для безопасного извлечения имени класса
    handler_match = re.match(r'(\w+)(?:\s*\([^)]*\))?', handlerclass.strip())
    
    if handler_match:
        handler_name = handler_match.group(1)
        if handler_name in SAFE_HANDLERS:
            # Создаем безопасный хендлер
            handler_class = SAFE_HANDLERS[handler_name]
            handler = handler_class()  # Пока без аргументов, для безопасности
        else:
            # по умолчанию используем StreamHandler
            handler = logging.StreamHandler()
    else:
        handler = logging.StreamHandler()
    
    formatter = logging.Formatter(format)
    handler.setFormatter(formatter)
    logging.root.addHandler(handler)
    logging.root.setLevel(level)

    try:
        for name, value in parser.items("logging.levels", True):
            value = getattr(logging, value)
            logging.getLogger(name).setLevel(value)
    except configparser.NoSectionError:
        pass