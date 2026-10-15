import copy
import json
import os

import pytest
from flask import Flask, session

HERE = os.path.dirname(__file__)
app = Flask(__name__)
app.secret_key = "test"


@pytest.fixture(scope="module")
def server():
    return __import__('empires-server')


@pytest.fixture
def user(server):
    with open(os.path.join(HERE, "init_user.json")) as f:
        init = json.load(f)
    with app.test_request_context():
        session["user_object"] = copy.deepcopy(init)
        session["quests"] = []
        yield session["user_object"]


def test_unit_unlock_is_saved_once(server, user):
    server.unit_unlock_response("U123")
    server.unit_unlock_response("U123")
    assert user["userInfo"]["player"]["unlockedUnits"].count("U123") == 1


def test_purchase_unlock_saves_item_and_charges_unlock_cost(server, user):
    item = next(e for e in server.game_settings['settings']['items']['item'] if int(e.get('unlockCost', 0) or 0) > 0)
    player = user["userInfo"]["player"]
    player["cash"] = 1000

    server.purchase_unlock_response({"itemCode": item["-code"]})
    server.purchase_unlock_response({"itemCode": item["-code"]})  # a second unlock is not charged again

    assert player["unlockedItems"] == [item["-code"]]
    assert player["cash"] == 1000 - int(item["unlockCost"])


def test_unlock_resource_only_raises_the_multiplier(server, user):
    user["unlockedResource"] = {"gold": 5}
    server.unlock_resource_response("gold", 7)
    server.unlock_resource_response("gold", 3)
    server.unlock_resource_response("uranium", 2)
    assert user["unlockedResource"] == {"gold": 7, "uranium": 2}


def test_upgrade_research_building_is_saved(server, user):
    user["userInfo"]["world"]["research2"] = {"buildingTypesUpgraded": None, "treesUnlocked": None}
    server.upgrade_research_building_response("barracks")
    server.upgrade_research_building_response("barracks")
    assert user["userInfo"]["world"]["research2"]["buildingTypesUpgraded"] == ["barracks"]
