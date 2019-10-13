import copy
import configparser
import json
import os
import sys
from datetime import datetime
import daiquiri
import editor
from flask import session
import logging

def lookup_object(id):
    [game_object] = [e for e in  session['user_object']["userInfo"]["world"]["objects"] if e['id'] == id]
    return game_object


def lookup_objects_by_item_name(id):
    return [e for e in session['user_object']["userInfo"]["world"]["objects"] if e['itemName'] == id]


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


def exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
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

