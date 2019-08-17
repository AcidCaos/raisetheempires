from flask import Flask, render_template, send_from_directory, request, Response, session, make_response, redirect
from flask_session import Session
from pyamf import remoting
from pyamf.flex import messaging
import pyamf
import io
# import connexion
import uuid
# import amfast
from units import units
from items import items
from itemsettings import item_settings
from questsettings import quest_settings
from game_settings import game_settings, lookup_yield
import threading, webbrowser
import pyamf.amf0
import json
import os
import sqlalchemy
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import time
from flask_compress import Compress
from flask_socketio import SocketIO
from quest_engine import *
from state_machine import *
import copy
import libscrc


COMPRESS_MIMETYPES = ['text/html', 'text/css', 'text/xml', 'application/json', 'application/javascript', 'application/x-amf']
COMPRESS_LEVEL = 6
COMPRESS_MIN_SIZE = 500
# import plot

#STATE todo statemachine class
rand_seed_w = 5445 # very random
rand_seed_z = 844

compress = Compress()
socketio = SocketIO()
sess = Session()
db = SQLAlchemy()

start = datetime.now()

# game_objects = []
with open("initial-island.json", 'r') as f:
    game_objects = json.load(f)
    print("Initial island template",  len(game_objects), "objects loaded")
    # game_objects = [o for o in game_objects_2 if int(o["position"].split(",")[0]) > 62 and int(o["position"].split(",")[1]) > 58]


app = Flask(__name__)

app.config['SESSION_TYPE']  = 'sqlalchemy'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///save.db'
app.config['SESSION_SQLALCHEMY'] = db


# app = connexion.App(__name__, specification_dir="./")
#application/x-amf
# app.add_api("swagger.yaml")


@app.route("/old")
def home():
    return render_template("home.html")


@app.route("/")
def index():
    print("index")
    return render_template("home.html", time=datetime.now().timestamp(), zid=str(get_zid()))



@app.route("/nodebug.html")
def no_debug():
    print("index")
    return render_template("nodebug.html", time=datetime.now().timestamp(),zid=str(get_zid()))


@app.route("/wipe_session", methods=['GET', 'POST'])
def wipe_session():
    session.clear()
    response = make_response(redirect('/'))
    # response.set_cookie('session', '', expires=0)
    return response

@app.route("/gazillionaire", methods=['GET', 'POST'])
def more_money():
    if 'user_object' in session:
        player = session['user_object']["userInfo"]["player"]
        player['cash'] += 10000
        response = make_response(redirect('/'))
        return response
    else:
        return ('Nope', 403)

@app.route("/127.0.0.1record_stats.php", methods=['GET', 'POST'])
def record_stats():
    return ('', 204)


@app.route("/files/empire-s.assets.zgncdn.com/assets/109338/ZGame.109338.swf")
def flashFile():
    # return send_from_directory("assets", "ZGame.109338.swf")
    return send_from_directory("assets", "ZGame.109338_tracer.swf")


@app.route("/gameSettings.xml")
def game_settings_file():
    # return send_from_directory("assets/32995", "gameSettings.xml")
    # return send_from_directory("assets/32995", "gameSettings.xml")
    #return send_from_directory("assets/29oct2012", "gameSettings.xml")
    #return send_from_directory("assets/29oct2012", "gameSettings_placeholders.xml")
    return send_from_directory("assets/29oct2012", "gameSettings_with_fixes.xml")


@app.route("/127.0.0.1en_US.xml")
def en_us_file():
    # return send_from_directory("assets/32995", "en_US.xml")
    return send_from_directory("assets/29oct2012", "en_US.xml")


@app.route("/127.0.0.1questSettings.xml")
def quest_settings_file():
    return send_from_directory("assets/29oct2012", "questSettings.xml")


# @app.route("/nullassets/game/terrain/Island3_Tileset_ENV.swf")
# def flash_fiddle():
# 	return send_from_directory("assets", "ZGame.109338.swf")

# @app.route("/nullassets/game/terrain/Island3_Tileset_ENV.swf")
# def flash_fiddle():
#     return send_from_directory("assets/cooking", "cw2_runtimeSharedAssets__6f788.swf")
#

@app.route('/nullassets/<path:path>')
def send_sol_assets(path):
    return send_from_directory('assets/sol_assets_octdict/assets', path)



@app.route('/files/empire-s.assets.zgncdn.com/assets/109338/127.0.0.1flashservices/gateway.php', methods=['POST'])
def post_gateway():
    print("Gateway:")
    print(repr(request))
    # print("Data:")
    # print(request.data)
    resp_msg = remoting.decode(request.data)
    print(resp_msg.headers)
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
            wr = perform_world_response(reqq.params[0], reqq.params[1].id, reqq.params[1].position, reqq.params[1].itemName, reqq.params[2][0].get('referenceItem') if len(reqq.params[2]) > 0 else None)
            resps.append(wr)
            report_world_log(reqq.params[0] + ' id ' + str(reqq.params[1].id) + '@' + reqq.params[1].position, wr["data"]["id"], reqq.params, reqq.sequence, resp_msg.bodies[0][0],
                             wr["metadata"].get('QuestComponent'), wr["metadata"].get('newPVE'))
        elif reqq.functionName == 'DataServicesService.getSuggestedNeighbors':
            resps.append(neighbor_suggestion_response())
        elif reqq.functionName == 'UserService.setSeenFlag':
            resps.append(seen_flag_response())
        elif reqq.functionName == 'PVPService.createRandomFleetChallenge':
            resps.append(random_fleet_challenge_response())
        elif reqq.functionName == 'WorldService.spawnFleet':
            resps.append(spawn_fleet(reqq.params[0]))
        elif reqq.functionName == 'PVPService.loadChallenge':
            resps.append(load_challenge_response())
        elif reqq.functionName == 'WorldService.resolveBattle':
            resps.append(battle_complete_response(reqq.params[0]))
        elif reqq.functionName == 'WorldService.genericString':
            resps.append(generic_string_response())
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
        elif reqq.functionName == 'WorldService.assignConsumable':
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

    ret_body = remoting.encode(ev, strict=True, logger=True).getvalue() #.read()
   # print(ret_body)
    return Response(ret_body, mimetype='application/x-amf')

    # return ('', 204)


def init_user():
    # global game_objects

    roads_data = [
        "54,55|54,55",
        "55,55|55,55",
        "56,55|56,55",
        "57,55|57,55",
        "58,55|58,55",
        "58,56|58,56",
        "58,57|58,57",
        "58,58|58,58",
        "58,59|58,59",
        "57,59|57,59",
        "56,59|56,59",
        "55,59|55,59",
        "54,59|54,59",
        "54,58|54,58",
        "54,57|54,57",
        "54,56|54,56",
        "56,54|56,54",
        "56,53|56,53",
        "56,52|56,52",
        "56,51|56,51",
        "56,60|56,60",
        "56,61|56,61",
        "56,62|56,62",
        "56,63|56,63",
        "59,57|59,57",
        "60,57|60,57",
        "61,57|61,57",
        "62,57|62,57",
        "53,57|53,57",
        "52,57|52,57",
        "51,57|51,57",
        "50,57|50,57",

    ]

    unit = "U01,,,,"

    # resources = {"energy": 100, "coins": 100000, "oil": 7000, "wood": 5000, "aluminum": 9000,
    #                                 "copper": 4000, "gold": 3000, "iron": 2000, "uranium": 1000}

    resources = {"energy": 25, "coins": 5000, "oil": 25, "wood": 150, "aluminum": 1000,
                 "copper": 0, "gold": 0, "iron": 0, "uranium": 0}

    # xp = 20000
    # level =100
    #zcash = 1000
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
                "expansions": {"data":[4294967295,4294967295,4294967295,4294967295,4294967295,4294967295,4294967295,4294967295,4294967295,4294967295,4294967295,4294967295,4294967295,4294967295,4294967295,4294967295,4294967295,4294967295,4294967295,4294967295,4294967295,4294967295,4294967295]},
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
                "seenFlags": {},    #seen "introCine":True otherwise blackscreen but no startepisode then ->  either false (ZGlobal.noIntroCineVariant != ZGlobal.EXPERIMENT_NO_INTRO_CINE && Zlab.getFlashVar("mute") == null)
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
                "inventory": {"items": {}},
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

            "world": {"fleets": [], "enemies": [], "globalFleetId": 0, "battleStatus": {},  #user_fleet
                      "research": {}, "research2": {"buildingTypesUpgraded": None, "treesUnlocked": None},
                      "resourceOrder": ["aluminum", "copper", "gold", "iron", "uranium"],
                      "globalObjectId": 10000, #initial id high enough not to overlap with preloaded objects
                      "sizeX": 200,
                      "sizeY": 200,
                      "ownerId": 0,
                      "randSeedW": rand_seed_w,
                      "randSeedZ": rand_seed_z,
                      "unitDropData": {"unclaimedUnits": []},
                      "islands": 1,
                      "roadData": roads_data,
                      "objects": game_objects,
                      "rewardRandSeedW": 484584,
                      "rewardRandSeedZ": 7549,
                      "ransomRandSeedW": 456647,
                      "ransomRandSeedZ": 4546,
                      "scrapRandSeedW": 5646,
                      "scrapRandSeedZ": 3567,
                      "resources": resources,
                      "campaign": {}
                      }

        },
        "neighbors": [
            {"uid": 123, "resource": 3, "coins": 100, "xp": 10, "level": 1, "socialXpGood": 0, "socialLevelGood": 1,
             "socialXpBad": 0, "socialLevelBad": 1, "profilePic": None, "dominanceRank": 1, "tending": {"actions": 3}},
            {"uid": -1, "resource": 3, "coins": 100, "xp": 10, "level": 6, "socialXpGood": 0, "socialLevelGood": 20,
             "socialXpBad": 0, "socialLevelBad": 1, "profilePic": "assets/game/GeneralAssetGroup_UI.swf/NeighborOneCP.png", "dominanceRank": 1, "tending": {"actions": 3}}],
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
        "experiments": {},
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
        "noIntroCineVariant": 2, #disable intro cinematics (we don't have yet)
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

#Q0516 ? start
def user_response():
    if 'user_object' in session:
        user = session['user_object']
        user["userInfo"]["player"]["uid"] = get_zid()
        qc = session['quests']
        print("loading user from save")

        user["neighbors"] = [
            {"uid": 123, "resource": 3, "coins": 100, "xp": 10, "level": 1, "socialXpGood": 0, "socialLevelGood": 1,
             "socialXpBad": 0, "socialLevelBad": 1, "profilePic": None, "dominanceRank": 1, "tending": {"actions": 3}},
            # {"uid": -2, "resource": 3, "coins": 100, "xp": 10, "level": 1, "socialXpGood": 0, "socialLevelGood": 1,
            #  "socialXpBad": 0, "socialLevelBad": 1, "profilePic": None, "dominanceRank": 1, "tending": {"actions": 3}},
            {"uid": -1, "resource": 3, "coins": 100, "xp": 10, "level": 6, "socialXpGood": 0, "socialLevelGood": 20,
             "socialXpBad": 0, "socialLevelBad": 1, "profilePic": "assets/game/GeneralAssetGroup_UI.swf/NeighborOneCP.png", "dominanceRank": 1, "tending": {"actions": 3}}]


    else:
        user = copy.deepcopy(init_user())
        print("initialized new")
        session['user_object'] = user
        # qc = [{"name": "Q0516", "complete":False, "expired":False,"progress":[0],"completedTasks":0}]
        session['quests'] = []
        qc = []

        new_quest_with_sequels("Q0516", qc)
        session['quests'] = qc


    session['user_object']["userInfo"]["player"]["tutorialProgress"] = 'tut_step_inviteFriendsViral'
    # session['user_object']["userInfo"]["player"]["lastEnergyCheck"] = datetime.now().timestamp()

    replenish_energy()

    session["battle"] = None
    session["fleets"] = {}
    session['population'] = lookup_yield()

    session['campaign'] = {}
    session['campaign']['C000'] = {}
    user["completedQuests"] = [e["name"] for e in qc if e["complete"] == True]

    # for e in session['user_object']["userInfo"]["world"]["objects"]:
    #     e['lastUpdated'] = 1308211628  #1 minute earlier to test
    user_response = {"errorType": 0, "userId": get_zid(), "metadata": {"newPVE": 0, "QuestComponent": [e for e in qc if e["complete"] == False]},  # {"name": "Q0531", "complete":False, "expired":False,"progress":[0],"completedTasks":0},{"name": "QW120", "complete":False, "expired":False,"progress":[0],"completedTasks":0}
                    "data": user}
    return user_response


def get_zid():
    return libscrc.iso(session.sid.encode()) // 1000


def friend_response():
    friend = {
        "recommendedFriends":{"data":[]},
        "zyngaFriends":{"data":[]},
        "empireFriends":{"data":[]},
        "sevenDayFriends":{"data":[]},
        "fourteenDayFriends":{"data":[]},
        "thirtyDayFriends":{"data":[]},
        "payerFriends":{"data":[]},
        "allFriends":{"data":[]},
        "zyngaFriendsByEngagement":{"data":[]},
        "empireFriendsByEngagement":{"data":[]},
              }

    friend_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                    "data": friend}
    return friend_response

def invader_response():
    invader_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                    "data": None}
    return invader_response

def zlingshot_response():
    zlingshot_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                    "data": {   }}
    return zlingshot_response

def recent_response():
    recent_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                    "data": []}
    return recent_response

def friend_info_response():
    friend_info_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                    "data": {"nonAppFriends":[{"zid":100,"first_name":"MissTery","sex":'F',"portrait":None}]}}
    return friend_info_response

def tutorial_response(step, sequence, endpoint):
    meta = {"newPVE": 0}
    qz = {"name": "Q0516", "complete":True, "expired":False,"progress":[1],"completedTasks":1}
    qz_cadets_start = {"name": "Q0531", "complete":False, "expired":False,"progress":[0],"completedTasks":0}
    #complete cadets?
    qz_cadets_start = {"name": "Q0531", "complete":False, "expired":False,"progress":[0],"completedTasks":0}
    qz_cadets_done = {"name": "Q0531", "complete":True, "expired":False,"progress":[1],"completedTasks":1}
    qz_invasion_start = {"name": "Q6016", "complete":False, "expired":False,"progress":[0],"completedTasks":0}
    qz_invasion_done = {"name": "Q6016", "complete":True, "expired":False,"progress":[1],"completedTasks":1}
    flag_Q1098_start = {"name": "Q1098", "complete":False, "expired":False,"progress":[0],"completedTasks":0}
    flag_Q1098_done = {"name": "Q1098", "complete":True, "expired":False,"progress":[1],"completedTasks":1}
    cadets_Q0611_start = {"name": "Q0611", "complete":False, "expired":False,"progress":[0],"completedTasks":0}
    cadets_Q0611_done = {"name": "Q0611", "complete":True, "expired":False,"progress":[1],"completedTasks":1}
    flag_Q6011_start = {"name": "Q6011", "complete":False, "expired":False,"progress":[0],"completedTasks":0}
    flag_Q6011_done = {"name": "Q6011", "complete":True, "expired":False,"progress":[1],"completedTasks":1}

    sergeant_Q0671_start = {"name": "Q0671", "complete":False, "expired":False,"progress":[0,0],"completedTasks":0}#after 6011
    sergeant_Q0671_done = {"name": "Q0671", "complete":True, "expired":False,"progress":[1,1],"completedTasks":2}
    flag_Q0591_start = {"name": "Q0591", "complete":False, "expired":False,"progress":[0],"completedTasks":0}
    flag_Q0591_done = {"name": "Q0591", "complete":True, "expired":False,"progress":[1],"completedTasks":1}
    farm_Q0571_start = {"name": "Q0571", "complete":False, "expired":False,"progress":[0,0],"completedTasks":0}
    farm_Q0571_done = {"name": "Q0571", "complete":True, "expired":False,"progress":[1,1],"completedTasks":2}
    corn_Q0521_start = {"name": "Q0521", "complete":False, "expired":False,"progress":[0],"completedTasks":0}
    corn_Q0521_done = {"name": "Q0521", "complete":True, "expired":False,"progress":[1],"completedTasks":1}
    parliament_Q0691_start = {"name": "Q0691", "complete":False, "expired":False,"progress":[0],"completedTasks":0}
    parliament_Q0691_done = {"name": "Q0691", "complete":True, "expired":False,"progress":[1],"completedTasks":1}

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
    session['user_object']["userInfo"]["player"]["tutorialProgress"] = step # TODO: revert step when loading if needed

    report_tutorial_step(step, meta['QuestComponent'] if 'QuestComponent' in meta else None, meta['newPVE'], sequence, endpoint);
    tutorial_response = {"errorType": 0, "userId": 1, "metadata": meta,
                    "data": []}
    return tutorial_response


def perform_world_response(step, supplied_id, position, item_name, reference_item):
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
        click_next_state(id, meta, step, reference_item)  # place & setstate only

    if step == "setState":
        lookup_object(id)["referenceItem"] = reference_item

    if step == "clear":
        session['user_object']["userInfo"]["world"]["objects"].remove(lookup_object(id))

    perform_world_response = {"errorType": 0, "userId": 1, "metadata": meta,
                    "data": {"id": id}}
    print("perform_world_response" , repr(perform_world_response))
    return perform_world_response


def neighbor_suggestion_response():
    neighbor_suggestion_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                    "data": []}
    return neighbor_suggestion_response

def seen_flag_response():
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
        "units": [unit], # only one unit for tutorial [unit, unit, unit],
        "store": [0], #[0, 0, 0],
        "fleets": [user_fleet],
        "upgrades": None,
        "hp": None
    }

    random_fleet_challenge_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                    "data": {
                        "state": 0,
                        "challengerFleet" : fleet,
                        "challengeInfo": {"status": 0, "state": 1},
                        "maxUnits": 1
                    }}
    return random_fleet_challenge_response

def spawn_fleet(params):
    global battle_seq
    battle_seq = 0 #STATE! no multiple battles at the same time!!
    meta = {}

    # params['code']
    # params['fleet']

    quest = lookup_quest(params['code'])
    tasks = get_tasks(quest)

    [task] = [t for t in tasks if t["_action"] == "fight"]

   # meta["newPVE"] = {"status": 2, "pos": "58,60,0", "villain": "v18"}
   #  meta["newPVE"] = {"status": 2, "pos": "60,63,0", "villain": "v18", "quest": "Q6016"}
    meta["newPVE"] = {"status": 2, "pos": task["_spawnLocation"], "villain": task["_pveVillain"], "quest": params['code']}
    spawn_fleet = {"errorType": 0, "userId": 1, "metadata": meta,
                          "data": []}
    return spawn_fleet

def load_challenge_response():
    load_challenge_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                    "data": {"eFID":"pve", "state":1}}  #CHALLENGE_STATE_IN_PROGRESS
    return load_challenge_response

def battle_complete_response(params):
    if params['target'].startswith('fleet'):
        baddies = [lookup_item_by_code(friendly[1:]) for friendly, count in session['fleets'][params['target']].items() for i in range(int(count))]
        friendlies = [lookup_item_by_code(friendly.split(',')[0]) for friendly in session['fleets'][params['fleet']]]
    else:
        quest = lookup_quest(params['target'])
        tasks = get_tasks(quest)
        [task] = [t for t in tasks if t["_action"] == "fight"]
        enemy_fleet = lookup_item_by_code(task["_item"])
        baddies = [lookup_item_by_code(baddie_slot["-item"]) for baddie_slot in simple_list(enemy_fleet["baddie"])]
        friendlies = [lookup_item_by_code(friendly[1:]) for friendly, count in task["fleet"].items() for i in range(int(count))]

    player_unit_id = 0
    enemy_unit_id = 0

    if 'id' in params:
        [player_unit_id, enemy_unit_id] = params['id']  #player turn
        player_turn = True
    else:
        player_turn = False

    print("repr baddies", baddies)
    baddie_unit = baddies[enemy_unit_id]["unit"]
    baddie_max_strength = int(baddie_unit.get("-strength","0"))
    baddie_weak = int(baddie_unit.get("-weak","0"))
    [baddie_unit_type, baddie_unit_terrain] = baddie_unit.get("-type",",").split(',')

    friendly_unit = friendlies[player_unit_id]["unit"]
    friendly_max_strength = int(friendly_unit.get("-strength", "0"))
    friendly_weak = int(friendly_unit.get("-weak", "0"))
    [friendly_unit_type, friendly_unit_terrain] = friendly_unit.get("-type", ",").split(',')

    if "battle" not in session or not session["battle"]:
        baddie_strengths = [int(baddie["unit"].get("-strength", "0")) for baddie in baddies]
        friendly_strengths = [int(friendly["unit"].get("-strength", "0")) for friendly in friendlies]
        session["battle"] = (friendly_strengths, baddie_strengths)
    else:
        (friendly_strengths, baddie_strengths) = session["battle"]

    friendly_strength = friendly_strengths[player_unit_id]
    baddie_strength = baddie_strengths[enemy_unit_id]


    if not player_turn:
        unknown_rolls = ["init seed", get_seed_w(),get_seed_z(),
                         roll_random_between(0, 1),"seed",get_seed_w(),get_seed_z(),
                        roll_random_between(0, 1),"seed",get_seed_w(),get_seed_z(),
                        roll_random_between(0, 1),"seed",get_seed_w(),get_seed_z()]
    else:
        unknown_rolls = ["init seed", get_seed_w(),get_seed_z()]

    roll = unit_roll(friendly_weak if player_turn else baddie_weak, baddie_weak if player_turn else friendly_weak)

    (crit, direct) = get_hit_value(friendly_unit_type if player_turn else baddie_unit_type, baddie_unit_type if player_turn else friendly_unit_type)

    hit = roll >= direct

    base_damage = 25 # TODO tier difference & increments

    if player_turn:
        damage = base_damage * (3 * friendly_max_strength + baddie_strength) / (3 * baddie_strength + friendly_max_strength)
        damage = damage / 100 * baddie_max_strength
    else:
        damage = base_damage * (3 * baddie_max_strength + friendly_strength) / (3 * friendly_strength + baddie_max_strength)
        damage = damage / 100 * friendly_max_strength

    damage = math.floor(damage * 10 ** 3) / 10 ** 3

    glance = 0.10
    critter = 1.5

    if not hit:
        damage *= glance
    elif roll != 2 and roll >= crit:
        damage *= critter

    damage = math.ceil(damage)

    if player_turn:
        baddie_strengths[enemy_unit_id] -= damage
        if baddie_strengths[enemy_unit_id] < 0:
            baddie_strengths[enemy_unit_id] = 0 #dead
            # session["battle"] = None
        print("Attacking for", damage , "damage, enemy hp:", baddie_strengths[enemy_unit_id], roll,"after seed", get_seed_w(),get_seed_z(), repr(unknown_rolls))
    else:
        friendly_strengths[player_unit_id] -= damage
        if friendly_strengths[player_unit_id] < 0:
            friendly_strengths[player_unit_id] = 0  # dead
            # session["battle"] = None
        print("Taken", damage, "damage, player hp:", friendly_strengths[player_unit_id], "after seed", get_seed_w(),get_seed_z(), repr(unknown_rolls))

    if not player_turn:
        pass

    if sum(baddie_strengths) == 0:
        print("Enemy defeated")
        session["battle"] = None


    if sum(friendly_strengths) == 0:
        print("Player defeated")
        session["battle"] = None


    result = {"attackerStunned": None, "psh": 0, "esh": 0, "ps": friendly_strengths[player_unit_id], "es": baddie_strengths[enemy_unit_id], "hv": None, "ur": roll,
     "playerUnit": player_unit_id, "enemyUnit": enemy_unit_id, "seeds": {"w": get_seed_w(), "z": get_seed_z()},
     "energy": None}

    print("ch", params.ch)

    meta = {"newPVE": 0}
    handle_quest_progress(meta, progress_action("fight"))
    battle_complete_response = {"errorType": 0, "userId": 1, "metadata": meta, "data": result}
    return battle_complete_response


def unit_roll(attacker_weak, defender_weak):
    if attacker_weak:
        return -2
    elif defender_weak:
        return 2
    else:
        return roll_random_between(0, 1)


def get_hit_value(type, defender_type):
    [chain] = [e for e in game_settings['settings']['combatChain']['chain'] if e['-type'] == type]
    if defender_type in chain.get('-great').split(','):
        grade = 'great'
    elif defender_type in chain.get('-poor').split(','):
        grade = 'poor'
    else:
        grade = 'good'

    [value] = [e for e in game_settings['settings']['combatHitValues']['value'] if e['-type'] == grade]

    return (float(value["-critical"]), float(value["-direct"]))


def generic_string_response():
    generic_string_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
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

    print("world resp", int(params[0]) , session['user_object']["userInfo"]["player"]["uid"])
    if int(params[0]) == session['user_object']["userInfo"]["player"]["uid"]:
        ally = session['user_object']["userInfo"]
        # qc = session['quests']
        print("reloading user from save")
    else:
        ally = copy.deepcopy(init_user()["userInfo"])
        ally["player"]["uid"] = int(params[0])
        # ally["gf"] = False
        # ally["yimf"] = ""
        # ally["novisit"] = False
        # ally["globalPVP"] = {}
        # ally["nonFriendInfo"] = {}
        # ally["untendableObjIDs"] = []

        # ally["world"]["yimf"] = ""
    ally["pvpMode"] = params[2]
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


def next_campaign_response(map):
    meta = {"newPVE": 0}

    map_item = lookup_item_by_code(map["map"])

    if map["map"] not in session['campaign'] or not session['campaign'][map["map"]]:
        session['campaign'][map["map"]] = {"island": -1}

    session['campaign'][map["map"]]["island"] += 1

    island = session['campaign'][map["map"]]["island"]

    next_campaign_response = {"errorType": 0, "userId": 1, "metadata": meta,
                              "data": {"map": map["map"], "island": island}}

    if 'fleets' not in session:
        session["fleets"] = {}

    enemy_fleet = map_item["island"][island]['fleet']

    i=1
    fleet_name = "fleet1_" + str(get_zid())
    while fleet_name in session["fleets"]:
        i += 2
        fleet_name = "fleet" + str(i) + "_" + str(get_zid())

    session["fleets"][fleet_name] = enemy_fleet
    print("Enemy fleet:", enemy_fleet)

    return next_campaign_response


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

def report_tutorial_step(step, response, new_pve, sequence, endpoint):
    quest_names = [r['name'] for r in response] if response else []
    quests = [r for r in quest_settings['quests']['quest'] if r['_name'] in quest_names]
    socketio.emit('tutorial_step', [step, response, new_pve , describe_step(step), quests, sequence, endpoint])


def describe_step(step):
    [descr] = [e for e in game_settings['settings']['tutorial']['step'] if e['-id'] == step]
    return descr

def report_world_log(operation, response, req, sequence, endpoint, response2, new_pve):
    quest_names = [r['name'] for r in response2] if response2 else []
    quests = [r for r in quest_settings['quests']['quest'] if r['_name'] in quest_names]
    req2 = json.loads(json.dumps(req, default=lambda o: '<not serializable>'))
    socketio.emit('world_log', [operation, response, req2, sequence, endpoint, response2, new_pve,quests])

def report_other_log(service, response, req, endpoint):
    req2 = json.loads(json.dumps(req, default=lambda o: '<not serializable>'))
    socketio.emit('other_log', [service, response, req2, req.sequence, endpoint])


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
    socketio.run(app, host='127.0.0.1', port=5005, debug=True)
    # app.run(host='127.0.0.1', port=5005, debug=True)
