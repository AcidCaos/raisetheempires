from quest_engine import  handle_world_state_change
from datetime import datetime
from flask import session
from game_settings import game_settings, lookup_item_by_name, lookup_state_machine


def click_next_state(id, meta, step, reference_item):
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
                previous_state = state
                state = lookup_state(state_machine, next_state_id)
                do_rewards(state)
                if 'lastUpdated' not in cur_object:
                    cur_object['lastUpdated'] = 0  #init?
                cur_object['lastUpdated'] += duration * 1000
                cur_object['state'] = next_state_id
                print("pre auto_next_state:", repr(state), 'time', cur_object['lastUpdated'], "duration", duration)
                handle_world_state_change(meta, state, state_machine, game_item, step, previous_state, cur_object.get('referenceItem'), cur_object.get('referenceItem'))
            else:
                print("state has autoNext, but not enough time was passed")
                break

        if '-clickNext' in state:
            next_state_id = state['-clickNext']  # not all states have this!! end states? autostate after time?
            next_click_state = lookup_state(state_machine, next_state_id)
            print("next_click_state:", repr(next_click_state))
            do_rewards(next_click_state)
            handle_world_state_change(meta, next_click_state, state_machine, game_item, step, state, reference_item,  cur_object.get('referenceItem'))

            while '-autoNext' in next_click_state and next_state_id != next_click_state['-autoNext'] and next_click_state.get('-duration', '0') in ['0', '0s']:   #'-clientDuration': '2.0s', '-duration': '0' respect duration for harvest?
                next_state_id = next_click_state['-autoNext']  # not all states have this!! end states? autostate after time?
                previous_state = next_click_state
                next_click_state = lookup_state(state_machine, next_state_id)
                print("auto_next_state:", repr(next_click_state))
                do_rewards(next_click_state)
                handle_world_state_change(meta, next_click_state, state_machine, game_item, step, previous_state, reference_item, reference_item)

            cur_object['state'] = next_state_id
            cur_object['lastUpdated'] = datetime.now().timestamp() * 1000
        else:
            print("state has no clicknext, click does nothing")
            cur_object['lastUpdated'] = datetime.now().timestamp() * 1000
    else:
        print("object has no statemachine, click does nothing")
        cur_object['lastUpdated'] = datetime.now().timestamp() * 1000
        handle_world_state_change(meta, {}, None, game_item, step, {}, reference_item, reference_item)


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

def do_rewards(state):
    player = session['user_object']["userInfo"]["player"]
    player['xp'] += int(state.get('-xp', 0))
    player['energy'] += int(state.get('-energy', 0))
    player['cash'] += int(state.get('-cash', 0))
    player['socialXpGood'] += int(state.get('-socialXpGood', 0))
    player['socialXpBad'] += int(state.get('-socialXpBad', 0))

    world = session['user_object']["userInfo"]["world"]
    resources = world['resources']
    resources['coins'] += int(state.get('-coins', 0))
    resources['energy'] += int(state.get('-energy', 0)) #correct one?  #repleenish!!
    resources['oil'] += int(state.get('-oil', 0))
    resources['wood'] += int(state.get('-wood', 0))

    resourceOrder = world['resourceOrder']
    resources[resourceOrder[0]] += int(state.get('-rare', 0))
    resources[resourceOrder[0]] += int(state.get('-nrare0', 0))
    resources[resourceOrder[1]] += int(state.get('-nrare1', 0))
    resources[resourceOrder[2]] += int(state.get('-nrare2', 0))
    resources[resourceOrder[3]] += int(state.get('-nrare3', 0))
    resources[resourceOrder[4]] += int(state.get('-nrare4', 0))

    level_cash = 0
    levels_count = 0
    levels = [level for level in game_settings['settings']['levels']['level'] if
              int(level["-num"]) > player['level'] and int(level["-requiredXP"]) <= player['xp']]
    for level in levels:
        print("Level increased to", level["-num"])
        player['level'] = int(level["-num"])
        levels_count += 1
        if "reward" in level and level["reward"]["-type"] == "cash":
            player['cash'] += level["reward"]["-count"]
            level_cash += level["reward"]["-count"]

    log_rewards = ", ".join([label + " " + ("+" if int(increment) > 0 else "") + str(increment) + " (" + str(total) + ")" for
                     (label, increment, total)
                     in
                     [("xp:", state.get('-xp', 0), player['xp']),
                      ("energy:", state.get('-energy', 0), resources['energy']),
                      ("coins:", state.get('-coins', 0), resources['coins']),
                      ("oil:", state.get('-oil', 0), resources['oil']),
                      ("wood:", state.get('-wood', 0), resources['wood']),
                      ("cash:", state.get('-cash', 0), player['cash']),
                      ("cash (level):", level_cash, player['cash']),
                      ("levels:", levels_count, player['level']),
                      ("socialXpGood:", state.get('-socialXpGood', 0), player['socialXpGood']),
                      ("socialXpBad:", state.get('-socialXpBad', 0), player['socialXpBad']),
                      (resourceOrder[0] + ":", state.get('-rare', 0), resources[resourceOrder[0]]),
                      (resourceOrder[0] + ":", state.get('-nrare0', 0), resources[resourceOrder[0]]),
                      (resourceOrder[1] + ":", state.get('-nrare1', 0), resources[resourceOrder[1]]),
                      (resourceOrder[2] + ":", state.get('-nrare2', 0), resources[resourceOrder[2]]),
                      (resourceOrder[3] + ":", state.get('-nrare3', 0), resources[resourceOrder[3]]),
                      (resourceOrder[4] + ":", state.get('-nrare4', 0), resources[resourceOrder[4]])
                      ] if int(increment) != 0])
    if log_rewards:
        print("State rewards:", log_rewards)
