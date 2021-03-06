# -*- coding: utf-8 -*-
#
import appdirs
try:
    import configparser
except ImportError:
    import ConfigParser as configparser
from datetime import datetime
from distutils.version import LooseVersion
import json
import os
from sys import platform


class _bash_color:
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    DARKCYAN = '\033[36m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


_config_dir = appdirs.user_config_dir('pipdated')
if not os.path.exists(_config_dir):
    os.makedirs(_config_dir)
_config_file = os.path.join(_config_dir, 'config.ini')

_log_dir = appdirs.user_log_dir('pipdated', 'Nico Schlömer')
if not os.path.exists(_log_dir):
    os.makedirs(_log_dir)
_log_file = os.path.join(_log_dir, 'times.log')


def _get_seconds_between_checks():
    if not os.path.exists(_config_file):
        # add default config
        parser = configparser.ConfigParser()
        parser.set('DEFAULT', 'SecondsBetweenChecks', str(24*60*60))
        with open(_config_file, 'w') as handle:
            parser.write(handle)

    # read config
    config = configparser.ConfigParser()
    config.read(_config_file)

    return config.getint('DEFAULT', 'SecondsBetweenChecks')


def _get_last_check_time(name):
    if not os.path.exists(_log_file):
        return None
    with open(_log_file, 'r') as handle:
        d = json.load(handle)
        if name in d:
            last_checked = datetime.strptime(
                d[name],
                '%Y-%m-%d %H:%M:%S'
                )
        else:
            return None
    return last_checked


def _log_time(name, time):
    if os.path.exists(_log_file):
        with open(_log_file, 'r') as handle:
            d = json.load(handle)
    else:
        d = {}

    d[name] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(_log_file, 'w') as handle:
        json.dump(d, handle)
    return


def needs_checking(name):
    seconds_between_checks = _get_seconds_between_checks()

    if seconds_between_checks < 0:
        return False

    # get the last time we checked and compare with seconds_between_checks
    last_checked = _get_last_check_time(name)
    return last_checked is None or \
        (datetime.now() - last_checked).total_seconds() \
        > seconds_between_checks


def get_pypi_version(name):
    import requests
    try:
        r = requests.get('https://pypi.python.org/pypi/%s/json' % name)
    except requests.ConnectionError:
        raise RuntimeError('Failed connection.')
    if not r.ok:
        raise RuntimeError(
            'Response code %s from pypi.python.org.' % r.status_code
            )
    data = r.json()
    return data['info']['version']


def check(name, installed_version, semantic_versioning=True):
    try:
        upstream_version = get_pypi_version(name)
    except RuntimeError:
        return None
    _log_time(name, datetime.now())

    iv = LooseVersion(installed_version)
    uv = LooseVersion(upstream_version)
    if iv < uv:
        return _get_message(
            name, iv, uv, semantic_versioning=semantic_versioning
            )

    return None


def _change_in_leftmost_nonzero(a, b):
    leftmost_changed = False
    for k in range(min(len(a), len(b))):
        if a[k] == 0 and b[k] == 0:
            continue
        leftmost_changed = (a[k] != b[k])
        break
    return leftmost_changed


def _get_message(name, iv, uv, semantic_versioning):
    messages = []
    messages.append(
        'Upgrade to   ' +
        _bash_color.GREEN +
        '%s %s' % (name, uv.vstring) +
        _bash_color.END +
        '    available! (installed: %s)\n' % iv.vstring
        )
    # Check if the leftmost nonzero version number changed. If yes, this means
    # an API change according to Semantic Versioning.
    if semantic_versioning and \
            _change_in_leftmost_nonzero(iv.version, uv.version):
        messages.append(
           (_bash_color.YELLOW +
            '%s\'s API changes in this upgrade. '
            'Changes to your code may be necessary.\n' +
            _bash_color.END
            ) % name
           )
    if platform == 'linux' or platform == 'linux2':
        messages.append((
            'To upgrade %s with pip, type\n\n'
            '   pip install -U %s\n\n'
            'To upgrade _all_ pip-installed packages, type\n\n'
            '   pipdate\n'
            ) % (name, name))

    messages.append(
        'To disable these checks, '
        'set SecondsBetweenChecks in %s to -1.' % _config_file
        )

    return '\n'.join(messages)
