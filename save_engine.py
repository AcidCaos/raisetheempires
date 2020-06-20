import copy
import configparser
import json
import os
import sys
from datetime import datetime
import daiquiri
import editor
from flask import session,current_app
import logging

from flask_session import SqlAlchemySessionInterface
from itsdangerous import want_bytes
try:
    import cPickle as pickle
except ImportError:
    import pickle

crash_log = True

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

def save_database_uri():
    save_db_path = os.path.join(my_games_path(), "save.db")
    print(save_db_path)
    print(os.path.exists(save_db_path))
    if not os.path.exists(save_db_path):
        print("ERROR: save.db cannot be found on '" + str(save_db_path) + "'. Uninstall and re-install if possible.")
        raise Exception("ERROR: save.db cannot be found on '" + str(save_db_path) + "'. Uninstall and re-install if possible.")
    return 'sqlite:///' + save_db_path


def my_games_path():
    return config['InstallFolders']['MyGamesPath']


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


def get_saves():
    return [enrich_save(save, record) for record in get_all_sessions() for save in [pickle.loads(want_bytes(record.data))] if 'user_object' in save]


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
    return (isinstance(save.get('user_object', {}).get("userInfo", {}).get("player", {}).get("level", {}), int) and \
            isinstance(save.get('user_object', {}).get("userInfo", {}).get("player", {}).get("uid", {}), int) and \
            isinstance(save.get('user_object', {}).get("userInfo", {}).get("worldName", {}), str) and \
            isinstance(save.get('user_object', {}).get("userInfo", {}).get("player", {}).get("xp", {}), int) and \
            isinstance(save.get('user_object', {}).get("userInfo", {}).get("player", {}).get("playerResourceType", {}), int) and \
            isinstance(save.get('user_object', {}).get("userInfo", {}).get("world", {}).get("resources", {}).get("coins", {}), int) and \
            isinstance(save.get('user_object', {}).get("userInfo", {}).get("player", {}).get("socialXpGood", {}), int) and \
            isinstance(save.get('user_object', {}).get("userInfo", {}).get("player", {}).get("socialLevelGood", {}), int) and \
            isinstance(save.get('user_object', {}).get("userInfo", {}).get("player", {}).get("socialXpBad", {}), int) and \
            isinstance(save.get('user_object', {}).get("userInfo", {}).get("player", {}).get("socialLevelBad", {}), int)) or \
           (blank_allowed and 'user_object' not in save)


class InvalidSaveException(Exception):
    """Exception when save is invalid while loading."""
    pass
