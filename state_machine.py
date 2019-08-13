from quest_engine import  handle_world_state_change
from datetime import datetime
from flask import session
from game_settings import lookup_item_by_name, lookup_state_machine


def click_next_state(id, meta, step):
    cur_object = lookup_object(id)
    print("cur_object used:", repr(cur_object))

    game_item = lookup_item_by_name(cur_object['itemName'])
    print("item used:", repr(game_item))

    if 'stateMachineValues' in game_item:
        state_machine = lookup_state_machine(game_item['stateMachineValues']['-stateMachineName'], game_item['stateMachineValues']['define'])

        print("state_machine used:", repr(state_machine))
        state = lookup_state(state_machine, cur_object.get('state', 0))
        print("cur state:", repr(state))

        while '-autoNext' in state and state['-stateName'] != state['-autoNext']:   # '-clientDuration': '2.0s', '-duration': '0' respect duration for harvest?
            duration =  parse_duration(state.get('-duration', '0'))
            if cur_object.get('lastUpdated', 0) / 1000 +  duration <= datetime.now().timestamp():
                next_state_id = state['-autoNext']  # not all states have this!! end states? autostate after time?
                state = lookup_state(state_machine, next_state_id)
                cur_object['lastUpdated'] += duration * 1000
                cur_object['state'] = next_state_id
                print("pre auto_next_state:", repr(state), 'time', cur_object['lastUpdated'], "duration", duration)
                handle_world_state_change(meta, state, state_machine, game_item, step)

        if '-clickNext' in state:
            next_state_id = state['-clickNext']  # not all states have this!! end states? autostate after time?
            next_click_state = lookup_state(state_machine, next_state_id)
            print("next_click_state:", repr(next_click_state))
            handle_world_state_change(meta, next_click_state, state_machine, game_item, step)

            while '-autoNext' in next_click_state and next_state_id != next_click_state['-autoNext'] and next_click_state.get('-duration', '0') in ['0', '0s']:   #'-clientDuration': '2.0s', '-duration': '0' respect duration for harvest?
                next_state_id = next_click_state['-autoNext']  # not all states have this!! end states? autostate after time?
                next_click_state = lookup_state(state_machine, next_state_id)
                print("auto_next_state:", repr(next_click_state))
                handle_world_state_change(meta, next_click_state, state_machine, game_item, step)

            cur_object['state'] = next_state_id
            cur_object['lastUpdated'] = datetime.now().timestamp() * 1000
        else:
            print("state has no clicknext, click does nothing")
            cur_object['lastUpdated'] = datetime.now().timestamp() * 1000
    else:
        print("object has no statemachine, click does nothing")
        cur_object['lastUpdated'] = datetime.now().timestamp() * 1000
        handle_world_state_change(meta, {}, None, game_item, step)


def lookup_state(state_machine, i):
    [state_machine] = [e for e in state_machine['state'] if e['-stateName'] == str(i)]
    return state_machine

def lookup_object(id):
    [game_object] = [e for e in  session['user_object']["userInfo"]["world"]["objects"] if e['id'] == id]
    return game_object

def lookup_object(id):
    [game_object] = [e for e in  session['user_object']["userInfo"]["world"]["objects"] if e['id'] == id]
    return game_object


def parse_duration(duration):
    # ["ms", "m", "s", "h", "d"];
    if duration == 'rand:1d,4d':
        return 86400 # 1d
    elif "ms" in duration:
        return float(duration[:-2]) / 1000
    elif "s" in duration:
        return float(duration[:-1])
    elif "m" in duration:
        return float(duration[:-1]) * 60
    elif "h" in duration:
        return float(duration[:-1]) * 3600
    elif "d" in duration:
        return float(duration[:-1]) * 86400
    else:
        return float(duration)
