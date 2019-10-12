import copy
import json
import os

import libscrc
from flask import session
from datetime import datetime
from save_engine import my_games_path

with open(os.path.join(my_games_path() ,"gamesettings-converted.json"), 'r') as f:
    game_settings = json.load(f)
    print("Gamesettings loaded: ",  len(game_settings['settings']), " setting sections loaded")

with open(os.path.join(my_games_path() ,"allies/initial-island.json"), 'r') as f:
    initial_island = json.load(f)
    print("Initial island template", len(initial_island["objects"]), "objects loaded", len(initial_island["roads"]),
          "roads loaded")
    # game_objects = [o for o in game_objects_2 if int(o["position"].split(",")[0]) > 62 and int(o["position"].split(",")[1]) > 58]

allies = {str(e["info"]["uid"] if e["info"] else e["friend"]["uid"]): e for e in
          [json.load(open(os.path.join(root, file_name), 'r')) for root, _, file_names in os.walk(os.path.join(my_games_path() ,"allies")) for
           file_name in
           file_names if 'island.json' in file_name and file_name != "initial-island.json"]}
print("Ally islands", len(allies.keys()), "allies loaded",
      sum([len(ally["objects"]) for ally in allies.values() if ally["objects"]]), "objects loaded",
      sum([len(ally["roads"]) for ally in allies.values() if ally["roads"]]), "roads loaded")


def lookup_item_by_name(item_name):
    try:
        [item] = [e for e in game_settings['settings']['items']['item'] if e['-name'] == item_name]
        return item
    except ValueError as e:
        print("ERROR: Could not look up item by name", item_name)
        raise e


def lookup_item_by_code(code):
    try:
        [item] = [e for e in game_settings['settings']['items']['item'] if e['-code'] == code]
        return item
    except ValueError as e:
        print("ERROR: Could not look up item by code", code)
        raise e


def lookup_reference_item(cur_object):
    return lookup_item_by_code(cur_object['referenceItem'].split(":")[0]) if cur_object and 'referenceItem' in cur_object and cur_object['referenceItem'] else None


def lookup_items_with_workers_yield():
    items = [e for e in game_settings['settings']['items']['item'] if 'yield' in e and '-workers' in e['yield']]
    return items


def lookup_yield():  #TODO buildstate
    yields = {e['-name']: int(e['yield']['-workers']) for e in lookup_items_with_workers_yield()}
    return sum([yields[e['itemName']] for e in session['user_object']["userInfo"]["world"]["objects"] if e['itemName'] in yields.keys()])


# def lookup_built_yield(placed_objects):
#     built_objects = [e for e in objects if
#                      int(e.get('state', 0)) >= (int(state_machine['-builtState']) if state_machine else 0)]
#
#     yields = {e['-name']: int(e['yield']['-workers']) for e in lookup_items_with_workers_yield()}
#     return sum([yields[e['itemName']] for e in session['user_object']["userInfo"]["world"]["objects"] if
#                 e['itemName'] in yields.keys()])

def lookup_state_machine(state_machine_name, custom_values, custom_reference_values=None):
    if custom_reference_values is None:
        custom_reference_values = []
    state_machine = copy.deepcopy(lookup_raw_state_machine(state_machine_name))
    replacements = {e['-name']: e['-value'] for e in custom_values}
    reference_replacements = {e['-name']: e['-value'] for e in simple_list(custom_reference_values)}
    print('replacements', repr(replacements))
    if reference_replacements:
        print('reference item replacements', repr(replacements))
        replacements = {**replacements, **reference_replacements}
        print('combined reference item replacements', repr(replacements))

    repl_dict(state_machine, replacements)
    return state_machine


def lookup_raw_state_machine(state_machine_name):
    try:
        [state_machine] = [e for e in game_settings['settings']['stateMachines']['stateMachine'] if e['-name'] == state_machine_name]
        return state_machine
    except ValueError as e:
        print("ERROR: Could not look up state machine by name", state_machine_name)
        raise e


def repl_dict(d, replacements):
    for k, v in d.items():
        if isinstance(v, dict):
            repl_dict(v, replacements)
        elif isinstance(v, list):
            for e in v:
                repl_dict(e, replacements)
        else:
            if "$" in v:
                # print('r1', v)
                for s, r in replacements.items():
                    d[k] = d[k].replace(s, r)
                # print('r2', d[k])
                if ":" in v:
                    d[k] = d[k].split(':', 1)[1 if "$" in d[k] else 0]
                    # print('r3', d[k])


def replenish_energy():
    player = session['user_object']["userInfo"]["player"]
    current_energy_max = max(player["energy"], player["energyMax"])  # overfill possible
    now = datetime.now().timestamp()
    energy_replenished = (now - player["lastEnergyCheck"]) // 300
    player["energy"] = min(player["energy"] + energy_replenished, current_energy_max)
    # print("Energy now:", now, "lastEnergyCheck", player["lastEnergyCheck"], "inc", (now - player["lastEnergyCheck"]), "till300", (now - player["lastEnergyCheck"]) % 300, "newec",  now - (now - player["lastEnergyCheck"]) % 300  )
    player["lastEnergyCheck"] = now - (now - player["lastEnergyCheck"] + 1) % 300
    if energy_replenished != 0:
        print("Energy replenished:", energy_replenished)


def simple_list(raw_list):
    return (raw_list if isinstance(raw_list, list) else [raw_list]) if raw_list != '' else []


def get_zid():
    return libscrc.iso(session.sid.encode()) // 2048
