import getopt
import sys
from tendo import singleton

from save_migration import migrate

opts, args = getopt.getopt(sys.argv[1:],"",["debug"])
debug = ("--debug", '') in opts

if not debug:
    me = singleton.SingleInstance()

from builtins import print
from time import sleep

from flask import Flask, render_template, send_from_directory, request, Response, make_response, redirect
from flask_session import Session
from pyamf import remoting
import pyamf

from battle_engine import battle_complete_response, spawn_fleet, next_campaign_response, assign_consumable_response
from game_settings import game_settings, get_zid, allies, initial_island
import threading, webbrowser
import pyamf.amf0
import json
import os
from flask_sqlalchemy import SQLAlchemy
from flask_compress import Compress
from quest_engine import *
from quest_settings import quest_settings
from state_machine import *
from logger import socketio, report_tutorial_step, report_world_log, report_other_log
import copy

# import logging.config

version = "0.03a"

COMPRESS_MIMETYPES = ['text/html', 'text/css', 'text/xml', 'application/json', 'application/javascript',
                      'application/x-amf']
COMPRESS_LEVEL = 6
COMPRESS_MIN_SIZE = 500

# STATE todo statemachine class
rand_seed_w = 5445  # very random
rand_seed_z = 844

compress = Compress()
sess = Session()
db = SQLAlchemy()

start = datetime.now()

app = Flask(__name__)

app.config['SESSION_TYPE'] = 'sqlalchemy'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///save.db'
app.config['SESSION_SQLALCHEMY'] = db


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/home.html")
def home():
    print("home")
    return render_template("home.html", time=datetime.now().timestamp(), zid=str(get_zid()),
                           allies=json.dumps([ally["friend"] for ally in allies.values()
                                              if "friend" in ally and ally["friend"] and ally["neighbor"]],
                                             default=lambda o: '<not serializable>', sort_keys=False, indent=2),
                           app_friends=json.dumps([ally["appFriendId"] for ally in allies.values()
                                                   if "appFriendId" in ally and ally["appFriendId"] is not None]))


@app.route("/nodebug.html")
def no_debug():
    print("index")
    return render_template("nodebug.html", time=datetime.now().timestamp(), zid=str(get_zid()),
                           allies=json.dumps([ally["friend"] for ally in allies.values()
                                              if "friend" in ally and ally["friend"] and ally["neighbor"]],
                                             default=lambda o: '<not serializable>', sort_keys=False, indent=2),
                           app_friends=json.dumps([ally["appFriendId"] for ally in allies.values()
                                                   if "appFriendId" in ally and ally["appFriendId"] is not None]))


@app.route("/wipe_session", methods=['GET', 'POST'])
def wipe_session():
    session.clear()
    response = make_response(redirect('/home.html'))
    # response.set_cookie('session', '', expires=0)
    return response


@app.route("/gazillionaire", methods=['GET', 'POST'])
def more_money():
    if 'user_object' in session:
        player = session['user_object']["userInfo"]["player"]
        player['cash'] += 10000
        session['saved'] = True
        response = make_response(redirect('/home.html'))
        return response
    else:
        return ('Nope', 403)


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

    return render_template("save-editor.html", savegame=json.dumps(
        {
            'user_object': session['user_object'] if 'user_object' in session else None,
            'quests': session['quests'] if 'quests' in session else None,
            'battle': session['battle'] if 'battle' in session else None,
            'fleets': session['fleets'] if 'fleets' in session else None,
            'population': session['population'] if 'population' in session else None,
            'saved': session['saved'] if 'saved' in session else None,
            'save_version': session['save_version'] if 'save_version' in session else None,
            'original_save_version': session['original_save_version'] if 'original_save_version' in session else None,
        }, default=lambda o: '<not serializable>', sort_keys=False, indent=2), uid=get_zid(), backups=backups)


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
    session["backup"] = {k: v for k, v in session.items() if
                         k in ['user_object', 'quests', 'battle', 'fleets', 'population', 'saved', 'saved_on',
                               'save_version', 'original_save_version', 'backup']}  # nested backups

    session['user_object'] = save_game['user_object']
    session['quests'] = save_game['quests']
    session['battle'] = save_game['battle']
    session['fleets'] = save_game['fleets']
    session['population'] = save_game['population']
    session['save_version'] = save_game['save_version']
    session['saved'] = True
    timestamp = datetime.now().timestamp()
    session['saved_on'] = timestamp
    session["backup"]['replaced_on'] = timestamp
    session["backup"]['message'] = message

    response = make_response(redirect('/home.html'))
    return response
    # return ('', 400)


def format_backup_message(backup):
    return datetime.fromtimestamp(backup.get('saved_on', 0)).strftime("%d %b %Y %H:%M:%S") + ' - ' \
           + datetime.fromtimestamp(backup.get('replaced_on', 0)).strftime("%d %b %Y %H:%M:%S") + ' @' \
           + backup.get('save_version', 'UNKNOWN VERSION') + ' ' \
           + backup.get("message", "")


@app.route("/127.0.0.1record_stats.php", methods=['GET', 'POST'])
def record_stats():
    return ('', 204)


@app.route("/files/empire-s.assets.zgncdn.com/assets/109338/ZGame.109338.swf")
def flashFile():
    return send_from_directory("assets", "ZGame.109338.swf")
    # return send_from_directory("assets", "ZGame.109338_tracer.swf")


@app.route("/gameSettings.xml")
def game_settings_file():
    # return send_from_directory("assets/32995", "gameSettings.xml")
    # return send_from_directory("assets/32995", "gameSettings.xml")
    # return send_from_directory("assets/29oct2012", "gameSettings.xml")
    # return send_from_directory("assets/29oct2012", "gameSettings_placeholders.xml")
    return send_from_directory("assets/29oct2012", "gameSettings_with_fixes.xml")


@app.route("/127.0.0.1en_US.xml")
def en_us_file():
    # return send_from_directory("assets/32995", "en_US.xml")
    return send_from_directory("assets/29oct2012", "en_US.xml")


@app.route("/127.0.0.1questSettings.xml")
def quest_settings_file():
    return send_from_directory("assets/29oct2012", "questSettings_with_fixes.xml")

@app.route("/releases.html")
def releases():
    return render_template("releases.html")

@app.route("/changelog.txt")
def change_log():
    return render_template("changelog.txt")

@app.route("/layouts/yc_r.css")
def fb_ccs_1():
    return send_from_directory("templates/layouts", "yc_r.css")


@app.route("/layouts/yz_r.css")
def fb_ccs_2():
    return send_from_directory("templates/layouts", "yz_r.css")


@app.route("/layouts/yC2_r.css")
def fb_ccs_3():
    return send_from_directory("templates/layouts", "yC2_r.css")


@app.route("/layouts/icon.png")
def icon_image():
    return send_from_directory("templates/layouts", "icon.png")


@app.route("/layouts/logo.png")
def logo_image():
    return send_from_directory("templates/layouts", "logo.png")


@app.route('/nullassets/<path:path>')
def send_sol_assets(path):
    return send_from_directory('assets/sol_assets_octdict/assets', path)


@app.route('/assets/<path:path>')
def send_sol_assets_alternate(path):
    return send_from_directory('assets/sol_assets_octdict/assets', path)


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
            resps.append(user_response())
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
            wr = perform_world_response(reqq.params[0], reqq.params[1].id, reqq.params[1].position,
                                        reqq.params[1].itemName,
                                        reqq.params[2][0].get('referenceItem') if len(reqq.params[2]) > 0 else None,
                                        reqq.params[2][0].get('isGift') if len(reqq.params[2]) > 0 else None,
                                        reqq.params[2][0].get('elapsed') if len(reqq.params[2]) > 0 else None,
                                        reqq.params[2][0] if len(reqq.params[2]) > 0 else None)
            resps.append(wr)
            report_world_log(reqq.params[0] + ' id ' + str(reqq.params[1].id) + '@' + reqq.params[1].position,
                             wr["data"], reqq.params, reqq.sequence, resp_msg.bodies[0][0],
                             wr["metadata"].get('QuestComponent'), wr["metadata"].get('newPVE'))
        elif reqq.functionName == 'DataServicesService.getSuggestedNeighbors':
            resps.append(neighbor_suggestion_response())
        elif reqq.functionName == 'UserService.setSeenFlag':
            resps.append(seen_flag_response(reqq.params[0]))
        elif reqq.functionName == 'PVPService.createRandomFleetChallenge':
            resps.append(random_fleet_challenge_response())
        elif reqq.functionName == 'WorldService.spawnFleet':
            resps.append(spawn_fleet(reqq.params[0]))
        elif reqq.functionName == 'PVPService.loadChallenge':
            resps.append(load_challenge_response())
        elif reqq.functionName == 'WorldService.resolveBattle':
            resps.append(battle_complete_response(reqq.params[0]))
        elif reqq.functionName == 'WorldService.genericString':
            resps.append(generic_string_response(reqq.params[0]))
        elif reqq.functionName == 'UserService.streakBonus':
            resps.append(streak_bonus_response())
        elif reqq.functionName == 'UserService.setWorldName':
            resps.append(world_name_response(reqq.params[0]))
        elif reqq.functionName == 'WorldService.updateRoads':
            resps.append(update_roads_response())
        elif reqq.functionName == 'UserService.streamPublish':
            resps.append(stream_publish_response())
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
            resps.append(tend_ally_response())
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
            resps.append(dummy_response())
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
            resps.append(dummy_response())
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
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.buyFullHeal':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.buyItem':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.buyItems':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.buyMOTDItem':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.buyQuestRestartTask':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.buyQuestTask':
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.buyRewardItem':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.calculateRansom':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.cancelUnstartedChallenge':
            resps.append(dummy_response())
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
            resps.append(dummy_response())
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
            resps.append(dummy_response())
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
            resps.append(dummy_response())
        elif reqq.functionName == 'QuestSurvivalModeService.loadQuestSurvivalMode':
            resps.append(dummy_response())
        elif reqq.functionName == 'SurvivalModeService.loadSurvivalMode':
            resps.append(dummy_response())
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
            resps.append(dummy_response())
        elif reqq.functionName == 'UserService.purchaseEnergyRefill':
            resps.append(dummy_response())
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
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.pillage':
            resps.append(dummy_response())
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
            resps.append(dummy_response())
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
            resps.append(dummy_response())
        elif reqq.functionName == 'RequestService.invasionHelpRequest':
            resps.append(dummy_response())
        elif reqq.functionName == 'RequestService.neighborRequest':
            resps.append(dummy_response())
        elif reqq.functionName == 'RequestService.giftRequest':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.resetParliamentDestroyed':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.retrieveNeighborRepelChallenge':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.reviveAllies':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.reviveUnits':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.moveRoad':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.sellRoad':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.seenPrisonCampNotification':
            resps.append(dummy_response())
        elif reqq.functionName == 'PVPService.seenStrikeTeamComment':
            resps.append(dummy_response())
        elif reqq.functionName == 'WorldService.select':
            resps.append(dummy_response())
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
            resps.append(dummy_response())
        elif reqq.functionName == 'VisitorService.decline':
            resps.append(dummy_response())
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
                "expansions": {
                    "data": [4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
                             4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
                             4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
                             4294967295, 4294967295]},
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
            "worldName": "Nataland",
            "titanName": "Natalie",
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
        "neighbors": [ally["info"] for ally in allies.values() if ally["info"] and ally.get("neighbor")],
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
        "experiments": {"empire_combataicancritical": 2},
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
        "visitorHelpRequests": None,
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
    if 'user_object' in session:
        print("Loading user from save")
        user = session['user_object']
        user["userInfo"]["player"]["uid"] = get_zid()
        if session.get('save_version') != version:
            print("WARNING: Save game was saved with version", session.get('save_version'), "while game is version",
                  version)

        qc = session['quests']

        user["neighbors"] = [ally["info"] for ally in allies.values() if ally["info"] and ally.get("neighbor")]

        meta = {"newPVE": 0, "QuestComponent": [e for e in qc if e["complete"] == False]}
    else:
        user = copy.deepcopy(init_user())
        print("initialized new")
        session['user_object'] = user
        # qc = [{"name": "Q0516", "complete":False, "expired":False,"progress":[0],"completedTasks":0}]
        session['quests'] = []
        qc = []

        session['quests'] = qc
        session['save_version'] = version
        session['original_save_version'] = version
        session['saved_on'] = datetime.now().timestamp()
        meta = {"newPVE": 0, "QuestComponent": [e for e in qc if e["complete"] == False]}
        new_quest_with_sequels("Q0516", qc, meta)

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

    user["completedQuests"] = [e["name"] for e in qc if e["complete"] == True]

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
    if session.get('save_version') != version:
        print("Trying migration")
        migrate(meta, session.get('save_version'), version)

    sleep(0.05)  # bugfix required delay for loading entire screen


    # for e in session['user_object']["userInfo"]["world"]["objects"]:
    #     e['lastUpdated'] = 1308211628  #1 minute earlier to test
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
                        "data": None}
    return invader_response


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

    merge_quest_progress(meta['QuestComponent'] if 'QuestComponent' in meta else [], session['quests'], "session quest")
    session['user_object']["userInfo"]["player"]["tutorialProgress"] = step  # TODO: revert step when loading if needed

    report_tutorial_step(step, meta['QuestComponent'] if 'QuestComponent' in meta else None, meta['newPVE'], sequence,
                         endpoint)
    tutorial_response = {"errorType": 0, "userId": 1, "metadata": meta,
                         "data": []}
    return tutorial_response


def perform_world_response(step, supplied_id, position, item_name, reference_item, from_inventory, elapsed, req2):
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
    # print("cur_object used:", repr(cur_object))
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

    if step in ["place", "setState"]:
        click_next_state(True, id, meta, step, reference_item, False)  # place & setstate only

    if step == "setState":
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
            if costs:
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
        click_next_state(False, id, meta, step, reference_item, True)
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
                                    "data": []}
    return neighbor_suggestion_response


def seen_flag_response(flag):
    seen_flags = session['user_object']["userInfo"]["player"]["seenFlags"]

    seen_flags[flag] = seen_flags.get(flag, 0) + 1

    seen_flag_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                          "data": []}
    return seen_flag_response


def random_fleet_challenge_response():
    unit_user = "U01,,,,"
    unit = "BD3,,,,"

    user_fleet = {
        "type": "army",
        "uid": "0",
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
        "units": [unit_user],  # only one unit for tutorial [unit, unit, unit],
        "store": [0],  # [0, 0, 0],
        "fleets": None,
        "upgrades": None,
        "hp": None
    }

    fleet = {
        "type": "army",
        "uid": "pve",
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
        "units": [unit],  # only one unit for tutorial [unit, unit, unit],
        "store": [0],  # [0, 0, 0],
        "fleets": [user_fleet],
        "upgrades": None,
        "hp": None
    }

    random_fleet_challenge_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                                       "data": {
                                           "state": 0,
                                           "challengerFleet": fleet,
                                           "challengeInfo": {"status": 0, "state": 1},
                                           "maxUnits": 1
                                       }}
    return random_fleet_challenge_response


def load_challenge_response():
    load_challenge_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                               "data": {"eFID": "pve", "state": 1}}  # CHALLENGE_STATE_IN_PROGRESS
    return load_challenge_response


def generic_string_response(param):
    meta = {"newPVE": 0}
    handle_quest_progress(meta, all_lambda(progress_action("genericString"),
                                           progress_parameter_equals("_string", str(param))))

    generic_string_response = {"errorType": 0, "userId": 1, "metadata": meta,
                               "data": []}
    return generic_string_response


def streak_bonus_response():
    streak_bonus_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                             "data": []}
    return streak_bonus_response


def world_name_response(name):
    world_name_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                           "data": []}
    session['user_object']["userInfo"]["worldName"] = name

    return world_name_response


def update_roads_response():
    update_roads_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                             "data": []}
    return update_roads_response


def stream_publish_response():
    stream_publish_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
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

    print("world resp", int(params[0]), session['user_object']["userInfo"]["player"]["uid"])
    if int(params[0]) == session['user_object']["userInfo"]["player"]["uid"]:
        ally = session['user_object']["userInfo"]
        # qc = session['quests']
        print("reloading user from save")
    else:
        ally = copy.deepcopy(init_user()["userInfo"])
        ally["player"]["uid"] = int(params[0])
        if allies[str(params[0])]["objects"]:
            ally["world"]["objects"] = allies[str(params[0])]["objects"]
        if allies[str(params[0])]["roads"]:
            ally["world"]["roadData"] = allies[str(params[0])]["roads"]
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


def tend_ally_response():
    meta = {"newPVE": 0}
    handle_quest_progress(meta, progress_action("tending"))
    tend_ally_response = {"errorType": 0, "userId": 1, "metadata": meta,
                          "data": []}
    return tend_ally_response


def add_fleet_response(param):
    meta = {"newPVE": 0}

    add_fleet_response = {"errorType": 0, "userId": 1, "metadata": meta,
                          "data": []}

    session["fleets"][param['name']] = param['units']
    print("Player fleet:", param['units'])
    return add_fleet_response


def dummy_response():
    dummy_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                      "data": []}
    return dummy_response


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



if __name__ == '__main__':
    if 'WERKZEUG_RUN_MAIN' not in os.environ:
        threading.Timer(1.25, lambda: webbrowser.open("http://127.0.0.1:5005/")).start()
    # init_db(app, db)

    compress.init_app(app)
    socketio.init_app(app)
    sess.init_app(app)
    db.init_app(app)
    # session.app.session_interface.db.create_all()
    # app.session_interface.db.create_all()
    # db.create_all()
    socketio.run(app, host='127.0.0.1', port=5005, debug=debug)
    # app.run(host='127.0.0.1', port=5005, debug=True)
    # logging.getLogger('socketio').setLevel(logging.ERROR)
    # logging.getLogger('engineio').setLevel(logging.ERROR)
    # logging.getLogger('geventwebsocket.handler').setLevel(logging.ERROR)
