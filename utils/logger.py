import logging
import os
import sys


RESET = '\x1b[0m'
DIM = '\x1b[2m'
BOLD = '\x1b[1m'
BLUE = '\x1b[34m'
CYAN = '\x1b[36m'
GREEN = '\x1b[32m'
YELLOW = '\x1b[33m'
RED = '\x1b[31m'
MAGENTA = '\x1b[35m'


def singleton(cls):
    instances = {}

    def _singleton(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return _singleton


class ColorFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.INFO: CYAN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: RED,
        logging.DEBUG: MAGENTA,
    }

    def __init__(self, use_color):
        super().__init__('[%(asctime)s] %(levelname)-7s %(message)s', '%H:%M:%S')
        self.use_color = use_color

    def format(self, record):
        original_levelname = record.levelname
        if self.use_color:
            color = self.LEVEL_COLORS.get(record.levelno, '')
            record.levelname = f'{color}{record.levelname}{RESET}'
        formatted = super().format(record)
        record.levelname = original_levelname
        return formatted


@singleton
class Logger:
    def __init__(self):
        self.logger = logging.getLogger('codeql_analysis_jar')
        self.logger.handlers.clear()
        self.logger.propagate = False

        use_color = self._supports_color()
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(ColorFormatter(use_color))

        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        self.use_color = use_color

    @staticmethod
    def _supports_color():
        if os.environ.get('NO_COLOR'):
            return False
        if os.environ.get('FORCE_COLOR'):
            return True
        return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()


def style(text, color='', bold=False, dim=False):
    logger = Logger()
    if logger.use_color is False:
        return text

    prefix = ''
    if bold:
        prefix += BOLD
    if dim:
        prefix += DIM
    if color:
        prefix += color
    return f'{prefix}{text}{RESET}'


def banner(title):
    line = '=' * 78
    log.info(style(line, color=BLUE, bold=True))
    log.info(style(title, color=BLUE, bold=True))
    log.info(style(line, color=BLUE, bold=True))


def section(title):
    log.info('')
    log.info(style(f'[{title}]', color=BLUE, bold=True))


def item(label, value):
    colored_label = style(f'{label}:', color=CYAN, bold=True)
    log.info('  %-20s %s', colored_label, value)


def step(message):
    log.info('  %s %s', style('->', color=BLUE, bold=True), message)


def success(message):
    log.info('  %s %s', style('[OK]', color=GREEN, bold=True), message)


def warning(message):
    log.warning('  %s %s', style('[WARN]', color=YELLOW, bold=True), message)


def failure(message):
    log.error('  %s %s', style('[ERROR]', color=RED, bold=True), message)


def note(message):
    log.info('  %s %s', style('[INFO]', color=CYAN, bold=True), message)


def duration(seconds):
    if seconds < 60:
        return f'{seconds:.1f}s'
    minutes, remain = divmod(seconds, 60)
    return f'{int(minutes)}m {remain:.1f}s'


def percent(current, total):
    if total <= 0:
        return '0%'
    return f'{(current / total) * 100:.0f}%'


log = Logger().logger
