from quest_engine import handle_world_state_change, roll_reward_random_float
from datetime import datetime
from flask import session
from game_settings import game_settings, lookup_item_by_name, lookup_state_machine, lookup_reference_item, \
    lookup_item_by_code


# TODO add new reference item from clicknext step, use old one for first autostep, new one for 2nd autonext,
#  not needed: is handled by checkstates if new one is null then use old reference item in clicknext(harvesting step?)
# TODO checkState?
def click_next_state(id, meta, step, reference_item):
    cur_object = lookup_object(id)
    print("cur_object used:", repr(cur_object))

    game_item = lookup_item_by_name(cur_object['itemName'])
    print("item used:", repr(game_item))

    if 'stateMachineValues' in game_item:
        state_machine = lookup_state_machine(game_item['stateMachineValues']['-stateMachineName'],
                                             game_item['stateMachineValues']['define'],
                                             (lookup_reference_item(cur_object) or {}).get('referenceValues',{}).get('define'))

        print("state_machine used:", repr(state_machine))
        state = lookup_state(state_machine, cur_object.get('state', 0), cur_object)
        print("cur state:", repr(state))

        while '-autoNext' in state and state['-stateName'] != state['-autoNext']:   # '-clientDuration': '2.0s', '-duration': '0' respect duration for harvest?
            duration =  parse_duration(state.get('-duration', '0'))
            if cur_object.get('lastUpdated', 0) / 1000 +  duration <= datetime.now().timestamp():
                next_state_id = state['-autoNext']  # not all states have this!! end states? autostate after time?
                previous_state = state
                state = lookup_state(state_machine, next_state_id, cur_object)
                check_state(state_machine, state, cur_object)
                do_state_rewards(state, cur_object.get('referenceItem'))
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
            next_state_id = state['-clickNext']
            if reference_item != cur_object.get('referenceItem'):
                state_machine = lookup_state_machine(game_item['stateMachineValues']['-stateMachineName'],
                                                     game_item['stateMachineValues']['define'],
                                                     (lookup_item_by_code(reference_item.split(":")[0]) if reference_item else {})
                                                     .get('referenceValues', {}).get('define'))
            next_click_state = lookup_state(state_machine, next_state_id, cur_object)
            check_state(state_machine, next_click_state, cur_object)
            print("next_click_state:", repr(next_click_state))
            do_state_rewards(next_click_state, cur_object.get('referenceItem'))
            handle_world_state_change(meta, next_click_state, state_machine, game_item, step, state, reference_item,  cur_object.get('referenceItem'))

            while '-autoNext' in next_click_state and next_state_id != next_click_state['-autoNext'] and next_click_state.get('-duration', '0') in ['0', '0s']:   #'-clientDuration': '2.0s', '-duration': '0' respect duration for harvest?
                next_state_id = next_click_state['-autoNext']
                previous_state = next_click_state
                next_click_state = lookup_state(state_machine, next_state_id, cur_object)
                check_state(state_machine, next_click_state, cur_object)
                print("auto_next_state:", repr(next_click_state))
                do_state_rewards(next_click_state, reference_item)
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


def lookup_state(state_machine, i, cur_object):
    [state] = [e for e in state_machine['state'] if e['-stateName'] == str(i)]
    if 'check_state' in cur_object and str(i) in cur_object['check_state']:
        state = cur_object['check_state'][str(i)]
        print("Overridden state used", str(i))
    return state


def lookup_object(id):
    [game_object] = [e for e in  session['user_object']["userInfo"]["world"]["objects"] if e['id'] == id]
    return game_object


def lookup_object(id):
    [game_object] = [e for e in  session['user_object']["userInfo"]["world"]["objects"] if e['id'] == id]
    return game_object


#use state from current statemachine as replacement state for that state (with values and 2 random numbers
def check_state(state_machine, state, cur_object):
    if '-checkState' in state:
        check_state = lookup_state(state_machine, state["-checkState"], cur_object) # possibly overriding using already overridden state
        if 'check_state' not in cur_object:
            cur_object['check_state'] = {}
        cur_object['check_state'][state["-checkState"]] = check_state
        print("Future check state overridden", state["-checkState"])
        if "-xp" in check_state:
            roll_reward_random_float() # prison xp
        if "-dooberType" in check_state:
            roll_reward_random_float() # for the platinum pipes


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


def do_state_rewards(state, reference_item):
    player = session['user_object']["userInfo"]["player"]
    player['xp'] += int(state.get('-xp', 0))
    player['energy'] += int(state.get('-energy', 0))
    player['cash'] += int(state.get('-cash', 0))
    player['socialXpGood'] += int(state.get('-socialXpGood', 0))
    player['socialXpBad'] += int(state.get('-socialXpBad', 0))

    world = session['user_object']["userInfo"]["world"]
    resources = world['resources']
    resources['coins'] += int(state.get('-coins', 0))
    resources['energy'] += int(state.get('-energy', 0)) #which one?
    resources['oil'] += int(state.get('-oil', '0').split('|')[0])
    resources['wood'] += int(state.get('-wood', '0').split('|')[0])

    resource_order = world['resourceOrder']
    resources[resource_order[0]] += int(state.get('-rare', '0').split('|')[0])
    resources[resource_order[0]] += int(state.get('-nrare0', '0').split('|')[0])
    resources[resource_order[1]] += int(state.get('-nrare1', '0').split('|')[0])
    resources[resource_order[2]] += int(state.get('-nrare2', '0').split('|')[0])
    resources[resource_order[3]] += int(state.get('-nrare3', '0').split('|')[0])
    resources[resource_order[4]] += int(state.get('-nrare4', '0').split('|')[0])

    item_inventory = player["inventory"]["items"]
    if int(state.get('-buildable', '0')):
        if reference_item:
            item_inventory[reference_item] = item_inventory.get(reference_item, 0) + 1
            print("Adding", reference_item, "to inventory")
        else:
            print("ERROR: Buildable present but no reference item")

    level_cash = 0
    levels_count = 0
    levels = [level for level in game_settings['settings']['levels']['level'] if
              int(level["-num"]) > player['level'] and int(level["-requiredXP"]) <= player['xp']]
    for level in levels:
        [energy_cap] = [e['-cap'] for e in game_settings['settings']['energycaps']['energycap'] if e['-level'] == level["-num"]]
        print("Level increased to", level["-num"], "New energy:", energy_cap)
        player['level'] = int(level["-num"])
        player['energy'] = int(energy_cap)
        player['energyMax'] = int(energy_cap)
        levels_count += 1
        if "reward" in level and level["reward"]["-type"] == "cash":
            player['cash'] += int(level["reward"]["-count"])
            level_cash += int(level["reward"]["-count"])

    log_rewards = ", ".join([label + " " + ("+" if int(increment) > 0 else "") + str(increment) + " (" + str(total) + ")" for
                     (label, increment, total)
                     in
                     [("xp:", state.get('-xp', '0'), player['xp']),
                      ("energy:", state.get('-energy', '0'), player['energy']),
                      ("coins:", state.get('-coins', '0'), resources['coins']),
                      ("oil:", state.get('-oil', '0'), resources['oil']),
                      ("wood:", state.get('-wood', '0'), resources['wood']),
                      ("cash:", state.get('-cash', '0'), player['cash']),
                      ("cash (level):", str(level_cash), player['cash']),
                      ("levels:", str(levels_count), player['level']),
                      ("socialXpGood:", state.get('-socialXpGood', '0'), player['socialXpGood']),
                      ("socialXpBad:", state.get('-socialXpBad', '0'), player['socialXpBad']),
                      ("buildable:", state.get('-buildable', '0'), sum(item_inventory.values())),
                      (resource_order[0] + ":", state.get('-rare', '0'), resources[resource_order[0]]),
                      (resource_order[0] + ":", state.get('-nrare0', '0'), resources[resource_order[0]]),
                      (resource_order[1] + ":", state.get('-nrare1', '0'), resources[resource_order[1]]),
                      (resource_order[2] + ":", state.get('-nrare2', '0'), resources[resource_order[2]]),
                      (resource_order[3] + ":", state.get('-nrare3', '0'), resources[resource_order[3]]),
                      (resource_order[4] + ":", state.get('-nrare4', '0'), resources[resource_order[4]])
                      ] if int(increment.split('|')[0]) != 0])
    if log_rewards:
        print("State rewards:", log_rewards)
        
        
def do_costs(costs):
    player = session['user_object']["userInfo"]["player"]
    player['xp'] -= int(costs.get('-xp', 0))
    player['energy'] -= int(costs.get('-energy', 0))
    player['cash'] -= int(costs.get('-cash', 0))
    player['socialXpGood'] -= int(costs.get('-socialXpGood', 0))
    player['socialXpBad'] -= int(costs.get('-socialXpBad', 0))

    world = session['user_object']["userInfo"]["world"]
    resources = world['resources']
    resources['coins'] -= int(costs.get('-coins', 0))
    resources['energy'] -= int(costs.get('-energy', 0)) #which one?
    resources['oil'] -= int(costs.get('-oil', '0').split('|')[0])
    resources['wood'] -= int(costs.get('-wood', '0').split('|')[0])

    resource_order = world['resourceOrder']
    resources[resource_order[0]] -= int(costs.get('-rare', '0').split('|')[0])
    resources[resource_order[0]] -= int(costs.get('-nrare0', '0').split('|')[0])
    resources[resource_order[1]] -= int(costs.get('-nrare1', '0').split('|')[0])
    resources[resource_order[2]] -= int(costs.get('-nrare2', '0').split('|')[0])
    resources[resource_order[3]] -= int(costs.get('-nrare3', '0').split('|')[0])
    resources[resource_order[4]] -= int(costs.get('-nrare4', '0').split('|')[0])

    log_costs = ", ".join([label + " " + ("+" if int(decrement) < 0 else "") + str(-int(decrement)) + " (" + str(total) + ")" for
                     (label, decrement, total)
                     in
                     [("xp:", costs.get('-xp', '0'), player['xp']),
                      ("energy:", costs.get('-energy', '0'), player['energy']),
                      ("coins:", costs.get('-coins', '0'), resources['coins']),
                      ("oil:", costs.get('-oil', '0'), resources['oil']),
                      ("wood:", costs.get('-wood', '0'), resources['wood']),
                      ("cash:", costs.get('-cash', '0'), player['cash']),
                      ("socialXpGood:", costs.get('-socialXpGood', '0'), player['socialXpGood']),
                      ("socialXpBad:", costs.get('-socialXpBad', '0'), player['socialXpBad']),
                      (resource_order[0] + ":", costs.get('-rare', '0'), resources[resource_order[0]]),
                      (resource_order[0] + ":", costs.get('-nrare0', '0'), resources[resource_order[0]]),
                      (resource_order[1] + ":", costs.get('-nrare1', '0'), resources[resource_order[1]]),
                      (resource_order[2] + ":", costs.get('-nrare2', '0'), resources[resource_order[2]]),
                      (resource_order[3] + ":", costs.get('-nrare3', '0'), resources[resource_order[3]]),
                      (resource_order[4] + ":", costs.get('-nrare4', '0'), resources[resource_order[4]])
                      ] if int(decrement.split('|')[0]) != 0])
    if log_costs:
        print("Costs:", log_costs)
