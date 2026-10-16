"""Mega series (MS01..MS07): long quest chains in three stages, opened from an entry building on the water.

What the client needs (reverse engineered from MegaseriesManager / Megaseries):
  player.megaseriesList   {series id: name of its current quest}; a series only exists for the client if it is a key
                          here. The client works out the stage itself from completedQuests.
  user.experiments        the series' requiredExperiment (empire_megaseries_00N) set to its variant, otherwise the
                          entry building destroys itself and the quests do not start.
  world.objects           the entry building (item MSEntryDecoN, state 0). Unlike mini series the client does not
                          create it, the server has to place it.

The quests are ordinary quests chained by sequels, so the quest engine does the rest. Stage changes reach the
server as setState calls on the entry building, which the state machine code already handles.

Two things crash the client: an entry building whose series is not in megaseriesList, and a stage quest finishing
while the series has no entry building. So keys are never removed (a finished series keeps its reward quest as
value) and the building is placed together with the series.

Only the series whose quest popup is present in the assets are offered, one at a time.
"""
import os

from flask import session

from game_settings import game_settings
from quest_engine import lookup_quest, new_quest_with_sequels
from quest_trees import ITEMS_BY_NAME, _asset_exists, _cells, _level_ok

MAX_ACTIVE = 1
ENTRY_STATE = "0"


def _as_list(value):
    return value if isinstance(value, list) else ([value] if value else [])


def _series():
    found = {}
    for series in _as_list(game_settings['settings'].get('megaSeriesList', {}).get('megaSeries')):
        found[series['-id']] = series
    return found


SERIES = _series()


def nodes(series):
    """Quests of the series in play order; the last one is the reward quest."""
    return [node['-quest'] for stage in _as_list(series.get('stage')) for node in _as_list(stage.get('node'))
            if node.get('-quest')]


def entry_item(series):
    return ITEMS_BY_NAME.get(series.get('-entryPointName'))


def _popup_files(series):
    popup = series.get('-assetPopupFile')
    if not popup:
        return []
    return [popup, popup.replace('megaseries_main.swf', 'MegaSeries_dialog.swf')]


def playable(series):
    item = entry_item(series)
    if not item or not series.get('requiredExperiment'):
        return False
    # inventory icons are not needed, the building is placed directly
    images = [image.get('-url') for image in _as_list(item.get('image'))
              if image.get('-url') and not str(image.get('-name', '')).startswith('icon')]
    quests = nodes(series)
    return bool(quests) and all(lookup_quest(q) for q in quests) and \
        all(_asset_exists(url) for url in _popup_files(series) + images)


PLAYABLE = [series_id for series_id, series in SERIES.items() if playable(series)]


def _completed():
    return {q["name"] for q in session['quests'] if q["complete"]}


def finished(series_id):
    return all(q in _completed() for q in nodes(SERIES[series_id]))


def current_quest(series_id):
    done = _completed()
    open_quests = [q for q in nodes(SERIES[series_id]) if q not in done]
    return open_quests[0] if open_quests else nodes(SERIES[series_id])[-1]


def water_spot(world, size):
    """An empty size x size spot on the water near the player's ships: the entry building can only stand on water
    and the save does not say which tiles are water, so stay close to water items and away from land ones."""
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
    best = None
    for x in range(int(world.get("sizeX", 200)) - size):
        for y in range(int(world.get("sizeY", 200)) - size):
            spot = _cells(x, y, size, size)
            if spot & taken or _cells(x - 3, y - 3, size + 6, size + 6) & land:
                continue
            near_water = len(_cells(x - 2, y - 2, size + 4, size + 4) & water)
            if near_water and (best is None or near_water > best[0]):
                best = (near_water, x, y)
    return (best[1], best[2]) if best else None


def _place_entry(world, series):
    item = entry_item(series)
    if any(o.get("itemName") == item['-name'] for o in world.get("objects", [])):
        return True
    spot = water_spot(world, max(int(item.get("sizeX", 4)), int(item.get("sizeY", 4))))
    if spot is None:
        print("No water spot for mega series", series['-id'])
        return False
    world["globalObjectId"] += 1
    world["objects"].append({"id": world["globalObjectId"], "itemName": item['-name'],
                             "position": "%d,%d,0" % spot, "referenceItem": None, "state": ENTRY_STATE})
    print("Mega series", series['-id'], "entry building placed at", spot)
    return True


def activate(series_id, user, new_quests, meta):
    series = SERIES[series_id]
    if not _place_entry(user["userInfo"]["world"], series):
        return False
    experiment = series['requiredExperiment']
    user.setdefault("experiments", {})[experiment['-name']] = int(experiment['-variants'].split(',')[0])
    first = nodes(series)[0]
    user["userInfo"]["player"]["megaseriesList"][series_id] = first
    if first not in [q['name'] for q in session['quests']]:
        new_quest_with_sequels(first, new_quests, meta, force=True)
    print("Mega series", series_id, "offered, first quest", first)
    return True


def update_megaseries(user, new_quests, meta):
    """Called on login: keep the current quest of each series up to date and offer the next playable series."""
    player = user["userInfo"]["player"]
    if not isinstance(player.get("megaseriesList"), dict):
        player["megaseriesList"] = {}
    if not isinstance(player.get("megaseriesFinished"), list):
        player["megaseriesFinished"] = []
    active = []
    for series_id in list(player["megaseriesList"]):
        if series_id not in SERIES:
            continue
        player["megaseriesList"][series_id] = current_quest(series_id)
        if finished(series_id):
            if series_id not in player["megaseriesFinished"]:
                player["megaseriesFinished"].append(series_id)
        else:
            active.append(series_id)
    for series_id in PLAYABLE:
        if len(active) >= MAX_ACTIVE:
            break
        if series_id in player["megaseriesList"] or not _level_ok(SERIES[series_id]):
            continue
        if activate(series_id, user, new_quests, meta):
            active.append(series_id)


def reset_response(params):
    """megaSeriesReset(series id): play the series again from its first quest."""
    series_id = params[0]
    response = {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0}, "data": []}
    if series_id not in SERIES:
        return response
    quests = nodes(SERIES[series_id])
    session['quests'][:] = [q for q in session['quests'] if q['name'] not in quests]
    new_quests, meta = [], {}
    new_quest_with_sequels(quests[0], new_quests, meta, force=True)
    session['quests'][:] = new_quests + session['quests']
    user = session['user_object']
    user["userInfo"]["player"]["megaseriesList"][series_id] = quests[0]
    finished_list = user["userInfo"]["player"].get("megaseriesFinished", [])
    if series_id in finished_list:
        finished_list.remove(series_id)
    item = entry_item(SERIES[series_id])
    for obj in user["userInfo"]["world"]["objects"]:
        if item and obj.get("itemName") == item['-name']:
            obj["state"] = ENTRY_STATE
    response["metadata"]["QuestComponent"] = new_quests
    return response
