from os import environ as ENV
from pathlib import Path
import yaml

# note: toml.loads cannot load strings that toml.dumps writes,
#       especialy with complex data structures.
# For Py3.11+, we use toml.dumps() and tomllib.loads().
# For Py<3.11, we use toml.dumps() and tomli.loads().
import toml
try:
    import tomllib
except ImportError:
    import tomli as tomllib

from pyshortcuts.utils import get_homedir


def load_yaml(text):
    """very simple yaml loader"""
    return yaml.load(text, Loader=yaml.Loader)

def load_toml(text):
    """very simple toml loader"""
    return tomllib.loads(text)

def get_configfolder():
    """
    get an epicsapps config folder
    Returns:
        path name of config folder, typically $HOME/.config/epicsapps

    """
    escancred = ENV.get('ESCAN_CREDENTIALS', None)
    if escancred is not None:
        confdir = Path(escancred).parent
    else:
        confdir = Path(get_homedir(), '.config', 'epicsapps')

        if not confdir.exists():
            try:
                confdir.mkdir(mode=0o755, parents=True, exist_ok=True)
            except FileExistsError:
                pass
    return confdir.as_posix()

def get_default_configfile(fname):
    """get the default configfile, if it exists or None if it does not"""
    path = Path(get_configfolder(), fname)
    if path.exists():
        return path.as_posix()
    return None

def read_recents_file(fname='recent_ad_pvs.txt'):
    fpath = Path(get_configfolder(), fname)
    lines = ['#']
    out = []
    if fpath.exists():
        with open(fpath, 'r') as fh:
            lines = fh.readlines()
    for line in lines:
        if not line.startswith('#') and len(line) > 2:
            out.append(line[:-1])
    return out

def write_recents_file(fname='recent_ad_pvs.txt', nlist=None):
    if nlist is not None and len(nlist) > 0:
        fpath = Path(get_configfolder(), fname)
        with open(fpath, 'w') as fh:
            fh.write('\n'.join(nlist))

class ConfigFile(object):
    """
    Configuration File, using either YAML or TOML
    The ConfigFile will have attributes / methods:

    config:          dict of configuration data
    default_config:  factory default configuration data
    filename:         name of config file
    reset_default():  set config to factory default
    read(fname):     read config from file
    write(fname=None, config=None):  write config to file

    """
    def __init__(self, fname=None, default_config=None):
        self.filename = fname
        self.default_config = {}
        if default_config is not None:
            self.default_config.update(default_config)

        self.config = {}
        self.config.update(self.default_config)
        if fname is not None:
            self.read(fname)

    def reset_default(self):
        """reset config to initial / factory default"""
        self.config = {}
        self.config.update(self.default_config)

    def read(self, fname):
        """read config file

        Arguments:
            fname (str):  name of configuration file

        Notes:
           1. if the file is found in the current working folder or because the
              full path is given, that file will be read.
           2. if the file is not found, but a file with that name is found in
              the default configuration folder ($HOME/.config/epicsapps), that
              file will be read.

        """
        if fname is None:
            return
        fpath = Path(fname).absolute()
        if not fpath.exists():
            _path = Path(get_configfolder(), fname)
            if _path.exists():
                fpath  = _path

        if not fpath.exists():
            print("No config file to read: ", fname)
            self.config = self.default_config
            return

        self.filename = fpath.absolute().as_posix()
        stem  = fpath.suffix
        text = None
        with open(self.filename, 'r') as fh:
            text = fh.read()

        formats = ['yaml', 'toml']
        if fpath.suffix.endswith('toml'):
            formats = ['toml', 'yaml']
        for form in formats:
            if form == 'toml':
                try:
                    ret = tomllib.loads(text)
                    if isinstance(ret, dict):
                        self.config = ret
                except:
                    print("Warning could not read TOML Config")
            elif form == 'yaml':
                try:
                    ret = yaml.load(text, Loader=yaml.Loader)
                    if isinstance(ret, dict):
                        self.config = ret
                except:
                    pass

            if self.config is not None:
                break

    def write(self, fname=None, config=None):
        if fname is None:
            fname = self.filename

        if config is None:
            config = self.config

        fpath = Path(fname)
        if fpath.suffix == '.yaml':
            with open(fpath, 'w') as fh:
                yaml.dump(config, fh, default_flow_style=None)
        else:
            with open(fpath, 'w') as fh:
                fh.write(toml.dumps(config))
