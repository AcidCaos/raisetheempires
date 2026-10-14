import copy
import json
import os

from flask import Flask, session

import quest_trees

app = Flask(__name__)
app.secret_key = 'test'

with open(os.path.join(os.path.dirname(__file__), "init_user.json")) as f:
    INIT_USER = json.load(f)

TREE = quest_trees.PLAYABLE[0]
FIRST = quest_trees.first_quest(quest_trees.TREES[TREE])


def setup_session(level=40):
    user = copy.deepcopy(INIT_USER)
    user["userInfo"]["player"]["level"] = level
    user["neighbors"] = [{"uid": -1}, {"uid": 123}, {"uid": 131}]
    session["user_object"] = user
    session["quests"] = []
    return user


def quest_names():
    return [q["name"] for q in session["quests"]]


def offer_trees():
    user = session["user_object"]
    new_quests, meta = [], {}
    quest_trees.update_quest_trees(user, new_quests, meta)
    session["quests"][:] = new_quests + session["quests"]
    return user["userInfo"]["player"], new_quests


def complete(names):
    for q in session["quests"]:
        if q["name"] in names:
            q["complete"] = True


def test_playable_trees_have_screens_and_quests():
    assert quest_trees.PLAYABLE
    for tree_id in quest_trees.PLAYABLE:
        tree = quest_trees.TREES[tree_id]
        assert quest_trees.first_quest(tree) in quest_trees.nodes(tree)


def test_login_offers_one_tree_and_starts_its_first_quest():
    with app.test_request_context():
        setup_session()
        player, new_quests = offer_trees()

        assert list(player["questTrees"]) == [TREE]
        assert player["questTrees"][TREE] == [FIRST]
        assert [q["name"] for q in new_quests] == [FIRST]
        assert player["questTreeData"][TREE]["allies"] == [-1, 123, 131][:len(player["questTreeData"][TREE]["allies"])]

        offer_trees()  # logging in again does not offer another tree while this one is unfinished
        assert list(player["questTrees"]) == [TREE]
        assert quest_names().count(FIRST) == 1


def test_low_level_player_gets_no_tree():
    with app.test_request_context():
        setup_session(level=1)
        player, new_quests = offer_trees()

        assert player["questTrees"] == {}
        assert new_quests == []


def test_start_quest_tracks_node_and_activates_quest():
    with app.test_request_context():
        setup_session()
        player, _ = offer_trees()
        second = quest_trees.nodes(quest_trees.TREES[TREE])[1]

        response = quest_trees.start_quest_response([TREE, second])

        assert second in player["questTrees"][TREE]
        assert second in quest_names()
        assert [q["name"] for q in response["metadata"]["QuestComponent"]] == [second]
        quest_trees.start_quest_response([TREE, second])  # repeated calls do not duplicate the quest
        assert quest_names().count(second) == 1


def test_unlock_quest_is_remembered():
    with app.test_request_context():
        setup_session()
        player, _ = offer_trees()
        second = quest_trees.nodes(quest_trees.TREES[TREE])[1]

        quest_trees.unlock_quest_response([TREE, second])

        assert player["questTreeUnlocks"][TREE] == [second]


def test_finished_tree_makes_room_for_the_next():
    with app.test_request_context():
        setup_session()
        player, _ = offer_trees()
        for name in quest_trees.nodes(quest_trees.TREES[TREE]):
            quest_trees.start_quest_response([TREE, name])
        complete(quest_trees.nodes(quest_trees.TREES[TREE]))

        offer_trees()

        assert TREE not in player["questTrees"]
        assert TREE in player["questTreesFinished"]
        assert list(player["questTrees"]) == [quest_trees.PLAYABLE[1]]


def test_reset_replays_tree():
    with app.test_request_context():
        setup_session()
        player, _ = offer_trees()
        second = quest_trees.nodes(quest_trees.TREES[TREE])[1]
        quest_trees.start_quest_response([TREE, second])
        complete([FIRST])

        quest_trees.reset_response([TREE, None])

        assert player["questTreesRestarts"][TREE] == 1
        assert player["questTrees"][TREE] == [FIRST]
        assert second not in quest_names()
        assert [q for q in session["quests"] if q["name"] == FIRST][0]["complete"] is False


def test_reset_single_node():
    with app.test_request_context():
        setup_session()
        player, _ = offer_trees()
        second = quest_trees.nodes(quest_trees.TREES[TREE])[1]
        quest_trees.start_quest_response([TREE, second])

        quest_trees.reset_response([TREE, second])

        assert second not in quest_names()
        assert player["questTrees"][TREE] == [FIRST]


def test_set_mode_stores_mode_and_restarts():
    with app.test_request_context():
        setup_session()
        player, _ = offer_trees()

        quest_trees.set_mode_response([TREE, "hard"])

        assert player["questTreeData"][TREE]["difficultyMode"] == "hard"
        assert player["questTreesRestarts"][TREE] == 1
