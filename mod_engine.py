import os
from pathlib import Path

from save_engine import my_games_path, install_path
from xmldiff.main import patch_text
from jsonpatch import apply_patch
import init_settings as settings
import sys
from tqdm import tqdm
from base64 import b32encode

import xmldiff

import configparser
config = configparser.ConfigParser()

def read_file(file_name):
    with open(file_name, 'rb') as f:
        # print("Reading " + file_name)
        return f.read()

def write_file(file_name, content):
    with open(file_name, 'wb') as f:
        # print("Writing " + file_name)
        return f.write(content)

def is_mod(file_name):
    return is_xml_diff(file_name) or is_json_patch(file_name)


def is_xml_diff(file_name):
    return os.path.splitext(file_name)[1] == ".xmldiff"


def is_json_patch(file_name):
    return os.path.splitext(file_name)[1] == ".jsonpatch"


def apply_mod(source, mod_file, name):
    if is_xml_diff(name):
        return lambda: patch_text(read_file(mod_file), source())
    elif is_json_patch(name):
        return lambda: apply_patch(read_file(mod_file), source())
    else:
        return lambda: read_file(mod_file)


def get_cache_filename(original_path):
    return b32encode(original_path.encode()).decode("utf-8")


mod = {}
mod_folders = [os.path.join(install_path(), 'mods')]
mod_stats = []

if my_games_path() != install_path():
    mod_folders += [os.path.join(my_games_path(), 'mods')]

print("Loading mods...")

for mod_folder in mod_folders:
    if os.path.isfile(os.path.join(mod_folder, "mods.conf")):
        # config.read(.../mods.conf)
        config.read_string(open(os.path.join(mod_folder, "mods.conf"), 'r').read())
        if "mods" in config:
            #for mod_name in os.listdir(mod_folder):
            #for mod_name in mod_folders:
            for mod_name in config['mods']:
                #print("mod " + mod_name)
                if config['mods'][mod_name] == "false":
                    print("* mod " + mod_name + " is disabled")
                elif config['mods'][mod_name] == "true":
                    print("* mod " + mod_name + " is enabled")
                    if os.path.isdir(os.path.join(mod_folder, mod_name)):
                        for root, _, files in os.walk(os.path.join(mod_folder, mod_name)):
                            for name in files:
                                print(" -> ", root, name, os.path.join(root, name))
                                rel = os.path.relpath(root, os.path.join(mod_folder, mod_name))
                                source_file = Path(os.path.join(rel, os.path.splitext(name)[0] if is_mod(name) else name)).as_posix()
                                mod_file = os.path.join(root, name)
                                print(" | - rel " + rel)
                                print(" | - source_file " + source_file)
                                print(" | - mod_file " + mod_file)

                                source = mod.get(source_file, lambda: read_file(source_file))  # lambda chaining
                                mod[source_file] = apply_mod(source, mod_file, name)

                                stats = os.stat(mod_file)
                                mod_stats.append("%s: %i %i %i" % (mod_file, stats.st_size,stats.st_ctime_ns, stats.st_mtime_ns))
    else:
        print("mods.conf not found.")

cache_path = os.path.join(my_games_path(), 'cache')
if settings.caching:
    try:
        os.mkdir(cache_path)
    except FileExistsError:
        pass
    except OSError as error:
        print(error)
        print("WARNING: cache directory can't be created in ", my_games_path(), ", caching is disabled, this may decrease performance and increase loading times.")
        caching = False
else:
    print("WARNING: caching is disabled by choice, this may decrease performance and increase loading times.")

config_raw = repr({section: dict(config[section]) for section in config.sections()})
# for path in sorted(mod):
#     print(repr(os.stat(path)))

if settings.caching:

    if not os.path.exists(os.path.join(cache_path, 'mods.config.cache')) \
            or read_file(os.path.join(cache_path, 'mods.config.cache')) != config_raw.encode() or \
            not os.path.exists(os.path.join(cache_path, 'directory.cache')) \
            or read_file(os.path.join(cache_path, 'directory.cache')) != "\n".join(mod_stats).encode() :

        print("Updating cache")
        # Clear cache
        for filename in os.listdir(cache_path):
            file_path = os.path.join(cache_path, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print('ERROR: Failed to delete %s. Reason: %s' % (filename, e))
                print("Cache can't update, caching deactivated, this may decrease performance and increase loading times.")
                settings.caching = False
        # Write cache
        if settings.caching:
            for path in tqdm(sorted(mod), file=sys.stdout):
                try:
                    write_file(os.path.join(cache_path, get_cache_filename(path)), mod[path]())
                except Exception as e:
                    print('ERROR: Failed to write cache file %s. Reason: %s' % (get_cache_filename(path), e))
                    print("Cache can't update, caching deactivated, this may decrease performance and increase loading times.")
                    settings.caching = False
            if settings.caching:
                write_file(os.path.join(cache_path, 'mods.config.cache'), config_raw.encode())
                write_file(os.path.join(cache_path, 'directory.cache'), "\n".join(mod_stats).encode())
                print("Cache creation complete")
    else:
        print("Cache up to date")
    # Swap modded files with cache
    if settings.caching:
        for path in sorted(mod):
            if os.path.exists(os.path.join(cache_path, get_cache_filename(path))):
                mod[path] = lambda: read_file(os.path.join(cache_path, get_cache_filename(path)))
            else:
                print('ERROR: Cache miss, Cache file %s missing for original %s. ' % (get_cache_filename(path), path))
                print("This may decrease performance and increase loading times.")


print("mod " + repr(mod))
print("config " + config_raw)

