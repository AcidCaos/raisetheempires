import math

from flask import session

from game_settings import lookup_item_by_code, game_settings
from quest_engine import lookup_quest, get_tasks, simple_list, get_seed_w, get_seed_z, roll_random_between, \
    handle_quest_progress, progress_action


def battle_complete_response(params):
    if params['target'].startswith('fleet'):
        baddies = [lookup_item_by_code(friendly[1:]) for friendly, count in session['fleets'][params['target']].items() for i in range(int(count))]
        friendlies = [lookup_item_by_code(friendly.split(',')[0]) for friendly in session['fleets'][params['fleet']]]
    else:
        quest = lookup_quest(params['target'])
        tasks = get_tasks(quest)
        [task] = [t for t in tasks if t["_action"] == "fight"]
        enemy_fleet = lookup_item_by_code(task["_item"])
        baddies = [lookup_item_by_code(baddie_slot["-item"]) for baddie_slot in simple_list(enemy_fleet["baddie"])]
        friendlies = [lookup_item_by_code(friendly[1:]) for friendly, count in task["fleet"].items() for i in range(int(count))]

    player_unit_id = 0
    enemy_unit_id = 0

    if 'id' in params:
        [player_unit_id, enemy_unit_id] = params['id']  #player turn
        player_turn = True
    else:
        player_turn = False

    print("repr baddies", baddies)
    baddie_unit = baddies[enemy_unit_id]["unit"]
    baddie_max_strength = int(baddie_unit.get("-strength","0"))
    baddie_weak = int(baddie_unit.get("-weak","0"))
    [baddie_unit_type, baddie_unit_terrain] = baddie_unit.get("-type",",").split(',')

    friendly_unit = friendlies[player_unit_id]["unit"]
    friendly_max_strength = int(friendly_unit.get("-strength", "0"))
    friendly_weak = int(friendly_unit.get("-weak", "0"))
    [friendly_unit_type, friendly_unit_terrain] = friendly_unit.get("-type", ",").split(',')

    if "battle" not in session or not session["battle"]:
        baddie_strengths = [int(baddie["unit"].get("-strength", "0")) for baddie in baddies]
        friendly_strengths = [int(friendly["unit"].get("-strength", "0")) for friendly in friendlies]
        session["battle"] = (friendly_strengths, baddie_strengths)
    else:
        (friendly_strengths, baddie_strengths) = session["battle"]

    friendly_strength = friendly_strengths[player_unit_id]
    baddie_strength = baddie_strengths[enemy_unit_id]


    if not player_turn:
        unknown_rolls = ["init seed", get_seed_w(),get_seed_z(),
                         roll_random_between(0, 1),"seed",get_seed_w(),get_seed_z(),
                        roll_random_between(0, 1),"seed",get_seed_w(),get_seed_z(),
                        roll_random_between(0, 1),"seed",get_seed_w(),get_seed_z()]
    else:
        unknown_rolls = ["init seed", get_seed_w(),get_seed_z()]

    roll = unit_roll(friendly_weak if player_turn else baddie_weak, baddie_weak if player_turn else friendly_weak)

    (crit, direct) = get_hit_value(friendly_unit_type if player_turn else baddie_unit_type, baddie_unit_type if player_turn else friendly_unit_type)

    hit = roll >= direct

    base_damage = 25 # TODO tier difference & increments

    if player_turn:
        damage = base_damage * (3 * friendly_max_strength + baddie_strength) / (3 * baddie_strength + friendly_max_strength)
        damage = damage / 100 * baddie_max_strength
    else:
        damage = base_damage * (3 * baddie_max_strength + friendly_strength) / (3 * friendly_strength + baddie_max_strength)
        damage = damage / 100 * friendly_max_strength

    damage = math.floor(damage * 10 ** 3) / 10 ** 3

    glance = 0.10
    critter = 1.5

    if not hit:
        damage *= glance
    elif roll != 2 and roll >= crit:
        damage *= critter

    damage = math.ceil(damage)

    if player_turn:
        baddie_strengths[enemy_unit_id] -= damage
        if baddie_strengths[enemy_unit_id] < 0:
            baddie_strengths[enemy_unit_id] = 0 #dead
            # session["battle"] = None
        print("Attacking for", damage , "damage, enemy hp:", baddie_strengths[enemy_unit_id], roll,"after seed", get_seed_w(),get_seed_z(), repr(unknown_rolls))
    else:
        friendly_strengths[player_unit_id] -= damage
        if friendly_strengths[player_unit_id] < 0:
            friendly_strengths[player_unit_id] = 0  # dead
            # session["battle"] = None
        print("Taken", damage, "damage, player hp:", friendly_strengths[player_unit_id], "after seed", get_seed_w(),get_seed_z(), repr(unknown_rolls))

    if not player_turn:
        pass

    if sum(baddie_strengths) == 0:
        print("Enemy defeated")
        session["battle"] = None

    if sum(friendly_strengths) == 0:
        print("Player defeated")
        session["battle"] = None

    result = {"attackerStunned": None, "psh": 0, "esh": 0, "ps": friendly_strengths[player_unit_id], "es": baddie_strengths[enemy_unit_id], "hv": None, "ur": roll,
     "playerUnit": player_unit_id, "enemyUnit": enemy_unit_id, "seeds": {"w": get_seed_w(), "z": get_seed_z()},
     "energy": None}

    print("ch", params.ch)

    meta = {"newPVE": 0}
    handle_quest_progress(meta, progress_action("fight"))
    battle_complete_response = {"errorType": 0, "userId": 1, "metadata": meta, "data": result}
    return battle_complete_response


def unit_roll(attacker_weak, defender_weak):
    if attacker_weak:
        return -2
    elif defender_weak:
        return 2
    else:
        return roll_random_between(0, 1)


def get_hit_value(type, defender_type):
    [chain] = [e for e in game_settings['settings']['combatChain']['chain'] if e['-type'] == type]
    if defender_type in chain.get('-great').split(','):
        grade = 'great'
    elif defender_type in chain.get('-poor').split(','):
        grade = 'poor'
    else:
        grade = 'good'

    [value] = [e for e in game_settings['settings']['combatHitValues']['value'] if e['-type'] == grade]

    return (float(value["-critical"]), float(value["-direct"]))


def spawn_fleet(params):
    meta = {}

    # params['code']
    # params['fleet']

    quest = lookup_quest(params['code'])
    tasks = get_tasks(quest)

    [task] = [t for t in tasks if t["_action"] == "fight"]

   # meta["newPVE"] = {"status": 2, "pos": "58,60,0", "villain": "v18"}
   #  meta["newPVE"] = {"status": 2, "pos": "60,63,0", "villain": "v18", "quest": "Q6016"}
    meta["newPVE"] = {"status": 2, "pos": task["_spawnLocation"], "villain": task["_pveVillain"], "quest": params['code']}
    spawn_fleet = {"errorType": 0, "userId": 1, "metadata": meta,
                          "data": []}
    return spawn_fleet


def next_campaign_response(map):
    meta = {"newPVE": 0}

    map_item = lookup_item_by_code(map["map"])

    if map["map"] not in session['campaign'] or not session['campaign'][map["map"]]:
        session['campaign'][map["map"]] = {"island": -1}

    session['campaign'][map["map"]]["island"] += 1

    island = session['campaign'][map["map"]]["island"]

    next_campaign_response = {"errorType": 0, "userId": 1, "metadata": meta,
                              "data": {"map": map["map"], "island": island}}

    if 'fleets' not in session:
        session["fleets"] = {}

    enemy_fleet = map_item["island"][island]['fleet']

    i=1
    fleet_name = "fleet1_" + str(get_zid())
    while fleet_name in session["fleets"]:
        i += 2
        fleet_name = "fleet" + str(i) + "_" + str(get_zid())

    session["fleets"][fleet_name] = enemy_fleet
    print("Enemy fleet:", enemy_fleet)

    return next_campaign_response