from flask import Flask, render_template, send_from_directory, request, Response, session
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
import copy


COMPRESS_MIMETYPES = ['text/html', 'text/css', 'text/xml', 'application/json', 'application/javascript', 'application/x-amf']
COMPRESS_LEVEL = 6
COMPRESS_MIN_SIZE = 500
# import plot

#STATE todo statemachine class
rand_seed_w = 5445 # very random
rand_seed_z = 844
battle_seq = 0

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

with open("gamesettings-converted.json", 'r') as f:
    game_settings = json.load(f)
    print("Gamesettings loaded: ",  len(game_settings['settings']), " setting sections loaded")


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
    return render_template("home.html", time=datetime.now().timestamp())



@app.route("/nodebug.html")
def no_debug():
    print("index")
    return render_template("nodebug.html")



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
            wr = perform_world_response(reqq.params[0], reqq.params[1].id, reqq.params[1].position, reqq.params[1].itemName)
            resps.append(wr)
            report_world_log(reqq.params[0] + ' id ' + str(reqq.params[1].id) + '@' + reqq.params[1].position, wr["data"]["id"], reqq.params, reqq.sequence, resp_msg.bodies[0][0])
        elif reqq.functionName == 'DataServicesService.getSuggestedNeighbors':
            resps.append(neighbor_suggestion_response())
        elif reqq.functionName == 'UserService.setSeenFlag':
            resps.append(seen_flag_response())
        elif reqq.functionName == 'PVPService.createRandomFleetChallenge':
            resps.append(random_fleet_challenge_response())
        elif reqq.functionName == 'WorldService.spawnFleet':
            resps.append(spawn_fleet())
        elif reqq.functionName == 'PVPService.loadChallenge':
            resps.append(load_challenge_response())
        elif reqq.functionName == 'WorldService.resolveBattle':
            resps.append(battle_complete_response(reqq.params[0]))
        elif reqq.functionName == 'WorldService.genericString':
            resps.append(generic_string_response())
        elif reqq.functionName == 'UserService.streakBonus':
            resps.append(streak_bonus_response())
        elif reqq.functionName == 'UserService.setWorldName':
            resps.append(world_name_response())
        elif reqq.functionName == 'WorldService.updateRoads':
            resps.append(update_roads_response())
        elif reqq.functionName == 'UserService.streamPublish':
            resps.append(stream_publish_response())
        elif reqq.functionName == 'WorldService.stopMayhemEvent':
            resps.append(stop_mayhem_response())

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
                "uid": 0,
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
                "ammo": 1234,
                "ammoMax": 2000,
                "options": {"musicDisabled": False, "sfxDisabled": False},
                "worldName": "Nataland",
                "titanName": "Natalie",
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
        "neighbors": [{"uid":123, "resource": 3, "coins": 100, "xp":10, "level": 1, "socialXpGood": 0, "socialLevelGood":1,
                       "socialXpBad":0, "socialLevelBad":1, "profilePic": None,"dominanceRank":1, "tending":{"actions":3} }],
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
        qc = session['quests']
        print("loading user from save")
    else:
        user = copy.deepcopy(init_user())
        print("initialized new")
        session['user_object'] = user
        qc = [{"name": "Q0516", "complete":False, "expired":False,"progress":[0],"completedTasks":0}]
        session['quests'] = qc
    # for e in session['user_object']["userInfo"]["world"]["objects"]:
    #     e['lastUpdated'] = 1308211628  #1 minute earlier to test
    user_response = {"errorType": 0, "userId": session.sid, "metadata": {"newPVE": 0, "QuestComponent": [e for e in qc if e["complete"] == False]},  # {"name": "Q0531", "complete":False, "expired":False,"progress":[0],"completedTasks":0},{"name": "QW120", "complete":False, "expired":False,"progress":[0],"completedTasks":0}
                    "data": user}
    return user_response

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

    if step == 'tut_step_placeBarracksServer':
        meta['QuestComponent'] = [qz, qz_cadets_start]
    # if step == 'tut_step_setupTrainCadets':
    #     meta['QuestComponent'] = [qz_cadets_start]
    if step == 'tut_step_cadetsComplete':
        meta['QuestComponent'] = [qz_cadets_done, qz_invasion_start]  #what starts invasion?
        meta["newPVE"] = {"status": 2, "pos": "60,63,0", "villain":"v18", "quest":"Q6016"}
    # if step == 'tut_step_firstInvasionEnd':
    if step == 'tut_step_postFirstInvasionResumeQuests':
        meta['QuestComponent'] = [qz_invasion_done,flag_Q1098_start,cadets_Q0611_start]
      #  meta["newPVE"] = {"status": 2, "pos": "60,66,0", "villain":"v18", "quest":"Q6016"}  #contineous battle mode experience QT01_05b_2
    if step == 'tut_step_placeFlagQuestDialog':
        meta['QuestComponent'] = [flag_Q1098_done, flag_Q6011_start]
    if step == 'tut_step_placeFlagWaitForInventoryOpen':   # sometimes one of them is skipped?
        meta['QuestComponent'] = [flag_Q1098_done, flag_Q6011_start]
    if step == 'tut_step_placeFlagEnd':
        meta['QuestComponent'] = [flag_Q6011_done, sergeant_Q0671_start, flag_Q0591_start]
    if step == 'tut_step_buildFarm':  #after cadets placed?
        meta['QuestComponent'] = [cadets_Q0611_done, sergeant_Q0671_start] #possibly already done by this point see if it doesn't redo quests already done
    if step == 'tut_step_placeHouseEnd':  #after cadets placed?
        meta['QuestComponent'] = [flag_Q0591_done, farm_Q0571_start]
    if step == 'tut_step_placeFarmEnd':  #after cadets placed?
        meta['QuestComponent'] = [farm_Q0571_done, corn_Q0521_start, parliament_Q0691_start, sergeant_Q0671_start]


        # if step == 'tut_step_startFirstInvasion':
        #     meta['QuestComponent'] = [qz_invasion_start]
        # [0]	String	tut_step_firstInvasionCombatSequence
        # [0]	String	tut_step_firstInvasionClientBattleEnd
        # tut_step_firstInvasionEnd
    merge_quest_progress(meta['QuestComponent'] if 'QuestComponent' in meta else [])
    session['user_object']["userInfo"]["player"]["tutorialProgress"] = step # TODO: revert step when loading if needed

    report_tutorial_step(step, meta['QuestComponent'] if 'QuestComponent' in meta else None, meta['newPVE'], sequence, endpoint);
    tutorial_response = {"errorType": 0, "userId": 1, "metadata": meta,
                    "data": []}
    return tutorial_response

def merge_quest_progress(qc):
    print("new q before merge " + repr(qc))
    print("q list before merge " + repr (session['quests']))
    session['quests'] = qc + [e for e in session['quests'] if e['name'] not in [q['name'] for q in qc]]
    print("q list after merge " + repr (session['quests']))


def perform_world_response(step, supplied_id, position, item_name):
    id = supplied_id
    if step == "place":
        session['user_object']["userInfo"]["world"]["globalObjectId"] += 1  # for place only!
        id = session['user_object']["userInfo"]["world"]["globalObjectId"]
        session['user_object']["userInfo"]["world"]["objects"].append({
            "id": id,
            "itemName": item_name,
            "position": position,
            "referenceItem": None,
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

    if step in ["place", "setState"]:
        click_next_state(id)  # place & setstate only

    if step == "clear":
        session['user_object']["userInfo"]["world"]["objects"].remove(lookup_object(id))

    perform_world_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                    "data": {"id": id}}
    return perform_world_response

def click_next_state(id):
    cur_object = lookup_object(id)
    print("cur_object used:", repr(cur_object))

    game_item = lookup_item(cur_object['itemName'])
    print("item used:", repr(game_item))

    if 'stateMachineValues' in game_item:
        state_machine = lookup_state_machine(game_item['stateMachineValues']['-stateMachineName'], game_item['stateMachineValues']['define'])

        print("state_machine used:", repr(state_machine))
        state = lookup_state(state_machine, cur_object.get('state', 0))
        print("cur state:", repr(state))

        while '-autoNext' in state and state['-stateName'] != state['-autoNext']:   #'-clientDuration': '2.0s', '-duration': '0' respect duration for harvest?
            duration =  parse_duration(state.get('-duration', '0'))
            if cur_object.get('lastUpdated') / 1000 +  duration <= datetime.now().timestamp():
                next_state_id = state['-autoNext']  # not all states have this!! end states? autostate after time?
                state = lookup_state(state_machine, next_state_id)
                cur_object['lastUpdated'] += duration * 1000
                cur_object['state'] = next_state_id
                print("pre auto_next_state:", repr(state), 'time', cur_object['lastUpdated'], "duration", duration)

        if '-clickNext' in state:
            next_state_id = state['-clickNext']  # not all states have this!! end states? autostate after time?
            next_click_state = lookup_state(state_machine, next_state_id)
            print("next_click_state:", repr(next_click_state))

            while '-autoNext' in next_click_state and next_state_id != next_click_state['-autoNext'] and next_click_state.get('-duration', '0') in ['0', '0s']:   #'-clientDuration': '2.0s', '-duration': '0' respect duration for harvest?
                next_state_id = next_click_state['-autoNext']  # not all states have this!! end states? autostate after time?
                next_click_state = lookup_state(state_machine, next_state_id)
                print("auto_next_state:", repr(next_click_state))

            cur_object['state'] = next_state_id
            cur_object['lastUpdated'] = datetime.now().timestamp() * 1000
        else:
            print("state has no clicknext, click does nothing")
            cur_object['lastUpdated'] = datetime.now().timestamp() * 1000
    else:
        print("object has no statemachine, click does nothing")

# def autoclick_next_state(state_machine, next_click_state):
#     while '-autoNext' in next_click_state and next_click_state['-stateName'] != next_click_state[
#         '-autoNext']:  # '-clientDuration': '2.0s', '-duration': '0' respect duration for harvest?
#         next_state_id = next_click_state['-autoNext']  # not all states have this!! end states? autostate after time?
#         next_click_state = lookup_state(state_machine, next_state_id)
#         print("auto_next_state:", repr(next_click_state))

def parse_duration(duration):
    # ["ms", "m", "s", "h", "d"];
    if duration == 'rand:1d,4d':
        return 86400 # 1d
    elif "ms" in duration:
        return int(duration[:-2]) / 1000
    elif "s" in duration:
        return int(duration[:-1])
    elif "m" in duration:
        return int(duration[:-1]) * 60
    elif "h" in duration:
        return int(duration[:-1]) * 3600
    elif "d" in duration:
        return int(duration[:-1]) * 86400
    else:
        return int(duration)


def lookup_state_machine(state_machine_name, custom_values):
    state_machine = copy.deepcopy(lookup_raw_state_machine(state_machine_name))
    replacements = {e['-name']: e['-value'] for e in custom_values}
    print('replacements', repr(replacements))
    repl_dict(state_machine, replacements)
    return state_machine

def repl_dict(d, replacements):
    for k, v in d.items():
        if isinstance(v, dict):
            repl_dict(v, replacements)
        elif isinstance(v, list):
            for e in v:
                repl_dict(e, replacements)
        else:
            if "$" in v:
                # print('r1', v)
                for s, r in replacements.items():
                    d[k] = d[k].replace(s, r)
                # print('r2', d[k])
                if ":" in v:
                    d[k] = d[k].split(':', 1)[1 if "$" in d[k] else 0]
                    # print('r3', d[k])

def lookup_raw_state_machine(state_machine_name):
    [state_machine] = [e for e in game_settings['settings']['stateMachines']['stateMachine'] if e['-name'] == state_machine_name]
    return state_machine

def lookup_state(state_machine, i):
    [state_machine] = [e for e in state_machine['state'] if e['-stateName'] == str(i)]
    return state_machine

def lookup_item(item_name):
    [item] = [e for e in game_settings['settings']['items']['item'] if e['-name'] == item_name]
    return item

def lookup_object(id):
    [game_object] = [e for e in  session['user_object']["userInfo"]["world"]["objects"] if e['id'] == id]
    return game_object


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

def spawn_fleet():
    global battle_seq
    battle_seq = 0 #STATE! no multiple battles at the same time!!
    meta = {}
   # meta["newPVE"] = {"status": 2, "pos": "58,60,0", "villain": "v18"}
    spawn_fleet = {"errorType": 0, "userId": 1, "metadata": meta,
                          "data": []}
    return spawn_fleet

def load_challenge_response():
    load_challenge_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                    "data": {"eFID":"pve", "state":1}}  #CHALLENGE_STATE_IN_PROGRESS
    return load_challenge_response

def battle_complete_response(params):
    global battle_seq
    first_battle = [ #so predictable
        {"attackerStunned": None, "psh": 0, "esh": 0, "ps": 30, "es": 18, "hv": None, "ur": 2, "playerUnit": 0, "enemyUnit": 0, "seeds": {"w": rand_seed_w, "z": rand_seed_z}, "energy": None},
        {"attackerStunned": None, "psh": 0, "esh": 0, "ps": 29, "es": 18, "hv": None, "ur": -2, "playerUnit": 0, "enemyUnit": 0, "seeds": {"w": 602919250, "z": 1191588587}, "energy": None},
        {"attackerStunned": None, "psh": 0, "esh": 0, "ps": 29, "es": 9, "hv": None, "ur": 2, "playerUnit": 0, "enemyUnit": 0, "seeds": {"w": 602919250, "z": 1191588587}, "energy": None},
        {"attackerStunned": None, "psh": 0, "esh": 0, "ps": 28, "es": 9, "hv": None, "ur": -2, "playerUnit": 0, "enemyUnit": 0, "seeds": {"w": 369467547, "z": 2051718473}, "energy": None},
        {"attackerStunned": None, "psh": 0, "esh": 0, "ps": 28, "es": 0, "hv": None, "ur": 2, "playerUnit": 0, "enemyUnit": 0, "seeds": {"w": 369467547, "z": 2051718473}, "energy": None},
        # {"attackerStunned": None, "psh": 0, "esh": 0, "ps": 0, "es": 0, "hv": None, "ur": -2, "playerUnit": 0, "enemyUnit": 0, "seeds": {"w": rand_seed_w, "z": rand_seed_z}, "energy": None},
        # {"attackerStunned": None, "psh": 0, "esh": 0, "ps": 0, "es": 0, "hv": None, "ur": 2, "playerUnit": 0, "enemyUnit": 0, "seeds": {"w": rand_seed_w, "z": rand_seed_z}, "energy": None},
        # {"attackerStunned": None, "psh": 0, "esh": 0, "ps": 0, "es": 0, "hv": None, "ur": 2, "playerUnit": 0, "enemyUnit": 0, "seeds": {"w": rand_seed_w, "z": rand_seed_z}, "energy": None},
        # {"attackerStunned": None, "psh": 0, "esh": 0, "ps": 0, "es": 0, "hv": None, "ur": 2, "playerUnit": 0, "enemyUnit": 0, "seeds": {"w": rand_seed_w, "z": rand_seed_z}, "energy": None},
        # {"attackerStunned": None, "psh": 0, "esh": 0, "ps": 0, "es": 0, "hv": None, "ur": 2, "playerUnit": 0, "enemyUnit": 0, "seeds": {"w": rand_seed_w, "z": rand_seed_z}, "energy": None},
     ]
    print("ch", params.ch)
    print("battle_seq", battle_seq)
    #battle_seq++

    #params.ch - 1100 not sequential


    battle_complete_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},  #CHALLENGE_STATE_IN_PROGRESS
                    "data": first_battle[battle_seq]}
    battle_seq += 1
    return battle_complete_response


def generic_string_response():
    generic_string_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                    "data": []}
    return generic_string_response

def streak_bonus_response():
    streak_bonus_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                    "data": []}
    return streak_bonus_response

def world_name_response():
    world_name_response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0},
                    "data": []}
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


def report_tutorial_step(step, response, new_pve, sequence, endpoint):
    quest_names = [r['name'] for r in response] if response else []
    quests = [r for r in quest_settings['quests']['quest'] if r['_name'] in quest_names]
    socketio.emit('tutorial_step', [step, response, new_pve , describe_step(step), quests, sequence, endpoint])


def describe_step(step):
    [descr] = [e for e in game_settings['settings']['tutorial']['step'] if e['-id'] == step]
    return descr

def report_world_log(operation, response, req, sequence, endpoint):
    req2 = json.loads(json.dumps(req, default=lambda o: '<not serializable>'))
    socketio.emit('world_log', [operation, response, req2, sequence, endpoint])

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
