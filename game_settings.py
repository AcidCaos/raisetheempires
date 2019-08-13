import copy
import json


with open("gamesettings-converted.json", 'r') as f:
    game_settings = json.load(f)
    print("Gamesettings loaded: ",  len(game_settings['settings']), " setting sections loaded")


def lookup_item_by_name(item_name):
    [item] = [e for e in game_settings['settings']['items']['item'] if e['-name'] == item_name]
    return item


def lookup_item_by_code(code):
    [item] = [e for e in game_settings['settings']['items']['item'] if e['-code'] == code]
    return item


def lookup_state_machine(state_machine_name, custom_values):
    state_machine = copy.deepcopy(lookup_raw_state_machine(state_machine_name))
    replacements = {e['-name']: e['-value'] for e in custom_values}
    print('replacements', repr(replacements))
    repl_dict(state_machine, replacements)
    return state_machine


def lookup_raw_state_machine(state_machine_name):
    [state_machine] = [e for e in game_settings['settings']['stateMachines']['stateMachine'] if e['-name'] == state_machine_name]
    return state_machine


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
