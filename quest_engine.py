from questsettings import quest_settings
from game_settings import game_settings, lookup_item_by_code, lookup_state_machine
from flask import session
from functools import reduce

def merge_quest_progress(qc, output_list, label):
    print("new q before merge " + repr(qc))
    print(label + " list before merge " + repr (output_list))
    output_list[:] = qc + [e for e in output_list if e['name'] not in [q['name'] for q in qc]]
    print(label + " list after merge " + repr (output_list))


def lookup_quest(name):
    [quest] = [r for r in quest_settings['quests']['quest'] if r['_name'] == name]
    return quest


def new_quest(quest):
    # progress = [0 for e in quest['tasks']]
    progress, completes = map(list, zip(*[prepopulate_task(e) for e in get_tasks(quest)]))
    return {"name": quest['_name'], "complete": all(completes), "expired": False, "progress": progress, "completedTasks": reduce((lambda x, y: x << 1 | y), [False] + completes)}


def prepopulate_task(task):
    if task["_action"] == 'countPlaced':
        item = lookup_item_by_code(task["_item"])
        if 'stateMachineValues' in item:
            state_machine = lookup_state_machine(item['stateMachineValues']['-stateMachineName'],
                                                 item['stateMachineValues']['define'])
        else:
            state_machine = None
        objects = lookup_objects_by_item_name(item['-name'])
        number_built = len([e for e in objects if e.get('state', 0) >= (int(state_machine['-builtState']) if state_machine else 0)])
        return min(number_built, int(task["_total"])), number_built >= int(task["_total"])
    elif task["_action"] == 'autoComplete':
        return 1, True
    else:
        return 0, False


def lookup_objects_by_item_name(id):
    return [e for e in session['user_object']["userInfo"]["world"]["objects"] if e['itemName'] == id]


# "autoComplete","battleDamage","battleKill","build","buyExpansion","challengeCreate","clear","countPlaced","expandIsland","fight","finishBuilding","fullscreen","genericString","harvest","inventoryAdded","islandWin","marketAdd","marketBuy","move","neighborsAdded","openDialog","ownObjects","ownResource","place","population","pillage","pvpCombat","resourceAdded","seenFlag","select","socialXPAdded","startImmunity","state","tending","tendingRewardDropped","unlockTutorial","useConsumable","visit","zoom"
def handle_world_state_change(meta, *state_args):
    handle_quest_progress(meta, world_state_change(*state_args))


def world_state_change(*state_args):
    return lambda *args: \
        any([progress_finish_building_count_placed(*state_args)(*args),
             progress_auto_complete()(*args),
             progress_place(*state_args)(*args)])


def progress_finish_building_count_placed(state, state_machine, game_item, step):
    return lambda task, progress, i, *args: \
        task["_action"] in ["finishBuilding", "countPlaced"] and task["_item"] == game_item[
            '-code'] and progress < int(task["_total"]) and state['-stateName'] == state_machine['-builtState']


def progress_auto_complete():
    return lambda task, *args: task["_action"] == "autoComplete"


def progress_place(state, state_machine, game_item, step):
    return lambda task, progress, i, *args: \
        task["_action"] in ["place"] and task["_item"] == game_item['-code'] and progress < int(task["_total"] and step == "place")


def progress_action(action):
    return lambda task, *args: task["_action"] == action


def handle_quest_progress(meta, progress_function):
    incomplete_quests = [e for e in session['quests'] if e["complete"] == False]
    for session_quest in incomplete_quests:
        new_quests = []
        report_quest = False
        tasks = get_tasks(lookup_quest(session_quest['name']))
        for task, progress, i in zip(tasks, session_quest['progress'], range(len(session_quest['progress']))):
            print("task", repr(task), "progress", repr(progress), "i", i)
            if progress_function(task, progress, i):  #countPlaced tasks should be prepolulated with already placed items, however removed ones? precomplete autoComplete?
                    report_quest = True
                    session_quest['progress'][i] += 1
                    print("Task progress", task["_action"])
                    if session_quest['progress'][i] >= int(task["_total"]):
                        session_quest["completedTasks"] = session_quest["completedTasks"] | 1 << i
                        print("Task complete", task["_action"])

        print("completedTasks", session_quest["completedTasks"], "len(tasks)", len(tasks), "calc", 2 ** len(tasks) - 1)
        if session_quest["completedTasks"] >= 2 ** len(tasks) - 1:
            session_quest["complete"] = True
            print("Quest complete", session_quest['name'])
            activate_sequels(session_quest, new_quests)
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


def activate_sequels(session_quest, new_quests):
    raw_sequels = lookup_quest(session_quest['name'])['sequels']
    sequels = raw_sequels["sequel"] if isinstance(raw_sequels["sequel"], list) else [
        raw_sequels["sequel"]] if "sequel" in raw_sequels else []
    for sequel in sequels:
        new_quest_with_sequels(sequel["_name"], new_quests)


def new_quest_with_sequels(name, new_quests):
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
            activate_sequels(new_sequel_quest, new_quests)



# def autoclick_next_state(state_machine, next_click_state):
#     while '-autoNext' in next_click_state and next_click_state['-stateName'] != next_click_state[
#         '-autoNext']:  # '-clientDuration': '2.0s', '-duration': '0' respect duration for harvest?
#         next_state_id = next_click_state['-autoNext']  # not all states have this!! end states? autostate after time?
#         next_click_state = lookup_state(state_machine, next_state_id)
#         print("auto_next_state:", repr(next_click_state))
