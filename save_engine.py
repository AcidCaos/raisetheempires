import copy
from datetime import datetime
from flask import session


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
