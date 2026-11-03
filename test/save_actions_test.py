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


def test_full_heal_charges_cash(server, user):
    user["userInfo"]["player"]["cash"] = 100
    server.buy_full_heal_response({"cost": 30, "fleet": "f1"})
    assert user["userInfo"]["player"]["cash"] == 70


def test_multi_harvest_gives_back_the_discount(server, user):
    player, resources = user["userInfo"]["player"], user["userInfo"]["world"]["resources"]
    player["energy"], resources["energy"] = 10, 10
    server.multi_harvest_response([[1, 2, 3], 5, 5, 6, 4])
    assert player["energy"] == 12 and resources["energy"] == 12


def test_reward_item_goes_to_inventory_for_its_cash_price(server, user):
    item = next(e for e in server.game_settings['settings']['items']['item']
                if int(((e.get("cost") or {}).get("-cash", 0)) or 0) > 0)
    player = user["userInfo"]["player"]
    player["cash"] = 1000
    player["inventory"]["items"] = {}
    server.buy_reward_item_response({"code": item["-code"], "quest_name": "Q1"})
    assert player["inventory"]["items"] == {item["-code"]: 1}
    assert player["cash"] == 1000 - int(item["cost"]["-cash"])


def test_spend_completes_the_spend_task(server, user):
    quest = next(q for q in server.quest_settings['quests']['quest']
                 if any(t.get("_action") == "spend" and t.get("_type") == "coins" for t in server.get_tasks(q)))
    session["quests"] = [server.new_quest(quest)]
    task_index = [t.get("_action") for t in server.get_tasks(quest)].index("spend")
    total = int(server.get_tasks(quest)[task_index]["_total"])
    user["userInfo"]["world"]["resources"]["coins"] = total + 5

    server.spend_response({"type": "coins", "code": None, "amount": total})

    assert user["userInfo"]["world"]["resources"]["coins"] == 5
    assert session["quests"][0]["progress"][task_index] == total


def test_spend_item_takes_it_from_inventory(server, user):
    user["userInfo"]["player"]["inventory"]["items"] = {"X1": 3}
    server.spend_response({"type": "item", "code": "X1", "amount": 3})
    assert "X1" not in user["userInfo"]["player"]["inventory"]["items"]


def test_restart_task_unexpires_the_quest_for_its_restart_cost(server, user):
    quest = next(q for q in server.quest_settings['quests']['quest'] if int(q.get("_restartCost", 0) or 0) > 0)
    session["quests"] = [dict(server.new_quest(quest), expired=True)]
    user["userInfo"]["player"]["cash"] = 1000
    server.buy_quest_restart_task_response({"name": quest["_name"]})
    assert session["quests"][0]["expired"] is False
    assert user["userInfo"]["player"]["cash"] == 1000 - int(quest["_restartCost"])


def test_upgrade_state_switches_the_building(server, user):
    user["userInfo"]["world"]["objects"] = [{"id": 7, "itemName": "Parliament", "state": "8", "position": "1,1,0"}]
    server.upgrade_state_response([{"id": 7}, "CA2", "upgrade1"])
    assert user["userInfo"]["world"]["objects"][0]["state"] == "upgrade1"


def test_remove_expired_inventory_removes_one(server, user):
    user["userInfo"]["player"]["inventory"]["items"] = {"A": 2, "B": 1}
    server.remove_expired_inventory_response({"code": "A"})
    server.remove_expired_inventory_response({"code": "B"})
    assert user["userInfo"]["player"]["inventory"]["items"] == {"A": 1}
