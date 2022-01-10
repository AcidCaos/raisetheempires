import json

import pytest
from flask import Flask, session, request
from pyamf import remoting

empires_server = __import__('empires-server')
import quest_engine

app = Flask(__name__)
app.secret_key = 'test'


def test_add_fleet():
    with app.test_request_context():
        session["fleets"] = {}
        empires_server.add_fleet_response(
            {'status': 104, 'allies': ['123'], 'name': 'fleet14_3398563345700246', 'type': 'air',
             'uid': '3398563345700246', 'ch': 5921, 'units': ['UB96,300,0,0,0', 'UB96,300,0,1,0']})

        assert session["fleets"]["fleet14_3398563345700246"] == ['UB96,300,0,0,0', 'UB96,300,0,1,0']
        assert session["fleets"]["ally_fleet14_3398563345700246"] == ['123']


def test_random_fleet_challenge_response(monkeypatch):
    def get_saves_mock():
        return [{'user_object': {"userInfo": {"player": {"uid": 1}}, "pvp": {
            "invaders": {"u2341959767162880": {"defender_fleet": ['V61,,,,', 'U01,,,,', 'U01,,,,', 'U01,,,,']}}}}}]

    monkeypatch.setattr(empires_server, "get_saves", get_saves_mock)

    with app.test_request_context():
        session.sid = "0"
        session["fleets"] = {}
        resp = empires_server.random_fleet_challenge_response(1)

        assert resp == {'errorType': 0, 'userId': 1, 'metadata': {'newPVE': 0},
                        'data': {'state': 0,
                                 'challengerFleet': {'type': 'army', 'uid': 1, 'name': 'FleetName', 'status': 0,
                                                     'target': '', 'consumables': [], 'inventory': [], 'playerLevel': 1,
                                                     'specialBits': None, 'lost': None, 'lastUnitLost': None,
                                                     'lastIndexLost': None, 'allies': None, 'battleTarget': None,
                                                     'battleTimestamp': None, 'ransomRandom': None,
                                                     'ransomResource': None, 'ransomAmount': None,
                                                     'units': ['V61,,,,', 'U01,,,,', 'U01,,,,', 'U01,,,,'],
                                                     'store': [0], 'fleets': [], 'upgrades': None, 'hp': None,
                                                     'invader': False}, 'challengeInfo': {'status': 0, 'state': 1},
                                 'maxUnits': 5}}


        assert session['fleets'] == {
            'FleetName': {'type': 'army', 'uid': 1, 'name': 'FleetName', 'status': 0, 'target': '',
                                        'consumables': [], 'inventory': [], 'playerLevel': 1, 'specialBits': None,
                                        'lost': None, 'lastUnitLost': None, 'lastIndexLost': None, 'allies': None,
                                        'battleTarget': None, 'battleTimestamp': None, 'ransomRandom': None,
                                        'ransomResource': None, 'ransomAmount': None,
                                        'units': ['V61,,,,', 'U01,,,,', 'U01,,,,', 'U01,,,,'], 'store': [0],
                                        'fleets': [], 'upgrades': None, 'hp': None, 'invader': False}}


def test_random_enemy_fleet_challenge_response():
    with app.test_request_context():
        session.sid = "0"

        session["fleets"] = {'fleet1_2341959767162880': None, 'fleet3_2341959767162880': None,
                             'fleet5_2341959767162880': None,
                             'fleet7_2341959767162880': None, 'fleet9_2341959767162880': None,
                             'fleet11_2341959767162880': None,
                             'fleet13_2341959767162880': None}

        session['user_object'] = {}
        session['user_object']["pvp"] = {}
        session['user_object']["pvp"]["invaders"] = \
            {'pve': {'quest': True},
             'u1': {'ts': 1641396925.262768, 'pillTS': 1641396925.262768, 'status': 2, 'pos': '53,57', 'size': 5,
                    'chID': '1',
                    'defender_fleet': ['V03,,,,', 'U04,,,,', 'U04,,,,', 'V61,,,,', 'V61,,,,'],
                    'attacker_fleet': ['U25,,,,', 'V62,,,,', 'V62,,,,', 'V04,,,,', 'V03,,,,']}}

        resp = empires_server.random_enemy_fleet_challenge_response('fleet1_1')

        assert resp == {'errorType': 0, 'userId': 1, 'metadata': {'newPVE': 0},
                        'data': {'state': 0,
                                 'challengerFleet': {'type': 'army', 'uid': '1', 'invaded_uid': None,
                                                     'name': 'FleetName', 'status': 0, 'target': '', 'consumables': [],
                                                     'inventory': [], 'playerLevel': 1, 'specialBits': None,
                                                     'lost': None, 'lastUnitLost': None, 'lastIndexLost': None,
                                                     'allies': None, 'battleTarget': None, 'battleTimestamp': None,
                                                     'ransomRandom': None, 'ransomResource': None, 'ransomAmount': None,
                                                     'units': ['U25,,,,', 'V62,,,,', 'V62,,,,', 'V04,,,,', 'V03,,,,'],
                                                     'store': [0], 'fleets': [], 'upgrades': None, 'hp': None,
                                                     'invader': True}, 'challengeInfo': {'status': 0, 'state': 1},
                                 'maxUnits': 5}}

        assert session['fleets'] == \
               {'fleet1_2341959767162880': None, 'fleet3_2341959767162880': None, 'fleet5_2341959767162880': None,
                'fleet7_2341959767162880': None, 'fleet9_2341959767162880': None, 'fleet11_2341959767162880': None,
                'fleet13_2341959767162880': None,
                'FleetName': {'type': 'army', 'uid': '1', 'invaded_uid': None,
                                             'name': 'FleetName', 'status': 0, 'target': '', 'consumables': [],
                                             'inventory': [], 'playerLevel': 1, 'specialBits': None, 'lost': None,
                                             'lastUnitLost': None, 'lastIndexLost': None, 'allies': None,
                                             'battleTarget': None,
                                             'battleTimestamp': None, 'ransomRandom': None, 'ransomResource': None,
                                             'ransomAmount': None,
                                             'units': ['U25,,,,', 'V62,,,,', 'V62,,,,', 'V04,,,,', 'V03,,,,'],
                                             'store': [0],
                                             'fleets': [], 'upgrades': None, 'hp': None, 'invader': True}}


def test_load_challenge_response():
    with app.test_request_context():
        session.sid = "0"

        session["fleets"] = \
            {'fleet1_2341959767162880': None, 'fleet3_2341959767162880': None, 'fleet5_2341959767162880': None,
             'fleet7_2341959767162880': None, 'fleet9_2341959767162880': None, 'fleet11_2341959767162880': None,
             'fleet13_2341959767162880': None,
             'fleet15_2341959767162880': {'type': 'army', 'uid': '1', 'invaded_uid': None,
                                          'name': 'FleetName',
                                          'status': 0, 'target': '', 'consumables': [], 'inventory': [],
                                          'playerLevel': 1,
                                          'specialBits': None, 'lost': None, 'lastUnitLost': None,
                                          'lastIndexLost': None,
                                          'allies': None, 'battleTarget': None, 'battleTimestamp': None,
                                          'ransomRandom': None,
                                          'ransomResource': None, 'ransomAmount': None,
                                          'units': ['U25,,,,', 'V62,,,,', 'V62,,,,', 'V04,,,,', 'V03,,,,'],
                                          'store': [0],
                                          'fleets': [], 'upgrades': None, 'hp': None, 'invader': True}}

        resp = empires_server.load_challenge_response({'challengeeFleet': {'name': 'fleet14_2341959767162880',
                                                                           'type': 'army', 'uid': '2341959767162880',
                                                                           'status': 104,
                                                                           'units': ['UN06,740,0,0,0', 'V06,180,1,1,0',
                                                                                     'V06,180,1,2,0', 'UN33,780,0,3,0',
                                                                                     'UN33,780,0,4,0']},
                                                       'challengeFleetName': 'FleetName'})

        assert resp == {'errorType': 0, 'userId': 1, 'metadata': {'newPVE': 0}, 'data': {'eFID': 'pve', 'state': 1}}
        assert {'fleet1_2341959767162880': None, 'fleet3_2341959767162880': None, 'fleet5_2341959767162880': None,
                'fleet7_2341959767162880': None, 'fleet9_2341959767162880': None, 'fleet11_2341959767162880': None,
                'fleet13_2341959767162880': None,
                'fleet15_2341959767162880': {'type': 'army', 'uid': '1', 'invaded_uid': None,
                                             'name': 'FleetName', 'status': 0, 'target': '', 'consumables': [],
                                             'inventory': [], 'playerLevel': 1, 'specialBits': None, 'lost': None,
                                             'lastUnitLost': None, 'lastIndexLost': None, 'allies': None,
                                             'battleTarget': None, 'battleTimestamp': None, 'ransomRandom': None,
                                             'ransomResource': None, 'ransomAmount': None,
                                             'units': ['U25,,,,', 'V62,,,,', 'V62,,,,', 'V04,,,,', 'V03,,,,'], 'store': [0],
                                             'fleets': [], 'upgrades': None, 'hp': None, 'invader': True},
                'fleet14_2341959767162880': ['UN06,740,0,0,0', 'V06,180,1,1,0', 'V06,180,1,2,0', 'UN33,780,0,3,0',
                                             'UN33,780,0,4,0']}


def test_tutorial_response(monkeypatch):
    step = None
    reported_quests = None
    pve = None
    sequence = None
    reported_endpoint = None
    def report_tutorial_step(a, b, c, d, e):
        nonlocal step, reported_quests, pve, sequence, reported_endpoint
        (step, reported_quests, pve, sequence, reported_endpoint) = (a, b, c, d, e)


    def get_saves_mock():
        return []

    monkeypatch.setattr(quest_engine, "get_saves", get_saves_mock)
    monkeypatch.setattr(empires_server, "report_tutorial_step", report_tutorial_step)

    with app.test_request_context():
        session["quests"] = [{'name': 'Q1140', 'complete': False, 'expired': False, 'progress': [0], 'completedTasks': 0},
                             {'name': 'Q0516', 'complete': False, 'expired': False, 'progress': [0],
                              'completedTasks': 0}]

        session['user_object'] = {}
        session['user_object']["userInfo"] = {}
        session['user_object']["userInfo"]["player"] = {"inventory": {"items": {}},
                                                        "tutorialProgress": "tut_step_inviteFriendsViral",
                                                        "xp": 0, "energy": 0, "cash": 0, "socialXpGood": 0,
                                                        "socialXpBad": 0, "level": 0, "energyMax": 0,
                                                        "playerResourceType": 3, "lastEnergyCheck": 0}
        session['user_object']["userInfo"]["world"] = {}
        session['user_object']["userInfo"]["world"]["resources"] = {"coins": 0, "energy": 0, "oil": 0, "wood": 0,
                                                                    "aluminum": 0, "copper": 0, "gold": 0, "iron": 0,
                                                                    "uranium": 0}
        session['user_object']["userInfo"]["world"]["resourceOrder"] = ["aluminum", "copper", "gold", "iron", "uranium"]
        session['user_object']["experiments"] = {}


        resp = empires_server.tutorial_response('tut_step_inviteFriendsEndPauseTutorial', 18, '/14')

        assert resp == {'errorType': 0, 'userId': 1, 'metadata': {'newPVE': 0, 'QuestComponent': [
            {'name': 'Q1140', 'complete': True, 'expired': False, 'progress': [1], 'completedTasks': 1}]}, 'data': []}
        assert session['user_object']["userInfo"]["player"]["tutorialProgress"] == 'tut_step_inviteFriendsEndPauseTutorial'
        assert session["quests"] == [{'name': 'Q1140', 'complete': True, 'expired': False, 'progress': [1], 'completedTasks': 1},
                                     {'name': 'Q0516', 'complete': False, 'expired': False, 'progress': [0], 'completedTasks': 0}]
        assert step == 'tut_step_inviteFriendsEndPauseTutorial'
        assert reported_quests == [{'name': 'Q1140', 'complete': True, 'expired': False, 'progress': [1], 'completedTasks': 1}]
        assert pve == 0
        assert sequence == 18
        assert reported_endpoint == '/14'


def test_init_user(monkeypatch):
    def get_saves_mock():
        return []

    monkeypatch.setattr(empires_server, "get_saves", get_saves_mock)

    with app.test_request_context():
        session.sid = "0"
        session['profilePic'] = "assets/game/GeneralAssetGroup_UI.swf/TheVille_50.png"
        user = empires_server.init_user()

        with open('init_user.json', 'r') as f:
            user["userInfo"]["player"]["lastEnergyCheck"] = 0
            assert user == json.load(f)


# def test_index():
#     with app.test_client() as client:
#         rv = client.get('/')
#         print(repr(rv))


def test_post_gateway(monkeypatch):
    reported_service = None
    reported_response = None
    reported_req = None
    reported_endpoint = None

    def report_other_log_mock(a, b, c, d):
        nonlocal reported_service, reported_response, reported_req, reported_endpoint
        (reported_service, reported_response, reported_req, reported_endpoint) = (a, b, c, d)

    monkeypatch.setattr(empires_server, "report_other_log", report_other_log_mock)


    with app.test_request_context():
        session["fleets"] = {}

        envelope = remoting.Envelope(3);
        req = remoting.Request('BaseService.dispatchBatch', body=[{'flashRevision': None}, [
            {'transaction': None, 'sequence': 22, 'stamp': 1641513847112.56, 'params': [
                {'status': 104, 'allies': ['-1'], 'name': 'fleet16_3398563345700246', 'type': 'air',
                 'uid': '3398563345700246', 'ch': 5867, 'units': ['UB96,300,0,0,0', 'UB96,300,0,1,0']}],
             'functionName': 'WorldService.addFleet'}], 0], envelope=envelope)
        envelope.bodies = [('/9', req)]

        raw_data = remoting.encode(envelope)

        request.data = raw_data
        response_result = empires_server.post_gateway()

        assert reported_service == 'WorldService.addFleet'
        assert reported_response == {'errorType': 0, 'userId': 1, 'metadata': {'newPVE': 0}, 'data': []}
        assert reported_req == {'transaction': None, 'sequence': 22, 'stamp': 1641513847112.56, 'params': [
            {'status': 104, 'allies': ['-1'], 'name': 'fleet16_3398563345700246', 'type': 'air',
             'uid': '3398563345700246', 'ch': 5867, 'units': ['UB96,300,0,0,0', 'UB96,300,0,1,0']}],
         'functionName': 'WorldService.addFleet'}
        assert reported_endpoint == '/9'

        endpoint_response = remoting.decode(response_result.data)

        assert endpoint_response.bodies[0][0] == '/9'
        assert remoting.decode(response_result.data).bodies[0][1].body['errorType'] == 0
        assert remoting.decode(response_result.data).bodies[0][1].body['data'] == [{'errorType': 0, 'userId': 1, 'metadata': {'newPVE': 0}, 'data': []}]


pytest.main(['-rPA'])
