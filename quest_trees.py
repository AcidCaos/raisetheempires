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
import functools
import json
import os
import re
import zlib

from flask import session

import mod_engine
from game_settings import game_settings, lookup_item_by_code
from quest_engine import lookup_quest, new_quest_with_sequels
from save_engine import install_path, my_games_path

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


def _asset_file(relative):
    if relative.startswith('assets/'):
        relative = relative[len('assets/'):]
    key = ASSET_ROOT + '/' + relative
    if key in mod_engine.mod:
        return key
    path = os.path.join(install_path(), key)
    return path if os.path.exists(path) else None


@functools.lru_cache(maxsize=None)
def _swf_bytes(relative):
    """Uncompressed body of a swf, to look up the names of the symbols it exports."""
    found = _asset_file(relative)
    if not found:
        return None
    data = mod_engine.mod[found]() if found in mod_engine.mod else open(found, 'rb').read()
    if isinstance(data, str):
        data = data.encode('latin-1')
    if data[:3] == b'CWS':
        return zlib.decompress(data[8:])
    return data


def _asset_exists(url):
    """A file, or for "file.swf/Symbol.png" a symbol inside a swf (one swf holds the images of many hooks)."""
    relative = url.split('?')[0]
    if '.swf/' in relative:
        swf, symbol = relative.split('.swf/', 1)
        body = _swf_bytes(swf + '.swf')
        return body is not None and symbol.encode() in body
    return _asset_file(relative) is not None


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
    return sorted(set(re.findall(r'assets/[^"\s]+?\.(?:swf|png|jpg)(?:/[^"\s]+?\.png)?', json.dumps(item))))


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
    remember_hook_spots(user["userInfo"]["world"])
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


HOOK_SIZE = 3
HOOK_SPOTS = 6
ITEMS_BY_NAME = {item['-name']: item for item in game_settings['settings']['items']['item']}


def _cells(x, y, size_x, size_y):
    return {(x + i, y + j) for i in range(size_x) for j in range(size_y)}


def hook_spots(world, count=HOOK_SPOTS):
    """Empty 3x3 spots on land for the hook building.

    The client only tries the fixed positions of the tree's <hook> and otherwise puts the building at 0,0, outside of
    the map. On a built up island those positions are usually taken, so offer spots of this world instead. The save
    does not say which tiles are land, so a spot counts as land when roads or land buildings surround it and no water
    item (ships, docks) is near.
    """
    land, water, taken = set(), set(), set()
    for obj in world.get("objects", []):
        try:
            x, y = map(int, obj["position"].split(",")[:2])
            item = ITEMS_BY_NAME[obj["itemName"]]
        except (KeyError, ValueError):
            continue
        cells = _cells(x, y, int(item.get("sizeX", 1)), int(item.get("sizeY", 1)))
        taken |= cells
        (water if "W" in str(item.get("canBuildOn", "")) else land).update(cells)
    for road in world.get("roadData", []):
        (x1, y1), (x2, y2) = [map(int, end.split(",")) for end in road.split("|")]
        cells = _cells(min(x1, x2), min(y1, y2), abs(x2 - x1) + 1, abs(y2 - y1) + 1)
        taken |= cells
        land |= cells
    candidates = []
    for x in range(int(world.get("sizeX", 200)) - HOOK_SIZE):
        for y in range(int(world.get("sizeY", 200)) - HOOK_SIZE):
            spot = _cells(x, y, HOOK_SIZE, HOOK_SIZE)
            if spot & taken:
                continue
            ring = _cells(x - 1, y - 1, HOOK_SIZE + 2, HOOK_SIZE + 2) - spot
            surrounding = len(ring & land)
            if surrounding >= 6 and not (_cells(x - 3, y - 3, HOOK_SIZE + 6, HOOK_SIZE + 6) & water):
                candidates.append((-surrounding, x, y))
    spots, used = [], set()
    for _, x, y in sorted(candidates):
        spot = _cells(x - 1, y - 1, HOOK_SIZE + 2, HOOK_SIZE + 2)  # keep spots apart, hooks may not overlap
        if spot & used:
            continue
        spots.append((x, y))
        used |= spot
        if len(spots) == count:
            break
    return spots


def _spots_file():
    return os.path.join(my_games_path(), "quest_tree_spots.json")


def remember_hook_spots(world):
    """The client fetches gameSettings.xml before it logs in and without the session cookie, so the free spots of
    the island played last are kept in a file for the next time the settings are served."""
    spots = hook_spots(world)
    try:
        with open(_spots_file(), "w") as f:
            json.dump(spots, f)
    except OSError as error:
        print("Could not store mini series spots", error)
    return spots


def remembered_hook_spots():
    try:
        with open(_spots_file()) as f:
            return [tuple(spot) for spot in json.load(f)]
    except (OSError, ValueError):
        return []


def patch_settings_xml(xml, spots):
    """Put free spots of the player's island in front of the fixed hook positions of every offered tree."""
    positions = "".join("<pos>%d,%d</pos>" % tuple(spot) for spot in spots)
    if not positions:
        return xml
    for tree_id in PLAYABLE:
        hook = TREES[tree_id].get('hook', {}).get('-item')
        start = xml.find('<questTree id="%s"' % tree_id)
        if not hook or start < 0:
            continue
        tag = '<hook item="%s">' % hook
        at = xml.find(tag, start, xml.find('</questTree>', start))
        if at >= 0:
            at += len(tag)
            xml = xml[:at] + positions + xml[at:]
    return xml
