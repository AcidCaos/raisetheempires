import os

from quest_settings import quest_titles

os.environ["PBR_VERSION"] = '5.4.3'
if not os.environ.get('EDITOR'):
    os.environ["EDITOR"] = 'notepad'  # system specific!

import editor
from tendo import singleton
from init_settings import *

if not debug:
    me = singleton.SingleInstance()


from save_engine import save_database_uri, log_path, lookup_objects_save_by_position, get_all_sessions, \
    store_session, validate_save, InvalidSaveException, set_crash_log, my_games_path, install_path
from save_migration import migrate, is_0_08a_preview
from builtins import print
from time import sleep
from datetime import timedelta

from flask import Flask, render_template, send_from_directory, request, Response, make_response, redirect, safe_join
from flask_session import Session
from pyamf import remoting
import pyamf

import mod_engine
from battle_engine import battle_complete_response, spawn_fleet, next_campaign_response, assign_consumable_response, \
    get_active_island_by_map, set_active_island_by_map, format_player_fleet, \
    cancel_unstarted_invasions, register_fleetname_fleet, get_last_fleet_name, is_shielded
from game_settings import get_zid, initial_island, random_image, randomReward, get_sessions_id, unlock_expansion, \
    lookup_wave, lookup_crew_template
import threading, webbrowser
import pyamf.amf0
import json
import xml.etree.ElementTree as ET
from flask_sqlalchemy import SQLAlchemy
from quest_engine import *
from state_machine import *
from logger import socketio, report_tutorial_step, report_world_log, report_other_log
import copy

try:
    from flask_compress import Compress
except ImportError as error:
    print("Warning: compression can't be initialized. Compression is disabled.", error)
    compression = False

# import logging.config

version = "0.07a.2022_01_15"
release_date = 'Saturday, 15 January 2022'

COMPRESS_MIMETYPES = ['text/html', 'text/css', 'text/xml', 'application/json', 'application/javascript',
                      'application/x-amf']
COMPRESS_LEVEL = 6
COMPRESS_MIN_SIZE = 500

# starting seeds
rand_seed_w = 5445  # very random
rand_seed_z = 844

compress = Compress() if compression else None
sess = Session()
db = SQLAlchemy()

start = datetime.now()

app: Flask = Flask(__name__)

app.config['SESSION_TYPE'] = 'sqlalchemy'
app.config['SQLALCHEMY_DATABASE_URI'] = save_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Flask-SQLAlchemy has its own event notification system that gets layered on top of SQLAlchemy. To do this, it tracks modifications to the SQLAlchemy session. This option disables the modification tracking system.
app.config['SESSION_SQLALCHEMY'] = db
app.config['SESSION_COOKIE_HTTPONLY'] = False
app.permanent_session_lifetime = timedelta(weeks=520)

MIN_ADMIN_ID = -1
STEELE_ID = -1
MAX_ADMIN_ID = 123

@app.route("/")
def index():
    return render_template("index.html", version=version, release_date=release_date)


@app.route("/home.html")
def home():
    print("home")
    if not validate_save(session, True):
        print("Invalid save game")
        return make_response(redirect('/save-editor')) #todo disable save editor toggle?
    saves = get_saves()
    return render_template("home.html", time=datetime.now().timestamp(), zid=str(get_zid()),
                           version=version,
                           allies=json.dumps(get_allies_friend(saves),
                                             default=lambda o: '<not serializable>', sort_keys=False, indent=2),
                           app_friends=json.dumps(get_allies_id(saves)),
                           computername=session['user_object']["userInfo"]["worldName"] if 'user_object' in session else "Emperor",
                           picture=get_avatar_pic(),
                           dropdown_items=get_sessions_dropdown_info(saves)
                           )


def get_allies_friend(saves):
    return [ally["friend"] for ally in allies.values()
            if "friend" in ally and ally["friend"] and ally["neighbor"]] + get_sessions_friends(saves)


def get_suggested_friends():
    return [ally["friend"] for ally in allies.values()
            if "friend" in ally and ally["friend"] and not ally["neighbor"]]


def get_allies_id(saves):
    return [ally["appFriendId"] for ally in allies.values()
            if "appFriendId" in ally and ally["appFriendId"] is not None] + get_sessions_id(saves)


def get_allies_info():
    return [ally["info"] for ally in allies.values() if ally["info"] and ally.get("neighbor")]+ get_sessions_info(
        get_saves())


@app.route("/nodebug.html")
def no_debug():
    print("no debug page")
    saves = get_saves()
    return render_template("nodebug.html", time=datetime.now().timestamp(), zid=str(get_zid()),
                           version=version,
                           allies=json.dumps(get_allies_friend(saves),
                                             default=lambda o: '<not serializable>', sort_keys=False, indent=2),
                           app_friends=json.dumps(get_allies_id(saves)),
                           picture=get_avatar_pic(),
                           dropdown_items=get_sessions_dropdown_info(saves)
                           )


@app.route("/wipe_session", methods=['GET', 'POST'])
def wipe_session():
    session.clear()
    response = make_response(redirect('/home.html'))
    # response.set_cookie('session', '', expires=0)
    return response


# @app.route("/switch-session/session-id/<session_id>", methods=['GET', 'POST'])
# def switch_session(session_id):
#     response = make_response(redirect('/home.html'))
#     #session.sid = session_id.split(":")[1]
#     #response.set_cookie('sessions3', session_id.split(":")[1], max_age=60*60*24*365*2)
#     return response


@app.route("/list_session", methods=['GET', 'POST'])
def list_session():
    response = get_sessions_dropdown_info(get_all_sessions())

    dump = json.dumps(response,
                      default=lambda o: '<not serializable>', sort_keys=False, indent=2)
    return dump


def get_sessions_dropdown_info(saves):
    if saves:
        response = [{
            "session_id": save['session_id'],
            # "expiry" : record.expiry,
            "uid": save['user_object']["userInfo"]["player"]["uid"],
            "world_name": save['user_object']["userInfo"]["worldName"],
            "level": save['user_object']["userInfo"]["player"]["level"],
            "xp": save['user_object']["userInfo"]["player"]["xp"],
        } for save in saves if validate_save(save)]
    else:
        response = []
    return response

def get_sessions_info(saves):
    if saves:
        response = [{
            "uid": save['user_object']["userInfo"]["player"]["uid"],
            "resource": save['user_object']["userInfo"]["player"]["playerResourceType"],
            "coins": save['user_object']["userInfo"]["world"]['resources']["coins"],
            "xp": save['user_object']["userInfo"]["player"]["xp"],
            "level": save['user_object']["userInfo"]["player"]["level"],
            "socialXpGood": save['user_object']["userInfo"]["player"]["socialXpGood"],
            "socialLevelGood": save['user_object']["userInfo"]["player"]["socialLevelGood"],
            "socialXpBad": save['user_object']["userInfo"]["player"]["socialXpBad"],
            "socialLevelBad": save['user_object']["userInfo"]["player"]["socialLevelBad"],
            "profilePic": "layouts/avatars/" + save['profilePic'] if 'profilePic' in save and save['profilePic'] is not None  else random_image(),
            "dominanceRank": 1,
            "pvpNumOccupiers": len([k for k, v in save['user_object']["pvp"]["invaders"].items() if k != "pve"]),
            "pvpNumOccupiersNotDefended": len([k for k, v in save['user_object']["pvp"]["invaders"].items() if k != "pve"]),
            "pvpInfo": next((v for k, v in save['user_object']["pvp"]["invaders"].items() if k == "u" + str(get_zid())), None),
            "tending": {
                "actions": 3
            }
        } for save in saves if validate_save(save) and save['user_object']["userInfo"]["player"]["level"] >= -6]
    else:
        response = []
    return response


@app.route("/gazillionaire", methods=['GET', 'POST'])
def more_money():
    if 'user_object' in session:
        create_backup("gazillionaire cheat")
        player = session['user_object']["userInfo"]["player"]
        player['cash'] += 10000
        session['saved'] = str(session.get('saved', "")) +  "gazillionaire"
        response = make_response(redirect('/home.html'))
        return response
    else:
        return ("Nope! You don't have a game session yet", 403)


@app.route("/deprogress", methods=['GET', 'POST'])
def deprogress_battle_map():
    if 'user_object' in session:
        # player = session['user_object']["userInfo"]["player"]
        campaign = session['user_object']['userInfo']['world']['campaign']
        # if map_name not in campaign['active'].keys():
        #     campaign['active'][map_name] = {"status": 0, "fleets": []}
        list = sorted(campaign['active'].keys())

        map, island = get_active_island_by_map(list[-1])

        create_backup("before deprogress battle map " + str(island+1) + "=>" + str(island))
        session['saved'] = str(session.get('saved', "")) + "deprogress"
        if island <= 0:
            del campaign['active'][map]
            deprogress_battle_map()
        else:
            set_active_island_by_map(map, island - 1)
        response = make_response(redirect('/home.html'))
        return response
    else:
        return ("Nope! You don't have a game session yet", 403)


@app.route("/seed/w/<int:w>/z/<int:z>", methods=['GET', 'POST'])
def change_seed(w, z):
    if 'user_object' in session:
        create_backup("seed")
        world = session['user_object']["userInfo"]["world"]
        prev_seed = str(world["randSeedW"]) + ', ' + str(world["randSeedZ"])
        world["randSeedW"] = w
        world["randSeedZ"] = z
        print("Seed change", prev_seed, "=>", str(world["randSeedW"]) + ', ' + str(world["randSeedZ"]))

        session['saved'] = str(session.get('saved', "")) +  "seed"
        response = make_response(redirect('/home.html'))
        return response
    else:
        return ("Nope! You don't have a game session yet", 403)


@app.route("/patch/<path:path>/empty-dict", methods=['GET', 'POST'])
def patch_user_empty_dict(path):
    return patch_user(path, {})


@app.route("/patch/<path:path>/empty-list", methods=['GET', 'POST'])
def patch_user_empty_list(path):
    return patch_user(path, [])


@app.route("/patch/<path:path>/none", methods=['GET', 'POST'])
def patch_user_dict(path):
    return patch_user(path, None)


@app.route("/patch/<path:path>/int/<int:value>", methods=['GET', 'POST'])
@app.route("/patch/<path:path>/string/<value>", methods=['GET', 'POST'])
def patch_user(path, value):
    if 'user_object' in session:
        if path.split('/')[0] not in ("saved", "original_save_version"):
            create_backup("patch")
            dictionary = session
            for p in path.split('/')[:-1]:
                dictionary = dictionary[p]

            dictionary[path.split('/')[-1]] = value

            session['saved'] = str(session.get('saved', "")) + "patch"
            response = make_response(redirect('/home.html'))
            return response
        else:
            return ("Nope! Disallowed patch root", 403)
    else:
        return ("Nope! You don't have a game session yet", 403)


@app.route("/patch/<path:path>/list/index/<int:i>/int/<int:value>", methods=['GET', 'POST'])
@app.route("/patch/<path:path>/list/index/<int:i>/string/<value>", methods=['GET', 'POST'])
def patch_user_list(path, i, value):
    if 'user_object' in session:
        if path.split('/')[0] not in ("saved", "original_save_version"):
            create_backup("patch")
            dictionary = session
            for p in path.split('/'):
                dictionary = dictionary[p]

            dictionary[i] = value

            session['saved'] = str(session.get('saved', "")) + "patch"
            response = make_response(redirect('/home.html'))
            return response
        else:
            return ("Nope! Disallowed patch root", 403)
    else:
        return ("Nope! You don't have a game session yet", 403)


@app.route("/unlock_quest/<value>", methods=['GET', 'POST'])
def unlock_quest(value):
    if 'user_object' in session:
        create_backup("Unlocked quest " + value)
        new_quests=[]
        meta = {}
        new_quest_with_sequels(value, new_quests, meta, force=True)
        merge_quest_progress(new_quests, session['quests'], "session quest")
        session['saved'] = str(session.get('saved', "")) + "unlock"

        response = make_response(redirect('/home.html'))
        return response
    else:
        return ("Nope! You don't have a game session yet", 403)


@app.route("/complete_quest/<value>", methods=['GET', 'POST'])
def complete_quest(value):
    if 'user_object' in session:
        create_backup("Complete quest " + value)
        new_quests=[]
        meta = {}
        handle_quest_progress(meta, progress_quest(value))
        session['saved'] = str(session.get('saved', "")) + "complete"

        response = make_response(redirect('/home.html'))
        return response
    else:
        return ("Nope! You don't have a game session yet", 403)


@app.route("/remove_quest/<value>", methods=['GET', 'POST'])
def remove_quest(value):
    if 'user_object' in session:
        create_backup("Remove quest " + value)
        session['quests'] = [e for e in session['quests'] if e["name"] != value]
        session['saved'] = str(session.get('saved', "")) + "remove"

        response = make_response(redirect('/home.html'))
        return response
    else:
        return ("Nope! You don't have a game session yet", 403)


@app.route("/save-editor", methods=['GET'])
def save_editor():
    backups = []
    s = session
    backup_count = 0
    while "backup" in s:
        backups.append(format_backup_message(s["backup"]))
        s = s["backup"]
        backup_count += 1
    print("Backups present", backup_count)

    incomplete_quests = [e["name"] for e in session['quests'] if e["complete"] == False]
    complete_quests = [e["name"] for e in session['quests'] if e["complete"]]

    return render_template("save-editor.html", savegame=json.dumps(
        {
            'user_object': session['user_object'] if 'user_object' in session else None,
            'profilePic': session['profilePic'] if 'profilePic' in session else None,
            'quests': session['quests'] if 'quests' in session else None,
            'battle': session['battle'] if 'battle' in session else None,
            'fleets': session['fleets'] if 'fleets' in session else None,
            'population': session['population'] if 'population' in session else None,
            'saved': session['saved'] if 'saved' in session else None,
            'save_version': session['save_version'] if 'save_version' in session else None,
            'original_save_version': session['original_save_version'] if 'original_save_version' in session else None,
        }, default=lambda o: '<not serializable>', sort_keys=False, indent=2), uid=get_zid(), backups=backups,
                           valid=validate_save(session, False),
                           quest_names={q: v for q, v in quest_titles.items() if q not in complete_quests and q not in incomplete_quests},
                           incomplete_quest_names={q: v for q, v in quest_titles.items() if q in incomplete_quests},
                           complete_quest_names={q: v for q, v in quest_titles.items() if q in complete_quests}
                           )


@app.route("/save-editor", methods=['POST'])
def save_savegame():
    print("Going to save:")
    restores = [int(key[7:]) for key in request.form.keys() if "restore" in key]

    if restores:
        save_game = session["backup"]
        for i in range(restores[0]):
            save_game = save_game["backup"]
        save_game = copy.deepcopy(save_game)
        print("restoring backup")
        message = "Revert to backup \"" + format_backup_message(save_game) + "\""
    else:
        save_game = json.loads(request.form['savegame'])
        message = "before " + request.form.get("message")

    print(repr(save_game))

    create_backup(message)
    session['saved'] = str(session.get('saved', "")) + "edit"
    session['user_object'] = save_game['user_object']
    if 'profilePic' in session:
        session['profilePic'] = save_game['profilePic']
    else:
        pass
    session['quests'] = save_game['quests']
    session['battle'] = save_game['battle']
    session['fleets'] = save_game['fleets']
    session['population'] = save_game['population']
    session['save_version'] = save_game.get('save_version')

    response = make_response(redirect('/home.html'))
    return response
    # return ('', 400)


def format_backup_message(backup):
    return datetime.fromtimestamp(backup.get('saved_on', 0)).strftime("%d %b %Y %H:%M:%S") + ' - ' \
           + datetime.fromtimestamp(backup.get('replaced_on', 0)).strftime("%d %b %Y %H:%M:%S") + ' @' \
           + str(backup.get('save_version', 'UNKNOWN VERSION')) + ' ' \
           + str(backup.get("message", ""))


@app.route("/127.0.0.1record_stats.php", methods=['GET', 'POST'])
def record_stats():
    return ('', 204)


@app.route("/files/empire-s.assets.zgncdn.com/assets/109338/ZGame.109338.swf")
def flashFile():
    # return send_from_directory_mod("assets", "ZGame.109338.swf")
    return send_from_directory_mod("assets", "ZGame.109338_tracer2.swf")  # regular one
    # return send_from_directory_mod("assets", "ZGame.109338_tracer2a.swf")  # with extra debug logging


@app.route("/gameSettings.xml")
def game_settings_file():
    # return send_from_directory_mod("assets/32995", "gameSettings.xml")
    # return send_from_directory_mod("assets/32995", "gameSettings.xml")
    # return send_from_directory_mod("assets/29oct2012", "gameSettings.xml")
    # return send_from_directory_mod("assets/29oct2012", "gameSettings_placeholders.xml")
    return send_from_directory_mod("assets/29oct2012", "gameSettings_with_fixes.xml")


@app.route("/127.0.0.1en_US.xml")
def en_us_file():
    # return send_from_directory_mod("assets/32995", "en_US.xml")
    return send_from_directory_mod("assets/29oct2012", "en_US.xml")


@app.route("/127.0.0.1questSettings.xml")
def quest_settings_file():
    return send_from_directory_mod("assets/29oct2012", "questSettings_with_fixes.xml")

@app.route("/releases.html")
def releases():
    return render_template("releases.html", version=version)

@app.route("/friends.html")
def friends_page():
    saves = get_saves()
    return render_template("friends.html", version=version, release_date=release_date, dropdown_items=get_sessions_dropdown_info(saves), zid=str(get_zid()))

@app.route("/login.html")
def login_page():
    saves = get_saves()
    return render_template("login.html", version=version, release_date=release_date, dropdown_items=get_sessions_dropdown_info(saves))

def get_avail_avatars():
    # list(set([u for u in fetch_urls() if u.endswith('.png')]))
    # return avatar_file_names in os.walk(os.path.join(my_games_path() ,"templates/layouts"))
    # TODO
    avatar_list = ["2_PincusCP_100.png",
                    "4_NavyCP_04_100.png",
                    "5_NavyCP_03_100.png",
                    "6_NavyCP_02_100.png",
                    "7_NavyCP_01_100.png",
                    "8_HansCP_100.png",
                    "9_ArtCP_100.png",
                    "10_ArmyCP_04_100.png",
                    "11_ArmyCP_03_100.png",
                    "12_ArmyCP_02_100.png",
                    "13_ArmyCP_01_100.png",
                    "14_AirForceCP_04_100.png",
                    "15_AirForceCP_03_100.png",
                    "16_AirForceCP_02_100.png",
                    "17_AirForceCP_01_100.png"]
    return avatar_list

@app.route("/new.html")
def new_player_page():
    saves = get_saves()
    return render_template("new.html", version=version, release_date=release_date, avatars=get_avail_avatars())

@app.route("/chooseavatar/<path:path>", methods=['GET', 'POST'])
def choose_avatar(path):
    avatar = path
    session['profilePic'] = avatar
    response = make_response(redirect('/home.html'))
    return response

def get_avatar_pic():
    avatar_pic = "layouts/avatars/" + session['profilePic'] if 'profilePic' in session and session['profilePic'] is not None else random_image()
    return avatar_pic

@app.route("/changelog.txt")
def change_log():
    return render_template("changelog.txt")

@app.route("/layouts/<path:path>")
def template_layouts(path):
    return send_from_directory_mod("templates/layouts", path)

@app.route('/nullassets/<path:path>')
def send_sol_assets(path):
    return send_from_directory_mod('assets/sol_assets_octdict/assets', path)

@app.route('/assets/<path:path>')
def send_sol_assets_alternate(path):
    return send_from_directory_mod('assets/sol_assets_octdict/assets', path)


def send_from_directory_mod(directory, filename, **options):
    absolute_directory = os.path.join(install_path(), directory)
    path = safe_join(os.fspath(absolute_directory), os.fspath(filename))
    print(path)

    return mod_engine.mod.get(path)() if path in mod_engine.mod else send_from_directory(absolute_directory, filename, **options)


@app.route('/files/empire-s.assets.zgncdn.com/assets/109338/127.0.0.1flashservices/gateway.php', methods=['POST'])
def post_gateway():
    print("Gateway:")
    print(repr(request))
    # print("Data:")
    # print(request.data)
    resp_msg = remoting.decode(request.data)
    # print(resp_msg.headers)
    print(resp_msg.bodies)
    # print(resp_msg.bodies[0])

    resps = []
    for reqq in resp_msg.bodies[0][1].body[1]:
        if reqq.functionName == 'UserService.initUser':
            try:
                resps.append(user_response())
            except InvalidSaveException as error:
                print('Handling InvalidSaveException error:', error)
                # return make_response(redirect('/save-editor')) #can't do it here

        elif reqq.functionName == 'DataServicesService.getRequestFriends':
            resps.append(friend_response())
        elif reqq.functionName == 'PVPService.getUsersInvaderChallenges':
            resps.append(invader_response())
        elif reqq.functionName == 'ZlingshotService.presence':
            resps.append(zlingshot_response())
        elif reqq.functionName == 'DataServicesService.getRecentPlayers':
            resps.append(recent_response())
        elif reqq.functionName == 'DataServicesService.getFriendsInfo':
            resps.append(friend_info_response())
        elif reqq.functionName == 'UserService.tutorialProgress':
            resps.append(tutorial_response(reqq.params[0], reqq.sequence, resp_msg.bodies[0][0]))
        elif reqq.functionName == 'WorldService.performAction':
            # lastId = 0
            # for reqq2 in resp_msg.bodies[0][1].body[1]:
            #     if reqq2.functionName == 'WorldService.performAction' and reqq2.params[1] and reqq2.params[1].id:
            #         lastId=reqq2.params[1].id
            # 
            #wr = perform_world_response(step=reqq.params[0],
            #                            supplied_id=reqq.params[1].id,
            #                            position=reqq.params[1].position,
            #                            item_name=reqq.params[1].itemName,
            #                            reference_item=reqq.params[2][0].get('referenceItem') if len(reqq.params[2]) > 0 else None,
            #                            from_inventory=reqq.params[2][0].get('isGift') if len(reqq.params[2]) > 0 else None,
            #                            elapsed=reqq.params[2][0].get('elapsed') if len(reqq.params[2]) > 0 else None,
            #                            cancel=reqq.params[2][0].get('cancel') if len(reqq.params[2]) > 0 else None,
            #                            req2=reqq.params[2][0] if len(reqq.params[2]) > 0 else None)
            wr = perform_world_response(reqq.params)
            resps.append(wr)
            report_world_log(reqq.params[0] + ' id ' + str(reqq.params[1].id) + '@' + reqq.params[1].position,
                             wr["data"], reqq.params, reqq.sequence, resp_msg.bodies[0][0],
                             wr["metadata"].get('QuestComponent'), wr["metadata"].get('newPVE'))
        elif reqq.functionName == 'DataServicesService.getSuggestedNeighbors':
            resps.append(neighbor_suggestion_response())
        elif reqq.functionName == 'UserService.setSeenFlag':
            resps.append(seen_flag_response(reqq.params[0]))
        elif reqq.functionName == 'PVPService.createRandomFleetChallenge':
            resps.append(random_fleet_challenge_response(reqq.params[0]))
        elif reqq.functionName == 'WorldService.spawnFleet':
            resps.append(spawn_fleet(reqq.params[0]))
        elif reqq.functionName == 'PVPService.loadChallenge':
            resps.append(load_challenge_response(reqq.params[0]))
        elif reqq.functionName == 'WorldService.resolveBattle':
            resps.append(battle_complete_response(reqq.params[0]))
        elif reqq.functionName == 'WorldService.genericString':
            resps.append(generic_string_response(reqq.params[0]))
        elif reqq.functionName == 'UserService.streakBonus':
            resps.append(streak_bonus_response(reqq.params[0]))
        elif reqq.functionName == 'UserService.setWorldName':
            resps.append(world_name_response(reqq.params[0]))
        elif reqq.functionName == 'WorldService.updateRoads':
            resps.append(update_roads_response(reqq.params[0]))
        elif reqq.functionName == 'UserService.streamPublish':
            resps.append(stream_publish_response(reqq.params))
        elif reqq.functionName == 'WorldService.stopMayhemEvent':
            resps.append(stop_mayhem_response())
        elif reqq.functionName == 'UserService.saveOptions':
            resps.append(save_options_response(reqq.params[0]))
        elif reqq.functionName == 'WorldService.fullScreen':
            resps.append(full_screen_response())
        elif reqq.functionName == 'WorldService.viewZoom':
            resps.append(view_zoom_response(reqq.params[0].get('zoom')))
        elif reqq.functionName == 'WorldService.loadWorld':
            resps.append(load_world_response(reqq.params))
        elif reqq.functionName == 'VisitorService.help':
            resps.append(tend_ally_response(reqq.params))
        elif reqq.functionName == 'WorldService.beginNextCampaign':
            resps.append(next_campaign_response(reqq.params[0]))
        elif reqq.functionName == 'WorldService.addFleet':
            resps.append(add_fleet_response(reqq.params[0]))
        elif reqq.functionName == 'WorldService.assignConsumable':
            resps.append(assign_consumable_response(reqq.params[0]))
        elif reqq.functionName == 'UserService.publishUserAction':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.sendUserNotification':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.sendZaspReport':
            resps.append(dummy_response())
        elif reqq.functionName == 'ClansService.buyCrest':
            resps.append(dummy_response())
        elif reqq.functionName == 'ClansService.buyHealth':
            resps.append(dummy_response())
        elif reqq.functionName == 'ClansService.buySlots':
            resps.append(dummy_response())
        elif reqq.functionName == 'ClansService.clearNotifications':
            resps.append(dummy_response())
        elif reqq.functionName == 'ClansService.createClan':
            resps.append(dummy_response())
        elif reqq.functionName == 'ClansService.getClanInfo':
            resps.append(dummy_response())
        elif reqq.functionName == 'ClansService.getNeighborClanInfo':
            resps.append(dummy_response())
        elif reqq.functionName == 'ClansService.loadAllianceBattle':
            resps.append(dummy_response())
        elif reqq.functionName == 'ClansService.postGroupFeed':
            resps.append(dummy_response())
        elif reqq.functionName == 'ClansService.processMemberQueue':
            resps.append(dummy_response())
        elif reqq.functionName == 'ClansService.removeMember':
            resps.append(dummy_response())
        elif reqq.functionName == 'ClansService.addTaunt':
            resps.append(dummy_response())
        elif reqq.functionName == 'ClansService.updateName':
            resps.append(dummy_response())
        elif reqq.functionName == 'ClansService.updateCrest':
            resps.append(dummy_response())
        elif reqq.functionName == 'ClansService.updateTauntViewTime':
            resps.append(dummy_response())
        elif reqq.functionName == 'DeathMatchService.fetchOpponents':
            resps.append(dummy_response())
        elif reqq.functionName == 'DeathMatchService.joinRoom':
            resps.append(dummy_response())
        elif reqq.functionName == 'DeathMatchService.processRewardQueue':
            resps.append(dummy_response())
        elif reqq.functionName == 'ClansService.acceptQuest':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.acceptDecoBuildableRepel':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.acceptDefenseTowerRepel':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.acceptedGDP':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.acceptedTOS':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.acceptFriendRepel':
            resps.append(accept_friend_repel_response(reqq.params[0]))
        elif reqq.functionName == 'CrossPromoService.accepted':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.acknowledgeTOSStatus':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.reactivateFightMeter':
            resps.append(dummy_response())
        elif reqq.functionName == 'DominationModeService.addDominationChat':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.addFriendPublish':
            resps.append(dummy_response())
        elif reqq.functionName == 'ClansService.completeQuest':
            resps.append(dummy_response())
        elif reqq.functionName == 'RequestService.partRequest':
            resps.append(part_request_response(reqq.params))
        elif reqq.functionName == 'WorldService.beginQuestBattle':
            resps.append(dummy_response())
        elif reqq.functionName == 'BlackMarketHelperService.tradeForPart':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.bookmarksDailySpin':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.buyBack':
            resps.append(dummy_response())
        elif reqq.functionName == 'MiniGameService.buyMiniGameFuel':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.buyCrewRepelPosition':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.buyExpansion':
            resps.append(buy_expansion_response(reqq.params[0]))
        elif reqq.functionName == 'UserService.buyFullHeal':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.buyItem':
            resps.append(buy_item_response(reqq.params[0]))
        elif reqq.functionName == 'UserService.buyItems':
            resps.append(buy_items_response(reqq.params[0]))
        elif reqq.functionName == 'UserService.useItem':
            resps.append(use_item_response(reqq.params[0]))
        elif reqq.functionName == 'UserService.buyMOTDItem':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.buyQuestRestartTask':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.buyQuestTask':
            resps.append(buy_quest_task_response(reqq.params[0]))
        elif reqq.functionName == 'UserService.buyRewardItem':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.calculateRansom':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.cancelUnstartedChallenge':
            resps.append(cancel_unstarted_challenge_response())
        elif reqq.functionName == 'UserService.checkForPromoReward':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.clearOldFlashTokens':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.clearIncentive':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.collectLeaderboards':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.completeSocialRepel':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.crewNeighborPoll':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.crewZMCEvent':
            resps.append(dummy_response())
        elif reqq.functionName == 'MiniGameService.dropBomb':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.energizerSetup':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.EPGiftSend':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.finishSpy':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.setEspionageHQData':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.exitBattle':
            resps.append(exit_battle_response())
        elif reqq.functionName == 'WorldService.expireAQuest':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.getFightList':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.flashFeedRedeemItem':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.EPGiftThankYou':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.getAllChallenges':
            resps.append(dummy_response())
        elif reqq.functionName == 'DominationModeService.getDominationChat':
            resps.append(dummy_response())
        elif reqq.functionName == 'DominationModeService.getDominationModeOpponentList':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.getFBCreditPromoStatus':
            resps.append(dummy_response())
        elif reqq.functionName == 'FeedService.getFeed':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.getLeaderboards':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.getNeighborVisitChallenges':
            resps.append(neighbor_invader_response(reqq.params[0]))
        elif reqq.functionName == 'UserService.getPrisonerInfo':
            resps.append(dummy_response())
        elif reqq.functionName == 'DataServicesService.getPromoData':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.getTargetingData':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.getTargetingGroups':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.grantWatchToEarnRewardNew':
            resps.append(dummy_response())
        elif reqq.functionName == 'DominationModeService.loadDominationModeBattle':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.loadEnemyFleetForChallenge':
            resps.append(random_enemy_fleet_challenge_response(reqq.params[0]))
        elif reqq.functionName == 'QuestSurvivalModeService.loadQuestSurvivalMode':
            resps.append(dummy_response())
        elif reqq.functionName == 'SurvivalModeService.loadSurvivalMode':
            resps.append(load_survival_mode_response(reqq.params[0]))
        elif reqq.functionName == 'UserService.lcs':
            resps.append(dummy_response())
        elif reqq.functionName == 'DataServicesService.getMatchmakingUsersData':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.matchMakingOptFlag':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.mechlabStatus':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.megaSeriesReset':
            resps.append(dummy_response())
        elif reqq.functionName == 'ZlingshotService.fetch':
            resps.append(dummy_response())
        elif reqq.functionName == 'MFSService.collectReward':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.motdAction':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.multiHarvest':
            resps.append(dummy_response())
        elif reqq.functionName == 'DataServicesService.getRecommendedNeighbors':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.openDialog':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.promoAction':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.purchaseAmmoRefill':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.purchaseContractUnlock':
            resps.append(purchase_contact_unlock(reqq.params[0]))
        elif reqq.functionName == 'UserService.purchaseEnergyRefill':
            resps.append(purchase_energy_refill_response(reqq.params[0]))
        elif reqq.functionName == 'UserService.purchaseManaRefill':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.purchaseUnlock':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.globalPVPOptInOut':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.slotMachineSpin':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.slotMachineSpinBuy':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.immunityExtend':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.immunityStart':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.occupationPlace':
            resps.append(occupation_place_response(reqq.params))
        elif reqq.functionName == 'PVPService.pillage':
            resps.append(pillage_response(reqq.params))
        elif reqq.functionName == 'UserService.doFavQuest':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.doSeenQuestNotification':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.questTreeReset':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.questTreeSetMode':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.questTreeStartQuest':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.questTreeUnlockQuest':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.rejectDecoBuildableRepel':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.rejectDefenseTowerRepel':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.rejectFriendRepel':
            resps.append(reject_friend_repel_response(reqq.params[0]))
        elif reqq.functionName == 'UserService.removeExpiredInventory':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.removeExtraInventoryBuildings':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.removeExtraWorldBuildings':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.setTitanName':
            resps.append(dummy_response())
        elif reqq.functionName == 'RequestService.allianceInviteRequest':
            resps.append(dummy_response())
        elif reqq.functionName == 'RequestService.allianceJoinRequest':
            resps.append(dummy_response())
        elif reqq.functionName == 'RequestService.crewRequest':
            resps.append(crew_request_response(reqq.params))
        elif reqq.functionName == 'RequestService.invasionHelpRequest':
            resps.append(dummy_response())
        elif reqq.functionName == 'RequestService.neighborRequest':
            resps.append(dummy_response())
        elif reqq.functionName == 'RequestService.giftRequest':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.resetParliamentDestroyed':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.retrieveNeighborRepelChallenge':
            resps.append(neighbor_repel_challenge_response(reqq.params))
        elif reqq.functionName == 'PVPService.reviveAllies':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.reviveUnits':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.moveRoad':
            resps.append(update_roads_response(reqq.params[0]))
        elif reqq.functionName == 'WorldService.sellRoad':
            resps.append(update_roads_response(reqq.params[0]))
        elif reqq.functionName == 'PVPService.seenPrisonCampNotification':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.seenStrikeTeamComment':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.select':
            resps.append(select_response(reqq.params[0]))
        elif reqq.functionName == 'UserService.setCommandoAnimationDone':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.setCurrentCampaign':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.setDefenderComment':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.setEnergiserAnimationDone':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.setFBCreditParticipation':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.setInvasionComment':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.setStrikeTeamComment':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.setTag':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.spend':
            resps.append(dummy_response())
        elif reqq.functionName == 'DeathMatchService.loadBattle':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.startMayhemEvent':
            resps.append(dummy_response())
        elif reqq.functionName == 'MiniGameService.loadGame':
            resps.append(dummy_response())
        elif reqq.functionName == 'MiniGameService.stop':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.streamPublishWithComment':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.superOreOrder':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.setSurvivalModeToaster':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.treasureVaultSpin':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.unitDropRevealAll':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.unitDropSwitchUnit':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.unitUnlock':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.buyUnlimitedEnergy':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.unlockResource':
            resps.append(dummy_response())
        elif reqq.functionName == 'DominationModeService.updateDefenseForce':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.upgradeResearchBuilding':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.upgradeState':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.useItem':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.useStrikeTeam':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.viralSurfacingSeen':
            resps.append(dummy_response())
        elif reqq.functionName == 'VisitorService.accept':
            resps.append(accept_tend_ally_response(reqq.params))
        elif reqq.functionName == 'VisitorService.decline':
            resps.append(decline_tend_ally_response(reqq.params))
        elif reqq.functionName == 'VisitorService.helpedInvalid':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.grantWatchToEarnReward':
            resps.append(dummy_response())
        elif reqq.functionName == 'ZlingshotService.zoom':
            resps.append(dummy_response())
        else:
            resps.append(dummy_response())

        if reqq.functionName != 'UserService.tutorialProgress' and reqq.functionName != 'WorldService.performAction':
            report_other_log(reqq.functionName, resps[-1] if resps else None, reqq, resp_msg.bodies[0][0])

    emsg = {
        "serverTime": datetime.now().timestamp(),
        "errorType": 0,
        "data": resps
    }

    req = remoting.Response(emsg)
    ev = remoting.Envelope(pyamf.AMF0)
    ev[resp_msg.bodies[0][0]] = req
    #  print(ev.headers)
    # print(ev.bodies)

    ret_body = remoting.encode(ev, strict=True, logger=True).getvalue()  # .read()
    # print(ret_body)
    return Response(ret_body, mimetype='application/x-amf')

    # return ('', 204)


def init_user():
    # global game_objects
    unit = "U01,,,,"

    # resources = {"energy": 100, "coins": 100000, "oil": 7000, "wood": 5000, "aluminum": 9000,
    #                                 "copper": 4000, "gold": 3000, "iron": 2000, "uranium": 1000}

    resources = {"energy": 25, "coins": 5000, "oil": 25, "wood": 150, "aluminum": 1000,
                 "copper": 0, "gold": 0, "iron": 0, "uranium": 0}

    # xp = 20000
    # level =100
    # zcash = 1000
    # energy = 200
    # energy_max = 400
    xp = 0
    level = 1
    zcash = 15
    energy = 25
    energy_max = 25

    # user_fleet = {
    #     "type": "army",
    #     "uid": "0",
    #     "name": "FleetName",
    #     "status": 0,
    #     "target": "",
    #     "consumables": [],
    #     "inventory": [],
    #     "playerLevel": 1,
    #     "specialBits": None,
    #     "lost": None,
    #     "lastUnitLost": None,
    #     "lastIndexLost": None,
    #     "allies": None,
    #     "battleTarget": None,
    #     "battleTimestamp": None,
    #     "ransomRandom": None,
    #     "ransomResource": None,
    #     "ransomAmount": None,
    #     "units": [unit],  # only one unit for tutorial [unit, unit, unit],
    #     "store": [0],  # [0, 0, 0],
    #     "fleets": None,
    #     "upgrades": None,
    #     "hp": None
    # }

    user = {
        "userInfo": {
            "player": {
                "uid": get_zid(),
                "lastTrackingTimestamp": 0,
                "viralSurfacing": {"seen": [], "counts": {}},
                "crewNeighbors": [],
                "dm_band": None,
                "dm_endTS": None,
                "tutorialProgress": "",
                "xp_multiplier": 1,
                "cp_static": 1,
                "lightningDeals": {},
                "friendFlashSessionInfo": {},
                "m_friendFlashEPBank": 1000,
                "playerResourceType": 3,  # 0:coins 1:oil 2: wood 3:alum,
                "meetsCriteriaLowWalletOnly": False,
                "newInstallExperiments": None,
                "staticWorkers": 20,
                "staticWorkersCap": 100,
                # "expansions": {
                #     "data": [4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
                #              4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
                #              4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
                #              4294967295, 4294967295]},
                "expansions": {"data": [0,0,0,0,805306368,6291456,49152,0,0,0,0]},
                "questTrees": {},
                "questTreeUnlocks": {},
                "questTreeData": {},
                "starredQuests": [],
                "seenQuests": [],
                "megaseriesList": {},
                "questGatesComplete": False,
                "warpSeconds": 0,
                "worldGamesOver": 0,
                "lastLoginTimestamp": 0,
                "RUXStatus": False,
                "RUXQuest": False,
                "RUXDay": 0,
                "RUXInitShow": False,
                "RUXDelta": 0,
                "MFSRewardPoints": 0,
                "MFSRewardClaimed": False,
                "MFSRewardLap": 0,
                "mana": {"value": 100},
                "cash": zcash,
                "level": level,
                "xp": xp,
                "numCashTransactions": 100,
                "cashPurchasedTotal": 1000,
                "transactionLog": [],
                "combatSpecialBits": None,
                "promos": None,
                "autopromo": None,
                "motdMerchHistory": None,
                "motdMerchUnlockHistory": None,
                "lufCodes": None,
                "lufEndDate": 0,
                "lufZRTData": None,
                "lufCodesLevelUnlocked": None,
                "miniGamePlayedTS": 0,
                "bomberFuel": 1000,
                "bombTierReached": 0,
                "miniGameRewardTier": 0,
                "miniGameRewards": [],
                "miniGameTotalFuel": 1500,
                "mgrsData": "",
                "seenFlags": {},
                # seen "introCine":True otherwise blackscreen but no startepisode then ->  either false (ZGlobal.noIntroCineVariant != ZGlobal.EXPERIMENT_NO_INTRO_CINE && Zlab.getFlashVar("mute") == null)
                "motdsViewed": [],
                "motdsAccepted": [],
                "m_mayhemEvents": None,
                "bountyCenter": {"lastActivated": 0, "bountyBonds": 0},
                "energizerRefill": 1000,
                "energiserEventFinished": False,
                "energiserAnimationInitTime": 0,
                "energyDeduct": 0,
                "energizerMax": 1000,
                "energy": energy,
                "energyMax": energy_max,
                "unlimitedEnergyTS": 0,
                "unlimitedEnergyIndex": 0,
                "lastEnergyCheck": datetime.now().timestamp(),
                "ammo": 1234,
                "ammoMax": 2000,
                "options": {"musicDisabled": False, "sfxDisabled": False},
                "socialLevelGood": 100,
                "socialXpGood": 10000,
                "socialLevelBad": 0,
                "socialXpBad": 0,
                "scrap": None,
                "enableIdlePopup": False,
                "enableInterPage": False,
                "enableOnetimePopup": False,
                "alliesUsed": None,
                "storageData": {},
                "inventory": {"items": {"B01": 20}},
                "neighborVisits": {},
                "unlockedUnits": [],
                "unlockedItems": [],
                "unlockedContracts": [],
                "tags": {},
                "consumableUsedByCode": None,
                "treasureVaultOpenTS": 0,
                "watchToEarn": {"dailyWatchCount": 0, "dailyWatchStartTime": 0},
                "userGroups": None,
                "flashFeedTokens": None,
                "lastSurvialModeToaster": 0,
                "clanStatus": None,
                "allianceStorage": None,
                "acceptedAllianceQuests": None,
                "isCIP": False,
                "acceptedGDP": True,
                "acceptedTOS": True,
                "fightMeter": {"lastActivated": 0, "lastInitWeek": 0, "weekInitTarget": 0},
                "fightsPerDay": 1,
                # "fleets": None,
                "activeVirals": {},
                "sequentialLogins": 1,
                "mechDailyRewardOffset": 0,

                "world": {
                    "deathMatch": None
                }
            },
            "worldName": "Rising Empire",
            "titanName": "Titan",
            "isCIP": False,
            "dominanceDefaultFleets": [],
            "bookmarkReward": 0,
            "iconCodes": None,

            "world": {"fleets": [], "enemies": [], "globalFleetId": 0, "battleStatus": {},  # user_fleet
                      "research": {}, "research2": {"buildingTypesUpgraded": None, "treesUnlocked": None},
                      "resourceOrder": ["aluminum", "copper", "gold", "iron", "uranium"],
                      "globalObjectId": 10000,  # initial id high enough not to overlap with preloaded objects
                      "sizeX": 200,
                      "sizeY": 200,
                      "ownerId": 0,
                      "randSeedW": rand_seed_w,
                      "randSeedZ": rand_seed_z,
                      "unitDropData": {"unclaimedUnits": []},
                      "islands": 1,
                      "roadData": initial_island["roads"],
                      "objects": initial_island["objects"],
                      "rewardRandSeedW": 484584,
                      "rewardRandSeedZ": 7549,
                      "ransomRandSeedW": 456647,
                      "ransomRandSeedZ": 4546,
                      "scrapRandSeedW": 5646,
                      "scrapRandSeedZ": 3567,
                      "resources": resources,
                      "campaign": {"current": "camp001", "active": {}, "mastery": {}}
                      }

        },
        "neighbors": get_allies_info(),
        "unlockedResource": {"aluminum": 3, "copper": 4, "gold": 5, "iron": 6},
        "showBookmark": True,
        "firstDay": True,
        "survivalMode": None,
        "prisonerInfo": [],
        "pvp": {"invaders": {"pve": {"quest": True}}, "gpInv": None, "nAssists": None, "immunity": [],
                "notifications": None, "pcCapturedNotify": None, "pcEscapedNotify": None},
        "autoFilledCrewBuildings": None,
        "numCrewNeighborsDirty": 0,
        "ineligibleGiftRecipients": [],
        "priceTestSettings": {},
        "buyBackSettings": {},
        "DEATHMATCH_FRAG_LIMITS": None,
        "DEATHMATCH_CACHE_TTL": None,
        "DEATHMATCH_OPP_COOLDOWN": None,
        "DEATHMATCH_STANDARD_REWARDS": None,
        "DEATHMATCH_GRAND_REWARDS": None,
        "DEATHMATCH_START_TIME": None,
        "DEATHMATCH_DURATION": None,
        "clansInfo": None,
        "immunityTimeVariant": 0,
        "experiments": {"empire_combataicancritical": 2, "empire_decorations_master": 2, "empire_doober_pickup": 3,
                        "empires_consumable_2": 3, "empire_research_shield_upgrade": 2, "empires_support_units": 5,
                        "empire_buildable_zrig_master": 3, "empire_request2_master": 2, "empire_mfs_uili": 4,
                        "empire_survivalmode3_master": 3, "empire_survivalMode_master": 2,
                        "empire_survivalmode_enhancements": 2},
        "completedQuests": [],
        "decorationsInfo": None,
        "treasureVaultHighlights": None,
        "crewSlotCostExperiment": 0,
        "combatAllyGatingVarient": 0,
        "cashOnLevelUpVarient": 0,
        "immunityViralVarient": 0,
        "autopublishFeedVarient": 0,
        "autopublishFeedMessageVarient": 0,
        "publishFeedPermissionVarient": 0,
        "autopublishAllFeedVarient": 0,
        "researchPartsVariantArmy": 0,
        "researchPartsVariantNavy": 0,
        "researchPartsVariantAir": 0,
        "noIntroCineVariant": 2,  # disable intro cinematics (we don't have yet)
        "energyRewardVariant_v2": 0,
        "energyRewardVariant_v3": 0,
        "allyTimeoutVariant": 0,
        "speedUpViralVarient": 0,
        "pricetestEarlyUnitUnlockVariant": 0,
        "starterBundleVariant": 0,
        "meetsCriteriaStarterPack": False,
        "energyRewardModVariant": 0,
        "enhancedProgressBarVariant": 0,
        "epSpendConfirmation": 0,
        "leaderboardsVariant": 0,
        "survivalModeMaster": 0,
        "survivalModeContinueCost": 0,
        "survivalModeCardAccess": 0,
        "INTERSTITIAL_GIFTING_REWARDS": "",
        "FREE_GIFT_PARTS_BUILDING_DATA": "",
        "snid": 0,
        "snuid": 0,
        "visitorHelpRequests": {},
        "LE_DISCOUNT_SALE": 0,
        "LOW_EP_POPUP": None,
        "COMBAT_NO_ENERGY": 0,
        "COMBAT_DOUBLE_XP": 2,
        "COMBAT_HALF_RANSOM": 1,
        "overlaySurveyURL": None,
        "friendBarVarient": 0,
        "requestTracker": {"giftRequestSent": {}, "helpRequestSent": {}, "crewRequestSent": {},
                           "neighborRequestSent": {}, "repelInvasionRequestSent": {}, "allianceInviteRequestSent": {}},
        "activeRequests": {"request_speedup": None, "request_buildingpart_send": None, "request_crew": None,
                           "request_gift_request": None, "request_gift_send": None, "request_neighbor": None,
                           "request_repel_invasion": None, "request_alliance_invite": None},
        "activeGiftRequests": [],
        "activeHelpRequests": [],
        "allPendingNeighbors": [],
        "playerAsn": 1,
        "questInitAsn": 1,
        "partsGatherInitAsn": 1,
        "blackmarketItems": None,
        "worldEvents": None,
        "FLASHFEED_EXPIRE_TIME": 0,
        "FB_REQ_PERMS": "gdpr",
    }
    return user


# Q0516 ? start
def user_response():
    new_quests = []
    if 'user_object' in session:
        print("Loading user from save")
        if not validate_save(session):
            print("invalid save file")
            raise InvalidSaveException
        user = session['user_object']
        user["userInfo"]["player"]["uid"] = get_zid()
        if session.get('save_version') != version:
            print("WARNING: Save game was saved with version", session.get('save_version'), "while game is version",
                  version)

        qc = session['quests']

        user["neighbors"] = get_allies_info()

        meta = {"newPVE": 0, "QuestComponent": [e for e in session['quests'] if e["complete"] == False]}

    else:
        user = copy.deepcopy(init_user())
        print("initialized new")
        session['user_object'] = user
        # qc = [{"name": "Q0516", "complete":False, "expired":False,"progress":[0],"completedTasks":0}]
        session['quests'] = []

        session['save_version'] = version
        session['original_save_version'] = version
        session['saved_on'] = datetime.now().timestamp()
        meta = {"newPVE": 0, "QuestComponent": [e for e in session['quests'] if e["complete"] == False]}
        new_quest_with_sequels("Q0516", new_quests, meta)

    # session['user_object']["userInfo"]["player"]["tutorialProgress"] = "tut_step_krunsch1Battle2Speeech" #'tut_step_inviteFriendsViral'
    # session['user_object']["userInfo"]["player"]["tutorialProgress"] = 'tut_step_remindCombatUIWaitForPreBattleUI'
    # session['user_object']["userInfo"]["player"]["tutorialProgress"] = 'tut_step_remindCombatUIClearCircles'
    # session['user_object']["userInfo"]["player"]["lastEnergyCheck"] = datetime.now().timestamp()
    # save migration only
    # if "lastEnergyCheck" not in session['user_object']["userInfo"]["player"]:
    #     session['user_object']["userInfo"]["player"]["lastEnergyCheck"] = datetime.now().timestamp()

    replenish_energy()

    session["battle"] = None
    session["fleets"] = {}
    session['population'] = lookup_yield()

    if "market" not in session:
        session["market"] = {}
    # #temp migration
    # session['user_object']["experiments"]["empire_store_sorting_rev_enhanced"] = 0
    # session['user_object']["experiments"]["empires_shop_improvements"] = 0
    session['user_object']["experiments"]["empire_combataicancritical"] = 2
    unlock_expansion(156)
    unlock_expansion(157)
    unlock_expansion(181)
    unlock_expansion(182)
    unlock_expansion(206)
    unlock_expansion(207)
    # battle_status = 0
    # island = 2
    # replay_island = 0
    #
    # status_campaign = battle_status | replay_island << 8 | island << 20
    # status_campaign_2 = battle_status | replay_island << 8 | 5 << 20
    # # #
    # user['userInfo']['world']['campaign'] = {"current": "camp001", "active":{'C000': {"status": status_campaign, "fleets":[]},
    #                                                                        'C003': {"status": status_campaign_2, "fleets":[]}}, "mastery": {}}

    # user['userInfo']['world']['campaign'] =  {"current": "camp001", "active": {}, "mastery": {}}
    # user['userInfo']['world']['campaign'] =  {"current": "camp001", "active": {'C000': {"status": 1 << 20, "fleets":[]}}, "mastery": {}}

    # session['campaign'] = {}
    # session['campaign']['C003'] = {'island':4} #will receive a next "island": 1

    # if ""B01": 20"


    item_inventory = session['user_object']["userInfo"]["player"]["inventory"]["items"]
    if item_inventory.get("B01", 0) < 20:
        item_inventory["B01"] = 20
        print("Refilling upgrade blueprints to 20")  # until friend gift mechanisms are working
    if item_inventory.get("B05", 0) < 25:
        item_inventory["B05"] = 25
        print("Refilling advanced hull plating to 25")  # until friend gift mechanisms are working
    if item_inventory.get("B18", 0) < 25:
        item_inventory["B18"] = 25
        print("Refilling propeller to 25")  # until friend gift mechanisms are working
    if item_inventory.get("B04", 0) < 25:
        item_inventory["B04"] = 25
        print("Refilling mission map to 25")  # until friend gift mechanisms are working
    if item_inventory.get("B23", 0) < 25:
        item_inventory["B23"] = 25
        print("Refilling blast shield to 25")  # until friend gift mechanisms are working
    if item_inventory.get("B17", 0) < 25:
        item_inventory["B17"] = 25
        print("Refilling deck turret to 25")  # until friend gift mechanisms are working

    handle_quest_progress(meta, progress_inventory_count())
    handle_quest_progress(meta, progress_neighbor_count())
    handle_quest_progress(meta, progress_upgrades_count())

    activate_unlocked_quests(new_quests, meta)

    for neighbor in user["neighbors"]:
        if neighbor["uid"] in [MIN_ADMIN_ID, MAX_ADMIN_ID]:
            neighbor["level"] =  user["userInfo"]["player"]["level"] + 5

    if session.get('save_version') != version or is_0_08a_preview(version):
        print("Trying migration")
        migrate(meta, session.get('save_version'), version)

    sleep(0.05)  # bugfix required delay for loading entire screen

    # for e in session['user_object']["userInfo"]["world"]["objects"]:
    #     e['lastUpdated'] = 1308211628  #1 minute earlier to test
    user["completedQuests"] = [e["name"] for e in session['quests'] if e["complete"] == True]

    merge_quest_progress(new_quests, meta['QuestComponent'], "output quest")
    merge_quest_progress(new_quests, session['quests'], "session quest")
    user_response = {"errorType": 0, "userId": get_zid(), "metadata": meta,
                     # {"name": "Q0531", "complete":False, "expired":False,"progress":[0],"completedTasks":0},{"name": "QW120", "complete":False, "expired":False,"progress":[0],"completedTasks":0}
                     "data": user}
    return user_response


def friend_response():
    friend_types = ["recommendedFriends", "zyngaFriends", "empireFriends", "sevenDayFriends", "fourteenDayFriends",
                    "thirtyDayFriends", "payerFriends", "allFriends", "zyngaFriendsByEngagement", "empireFriendsByEngagement"]
    friend = {friend_type: {"data": [ally["friend"] for ally in allies.values() if ally.get("friend") and ally.get(friend_type)]} for friend_type in friend_types}



    #     "recommendedFriends": {"data": [{"zid": 124, "uid":124, "first_name": "MissTery", "sex": 'F',"portrait": "assets/game/GeneralAssetGroup_UI.swf/TheVille_50.png",
    # "pic": "assets/game/GeneralAssetGroup_UI.swf/TheVille_50.png",
    # "pic_square": "assets/game/GeneralAssetGroup_UI.swf/TheVille_50.png"}]},
    #     "zyngaFriends": {"data": [{"zid": 124,"uid":124, "first_name": "MissTery", "sex": 'F', "portrait": "assets/game/GeneralAssetGroup_UI.swf/TheVille_50.png",
    # "pic": "assets/game/GeneralAssetGroup_UI.swf/TheVille_50.png",
    # "pic_square": "assets/game/GeneralAssetGroup_UI.swf/TheVille_50.png"}]},
    #     "empireFriends": {"data": [{"zid": 124,"uid":124, "first_name": "MissTery", "sex": 'F', "portrait": "assets/game/GeneralAssetGroup_UI.swf/TheVille_50.png",
    # "pic": "assets/game/GeneralAssetGroup_UI.swf/TheVille_50.png",
    # "pic_square": "assets/game/GeneralAssetGroup_UI.swf/TheVille_50.png"}]},
    #     "sevenDayFriends": {"data": [{"zid": 124, "uid":124,"first_name": "MissTery", "sex": 'F', "portrait": "assets/game/GeneralAssetGroup_UI.swf/TheVille_50.png",
    # "pic": "assets/game/GeneralAssetGroup_UI.swf/TheVille_50.png",
    # "pic_square": "assets/game/GeneralAssetGroup_UI.swf/TheVille_50.png"}]},
    #     "fourteenDayFriends": {"data": []},
    #     "thirtyDayFriends": {"data": []},
    #     "payerFriends": {"data": []},
    #     "allFriends": {"data": [{"zid": 124,"uid":124, "first_name": "MissTery", "sex": 'F',"portrait": "assets/game/GeneralAssetGroup_UI.swf/TheVille_50.png",
    # "pic": "assets/game/GeneralAssetGroup_UI.swf/TheVille_50.png",
    # "pic_square": "assets/game/GeneralAssetGroup_UI.swf/TheVille_50.png"}]},
    #     "zyngaFriendsByEngagement": {"data": []},
    #     "empireFriendsByEngagement": {"data": []},


    friend_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                       "data": friend}
    return friend_response


def invader_response():
    invader_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                        "data": [invader_entry(k[1:]) for k, v in session['user_object']["pvp"]["invaders"].items() if k != "pve"]}
    return invader_response


def neighbor_invader_response(uid):
    saves = [save for save in get_saves() if
              str(save['user_object']["userInfo"]["player"]["uid"]) == str(uid)]

    if saves:
        neigbor_invader_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                            "data": [invader_entry(k[1:]) for k, v in saves[0]['user_object']["pvp"]["invaders"].items() if k != "pve"]}
    else:
        neigbor_invader_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                                    "data": []}
    return neigbor_invader_response


def neighbor_repel_challenge_response(params):
    [save] = [save for save in get_saves() if
              str(save['user_object']["userInfo"]["player"]["uid"]) == str(params[0])]

    neigbor_invader_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                        "data": next((invader_entry(k[1:] + "_" + str(params[0])) for k, v in save['user_object']["pvp"]["invaders"].items() if k == "u" + str(params[1])), None)}
    return neigbor_invader_response


def accept_friend_repel_response(invader_uid):
    accept_friend_repel_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                        "data": []}

    del session['user_object']["pvp"]["invaders"]["u" + invader_uid]
    return accept_friend_repel_response


def reject_friend_repel_response(invader_uid):
    reject_friend_repel_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                        "data": []}

    del session['user_object']["pvp"]["invaders"]["u" + str(invader_uid)]["dID"]
    return reject_friend_repel_response


def cancel_unstarted_challenge_response():
    cancel_unstarted_invasions()
    cancel_unstarted_challenge_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                        "data": []}

    return cancel_unstarted_challenge_response


def invader_entry(id):
    response = {"state": 0,
                "status": 0,
                "pFID": "",
                "eFID": "fleet1_" + id,
                "eID": id,
                "isAI": False,
                "isPVE": False,
                "isAssist": False
                }
    return response


def zlingshot_response():
    zlingshot_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                          "data": {}}
    return zlingshot_response


def recent_response():
    recent_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                       "data": []}
    return recent_response


def friend_info_response():
    friend_info_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                            "data": {"nonAppFriends": [
                                ]}}
    return friend_info_response


def tutorial_response(step, sequence, endpoint):
    meta = {"newPVE": 0}
    qz = {"name": "Q0516", "complete": True, "expired": False, "progress": [1], "completedTasks": 1}
    qz_cadets_start = {"name": "Q0531", "complete": False, "expired": False, "progress": [0], "completedTasks": 0}
    # complete cadets?
    qz_cadets_start = {"name": "Q0531", "complete": False, "expired": False, "progress": [0], "completedTasks": 0}
    qz_cadets_done = {"name": "Q0531", "complete": True, "expired": False, "progress": [1], "completedTasks": 1}
    qz_invasion_start = {"name": "Q6016", "complete": False, "expired": False, "progress": [0], "completedTasks": 0}
    qz_invasion_done = {"name": "Q6016", "complete": True, "expired": False, "progress": [1], "completedTasks": 1}
    flag_Q1098_start = {"name": "Q1098", "complete": False, "expired": False, "progress": [0], "completedTasks": 0}
    flag_Q1098_done = {"name": "Q1098", "complete": True, "expired": False, "progress": [1], "completedTasks": 1}
    cadets_Q0611_start = {"name": "Q0611", "complete": False, "expired": False, "progress": [0], "completedTasks": 0}
    cadets_Q0611_done = {"name": "Q0611", "complete": True, "expired": False, "progress": [1], "completedTasks": 1}
    flag_Q6011_start = {"name": "Q6011", "complete": False, "expired": False, "progress": [0], "completedTasks": 0}
    flag_Q6011_done = {"name": "Q6011", "complete": True, "expired": False, "progress": [1], "completedTasks": 1}

    sergeant_Q0671_start = {"name": "Q0671", "complete": False, "expired": False, "progress": [0, 0],
                            "completedTasks": 0}  # after 6011
    sergeant_Q0671_done = {"name": "Q0671", "complete": True, "expired": False, "progress": [1, 1], "completedTasks": 2}
    flag_Q0591_start = {"name": "Q0591", "complete": False, "expired": False, "progress": [0], "completedTasks": 0}
    flag_Q0591_done = {"name": "Q0591", "complete": True, "expired": False, "progress": [1], "completedTasks": 1}
    farm_Q0571_start = {"name": "Q0571", "complete": False, "expired": False, "progress": [0, 0], "completedTasks": 0}
    farm_Q0571_done = {"name": "Q0571", "complete": True, "expired": False, "progress": [1, 1], "completedTasks": 2}
    corn_Q0521_start = {"name": "Q0521", "complete": False, "expired": False, "progress": [0], "completedTasks": 0}
    corn_Q0521_done = {"name": "Q0521", "complete": True, "expired": False, "progress": [1], "completedTasks": 1}
    parliament_Q0691_start = {"name": "Q0691", "complete": False, "expired": False, "progress": [0],
                              "completedTasks": 0}
    parliament_Q0691_done = {"name": "Q0691", "complete": True, "expired": False, "progress": [1], "completedTasks": 1}

    # if step == 'tut_step_placeBarracksServer':
    #     meta['QuestComponent'] = [qz, qz_cadets_start]
    # if step == 'tut_step_cadetsComplete':
    #     pass
    # handle_quest_progress(meta, progress_action("build")) build is covered
    # meta['QuestComponent'] = [qz_cadets_done, qz_invasion_start]  #what starts invasion?
    ## meta["newPVE"] = {"status": 2, "pos": "60,63,0", "villain":"v18", "quest":"Q6016"}
    # if step == 'tut_step_firstInvasionEnd':
    # if step == 'tut_step_postFirstInvasionResumeQuests':
    #     handle_quest_progress(meta, progress_action(
    #         "fight"))
    # meta['QuestComponent'] = [qz_invasion_done,flag_Q1098_start,cadets_Q0611_start]
    #  meta["newPVE"] = {"status": 2, "pos": "60,66,0", "villain":"v18", "quest":"Q6016"}  #contineous battle mode experience QT01_05b_2
    # if step == 'tut_step_placeFlagQuestDialog':
    #     meta['QuestComponent'] = [flag_Q1098_done, flag_Q6011_start]

    # if step == 'tut_step_placeFlagWaitForInventoryOpen':   # sometimes one of them is skipped?
    #     meta['QuestComponent'] = [flag_Q1098_done, flag_Q6011_start]
    # if step == 'tut_step_placeFlagEnd':
    #     meta['QuestComponent'] = [flag_Q6011_done, sergeant_Q0671_start, flag_Q0591_start]
    # if step == 'tut_step_buildFarm':  #after cadets placed?
    #     meta['QuestComponent'] = [cadets_Q0611_done, sergeant_Q0671_start] #possibly already done by this point see if it doesn't redo quests already done
    # if step == 'tut_step_placeHouseEnd':  #after cadets placed?
    #     meta['QuestComponent'] = [flag_Q0591_done, farm_Q0571_start]
    # if step == 'tut_step_placeFarmEnd':  #after cadets placed?
    #     meta['QuestComponent'] = [farm_Q0571_done, corn_Q0521_start, parliament_Q0691_start, sergeant_Q0671_start]
    #
    if step == 'tut_step_inviteFriendsEndPauseTutorial':
        handle_quest_progress(meta, progress_neighbor_count())

    merge_quest_progress(meta['QuestComponent'] if 'QuestComponent' in meta else [], session['quests'], "session quest")
    session['user_object']["userInfo"]["player"]["tutorialProgress"] = step  # TODO: revert step when loading if needed

    report_tutorial_step(step, meta['QuestComponent'] if 'QuestComponent' in meta else None, meta['newPVE'], sequence,
                         endpoint)
    tutorial_response = {"errorType": 0, "userId": 1, "metadata": meta,
                         "data": []}
    return tutorial_response


#def perform_world_response(step, supplied_id, position, item_name, reference_item, from_inventory, elapsed, cancel, req2):
def perform_world_response(params):

    step=params[0]
    supplied_id=params[1].id
    position=params[1].position
    item_name=params[1].itemName

    reference_item=params[2][0].get('referenceItem') if len(params[2]) > 0 else None
    from_inventory=params[2][0].get('isGift') if len(params[2]) > 0 else None
    elapsed=params[2][0].get('elapsed') if len(params[2]) > 0 else None
    cancel=params[2][0].get('cancel') if len(params[2]) > 0 else None
    req2=params[2][0] if len(params[2]) > 0 else None
    index_ref=params[2][0] if len(params[2]) > 0 else None

    print("this is step",step, supplied_id, position)

    id = supplied_id
    if step == "place":
        session['user_object']["userInfo"]["world"]["globalObjectId"] += 1  # for place only!
        id = session['user_object']["userInfo"]["world"]["globalObjectId"]
        session['user_object']["userInfo"]["world"]["objects"].append({
            "id": id,
            "itemName": item_name,
            "position": position,
            "referenceItem": reference_item,
            "state": 0
        })

    # cur_object = lookup_object(id)
    # print("cur_object used:"`, repr(cur_object))
    #
    #
    # game_item = lookup_item(item_name)
    # print("item used:", repr(game_item))
    #
    # state_machine = lookup_state_machine(game_item['stateMachineValues']['-stateMachineName'])
    # print("state_machine used:", repr(state_machine))
    # state = lookup_state(state_machine, cur_object['state'])
    # print("cur state:", repr(state))
    # next_click_state = lookup_state(state_machine, state['-clickNext']) # not all states have this!! end states? autostate after time?
    # print("next_click_state:", repr(next_click_state))
    meta = {"newPVE": 0}
    print(step)
    if step in ["place", "setState"]:
        click_next_state(True, id, meta, step, reference_item, cancel=cancel)  # place & setstate only

    if step == "setState":
        if lookup_object(id)["referenceItem"] == None and reference_item != None:
            costs = lookup_item_by_code(reference_item.split(":")[0]).get("cost")
            do_costs({k: v for k, v in costs.items() if k != "-cash"})
        lookup_object(id)["referenceItem"] = reference_item

    if step == "clear":
        session['user_object']["userInfo"]["world"]["objects"].remove(lookup_object(id))
        print("Object", id, "removed")

    if step == "move":
        lookup_object(id)["position"] = position
        print("Object", id, "moved to", position)

    if step == "place":
        if not from_inventory:
            costs = lookup_item_by_name(item_name).get("cost")
            if "-unitClass" in lookup_item_by_name(item_name):
                do_costs({k: v for k, v in costs.items() if k == "-cash"})
            else:
                do_costs(costs)
        else:
            item = lookup_item_by_name(item_name)
            item_inventory = session['user_object']["userInfo"]["player"]["inventory"]["items"]

            if item['-code'] in item_inventory:
                item_inventory[item['-code']] -= 1
                if item_inventory[item['-code']] <= 0:
                    del item_inventory[item['-code']]
                print("Placing", item_name + "(" + item['-code'] + ")", "from inventory")
            else:
                print("ERROR: Placing", item_name + "(" + item['-code'] + ")",
                      "from inventory but not in inventory. Ignoring for now.")

    if step == "speedUp":
        # lookup_object(id)['lastUpdated'] = lookup_object(id).get('lastUpdated', 0) - elapsed * 1000
        click_next_state(False, id, meta, step, reference_item, speed_up=True)
    # TODO: cost of speedup?

    if step == "add":
        market = lookup_object(id)
        refund_market_order(market)
        place_market_order(market, req2, meta)

    perform_world_response = {"errorType": 0, "userId": 1, "metadata": meta,
                              "data": {"id": id}}
    if step == "list":
        market = lookup_object(id)
        # perform_world_response["data"].update(session['market'].get(str(id), {}))
        perform_world_response["data"] = [market]
        # perform_world_response["data"][0]["id"] = id

    if step == "remove":
        market = lookup_object(id)
        perform_world_response["data"] = ["success"]  #  TODO fail if bought
        refund_market_order(market)

    if step == "sell":
        for i in range(len(session['user_object']["userInfo"]["world"]["objects"])):
            if session['user_object']["userInfo"]["world"]["objects"][i]['position'] == position:
                del session['user_object']["userInfo"]["world"]["objects"][i]
                break
        #TODO cost for selling
        # list1 = session['user_object']["userInfo"]["world"]["objects"]
        # session['user_object']["userInfo"]["world"]["objects"] = list(filter(lambda i: i['position'] != position), list1)

    if step == "staffPosition":
        crewTemplate = lookup_crew_template(item_name)
        num_slots = len(crewTemplate["position"])
        decoration = lookup_object(id)

         # TODO Crew index position is given, but not used.
        position_index = index_ref['index']

        current_crew = decoration.get("crewInfo", [])
        new_crew = current_crew + ["-1"]
        decoration["crewInfo"] = new_crew[:num_slots]

        print("staffing")

    if step == "decoCrewBuyOnce":
        decoration = lookup_object(id)
        item = lookup_item_by_name(item_name)
        decoration["crewInfo"] = [-1, -1, -1]
        print("staffing full")

    if step == "randomRewards":
        print(lookup_item_by_name(item_name).get("-code", 0))
        item_info = randomReward(lookup_item_by_name(item_name).get("-code", 0))
        item_code = item_info[0]
        item_amount = item_info[1]
        item_type = item_info[2]
        perform_world_response["data"]["data"] = {}
        perform_world_response["data"]["data"]["type"] = item_type
        perform_world_response["data"]["data"]["item"] = item_code
        perform_world_response["data"]["data"]["count"] = item_amount
        if item_type == "item":
            if item_code not in session['user_object']["userInfo"]["player"]["inventory"]["items"]:
                session['user_object']["userInfo"]["player"]["inventory"]["items"][item_code] = item_amount
            else:
                session['user_object']["userInfo"]["player"]["inventory"]["items"][item_code] += item_amount
        elif item_type == "cash":
            session['user_object']["userInfo"]["player"]["cash"] += item_amount
        else:
            session['user_object']["userInfo"]["world"]['resources']["coins"] += item_amount

    print("perform_world_response", repr(perform_world_response))
    return perform_world_response


def refund_market_order(market):
    world = session['user_object']["userInfo"]["world"]
    resources = world['resources']
    if market.get("type") == "resource":
        standard_resources = ["coins", "oil" , "wood", "aluminum", "copper", "gold", "iron", "uranium"]
        resources[standard_resources[int(market["item"])]] += market["units"]
        print("Market: Refunded", standard_resources[int(market["item"])] + ":", str(market["units"]) +
              "(" + str(resources[standard_resources[int(market["item"])]]) + ")")
    else:
        print("TODO: Can't refund market type", market.get("type"), "yet")
    market["type"] = None
    market["item"] = None
    market["units"] = None


def place_market_order(market, order, meta):
    world = session['user_object']["userInfo"]["world"]
    resources = world['resources']
    if order["type"] == "resource":
        standard_resources = ["coins", "oil", "wood", "aluminum", "copper", "gold", "iron", "uranium"]
        resources[standard_resources[int(order["item"])]] -= order["units"]
        print("Market: Order placed & removed", standard_resources[int(order["item"])] + ":", str(order["units"])
              + "(" + str(resources[standard_resources[int(order["item"])]]) + ")")
        handle_quest_progress(meta, progress_market_added_count(order["units"]))
    else:
        print("TODO: Can't reserve market type", order.get("type"), "yet")
    market["type"] = order["type"]
    market["item"] = order["item"]
    market["units"] = order["units"]


def neighbor_suggestion_response():
    neighbor_suggestion_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                                    "data": get_suggested_friends()}
    return neighbor_suggestion_response


def seen_flag_response(flag):
    seen_flags = session['user_object']["userInfo"]["player"]["seenFlags"]

    seen_flags[flag] = seen_flags.get(flag, 0) + 1

    seen_flag_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                          "data": []}
    return seen_flag_response


def random_fleet_challenge_response(host_uid):
    unit_user = "U01,,,,"
    unit = "U01,,,,"

    # user_fleet = {
    #     "type": "army",
    #     "uid": "0",
    #     "name": "FleetName",
    #     "status": 0,
    #     "target": "",
    #     "consumables": [],
    #     "inventory": [],
    #     "playerLevel": 1,
    #     "specialBits": None,
    #     "lost": None,
    #     "lastUnitLost": None,
    #     "lastIndexLost": None,
    #     "allies": None,
    #     "battleTarget": None,
    #     "battleTimestamp": None,
    #     "ransomRandom": None,
    #     "ransomResource": None,
    #     "ransomAmount": None,
    #     "units": [
    #         unit_user,
    #
    #               ],  # only one unit for tutorial [unit, unit, unit],
    #     "store": [0],  # [0, 0, 0],
    #     "fleets": None,
    #     "upgrades": None,
    #     "hp": None
    # }

    [save] = [save for save in get_saves() if str(save['user_object']["userInfo"]["player"]["uid"]) == str(host_uid)]
    defender_fleet = save['user_object']["pvp"]["invaders"]["u" + str(get_zid())]["defender_fleet"]

    subtype = lookup_item_by_code(defender_fleet[0].split(',')[0])["-subtype"]

    fleet = {
        "type": subtype,
        "uid": host_uid,
        "name": "FleetName",
        "status": 0,
        "target": "",
        "consumables": [],
        "inventory": [],
        "playerLevel": 1,
        "specialBits": None,
        "lost": None,
        "lastUnitLost": None,
        "lastIndexLost": None,
        "allies": None,
        "battleTarget": None,
        "battleTimestamp": None,
        "ransomRandom": None,
        "ransomResource": None,
        "ransomAmount": None,
        "units": defender_fleet,
        "store": [0],  # [0, 0, 0],
        "fleets": [],
        "upgrades": None,
        "hp": None,
        "invader": False
    }

    register_fleetname_fleet(fleet)

    random_fleet_challenge_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                                       "data": {
                                           "state": 0,
                                           "challengerFleet": fleet,
                                           "challengeInfo": {"status": 0, "state": 1},
                                           "maxUnits": 5
                                       }}
    return random_fleet_challenge_response


def random_enemy_fleet_challenge_response(enemy_fleet_id):
    unit_user = "U01,,,,"
    unit = "U01,,,,"

    # user_fleet = {
    #     "type": "army",
    #     "uid": "0",
    #     "name": "FleetName",
    #     "status": 0,
    #     "target": "",
    #     "consumables": [],
    #     "inventory": [],
    #     "playerLevel": 1,
    #     "specialBits": None,
    #     "lost": None,
    #     "lastUnitLost": None,
    #     "lastIndexLost": None,
    #     "allies": None,
    #     "battleTarget": None,
    #     "battleTimestamp": None,
    #     "ransomRandom": None,
    #     "ransomResource": None,
    #     "ransomAmount": None,
    #     "units": [
    #         unit_user,
    #
    #               ],  # only one unit for tutorial [unit, unit, unit],
    #     "store": [0],  # [0, 0, 0],
    #     "fleets": None,
    #     "upgrades": None,
    #     "hp": None
    # }

    placeholder_fleet = [format_player_fleet("PT24"), format_player_fleet("PT23"), format_player_fleet("PT02"), format_player_fleet("PT22"), format_player_fleet("PT12")]

    if len(enemy_fleet_id.split("_")) <= 2:
        attacker_fleet = session['user_object']["pvp"]["invaders"]["u" + enemy_fleet_id.split("_")[1]].get('attacker_fleet', placeholder_fleet)
    else:
        [save] = [save for save in get_saves() if
                  str(save['user_object']["userInfo"]["player"]["uid"]) == str(enemy_fleet_id.split("_")[2])]
        attacker_fleet = save['user_object']["pvp"]["invaders"]["u" + enemy_fleet_id.split("_")[1]].get('attacker_fleet', placeholder_fleet)

    subtype = lookup_item_by_code(attacker_fleet[0].split(',')[0])["-subtype"]

    fleet = {
        "type": subtype,
        "uid": enemy_fleet_id.split("_")[1],
        "invaded_uid": enemy_fleet_id.split("_")[2] if len(enemy_fleet_id.split("_")) > 2 else None,
        "name": "FleetName",
        "status": 0,
        "target": "",
        "consumables": [],
        "inventory": [],
        "playerLevel": 1,
        "specialBits": None,
        "lost": None,
        "lastUnitLost": None,
        "lastIndexLost": None,
        "allies": None,
        "battleTarget": None,
        "battleTimestamp": None,
        "ransomRandom": None,
        "ransomResource": None,
        "ransomAmount": None,
        "units": attacker_fleet,  # [unit,unit,unit,unit,unit],  # only one unit for tutorial [unit, unit, unit],
        "store": [0],  # [0, 0, 0],
        "fleets": [],
        "upgrades": None,
        "hp": None,
        "invader": True
    }

    register_fleetname_fleet(fleet)

    random_enemy_fleet_challenge_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                                       "data": {
                                           "state": 0,
                                           "challengerFleet": fleet,
                                           "challengeInfo": {"status": 0, "state": 1},
                                           "maxUnits": 5
                                       }}
    return random_enemy_fleet_challenge_response


def load_challenge_response(param):
    load_challenge_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                               "data": {"eFID": "pve", "state": 1}}  # CHALLENGE_STATE_IN_PROGRESS

    session["fleets"][param['challengeeFleet']['name']] = param['challengeeFleet']['units']
    print("Challenge Player fleet:", param['challengeeFleet']['units'])

    return load_challenge_response


def occupation_place_response(params):
    cancel_unstarted_invasions()

    [save] = [save for save in get_saves() if str(save['user_object']["userInfo"]["player"]["uid"]) == str(params[0])]
    occupied_objects = lookup_objects_save_by_position(save, params[1], params[2], 5)
    # todo defenders from larger area?
    # occupied_objects_double = lookup_objects_save_by_position(save, params[1] - 3, params[2] - 3, 11)
    occupied_items = [lookup_item_by_name(e["itemName"]) for e in occupied_objects]
    defense_units = [e for e in occupied_items if "unit" in e]
    defense_units.sort(key=lambda e: int(e["unit"].get("-strength", "1000")), reverse=True)

    subtype = defense_units[0]["-subtype"] if defense_units else "army"

    defense_units = [e for e in defense_units if e["-subtype"] == subtype]

    defense_units = defense_units[:5]

    defense_fleet = [format_player_fleet(e["-code"]) for e in defense_units][:5]

    if not defense_fleet:
        defense_fleet = [format_player_fleet("PT24"), format_player_fleet("PT23"), format_player_fleet("PT02"), format_player_fleet("PT22"), format_player_fleet("PT12")]
    else:
        defense_fleet = (defense_fleet + [format_player_fleet("U01" if subtype == "army" else ("U43" if subtype == "navy" else "U66"))] * 2)[:5]

    save['user_object']["pvp"]["invaders"]["u" + str(get_zid())] = {
        "ts": datetime.now().timestamp(),
        "pillTS": datetime.now().timestamp(),
        "status": 1,
        "pos":  str(params[1]) + "," + str(params[2]),
        "size": 5,
        "chID": str(get_zid()),
        "defender_fleet": defense_fleet
    }
    store_session(save)

    occupation_place_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                      "data": []}
    return occupation_place_response


def pillage_response(params):
    [save] = [save for save in get_saves() if str(save['user_object']["userInfo"]["player"]["uid"]) == str(params[0])]
    # occupied_objects = lookup_objects_save_by_position(save, params[1], params[2], 5)
    # occupied_items = [lookup_item_by_name(e["itemName"]) for e in occupied_objects]
    # defense_units = [e for e in occupied_items if "unit" in e]
    # defense_units.sort(key=lambda e: int(e["unit"].get("-strength", "1000")), reverse=True)
    # defense_units = defense_units[:5]

    save['user_object']["pvp"]["invaders"]["u" + str(get_zid())]["pillTS"] = datetime.now().timestamp()
    store_session(save)

    pillage_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                      "data": []}
    return pillage_response



def generic_string_response(param):
    meta = {"newPVE": 0}
    handle_quest_progress(meta, all_lambda(progress_action("genericString"),
                                           progress_parameter_equals("_string", str(param))))

    generic_string_response = {"errorType": 0, "userId": 1, "metadata": meta,
                               "data": []}
    return generic_string_response


def streak_bonus_response(param):
    meta = {"newPVE": 0}

    do_rewards("Streak", {"_type": "coins", "_count": param["amount"]}, meta)

    streak_bonus_response = {"errorType": 0, "userId": 1, "metadata": meta,
                             "data": []}
    return streak_bonus_response


def world_name_response(name):
    world_name_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                           "data": []}
    session['user_object']["userInfo"]["worldName"] = name

    return world_name_response


def update_roads_response(roads):
    session["user_object"]["userInfo"]["world"]["roadData"] = roads
    update_roads_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                             "data": []}
    return update_roads_response


def stream_publish_response(params):
    meta = {"newPVE": 0}
    handle_quest_progress(meta, progress_feed(params[0]))
    stream_publish_response = {"errorType": 0, "userId": 1, "metadata": meta,
                               "data": []}
    return stream_publish_response


def stop_mayhem_response():
    stop_mayhem_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                            "data": []}
    return stop_mayhem_response


def save_options_response(options):
    save_options_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                             "data": []}
    session['user_object']["userInfo"]["player"]["options"] = options
    return save_options_response


def full_screen_response():
    meta = {"newPVE": 0}
    handle_quest_progress(meta, progress_action("fullscreen"))
    full_screen_response = {"errorType": 0, "userId": 1, "metadata": meta,
                            "data": []}
    return full_screen_response


def view_zoom_response(zoom):
    meta = {"newPVE": 0}
    handle_quest_progress(meta, all_lambda(progress_action("zoom"), progress_parameter_equals("_zoom", str(zoom))))
    view_zoom_response = {"errorType": 0, "userId": 1, "metadata": meta,
                          "data": []}
    return view_zoom_response


def load_world_response(params):
    meta = {"newPVE": 0}
    handle_quest_progress(meta, progress_action("visit"))

    print("world response. requested uid=", int(params[0]), session['user_object']["userInfo"]["player"]["uid"])
    if int(params[0]) == session['user_object']["userInfo"]["player"]["uid"]:
        ally = session['user_object']["userInfo"]
        # qc = session['quests']
        print("reloading user from save")
    else:
        ally = copy.deepcopy(init_user()["userInfo"])
        if int(params[0]) == STEELE_ID:
            ally["world"]["sizeX"] = 100
            ally["world"]["sizeY"] = 100
        ally["player"]["uid"] = int(params[0])
        if str(params[0]) in allies:
            if "objects" in allies[str(params[0])]:
                ally["world"]["objects"] = allies[str(params[0])]["objects"]
            if "roads" in allies[str(params[0])]:
                ally["world"]["roadData"] = allies[str(params[0])]["roads"]
            ##Added
            if "expansions" in allies[str(params[0])]:
                ally["expansions"] = allies[str(params[0])]["expansions"]
            if "worldName" in allies[str(params[0])]:
                ally["worldName"] = allies[str(params[0])]["worldName"]
            if "titanName" in allies[str(params[0])]:
                ally["titanName"] = allies[str(params[0])]["titanName"]
        else:
            [save] = [save for save in get_saves() if str(save['user_object']["userInfo"]["player"]["uid"]) == str(params[0])]
            ally["world"]["objects"] = save['user_object']["userInfo"]["world"]["objects"]
            ally["world"]["roadData"] = save['user_object']["userInfo"]["world"]["roadData"]
            ally["expansions"] = save['user_object']["userInfo"]["player"]["expansions"]
            ally["worldName"] = save['user_object']["userInfo"]["worldName"]
            ally["titanName"] = save['user_object']["userInfo"]["titanName"]
            ally["pvpInvaders"] = save['user_object']["pvp"]["invaders"]

        # ally["gf"] = False
        # ally["yimf"] = ""
        # ally["novisit"] = False
        # ally["globalPVP"] = {}
        # ally["nonFriendInfo"] = {}
        # ally["untendableObjIDs"] = []

        # ally["world"]["yimf"] = ""
    ally["pvpMode"] = params[2]
    ally["pvpImmunity"] = {"expTS": None}
    ally["visitorEnergy"] = 5

    load_world_response = {"errorType": 0, "userId": 1, "metadata": meta,
                           "data": ally}
    return load_world_response


def tend_ally_response(params):
    meta = {"newPVE": 0}
    handle_quest_progress(meta, progress_action("tending"))

    for save in get_saves():
        if save['user_object']["userInfo"]["player"]["uid"] == int(params[0]):
            if not save['user_object']["visitorHelpRequests"]:
                save['user_object']["visitorHelpRequests"] = {}
            if str(get_zid()) in save['user_object']["visitorHelpRequests"]:
                save['user_object']["visitorHelpRequests"][str(get_zid())] += "," + str(params[1])
            else:
                save['user_object']["visitorHelpRequests"][str(get_zid())] = str(params[1])
            store_session(save)
            click_next_state(False, params[1], meta, None, None, tending=True, save=copy.deepcopy(save), tend_type=params[2])

    tend_ally_response = {"errorType": 0, "userId": 1, "metadata": meta,
                          "data": []}
    return tend_ally_response


def accept_tend_ally_response(params):
    meta = {"newPVE": 0}
    for item in session['user_object']["visitorHelpRequests"][params[0]].split(","):
        click_next_state(False, int(item), meta, None, None, playback_tend=True)

    del session['user_object']["visitorHelpRequests"][params[0]]

    accept_tend_ally_response = {"errorType": 0, "userId": 1, "metadata": meta,
                          "data": []}
    return accept_tend_ally_response


def decline_tend_ally_response(params):
    meta = {"newPVE": 0}

    del session['user_object']["visitorHelpRequests"][params[0]]

    decline_tend_ally_response = {"errorType": 0, "userId": 1, "metadata": meta,
                          "data": []}
    return decline_tend_ally_response


def add_fleet_response(param):
    meta = {"newPVE": 0}

    add_fleet_response = {"errorType": 0, "userId": 1, "metadata": meta,
                          "data": []}

    session["fleets"][param['name']] = param['units']
    if "allies" in param:
        session["fleets"]["ally_" + param['name']] = param['allies']
    print("Player fleet:", param['units'])
    return add_fleet_response

def buy_item_response(param):
    meta = {"newPVE": 0}
    print(param)
    buy_item(meta, param["code"], param["amount"])
    buy_item_response = {"errorType": 0, "userId": 1, "metadata": meta,
                      "data": []}
    return buy_item_response
    #TODO buy powerup in combact


def buy_item(meta, code, amount):
    item = lookup_item_by_code(code)
    player = session['user_object']["userInfo"]["player"]
    world = session['user_object']["userInfo"]["world"]
    resources = world['resources']
    # standard_resources = ["coins", "oil", "wood", "aluminum", "copper", "gold", "iron", "uranium"]
    # resources[standard_resources[int(market["item"])]] += market["units"]
    if item["-type"] == 'mercenary':
        print("Buying mercenary")
    elif item.get("-subtype") == "expansion":
        print("Buying expansion")
    elif "-resourceType" in item and item["-resourceType"] != "energy":
        resources[item["-resourceType"]] += amount * int(item.get("resourceYield", "1"))

        print("Buy: received", item["-resourceType"] + ":", str(amount) +
              "(" + str(resources[item["-resourceType"]]) + ")")
    else:
        # param["useCash"]
        item_inventory = session['user_object']["userInfo"]["player"]["inventory"]["items"]
        item_inventory[code] = item_inventory.get(code, 0) + 1
    player['cash'] -= get_cash_cost(item, amount)
    handle_quest_progress(meta, progress_buy_consumable(item))


def buy_items_response(param):
    print(repr(param))
    meta = {"newPVE": 0}
    resource_Dict = dict(param["itemData"])
    for Res_code in resource_Dict:
        buy_item(meta, Res_code,resource_Dict[Res_code])
    buy_items_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                      "data": []}
    return buy_items_response


def use_item_response(param):
    print(param)
    item_inventory = session['user_object']["userInfo"]["player"]["inventory"]["items"]
    item_inventory[param] -= 1
    use_item_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                      "data": []}

    return use_item_response



# TODO
def purchase_energy_refill_response(param):
    print(repr(param))

    player = session['user_object']["userInfo"]["player"]
    world = session['user_object']["userInfo"]["world"]
    resources = world['resources']

    player['energy'] += int(player['energyMax']-player['energy'])  # TODO put item in inventory (storable?)

    player['cash'] -= int(player['energyMax']-player['energy'])

    purchase_energy_refill_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                      "data": []}
    return purchase_energy_refill_response


def buy_quest_task_response(param):
    print(param,type(param))
    
    # reqq.params[2][0].get('referenceItem')
    # player = session['user_object']["userInfo"]["player"]
    # world = session['user_object']["userInfo"]["world"]

    meta = {"newPVE": 0}
    handle_quest_progress(meta, progress_quest_task(param["name"], param["taskIndex"]))
    buy_quest_task_response = {"errorType": 0, "userId": 1, "metadata": meta, "data": []}
    return buy_quest_task_response


def buy_expansion_response(param):
    print(repr(param))
    unlock_expansion(param['index'])
    meta = {"newPVE": 0}
    handle_quest_progress(meta, progress_action("expansionsPurchased"))
    buy_expansion_response = {"errorType": 0, "userId": 1, "metadata": meta,
                      "data": []}
    return buy_expansion_response


def purchase_contact_unlock(param):
    print(repr(param))
    item = lookup_item_by_code(param["itemCode"])

    #TODO specops contractMultiple
    unlock_cost = int(game_settings['settings']['gamesettings']['-contractUnlockMultiple']) * get_cash_cost(item, 1)

    player = session['user_object']["userInfo"]["player"]
    player['cash'] -= unlock_cost
    item_inventory = session['user_object']["userInfo"]["player"]["inventory"]["items"]
    item_inventory[param["itemCode"]] = item_inventory.get(param["itemCode"], 0) + 1
    player['unlockedContracts'].append(param["itemCode"])

    meta = {"newPVE": 0}
    purchase_contact_unlock = {"errorType": 0, "userId": 1, "metadata": meta,
                              "data": []}
    return purchase_contact_unlock


def get_cash_cost(item, amount):
    #TODO unit price expirements cost
    #TODO priceTestSettings
    #TODO EXPERIMENT_LE_DISCOUNT_SALE
    cash_cost = float(item["cost"]["-cash"])

    required_level = int(item.get("requiredLevel", "0"))
    player_level = session["user_object"]["userInfo"]["player"]["level"]

    le_discount = 0
    if "requiredDate" in item:
        if required_level >= 25:
            if player_level >= 51:
                le_discount = .25
            elif player_level >= 35:
                le_discount = .15
        elif required_level >= 15:
            if player_level >= 51:
                le_discount = .30
            elif player_level >= 35:
                le_discount = .20
            elif player_level >= 20:
                le_discount = .10

    return math.ceil(cash_cost * amount * (1 - le_discount))


def select_response(param):
    meta = {"newPVE": 0}
    handle_quest_progress(meta, all_lambda(progress_action("select"),
                                           progress_parameter_equals("_item", param['itemCode'])))
    select_response = {"errorType": 0, "userId": 1, "metadata": meta,
                          "data": []}
    return select_response


def part_request_response(params):
    item = lookup_item_by_name(params[0])
    item_inventory = session['user_object']["userInfo"]["player"]["inventory"]["items"]

    item_inventory[item["-code"]] = item_inventory.get(item["-code"], 0) + len(params[3])

    meta = {"newPVE": 0}
    handle_quest_progress(meta, progress_gifted_parts(item, len(params[3])))
    handle_quest_progress(meta, progress_inventory_count())

    part_request_response = {"errorType": 0, "userId": 1, "metadata": meta,
                      "data": []}
    return part_request_response

def crew_request_response(params):
    # 'params': [[124], 10003, 'Parliament', 'crew']
    friends = params[0]
    building_id = params[1]
    building_name = params[2]
    action = params[3]
    
    building = lookup_object(building_id)
    
    if action == 'crew':
        
        current_crew = building.get("crewInfo", [])

        crewTemplate = lookup_crew_template(building_name)
        max_buyable_slots = int(crewTemplate["-numUnbuyableSlots"])
        num_slots = len(crewTemplate["position"])

        # Empty slots are automatically filled.
        avail_slots = max(min(num_slots - len(current_crew), num_slots), 0)
        new_crew = current_crew + friends[:avail_slots]
        building["crewInfo"] = [str(x) for x in new_crew] # string needed, so that no friend is 'deleted' on display
        
        print(building_name, "new crew (max", num_slots, "slots):", building.get("crewInfo", []))
    
    meta = {"newPVE": 0}
    crew_request_response = {"errorType": 0, "userId": 1, "metadata": meta, 'data': []}
    return crew_request_response


def exit_battle_response():
    exit_battle_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                      "data": []}
    session["battle"] = None

    return exit_battle_response


def load_survival_mode_response(param):
    wave_index = session["fleets"]["FleetName"]["playerLevel"] + 1 if "FleetName" in session["fleets"] and session["fleets"]["FleetName"]["status"] == 4096 and param["set"] is None else 1
    if param.get("continueGame") or "playerFleet" in param:
        wave_index = wave_index - 1
    wave = lookup_wave("set3", wave_index)

    baddies = ['%s,,,,' % baddy[1:] for sub_fleet in
               simple_list(wave['fleet'])
               for baddy, count in sub_fleet.items()
               for i in range(int(count))]

    fleet = {
        "type": wave["-unitType"],
        "uid": 1,
        "name": "FleetName",
        "status": 4096, #survival enemy
        "target": "",
        "consumables": [],
        "inventory": [],
        "playerLevel": wave_index,
        "specialBits": None,
        "lost": None,
        "lastUnitLost": None,
        "lastIndexLost": None,
        "allies": None,
        "battleTarget": None,
        "battleTimestamp": None,
        "ransomRandom": None,
        "ransomResource": None,
        "ransomAmount": None,
        "units": baddies,
        "store": [0],  # [0, 0, 0],
        "fleets": [],
        "upgrades": None,
        "hp": None,
        "invader": True
    }

    if "playerFleet" in param:
        load_survival_mode_resp = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                                   "data": {'state': 1, 'storage': {"curSet": "set3", "curWave": wave_index, "curLoop": 0,
                                                                    "curPlayerFleet": None,
                                                                    "curEnemyFleet": None, "lastPlayedTime": 0,
                                                                    "rewardRefreshCount": 0, "rewards": {},
                                                                    "rewardChanged": False}}}
        session["fleets"][param['playerFleetName']] = param["playerFleet"]["units"]
    elif param["set"] is None and not param.get("continueGame"):
        # load_survival_mode_resp = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
        #                            "data": {}}
        load_survival_mode_resp = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                                   "data": {'state': 3, 'storage': {"curSet": "set3", "curWave": wave_index, "curLoop": 0,
                                                                    "curPlayerFleet": get_survival_player_fleet(),
                                                                    "curEnemyFleet": fleet, "lastPlayedTime": 0,
                                                                    "rewardRefreshCount": 0, "rewards": {},
                                                                    "rewardChanged": False}, "enemyWaveFleet": fleet, "playerFleet":get_survival_player_fleet()}}
        session["battle"] = session["last_battle"]
        session["battle"] = ([e for e in session["battle"][0] if e != 0], None, session["battle"][2])
        register_fleetname_fleet(fleet)
    else:
        load_survival_mode_resp = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                                   "data": {'state': 2, 'storage': {"curSet": "set3", "curWave": wave_index, "curLoop": 0,
                                                                    "curPlayerFleet": None,
                                                                    "curEnemyFleet": None, "lastPlayedTime": 0,
                                                                    "rewardRefreshCount": 0, "rewards": {},
                                                                    "rewardChanged": False}, "enemyWaveFleet": fleet}}
        register_fleetname_fleet(fleet)
        session["last_battle"] = None
    return load_survival_mode_resp


def get_survival_player_fleet():
    player_units = session["fleets"][get_last_fleet_name()]
    subtype = lookup_item_by_code(player_units[0].split(',')[0])["-subtype"]

    fleet = {
    "type": subtype,
    "uid": get_zid(),
    "name": get_last_fleet_name(),
    "status": 2048,  # survival player
    "target": "",
    "consumables": [],
    "inventory": [],
    "playerLevel": 1,
    "specialBits": None,
    "lost": None,
    "lastUnitLost": None,
    "lastIndexLost": None,
    "allies": None,
    "battleTarget": None,
    "battleTimestamp": None,
    "ransomRandom": None,
    "ransomResource": None,
    "ransomAmount": None,
    "units": ["%s,%d,%d,," % (p.split(',')[0], session["last_battle"][0][i], is_shielded(("ally", i), session["last_battle"][2])) for i, p in enumerate(player_units) if session["last_battle"][0][i] != 0],
    "store": [0],  # [0, 0, 0],
    "fleets": [],
    "upgrades": None,
    "hp": None,
    "invader": False
    }
    return fleet

# def unit_encode


def dummy_response():
    dummy_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                      "data": []}
    return dummy_response


@app.route("/language_editor")
def language_editor():
    tree = ET.parse("assets/29oct2012/en_US.xml")
    root = tree.getroot()
    for pkg in root:
        print(pkg.tag, pkg.attrib)
        for text in pkg:
            print("  ",text.tag, text.attrib)

    return '', 204



# @app.after_request
# def add_header(r):
#     """
#     Add headers to both force latest IE rendering engine or Chrome Frame,
#     and also to cache the rendered page for 10 minutes.
#     """
#     # r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
#     # r.headers["Pragma"] = "no-cache"
#     # r.headers["Expires"] = "0"
#     # r.headers['Cache-Control'] = 'public, max-age=0'
#     return r

@socketio.on('message')
def handle_message(message):
    print('received message: ' + message)


@socketio.on('my event')
def handle_my_custom_event(json):
    print('received json: ' + str(json))


@socketio.on('delete_save')
def delete_save(message):
    # session.permanent = False
    # session.clear() #unsolved flask-session bug

    # print('deleted save: ' + message)
    print("Save will be deleted after redirect " + message)


@app.errorhandler(500)
def server_error_page(error):
    if crash_log:
        text = editor.edit(filename=os.path.join(log_path(), "log.txt"))
    return 'It went wrong'


if __name__ == '__main__':
    if 'WERKZEUG_RUN_MAIN' not in os.environ and open_browser:
        if os.path.exists(os.path.join("chromium", "chrome.exe")):
            threading.Timer(1.25, lambda: os.system(os.path.join("chromium", "chrome.exe") + " --user-data-dir=\"" + os.path.join(my_games_path(), "chromium-profile") + "\"" + " --allow-outdated-plugins " + ("--app=" if app_mode else "") + "http://" + http_host + ":" + str(port) + "/" + http_path)).start()
        elif os.path.exists(os.path.join("chromium", "chrome")):
            threading.Timer(1.25, lambda: os.system(os.path.join("chromium", "chrome") + " --user-data-dir=\"" + os.path.join(my_games_path(), "chromium-profile") + "\"" + " --–allow-outdated-plugins " + ("--app=" if app_mode else "") + "http://" + http_host + ":" + str(port) + "/" + http_path)).start()
        else:
            threading.Timer(1.25, lambda: webbrowser.open("http://" + http_host + ":" + str(port) + "/" + http_path)).start()
    # init_db(app, db)
    set_crash_log(crash_log)
    if compression:
        compress.init_app(app)
    socketio.init_app(app)
    sess.init_app(app)
    db.init_app(app)
    # session.app.session_interface.db.create_all()
    # app.session_interface.db.create_all()
    # db.create_all()

    socketio.run(app, host=host, port=port, debug=debug)
    # app.run(host='127.0.0.1', port=5005, debug=True)
    # logging.getLogger('socketio').setLevel(logging.ERROR)
    # logging.getLogger('engineio').setLevel(logging.ERROR)
    # logging.getLogger('geventwebsocket.handler').setLevel(logging.ERROR)