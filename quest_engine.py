from quest_settings import quest_settings
from game_settings import game_settings, lookup_item_by_code, lookup_state_machine, replenish_energy, lookup_yield, \
    allies
from save_engine import lookup_objects_by_item_name, create_backup
from flask import session
from functools import reduce
import math


def merge_quest_progress(qc, output_list, label):
    if qc:
        print("new q before merge " + repr(qc))
        print(label + " list before merge " + repr (output_list))
        output_list[:] = qc + [e for e in output_list if e['name'] not in [q['name'] for q in qc]]
        print(label + " list after merge " + repr (output_list))


def lookup_quest(name):
    quests = [r for r in quest_settings['quests']['quest'] if r['_name'] == name]
    return quests[0] if len(quests) == 1 else None


def new_quest(quest):
    # progress = [0 for e in quest['tasks']]
    progress, completes = map(list, zip(*[prepopulate_task(e) for e in get_tasks(quest)]))
    return {"name": quest['_name'], "complete": all(completes), "expired": False, "progress": progress, "completedTasks": reduce((lambda x, y: x << 1 | y), [False] + completes[::-1])}


def prepopulate_task(task):
    if task["_action"] == 'countPlaced':
        item = lookup_item_by_code(task["_item"])
        if 'stateMachineValues' in item:
            state_machine = lookup_state_machine(item['stateMachineValues']['-stateMachineName'],
                                                 item['stateMachineValues'].get('define', []))
        else:
            state_machine = None
        objects = lookup_objects_by_item_name(item['-name'])
        built_objects = [e for e in objects if
                 int(e.get('state', 0)) >= (int(state_machine['-builtState']) if state_machine else 0)]
        number_built = len(built_objects)
        return min(number_built, int(task["_total"])), number_built >= int(task["_total"])
    if task["_action"] == 'countPlacements':
        item = lookup_item_by_code(task.get("_item", task.get('_code')))
        objects = lookup_objects_by_item_name(item['-name'])
        number_placed = len(objects)
        return min(number_placed, int(task["_total"])), number_placed >= int(task["_total"])
    elif task["_action"] == 'inventoryCount':
        item_inventory = session['user_object']["userInfo"]["player"]["inventory"]["items"]
        return min(item_inventory.get(task["_item"], 0), int(task["_total"])), item_inventory.get(task["_item"], 0) >= int(task["_total"])
    elif task["_action"] == 'population':
        return min(session['population'], int(task["_total"])), session['population'] >= int(task["_total"])
    elif task["_action"] == 'neighborsAdded':
        neighbor_count = len([ally for ally in allies.values() if ally.get("friend") and ally.get("neighbor")])
        return min(neighbor_count, int(task["_total"])), neighbor_count >= int(task["_total"])
    elif task["_action"] == 'countUpgrades':
        research = session['user_object']["userInfo"]["world"]["research"]
        total = 0
        unit = task["unit"]
        for k, v in research.items():
            if "_item" in unit:
                if k == unit["_item"]:
                    total += len(v)
            elif "_unitClass" in unit:
                item = lookup_item_by_code(k)
                if item["-unitClass"] == unit["_unitClass"]:
                    total += len(v)
            elif "_subtype" in unit:
                item = lookup_item_by_code(k)
                if item["-subtype"] == unit["_subtype"]:
                    total += len(v)

        return min(total, int(task["_total"])), total >= int(task["_total"])
    elif task["_action"] == 'autoComplete':
        return 1, True
    else:
        return 0, False


# "autoComplete","battleDamage","battleKill","build","buyExpansion","challengeCreate","clear","countPlaced","expandIsland","fight","finishBuilding","fullscreen","genericString","harvest","inventoryAdded","islandWin","marketAdd","marketBuy","move","neighborsAdded","openDialog","ownObjects","ownResource","place","population","pillage","pvpCombat","resourceAdded","seenFlag","select","socialXPAdded","startImmunity","state","tending","tendingRewardDropped","unlockTutorial","useConsumable","visit","zoom"
def handle_world_state_change(meta, *state_args):
    handle_quest_progress(meta, world_state_change(*state_args))


def world_state_change(*state_args):
    return lambda *args: \
        any([progress_finish_building_count_placed(*state_args)(*args),
             progress_auto_complete()(*args),
             progress_place(*state_args)(*args),
             progress_build(*state_args)(*args),
             progress_harvest(*state_args)(*args),
             progress_state(*state_args)(*args),
             progress_inventory_count()(*args)
             ])


def progress_finish_building_count_placed(state, state_machine, game_item, step, previous_state, *state_args):
    return lambda task, progress, i, *args: \
        task["_action"] in ["finishBuilding", "countPlaced"] and task["_item"] == game_item[
            '-code'] and progress < int(task["_total"]) and state['-stateName'] == state_machine['-builtState'] and \
        int(previous_state['-stateName']) < int(state['-stateName'])


def progress_inventory_count():
    return lambda task, progress, i, extra, *args: \
        task["_action"] == "inventoryCount" and  progress_inventory(task["_item"], task["_total"], extra, progress) \
        and progress < int(task["_total"])


def progress_inventory(item, maximum_total, extra, progress):
    item_inventory = session['user_object']["userInfo"]["player"]["inventory"]["items"]
    total = min(item_inventory.get(item, 0), int(maximum_total))
    extra["total"] = total
    return total != progress


def progress_neighbor_count():
    return lambda task, progress, i, extra, *args: \
        task["_action"] == "neighborsAdded" and  progress_neighbors(task["_total"], extra, progress) \
        and progress < int(task["_total"])


def progress_neighbors(maximum_total, extra, progress):
    neighbor_count = len([ally for ally in allies.values() if ally.get("friend") and ally.get("neighbor")])
    total = min(neighbor_count, int(maximum_total))
    extra["total"] = total
    return total != progress


def progress_upgrades_count():
    return lambda task, progress, i, extra, *args: \
        task["_action"] == "countUpgrades" and progress_upgrades(task["unit"], task["_total"], extra, progress) \
        and progress < int(task["_total"])


def progress_upgrades(unit, maximum_total, extra, progress):
    research = session['user_object']["userInfo"]["world"]["research"]
    total = 0
    for k, v in research.items():
        if "_item" in unit:
            if k == unit["_item"]:
                total += len(v)
        elif "_unitClass" in unit:
            item = lookup_item_by_code(k)
            if item["-unitClass"] == unit["_unitClass"]:
                total += len(v)
        elif "_subtype" in unit:
            item = lookup_item_by_code(k)
            if item["-subtype"] == unit["_subtype"]:
                total += len(v)

    extra["total"] = min(total, int(maximum_total))
    return total != progress


def progress_battle_damage_count(action, damage, ally_unit, baddy_unit):
    return lambda task, progress, i, extra, *args: \
        task["_action"] == action and \
    all_lambda(
        progress_parameter_implies("_subtype", ally_unit.get("-subtype", "")),
        progress_parameter_implies("_unitClass", ally_unit.get("-unitClass", "")),
        progress_parameter_implies("_item", ally_unit.get("-code", "")),
        progress_nested_parameter_implies("targetInfo", "_unitClass", baddy_unit.get("-unitClass", "")),
        progress_nested_parameter_implies_contains("targetInfo", "_unitType",
                                                   baddy_unit.get("unit", {}).get("-type", ""))
    )(task, progress, i, extra, *args) \
        and progress_battle_damage(damage, task["_total"], extra, progress) \
        and progress < int(task["_total"])


def progress_battle_damage(damage, maximum_total, extra,  progress):
    extra["total"] = min(damage, int(maximum_total))
    return damage != progress


def progress_resource_added_count(rewards, prefix):
    return lambda task, progress, i, extra, *args: \
        task["_action"] == "resourceAdded" and rewards.get(prefix + task["_type"]) \
        and progress_yield_amount(rewards[prefix + task["_type"]].split('|')[0], task["_total"], extra, progress)


def progress_market_added_count(amount):
    return lambda task, progress, i, extra, *args: \
        task["_action"] == "marketAdd" and \
        progress_parameter_implies("_item", "rare") and \
        progress_total_amount(amount,task["_total"], extra, progress)


def progress_total_amount(amount, maximum_total, extra, progress):
    extra["total"] = min(int(amount), int(maximum_total))
    return amount != progress


def progress_yield_amount(amount, maximum_total, extra, progress):
    extra["yield"] = min(int(amount), int(maximum_total))
    return amount != progress


        #cancels?
def progress_build(state, state_machine, game_item, step, previous_state, reference_item, previous_reference_item, *state_args):
    return lambda task, progress, i, *args: \
        task["_action"] == "build" and reference_item is not None and (
                reference_item.split(":")[0] in task.get("_item", "").split(',') or
                progress_parameter_equals("_resourceType",
                                          lookup_item_by_code(reference_item.split(":")[0]).get("-resourceType", ""))(
                    task, progress, i, *args)
        ) \
        and previous_reference_item == None


def progress_harvest(state, state_machine, game_item, step, previous_state, reference_item, previous_reference_item, *state_args):
    return lambda task, progress, i, *args: \
        task["_action"] == "harvest" and previous_reference_item is not None and (
                previous_reference_item.split(":")[0] in  task.get("_item", "").split(',') or
                   progress_parameter_equals("_subtype", lookup_item_by_code(previous_reference_item.split(":")[0]).get("-subtype",""))(task, progress, i, *args)
                   or all_lambda(progress_parameter_equals("_isUpgrade", "true"),
                                 lambda *args: lookup_item_by_code(previous_reference_item.split(":")[0]).get("-type","upgrade"),
                                 progress_nested_parameter_implies("unit", "_subtype", lookup_item_by_code(previous_reference_item.split(":")[1]).get("-subtype","") if len(previous_reference_item.split(":")) > 1 else "")
                                 )(task, progress, i, *args)
                        ) \
        and reference_item == None


def progress_auto_complete():
    return lambda task, *args: task["_action"] in ["autoComplete", "population"]


def progress_place(state, state_machine, game_item, step, *state_args):
    return lambda task, progress, i, *args: \
        task["_action"] in ["place", "countPlacements"] and task.get("_item", task.get('_code')) == game_item['-code'] and progress < int(task["_total"]) and step == "place"


def progress_state(state, state_machine, game_item, step, *state_args):
    return lambda task, progress, i, *args: \
        task["_action"] in ["state", "countState"] and '-stateName' in state and state['-stateName'] in task["_state"].split(',')  and ("_item" not in task or task["_item"] == game_item['-code'])\
        and ("_subtype" not in task or task["_subtype"] == game_item['-subtype']) and progress < int(task["_total"])


# def all_lambda(lambdas, *initializer):
#     return lambda *args: all([l(*initializer)(*args) for l in lambdas])


def all_lambda(*lambdas):
    return lambda *args: all([l(*args) for l in lambdas])


def progress_action(action):
    return lambda task, *args: task["_action"] == action


def progress_parameter_equals(key, value):
    return lambda task, *args: task.get(key, "_NO_MATCH_") == value


def progress_parameter_implies(key, value):
    return lambda task, *args: task.get(key) == None or task.get(key, "_NO_MATCH_") == value


def progress_nested_parameter_implies(key, key2, value):
    return lambda task, *args: task.get(key, {}).get(key2) == None or task.get(key, {}).get(key2, "_NO_MATCH_") == value


def progress_nested_parameter_implies_contains(key, key2, value):
    return lambda task, *args: task.get(key, {}).get(key2) == None or any(i in task.get(key, {}).get(key2, "_NO_MATCH_").split(",") for i in value.split(","))


# deprogress functions?
def handle_quest_progress(meta, progress_function):
    replenish_energy()
    incomplete_quests = [e for e in session['quests'] if e["complete"] == False]
    for session_quest in incomplete_quests:
        new_quests = []
        report_quest = False
        tasks = get_tasks(lookup_quest(session_quest['name']))
        for task, progress, i in zip(tasks, session_quest['progress'], range(len(session_quest['progress']))):
            extra = {"yield": 1}
            if progress_function(task, progress, i, extra):  #countPlaced tasks should be prepopulated with already placed items, however removed ones? precomplete autoComplete?
                    print("Task", repr(task), "progress", repr(progress), "i", i)
                    report_quest = True
                    if task['_action'] == 'population':
                        session_quest['progress'][i] = min(lookup_yield(), int(task["_total"]))  # session['population']
                    else:
                        session_quest['progress'][i] = extra.get("total", session_quest['progress'][i] + extra["yield"])
                    print("Task progress", task["_action"])
                    if session_quest['progress'][i] >= int(task["_total"]):
                        session_quest["completedTasks"] = session_quest["completedTasks"] | 1 << i
                        print("Task complete", task["_action"])

        if report_quest:
            print("completedTasks", session_quest["completedTasks"], "len(tasks)", len(tasks), "calc", 2 ** len(tasks) - 1)
        if session_quest["completedTasks"] >= 2 ** len(tasks) - 1:
            session_quest["complete"] = True
            print("Quest complete", session_quest['name'])
            do_quest_rewards(lookup_quest(session_quest['name']), meta)
            activate_sequels(session_quest, new_quests, meta)
        if report_quest:
            if "QuestComponent" not in meta:
                meta['QuestComponent'] = []
            merge_quest_progress([session_quest] + new_quests, meta['QuestComponent'], "output quest")
            merge_quest_progress(new_quests, session['quests'], "session quest")
            #meta['QuestComponent'].append(session_quest) ### merge if already in it?
                    # progress = [0 for e in quest['tasks']]


def get_tasks(quest):
    raw_tasks = quest['tasks']['task']
    tasks = raw_tasks if isinstance(raw_tasks, list) else [raw_tasks]
    return tasks

def simple_list(raw_list):
    return (raw_list if isinstance(raw_list, list) else [raw_list]) if raw_list != '' else []

def activate_sequels(session_quest, new_quests, meta):
    raw_sequels = lookup_quest(session_quest['name'])['sequels']
    sequels = (raw_sequels["sequel"] if isinstance(raw_sequels["sequel"], list) else [
        raw_sequels["sequel"]]) if raw_sequels != "" and "sequel" in raw_sequels else []
    for sequel in sequels:
        new_quest_with_sequels(sequel["_name"], new_quests, meta)


def new_quest_with_sequels(name, new_quests, meta):
    if name in [e['name'] for e in session['quests']]:
        print("sequel", name, "already in session quests")
    elif new_quests is not None and name in [e['name'] for e in new_quests]:
        print("sequel", name, "already in new quests")
    else:
        print("activating sequel", name)
        q = lookup_quest(name)
        new_sequel_quest = new_quest(q)
        new_quests.append(new_sequel_quest)
        if new_sequel_quest["complete"]:
            print("Sequel quest precompleted", name)
            do_quest_rewards(q, meta)
            activate_sequels(new_sequel_quest, new_quests, meta)



# def autoclick_next_state(state_machine, next_click_state):
#     while '-autoNext' in next_click_state and next_click_state['-stateName'] != next_click_state[
#         '-autoNext']:  # '-clientDuration': '2.0s', '-duration': '0' respect duration for harvest?
#         next_state_id = next_click_state['-autoNext']  # not all states have this!! end states? autostate after time?
#         next_click_state = lookup_state(state_machine, next_state_id)
#         print("auto_next_state:", repr(next_click_state))


def do_quest_rewards(quest, meta):
    # TODO: rewardModifier
    raw_rewards = quest['reward']
    do_rewards("Quest", raw_rewards, meta)


def do_rewards(label, raw_rewards, meta):
    rewards = simple_list(raw_rewards)
    inc = {r.get("_type", r.get("-type")): int(r.get('_count', r.get('-count', 1))) for r in rewards if r.get("_type") != "item" and r.get("-type") != "item"}
    items = {r.get("_item", r.get("-item")): int(r.get('_count', r.get('-count', 1))) for r in rewards if r.get("_type") == "item" or r.get("-type") == "item"}

    player = session['user_object']["userInfo"]["player"]
    player['energy'] += int(inc.get('energy', 0))
    player['xp'] += int(inc.get('xp', 0))


    player['cash'] += int(inc.get('cash', 0))
    player['socialXpGood'] += int(inc.get('socialXpGood', 0))
    player['socialXpBad'] += int(inc.get('socialXpBad', 0))

    world = session['user_object']["userInfo"]["world"]
    resources = world['resources']
    resources['coins'] += int(inc.get('coins', 0))
    resources['energy'] += int(inc.get('energy', 0)) #which one?  #repleenish!!
    resources['oil'] += int(inc.get('oil', 0))
    resources['wood'] += int(inc.get('wood', 0))

    resource_order = world['resourceOrder']
    resources[resource_order[0]] += int(inc.get('rare', 0))
    resources[resource_order[0]] += int(inc.get('nrare0', 0))
    resources[resource_order[1]] += int(inc.get('nrare1', 0))
    resources[resource_order[2]] += int(inc.get('nrare2', 0))
    resources[resource_order[3]] += int(inc.get('nrare3', 0))
    resources[resource_order[4]] += int(inc.get('nrare4', 0))

    level_cash = 0
    levels_count = 0
    levels = [level for level in game_settings['settings']['levels']['level'] if int(level["-num"]) > player['level'] and int(level["-requiredXP"]) <= player['xp']    ]
    for level in levels:
        [energy_cap] = [e['-cap'] for e in game_settings['settings']['energycaps']['energycap'] if e['-level'] == level["-num"]]
        print("Level increased to", level["-num"], "New energy:", energy_cap)
        player['level'] = int(level["-num"])
        player['energy'] = int(energy_cap)
        resources['energy'] = int(energy_cap)
        player['energyMax'] = int(energy_cap)
        levels_count += 1
        if "reward" in level and level["reward"]["-type"] == "cash":
            player['cash'] += int(level["reward"]["-count"])
            level_cash += int(level["reward"]["-count"])
        create_backup("Level " + level["-num"])

    if inc:
        print(label, "rewards:", ", ".join(
            [label + " " + ("+" if int(increment) > 0 else "") + str(increment) + " (" + str(total) + ")" for
             (label, increment, total)
             in
             [("xp:", inc.get('xp', 0), player['xp']),
              ("energy:", inc.get('energy', 0), player['energy']),
              ("coins:", inc.get('coins', 0), resources['coins']),
              ("oil:", inc.get('oil', 0), resources['oil']),
              ("wood:", inc.get('wood', 0), resources['wood']),
              ("cash:", inc.get('cash', 0), player['cash']),
              ("cash (level):", level_cash, player['cash']),
              ("levels:", levels_count, player['level']),
              ("socialXpGood:", inc.get('socialXpGood', 0), player['socialXpGood']),
              ("socialXpBad:", inc.get('socialXpBad', 0), player['socialXpBad']),
              (resource_order[0] + ":", inc.get('rare', 0), resources[resource_order[0]]),
              (resource_order[0] + ":", inc.get('nrare0', 0), resources[resource_order[0]]),
              (resource_order[1] + ":", inc.get('nrare1', 0), resources[resource_order[1]]),
              (resource_order[2] + ":", inc.get('nrare2', 0), resources[resource_order[2]]),
              (resource_order[3] + ":", inc.get('nrare3', 0), resources[resource_order[3]]),
              (resource_order[4] + ":", inc.get('nrare4', 0), resources[resource_order[4]])
              ] if int(increment) != 0]))

    if items:
        item_inventory = session['user_object']["userInfo"]["player"]["inventory"]["items"]
        for k,v in items.items():
            item_inventory[k] = int(v)
        print(label, "item rewards:", ", ".join([ k + ": " + str(v) for k,v in items.items()]))
    handle_quest_progress(meta, progress_resource_added_count(inc, ""))

        # TODO store them & consumption ///s6 is code of flag

def roll_random():
    world = session['user_object']["userInfo"]["world"]
    world["randSeedZ"] = 36969 * (world["randSeedZ"] & 65535)  + (world["randSeedZ"] >> 16 & 65535) & 4294967295;
    world["randSeedW"] = 18000 * (world["randSeedW"] & 65535)  + (world["randSeedW"] >> 16 & 65535) & 4294967295;
    return (world["randSeedZ"] << 16) +  world["randSeedW"] & 4294967295


def roll_random_float():
    number = roll_random() / (2 ** 32 - 1)
    return math.floor(number * 10 ** 3) / 10 ** 3


def roll_random_between(a, b):
    return roll_random_float() * (b - a) + a


def get_seed_w():
    return session['user_object']["userInfo"]["world"]["randSeedW"]


def get_seed_z():
    return session['user_object']["userInfo"]["world"]["randSeedZ"]



def roll_reward_random():
    world = session['user_object']["userInfo"]["world"]
    world["rewardRandSeedZ"] = 36969 * (world["rewardRandSeedZ"] & 65535)  + (world["rewardRandSeedZ"] >> 16 & 65535) & 4294967295;
    world["rewardRandSeedW"] = 18000 * (world["rewardRandSeedW"] & 65535)  + (world["rewardRandSeedW"] >> 16 & 65535) & 4294967295;
    return (world["rewardRandSeedZ"] << 16) +  world["rewardRandSeedW"] & 4294967295


def roll_reward_random_float():
    number = roll_reward_random() / (2 ** 32 - 1)
    return math.floor(number * 10 ** 3) / 10 ** 3


def roll_reward_random_between(a, b):
    return roll_reward_random_float() * (b - a) + a



