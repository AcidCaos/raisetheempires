#TO RUN TESTS RUN empires_test.py

import state_machine
from flask import Flask, session

app = Flask(__name__)
app.secret_key = 'test'


def test_click_next_state():
    with app.test_request_context():
        session['user_object'] = {}
        session['user_object']["userInfo"] = {}
        session['user_object']["userInfo"]["world"] = {"rewardRandSeedZ": 0, "rewardRandSeedW": 0}
        session['user_object']["userInfo"]["world"]["objects"] = [{
            "id": 10000,
            "itemName": "Small Island Hut",
            "position": "50,50,0",
            "referenceItem": None,
            "state": 0
        }]
        session['user_object']["userInfo"]["world"]["resources"] = {"coins": 0, "energy": 0, "oil": 0, "wood": 0, "aluminum": 0, "copper": 0, "gold": 0, "iron": 0, "uranium": 0}
        session['user_object']["userInfo"]["world"]["resourceOrder"] = ["aluminum", "copper", "gold", "iron", "uranium"]
        session['user_object']["userInfo"]["world"]["research"] = {}
        session['user_object']["userInfo"]["player"] = {"xp": 0, "energy": 0, "cash": 0, "socialXpGood": 0, "socialXpBad": 0, "level": 0, "energyMax": 0, "playerResourceType": 3, "lastEnergyCheck": 0}
        session['user_object']["userInfo"]["player"]["inventory"] = {"items":{}}
        session['user_object']["experiments"] = {}
        session["quests"] = []

        meta = {}
        state_machine.click_next_state(True, 10000, meta, "place", None, cancel=None)

        session['user_object']["userInfo"]["world"]["objects"][0]['lastUpdated'] = 0
        assert session['user_object']["userInfo"]["world"]["objects"] == [
            {'id': 10000, 'itemName': 'Small Island Hut', 'position': '50,50,0', 'referenceItem': None, 'state': '1',
             'check_state': {
                 '2': {'-label': 'clearing', '-className': 'SimpleAuto', '-stateName': '2', '-autoNext': '3',
                       '-energy': '-1', '-xp': '1', '-dooberType': 'default', '-imageType': 'ConFence',
                       '-clientDuration': '2.0s', '-duration': '0', '-actionMessage': 'ClearingLandMessage',
                       '-progressBar': 'always', '-tooltip': 'generic_clearing', '-visitTooltip': 'generic_clearing',
                       '-visitorRewardType': 'build'}}, 'lastUpdated': 0}]
        assert meta == {'QuestComponent': [{'name': 'Q0516', 'complete': False, 'expired': False, 'progress': [0], 'completedTasks': 0}]}
        assert session["quests"] == [{'name': 'Q0516', 'complete': False, 'expired': False, 'progress': [0], 'completedTasks': 0}]
        session['user_object']["userInfo"]["player"]['lastEnergyCheck'] = 0
        assert session['user_object']["userInfo"]["player"] == {'xp': 0, 'energy': 25.0, 'cash': 0, 'socialXpGood': 0, 'socialXpBad': 0, 'level': 1, 'energyMax': 25, 'playerResourceType': 3, 'lastEnergyCheck': 0, 'inventory': {'items': {}}}


def test_click_next_state_finish_building():
    with app.test_request_context():
        session['user_object'] = {}
        session['user_object']["userInfo"] = {}
        session['user_object']["userInfo"]["world"] = {"rewardRandSeedZ": 0, "rewardRandSeedW": 0}
        session['user_object']["userInfo"]["world"]["objects"] = [{
            "id": 10000,
            "itemName": "Small Island Hut",
            "position": "50,50,0",
            "referenceItem": None,
            "state": 5
        }]
        session['user_object']["userInfo"]["world"]["resources"] = {"coins": 0, "energy": 0, "oil": 0, "wood": 0, "aluminum": 0, "copper": 0, "gold": 0, "iron": 0, "uranium": 0}
        session['user_object']["userInfo"]["world"]["resourceOrder"] = ["aluminum", "copper", "gold", "iron", "uranium"]
        session['user_object']["userInfo"]["world"]["research"] = {}
        session['user_object']["userInfo"]["player"] = {"xp": 0, "energy": 0, "cash": 0, "socialXpGood": 0, "socialXpBad": 0, "level": 0, "energyMax": 0, "playerResourceType": 3, "lastEnergyCheck": 0}
        session['user_object']["userInfo"]["player"]["inventory"] = {"items":{}}
        session['user_object']["experiments"] = {}
        session["quests"] = [{'name': 'Q0516', 'complete': False, 'expired': False, 'progress': [0], 'completedTasks': 0},{'name': 'QRUX1', 'complete': False, 'expired': False, 'progress': [0,0], 'completedTasks': 0}]

        meta = {}
        state_machine.click_next_state(True, 10000, meta, "setState", None, cancel=None)

        session['user_object']["userInfo"]["world"]["objects"][0]['lastUpdated'] = 0
        assert session['user_object']["userInfo"]["world"]["objects"] == [
            {'id': 10000, 'itemName': 'Small Island Hut', 'position': '50,50,0', 'referenceItem': None, 'state': '8',
              'lastUpdated': 0}]
        assert meta == {'QuestComponent': [{'name': 'QRUX1', 'complete': False, 'expired': False, 'progress': [1, 0], 'completedTasks': 1}]}
        assert session["quests"] == [{'name': 'Q0516', 'complete': False, 'expired': False, 'progress': [0], 'completedTasks': 0},
                                     {'name': 'QRUX1', 'complete': False, 'expired': False, 'progress': [1, 0], 'completedTasks': 1}]
        session['user_object']["userInfo"]["player"]['lastEnergyCheck'] = 0
        assert session['user_object']["userInfo"]["player"] == {'xp': 1, 'energy': 25.0, 'cash': 0, 'socialXpGood': 0, 'socialXpBad': 0, 'level': 1, 'energyMax': 25, 'playerResourceType': 3, 'lastEnergyCheck': 0, 'inventory': {'items': {}}}
