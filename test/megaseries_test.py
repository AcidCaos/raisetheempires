import copy
import json
import os

import pytest
from flask import Flask, session

import megaseries
import quest_trees

app = Flask(__name__)
app.secret_key = 'test'

with open(os.path.join(os.path.dirname(__file__), "init_user.json")) as f:
    INIT_USER = json.load(f)

SHIP = next(name for name, item in quest_trees.ITEMS_BY_NAME.items()
            if "W" in str(item.get("canBuildOn", "")) and int(item.get("sizeX", 1)) == 1)


@pytest.fixture(autouse=True)
def spots_file(monkeypatch, tmp_path):
    monkeypatch.setattr(quest_trees, "_spots_file", lambda: str(tmp_path / "quest_tree_spots.json"))


def setup_session(level=40, with_water=True):
    user = copy.deepcopy(INIT_USER)
    user["userInfo"]["player"]["level"] = level
    user["userInfo"]["world"] = {"sizeX": 60, "sizeY": 60, "globalObjectId": 100, "roadData": [], "resourceOrder": [],
                                 "objects": [{"id": i, "itemName": SHIP, "position": "%d,30,0" % (20 + i), "state": "0"}
                                             for i in range(20)] if with_water else []}
    session["user_object"] = user
    session["quests"] = []
    return user


def login():
    user = session["user_object"]
    new_quests, meta = [], {}
    megaseries.update_megaseries(user, new_quests, meta)
    session["quests"][:] = new_quests + session["quests"]
    return user, new_quests


def test_playable_series_have_quests_and_entry_buildings():
    assert megaseries.PLAYABLE
    for series_id in megaseries.PLAYABLE:
        assert megaseries.entry_item(megaseries.SERIES[series_id])
        assert megaseries.nodes(megaseries.SERIES[series_id])


def test_login_offers_a_series_with_building_experiment_and_first_quest():
    with app.test_request_context():
        setup_session()
        user, new_quests = login()
        player = user["userInfo"]["player"]

        assert len(player["megaseriesList"]) == 1
        series_id, quest = next(iter(player["megaseriesList"].items()))
        series = megaseries.SERIES[series_id]
        assert quest == megaseries.nodes(series)[0]
        assert [q["name"] for q in new_quests] == [quest]
        experiment = series["requiredExperiment"]
        assert user["experiments"][experiment["-name"]] == int(experiment["-variants"])
        entry = [o for o in user["userInfo"]["world"]["objects"] if o["itemName"] == series["-entryPointName"]]
        assert len(entry) == 1 and entry[0]["state"] == "0" and entry[0]["id"] == 101

        login()  # nothing new while the series is not finished
        assert list(player["megaseriesList"]) == [series_id]
        assert len([o for o in user["userInfo"]["world"]["objects"] if o["itemName"] == series["-entryPointName"]]) == 1


def test_no_series_without_water_or_below_level():
    with app.test_request_context():
        setup_session(with_water=False)
        user, _ = login()
        assert user["userInfo"]["player"]["megaseriesList"] == {}
        setup_session(level=1)
        user, _ = login()
        assert user["userInfo"]["player"]["megaseriesList"] == {}


def test_finished_series_keeps_its_key_and_makes_room_for_the_next():
    with app.test_request_context():
        user = setup_session()
        login()
        player = user["userInfo"]["player"]
        first = next(iter(player["megaseriesList"]))
        session["quests"][:] = [{"name": q, "complete": True, "expired": False, "progress": [], "completedTasks": 0}
                                for q in megaseries.nodes(megaseries.SERIES[first])]

        login()

        assert player["megaseriesList"][first] == megaseries.nodes(megaseries.SERIES[first])[-1]
        assert first in player["megaseriesFinished"]
        if len(megaseries.PLAYABLE) > 1:
            assert len(player["megaseriesList"]) == 2


def test_reset_starts_the_series_again():
    with app.test_request_context():
        user = setup_session()
        login()
        series_id = next(iter(user["userInfo"]["player"]["megaseriesList"]))
        quests = megaseries.nodes(megaseries.SERIES[series_id])
        session["quests"][:] = [{"name": q, "complete": True, "expired": False, "progress": [], "completedTasks": 0}
                                for q in quests[:3]]

        megaseries.reset_response([series_id])

        assert [q["name"] for q in session["quests"]] == [quests[0]]
        assert session["quests"][0]["complete"] is False
        assert user["userInfo"]["player"]["megaseriesList"][series_id] == quests[0]
