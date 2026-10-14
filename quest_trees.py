"""Mini series ("quest trees").

The client keeps the state of a mini series in the player object:

  player.questTrees          {tree id: [quest names started in this tree]}   one entry per tree the player has
  player.questTreesRestarts  {tree id: times the tree was played again}
  player.questTreeUnlocks    {tree id: [quest names unlocked]}
  player.questTreeData       {tree id: {"allies": [neighbor uids shown in the story], "difficultyMode": ...}}

A tree only exists for the client if it is a key of questTrees: it then places the tree's hook building on the home
island, and clicking it opens the tree screen. Accepting a node calls questTreeStartQuest (the client already
activates the quest locally); the quests themselves are ordinary quests, so the quest engine tracks their tasks.

The original server switched trees on and off by date. Those dates are long gone, so this server offers the trees
whose screens are present in the assets one after another: while the player has an unfinished tree no new one is
added, and a finished tree makes room for the next.
"""
import json
import os
import re

from flask import session

import mod_engine
from game_settings import game_settings, lookup_item_by_code
from quest_engine import lookup_quest, new_quest_with_sequels
from save_engine import install_path

ASSET_ROOT = "assets/sol_assets_octdict/assets"
MAX_ACTIVE_TREES = 1


def _as_list(value):
    return value if isinstance(value, list) else ([value] if value else [])


def _trees():
    trees = {}
    for tree in _as_list(game_settings['settings'].get('questTrees', {}).get('questTree')):
        trees[tree['-id']] = tree  # some ids appear twice, the client keeps the last one too
    return trees


TREES = _trees()


def nodes(tree):
    return [n['-quest'] for n in _as_list(tree.get('node')) if n.get('-quest')]


def first_quest(tree):
    roots = [n['-quest'] for n in _as_list(tree.get('node')) if n.get('-quest') and not n.get('-prequel')]
    return roots[0] if roots else None


def _asset_exists(url):
    relative = url.split('?')[0]
    if relative.startswith('assets/'):
        relative = relative[len('assets/'):]
    key = ASSET_ROOT + '/' + relative
    return key in mod_engine.mod or os.path.exists(os.path.join(install_path(), key))


def screen_urls(tree):
    screen, ui = tree.get('screen'), tree.get('ui') or {}
    if screen:
        urls = [screen.get('-url'), screen.get('-details'), screen.get('-final')]
    else:
        urls = [ui.get('mainScreen', {}).get('-url'), ui.get('questDetails', {}).get('-url'),
                ui.get('finalReward', {}).get('-url')]
    return [u for u in urls if u]


def hook_urls(tree):
    """Asset files of the hook building (its image and the dialog it opens)."""
    item = lookup_item_by_code(tree['hook']['-item']) if tree.get('hook') else None
    if not item:
        return None
    found = set(re.findall(r'assets/[^"\s]+?\.(?:swf|png|jpg)', json.dumps(item)))
    return [u.split('.swf')[0] + '.swf' if '.swf' in u else u for u in found]


def playable(tree):
    """The tree can be shown: its screens and hook building assets exist and all of its quests are known."""
    urls, hooks = screen_urls(tree), hook_urls(tree)
    quests = nodes(tree)
    return bool(urls) and hooks is not None and all(_asset_exists(u) for u in urls + hooks) and \
        bool(quests) and all(lookup_quest(q) for q in quests)


PLAYABLE = [tree_id for tree_id, tree in TREES.items() if playable(tree)]


def _player():
    return session['user_object']["userInfo"]["player"]


def _completed_quests():
    return {e["name"] for e in session['quests'] if e["complete"]}


def tree_complete(tree_id):
    done = _completed_quests()
    return all(q in done for q in nodes(TREES[tree_id]))


def _level_ok(tree):
    level = tree.get('criteria', {}).get('level', {})
    player_level = _player()["level"]
    return int(level.get('-min', 0)) <= player_level <= int(level.get('-max', 9999))


def _ensure_player_fields(player):
    for key in ("questTrees", "questTreeUnlocks", "questTreeData", "questTreesRestarts"):
        if not isinstance(player.get(key), dict):
            player[key] = {}
    if not isinstance(player.get("questTreesFinished"), list):
        player["questTreesFinished"] = []


def _tree_data(tree_id, user):
    tree = TREES[tree_id]
    # screens with story text name the player's allies; harmless for the others
    count = int(tree.get('-totalQuestTreeAllies', 2))
    return {"allies": [n["uid"] for n in user.get("neighbors", []) if "uid" in n][:count]}


def _start_quest(name, new_quests, meta):
    if name and name not in [e['name'] for e in session['quests']]:
        new_quest_with_sequels(name, new_quests, meta, force=True)


def activate_tree(tree_id, user, new_quests, meta):
    tree = TREES[tree_id]
    player = user["userInfo"]["player"]
    first = first_quest(tree)
    player["questTrees"][tree_id] = [first] if first else []
    player["questTreeData"][tree_id] = _tree_data(tree_id, user)
    experiment = tree.get('requiredExperiment')
    if experiment:  # quests of the tree may check the experiment, so put the player in the group that had it
        user.setdefault("experiments", {})[experiment['-name']] = int(experiment['-variants'].split(',')[0])
    if tree.get('-initializeFirstQuest', 'true') == 'true':
        _start_quest(first, new_quests, meta)
    print("Mini series", tree_id, "offered, first quest", first)


def update_quest_trees(user, new_quests, meta):
    """Called on login: retire finished trees and offer the next playable one."""
    player = user["userInfo"]["player"]
    _ensure_player_fields(player)
    for tree_id in list(player["questTrees"]):
        if tree_id in TREES and tree_complete(tree_id):
            reward_quest = TREES[tree_id].get('-rewardQuest')
            if reward_quest and lookup_quest(reward_quest) and reward_quest not in _completed_quests():
                _start_quest(reward_quest, new_quests, meta)
                continue  # keep the tree until its reward quest is done
            del player["questTrees"][tree_id]
            if tree_id not in player["questTreesFinished"]:
                player["questTreesFinished"].append(tree_id)
            print("Mini series", tree_id, "finished")
    active = [t for t in player["questTrees"] if t in TREES]
    for tree_id in PLAYABLE:
        if len(active) >= MAX_ACTIVE_TREES:
            break
        if tree_id in active or tree_id in player["questTreesFinished"] or not _level_ok(TREES[tree_id]):
            continue
        activate_tree(tree_id, user, new_quests, meta)
        active.append(tree_id)


def _response(new_quests):
    return {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0, "QuestComponent": new_quests}, "data": []}


def _merge(new_quests):
    names = [q['name'] for q in new_quests]
    session['quests'][:] = new_quests + [e for e in session['quests'] if e['name'] not in names]


def start_quest_response(params):
    tree_id, quest = params[0], params[1]
    player = _player()
    _ensure_player_fields(player)
    started = player["questTrees"].setdefault(tree_id, [])
    if quest not in started:
        started.append(quest)
    new_quests, meta = [], {}
    _start_quest(quest, new_quests, meta)
    _merge(new_quests)
    return _response(new_quests)


def unlock_quest_response(params):
    tree_id, quest = params[0], params[1]
    player = _player()
    _ensure_player_fields(player)
    unlocks = player["questTreeUnlocks"].setdefault(tree_id, [])
    if quest not in unlocks:
        unlocks.append(quest)
    return start_quest_response(params)


def _forget_quests(names):
    session['quests'][:] = [e for e in session['quests'] if e['name'] not in names]


def reset_response(params):
    """questTreeReset(tree, quest): with a quest only that node is reset, without one the whole tree is replayed."""
    tree_id = params[0]
    quest = params[1] if len(params) > 1 else None
    player = _player()
    _ensure_player_fields(player)
    if tree_id not in TREES:
        return _response([])
    new_quests, meta = [], {}
    if quest:
        _forget_quests([quest])
        if quest in player["questTrees"].get(tree_id, []):
            player["questTrees"][tree_id].remove(quest)
    else:
        player["questTreesRestarts"][tree_id] = player["questTreesRestarts"].get(tree_id, 0) + 1
        tree_quests = nodes(TREES[tree_id]) + [q for q in [TREES[tree_id].get('-rewardQuest')] if q]
        _forget_quests(tree_quests)
        player["questTreeUnlocks"].pop(tree_id, None)
        if tree_id in player["questTreesFinished"]:
            player["questTreesFinished"].remove(tree_id)
        first = first_quest(TREES[tree_id])
        player["questTrees"][tree_id] = [first] if first else []
        _start_quest(first, new_quests, meta)
        _merge(new_quests)
    return _response(new_quests)


def set_mode_response(params):
    tree_id, mode = params[0], params[1]
    player = _player()
    _ensure_player_fields(player)
    player["questTreeData"].setdefault(tree_id, {})["difficultyMode"] = mode
    return reset_response([tree_id])  # the client resets the tree when the mode changes
