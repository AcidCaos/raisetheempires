import copy
import configparser
import json
import os
import shutil
import sys
from datetime import datetime
from functools import reduce
from pathlib import Path

import daiquiri
import editor
from flask import session,current_app
import logging

from flask_session.sqlalchemy import SqlAlchemySessionInterface
from flask_sqlalchemy import SQLAlchemy
from itsdangerous import want_bytes
try:
    import cPickle as pickle
except ImportError:
    import pickle


crash_log = True

db = SQLAlchemy()

def lookup_object(id):
    [game_object] = [e for e in session['user_object']["userInfo"]["world"]["objects"] if e['id'] == id]
    return game_object


def lookup_object_save(save, id):
    [game_object] = [e for e in save['user_object']["userInfo"]["world"]["objects"] if e['id'] == id]
    return game_object


def lookup_objects_by_item_name(id):
    return [e for e in session['user_object']["userInfo"]["world"]["objects"] if e['itemName'] == id]


def lookup_objects_save_by_position(save, x, y, r):
    return [e for e in save['user_object']["userInfo"]["world"]["objects"]
            if x <= int(e["position"].split(",")[0]) <= (x + r) and
            y <= int(e["position"].split(",")[1]) <= (y + r)]


def create_backup(message):
    timestamp = datetime.now().timestamp()
    session["backup"] = copy.deepcopy({k: v for k, v in session.items() if
                         k in ['user_object', 'quests', 'battle', 'fleets', 'population', 'saved', 'saved_on',
                               'save_version', 'original_save_version', 'backup']})  # nested backups
    session['saved_on'] = timestamp
    session["backup"]['replaced_on'] = timestamp
    session["backup"]['message'] = message

def save_database_uri(root_path, instance_path):
    save_db_path = os.path.join(my_games_path(), "save.db")

    if os.path.samefile(my_games_path(), root_path):
        new_save_db_path = os.path.join(instance_path, "save.db")
        if os.path.exists(save_db_path):
            if not os.path.exists(new_save_db_path):
                print("INFORMATION: You're running from source, and because of Flask update save.db has to be moved to the instance folder. Installs out of folder should be unaffected")
                if not os.path.exists(instance_path):
                    os.makedirs(instance_path)
                backup_save_dir_path = os.path.join(my_games_path(), "backup-save-db")
                if not os.path.exists(backup_save_dir_path):
                    os.makedirs(backup_save_dir_path)
                shutil.copy(save_db_path, backup_save_dir_path)
                shutil.move(save_db_path, new_save_db_path)
                print("Moved your save.db to", instance_path, "and a backup can be found at", backup_save_dir_path)
            else:
                print("WARNING: You have a save.db in both the root as the instance folder (when running from source), only the instance one will be used!")
        save_db_path = new_save_db_path

    print("SQLITE", f"sqlite:///{save_db_path}")

    return f"sqlite:///{save_db_path}"


def my_games_path():
    return config['InstallFolders']['MyGamesPath']


def install_path():
    return config['InstallFolders']['InstallPath']


def log_path():
    if os.path.exists(my_games_path()):
        return my_games_path()
    else:
        print("Warning: folder in My games missing, falling back to install folder.")
        return "."


def set_crash_log(toggle):
    global crash_log

    crash_log = toggle


def exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    if crash_log:
        text = editor.edit(filename=os.path.join(log_path(), "log.txt"))

# logger = logging.getLogger(__name__)
# handler = logging.StreamHandler(stream=sys.stdout)
# logger.addHandler(handler)


config = configparser.ConfigParser()
config.read('RaiseTheEmpires.ini')

daiquiri.setup(level=logging.INFO, outputs=(
    daiquiri.output.Stream(sys.stdout),
    daiquiri.output.File(os.path.join(log_path(), "log.txt"), formatter=daiquiri.formatter.TEXT_FORMATTER),
    ))
logger = daiquiri.getLogger(__name__)

sys.excepthook = exception_handler


def get_all_sessions():
    sess_int: SqlAlchemySessionInterface = current_app.session_interface
    sess_model = sess_int.sql_session_model
    # record = sess_model.query.filter_by(
    #         id=17).first()
    records = sess_model.query.all()
    return records

def decode_save(serialized_save):
    try:
        sess_int: SqlAlchemySessionInterface = current_app.session_interface
        return sess_int.serializer.decode(serialized_save)
    except Exception as e:
        print("Skipping corrupt save")
        print(e)
        return None


def get_saves():
    return [enrich_save(save, record) for record in get_all_sessions() for save in [decode_save(want_bytes(record.data))] if save is not None and 'user_object' in save]


def enrich_save(save, record):
    save["session_id"] = record.session_id
    return save


def store_session(save):
    sess_int: SqlAlchemySessionInterface = current_app.session_interface
    sess_model = sess_int.sql_session_model
    record = sess_model.query.filter_by(
            session_id=save["session_id"]).first()

    record.data = pickle.dumps(dict(save))
    sess_int.db.session.commit()


def validate_save(save, blank_allowed = False):
    player = get_dict(save, "user_object", "userInfo", "player")
    return (isinstance(player.get("level"), int) and
            isinstance(player.get("uid", {}), int) and
            isinstance(get_dict(save, "user_object", "userInfo").get("worldName"), str) and
            isinstance(player.get("xp", {}), (int, float)) and
            isinstance(player.get("playerResourceType", {}), int) and
            isinstance(get_dict(save, "user_object", "userInfo", "world", "resources").get("coins"), (int, float)) and
            isinstance(player.get("socialXpGood", {}), (int, float)) and
            isinstance(player.get("socialLevelGood", {}), int) and
            isinstance(player.get("socialXpBad", {}), (int, float)) and
            isinstance(player.get("socialLevelBad", {}), int)) or \
           (blank_allowed and 'user_object' not in save)


def get_dict(*args):
    return reduce((lambda a, b: a.get(b, {}) if isinstance(a.get(b, {}), dict) else {}), args)


class InvalidSaveException(Exception):
    """Exception when save is invalid while loading."""
    pass

