import json
import pytest
from flask import Flask, session
import battle_engine

app = Flask(__name__)
app.secret_key = 'test'


def test_init_battle():
    run_init_battle({'id': [0, 0], 'fleet': 'fleet14_2341959767162880', 'target': 'fleet15_2341959767162880', 'ch': 4858,
     'map': 'C037'})


def test_init_battle_consumable():
    run_init_battle({'id': 1, 'ch': 3207, 'level': 0, 'name': 'fleet15_2341959767162880', 'fleet': None, 'map': 'C037', 'code': 'N04'})


def test_init_battle_ai_consumable():
    # AI consumable
    run_init_battle({'id': 0, 'ch': 1329, 'level': 0, 'name': 'AI', 'fleet': None, 'map': 'C037', 'code': None})


def test_init_battle_ai():
    run_init_battle({'fleet': 'fleet14_2341959767162880', 'target': 'fleet15_2341959767162880', 'ch': 4861, 'map': 'C037'})


def test_init_battle_ally_consumable():
    run_init_battle({'id': 27, 'ch': 3416, 'level': 90, 'name': '123', 'fleet': 'fleet15_2341959767162880', 'map': 'C037', 'code': 'A0A'})


def test_init_battle_self_consumable():
    run_init_battle({'id': 0, 'ch': 3210, 'level': 0, 'name': 'fleet14_2341959767162880', 'fleet': None, 'map': 'C037', 'code': 'N06'})


def test_init_battle_invade():
    run_init_battle_invade({'target': 'FleetName', 'ch': 4673, 'attackHostId': '1207348428048663', 'id': [0, 0], 'fleet': 'fleet14_2341959767162880', 'map': None})


def test_init_battle_ai_invade():
    run_init_battle_invade({'fleet': 'fleet14_2341959767162880', 'target': 'FleetName', 'ch': 4673, 'attackHostId': '6709797546928099', 'map': None})


def test_init_battle_invade_consumable():
    run_init_battle_invade({'id': 0, 'ch': 2065, 'level': 0, 'name': 'FleetName', 'fleet': None, 'map': None, 'code': 'N04'})


def test_init_battle_invade_self_consumable():
    run_init_battle_invade({'id': 3, 'ch': 2985, 'level': 0, 'name': 'fleet14_2341959767162880', 'fleet': None, 'map': None, 'code': 'N02'})


def run_init_battle(params):
    with app.test_request_context():
        setup_session()

        friendlies, friendly_strengths, baddies, baddie_strengths, active_consumables = \
            battle_engine.init_battle(params)

        assert_result(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths)
        log_result(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths)


def run_init_battle_invade(params):
    with app.test_request_context():
        setup_session_invade()

        friendlies, friendly_strengths, baddies, baddie_strengths, active_consumables = \
            battle_engine.init_battle(params)

        assert_result_invade(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths)
        log_result(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths)


def log_result(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths):
    print("friendlies", repr(friendlies))
    print("friendly_strengths", repr(friendly_strengths))
    print("baddies", repr(baddies))
    print("baddie_strengths", repr(baddie_strengths))
    print("active_consumables", repr(active_consumables))


def assert_result(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths):
    with open('friendlies.json', 'r') as f:
        assert friendlies == json.load(f)
    assert friendly_strengths == [300, 300]
    with open('baddies.json', 'r') as f:
        assert baddies == json.load(f)
    assert baddie_strengths == [120, 200, 150]
    assert active_consumables == []


def assert_result_invade(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths):
    with open('friendlies_invade.json', 'r') as f:
        assert friendlies == json.load(f)
    assert friendly_strengths == [180.0, 180.0, 780, 780, 340]
    with open('baddies_invade.json', 'r') as f:
        assert baddies == json.load(f)
    assert baddie_strengths == [40, 40, 30, 30, 30]
    assert active_consumables == [({'-name': 'consumable75', '-type': 'consumable', '-subtype': 'consumable',
                                    '-storable': 'true', '-buyable': 'true', '-code': 'N75', '-version': '2',
                                    'requiredLevel': '10', 'cost': {'-cash': '30'}, 'tooltip': {'-type': 'consumable'},
                                    'consumable': {'-duration': '0', '-energy': '0', '-type': 'all',
                                                   '-diweapon': 'DefenseShield', '-postWait': '1s',
                                                   '-givesAbility': 'shield'}, 'image': [
            {'-name': 'icon', '-url': 'assets/game/consumables/ConsumablesUI.swf/Shield_01_96.png'},
            {'-name': 'cursor', '-url': 'assets/game/consumables/ConsumablesUI.swf/Shield_01_49.png'}],
                                    'loc': {'-sentenceName': 'true'},
                                    'requiredExperiment': {'-name': 'empires_consumable_2', '-variants': '3'}},
                                   ('ally', 0), 9999999),
                                  ({'-name': 'consumable75', '-type': 'consumable', '-subtype': 'consumable',
                                    '-storable': 'true', '-buyable': 'true', '-code': 'N75', '-version': '2',
                                    'requiredLevel': '10', 'cost': {'-cash': '30'}, 'tooltip': {'-type': 'consumable'},
                                    'consumable': {'-duration': '0', '-energy': '0', '-type': 'all',
                                                   '-diweapon': 'DefenseShield', '-postWait': '1s',
                                                   '-givesAbility': 'shield'}, 'image': [
                                          {'-name': 'icon',
                                           '-url': 'assets/game/consumables/ConsumablesUI.swf/Shield_01_96.png'},
                                          {'-name': 'cursor',
                                           '-url': 'assets/game/consumables/ConsumablesUI.swf/Shield_01_49.png'}],
                                    'loc': {'-sentenceName': 'true'},
                                    'requiredExperiment': {'-name': 'empires_consumable_2', '-variants': '3'}},
                                   ('ally', 1), 9999999)]


def setup_session():
    session["fleets"] = {'fleet1_2341959767162880': None, 'fleet3_2341959767162880': None,
                         'fleet5_2341959767162880': None,
                         'fleet7_2341959767162880': None, 'fleet9_2341959767162880': None,
                         'fleet11_2341959767162880': None,
                         'fleet13_2341959767162880': None,
                         'fleet15_2341959767162880': {'-U58': '1', '-SU02': '1', '-U63': '1'},
                         'fleet14_2341959767162880': ['UB96,300,0,0,0', 'UB96,300,0,1,0'],
                         'ally_fleet14_2341959767162880': ['123']}
    setup_user_object()
    session.sid = "0"


def setup_session_invade():
    session["fleets"] = {'fleet1_2341959767162880': None, 'fleet3_2341959767162880': None,
                         'fleet5_2341959767162880': None,
                         'fleet7_2341959767162880': None, 'fleet9_2341959767162880': None,
                         'fleet11_2341959767162880': None,
                         'fleet13_2341959767162880': None,
                         'fleet15_2341959767162880': {'type': 'army', 'uid': '6709797546928099', 'name': 'FleetName',
                                                      'status': 0, 'target': '',
                                                      'consumables': [], 'inventory': [], 'playerLevel': 1,
                                                      'specialBits': None, 'lost': None,
                                                      'lastUnitLost': None, 'lastIndexLost': None, 'allies': None,
                                                      'battleTarget': None,
                                                      'battleTimestamp': None, 'ransomRandom': None,
                                                      'ransomResource': None,
                                                      'ransomAmount': None,
                                                      'units': ['V61,,,,', 'V61,,,,', 'U01,,,,', 'U01,,,,', 'U01,,,,'],
                                                      'store': [0], 'fleets': [], 'upgrades': None, 'hp': None,
                                                      'invader': False},
                         'fleet14_2341959767162880': ['V06,180,1,0,0', 'V06,180,1,1,0', 'UN33,780,0,2,0',
                                                      'UN33,780,0,3,0', 'UL61,340,0,4,0']}

    setup_user_object()
    session.sid = "0"


def setup_user_object():
    session['user_object'] = {'userInfo': {'world': {'campaign': {'current': 'camp001', 'active': {
        'C000': {'status': 2097152, 'fleets': []}, 'C003': {'status': 5242880, 'fleets': []},
        'C004': {'status': 6291456, 'fleets': []}, 'C005': {'status': 7340032, 'fleets': []},
        'C006': {'status': 7340032, 'fleets': []}, 'C007': {'status': 5242880, 'fleets': []},
        'C008': {'status': 7340032, 'fleets': []}, 'C009': {'status': 7340032, 'fleets': []},
        'C010': {'status': 7340032, 'fleets': []}, 'C011': {'status': 8388608, 'fleets': []},
        'C012': {'status': 7340032, 'fleets': []}, 'C013': {'status': 7340032, 'fleets': []},
        'C014': {'status': 7340032, 'fleets': []}, 'C015': {'status': 8388608, 'fleets': []},
        'C016': {'status': 8388608, 'fleets': []}, 'C017': {'status': 9437184, 'fleets': []},
        'C018': {'status': 9437184, 'fleets': []}, 'C019': {'status': 9437184, 'fleets': []},
        'C020': {'status': 9437184, 'fleets': []}, 'C021': {'status': 8388608, 'fleets': []},
        'C022': {'status': 8388608, 'fleets': []}, 'C023': {'status': 8388608, 'fleets': []},
        'C024': {'status': 9437184, 'fleets': []}, 'C025': {'status': 8388608, 'fleets': []},
        'C026': {'status': 9437184, 'fleets': []}, 'C027': {'status': 9437184, 'fleets': []},
        'C028': {'status': 8388608, 'fleets': []}, 'C029': {'status': 9437184, 'fleets': []},
        'C030': {'status': 8388608, 'fleets': []}, 'C031': {'status': 8388608, 'fleets': []},
        'C032': {'status': 9437184, 'fleets': []}, 'C033': {'status': 9437184, 'fleets': []},
        'C034': {'status': 8388608, 'fleets': []}, 'C035': {'status': 9437184, 'fleets': []},
        'C036': {'status': 8388608, 'fleets': []}, 'C037': {'status': 2097152, 'fleets': []}}, 'mastery': {}}}}}
    session['user_object']["userInfo"]["world"]["research"] = {'U43': ['XD01', 'XA01', 'XT01'], 'U45': ['XD01'],
                                                               'U44': ['XD01'], 'U72': ['XD01', 'XA01'],
                                                               'U48': ['XD02', 'XA02', 'XT02', 'XS02', 'XC02',
                                                                       'XR02'], 'U15': ['XD04'],
                                                               'V06': ['XD05', 'XT05', 'XA05', 'XC05', 'XR05',
                                                                       'XS05'],
                                                               'U60': ['XD04', 'XT04', 'XA04', 'XC04', 'XS04',
                                                                       'XR04']}


pytest.main(['-rP'])

