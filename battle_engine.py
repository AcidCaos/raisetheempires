import math

from flask import session

from game_settings import lookup_item_by_code, game_settings, get_zid
from quest_engine import lookup_quest, get_tasks, simple_list, get_seed_w, get_seed_z, roll_random_between, \
    handle_quest_progress, progress_action, roll_random_float, all_lambda, progress_parameter_equals


def battle_complete_response(params):
    friendlies, friendly_strengths, baddies, baddie_strengths = init_battle(params)
    meta = {"newPVE": 0}

    if 'id' in params:
        [player_unit_id, enemy_unit_id] = params['id']  #player turn
        player_turn = True
    else:
        player_turn = False
        enemy_unit_id, _, player_unit_id = ai_best_attack(friendlies, friendly_strengths, baddies, baddie_strengths)

    # print("repr baddies", baddies)
    baddie_max_strength = get_unit_max_strength(baddies[enemy_unit_id], params)
    baddie_weak = get_unit_weak(baddies[enemy_unit_id])
    baddie_unit_type = get_unit_type(baddies[enemy_unit_id])

    friendly_max_strength = get_unit_max_strength(friendlies[player_unit_id])
    friendly_weak = get_unit_weak(friendlies[player_unit_id])
    friendly_unit_type = get_unit_type(friendlies[player_unit_id])

    friendly_strength = friendly_strengths[player_unit_id]
    baddie_strength = baddie_strengths[enemy_unit_id]

    init_seed = ["init seed", get_seed_w(), get_seed_z()]
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
        if baddie_strengths[enemy_unit_id] == 1:
            damage +=1
            baddie_strengths[enemy_unit_id] -= 1
            print("Enemy inced to prevent 1 strength")
        if baddie_strengths[enemy_unit_id] <= 0: #incing
            baddie_strengths[enemy_unit_id] = 0 #dead
            print("Enemy unit", enemy_unit_id, "down")
            # session["battle"] = None
        print("Attacking for", damage , "damage, enemy hp:", baddie_strengths[enemy_unit_id], roll, "after seed", get_seed_w(),get_seed_z(), repr(init_seed))
    else:
        friendly_strengths[player_unit_id] -= damage
        if friendly_strengths[player_unit_id] <= 0:
            friendly_strengths[player_unit_id] = 0  # dead
            print("Player unit", player_unit_id, "down")
            # session["battle"] = None
        print("Taken", damage, "damage, player hp:", friendly_strengths[player_unit_id], roll, "after seed", get_seed_w(),get_seed_z(), repr(init_seed))

    if sum(baddie_strengths) == 0:
        print("Enemy defeated")
        session["battle"] = None
        handle_quest_progress(meta, progress_action("fight"))
        current_island = get_current_island(params)
        if current_island != None:
            handle_quest_progress(meta, all_lambda(progress_action("islandWin"),
                                                   progress_parameter_equals("_island", str(current_island))))

    if sum(friendly_strengths) == 0:
        print("Player defeated")
        session["battle"] = None

    result = {"attackerStunned": None, "psh": 0, "esh": 0, "ps": friendly_strengths[player_unit_id], "es": baddie_strengths[enemy_unit_id], "hv": None, "ur": roll,
     "playerUnit": player_unit_id, "enemyUnit": enemy_unit_id, "seeds": {"w": get_seed_w(), "z": get_seed_z()},
     "energy": None}

    battle_complete_response = {"errorType": 0, "userId": 1, "metadata": meta, "data": result}
    return battle_complete_response


def init_battle(params):
    if 'target' not in params:
        baddies = [lookup_item_by_code(friendly[1:]) for friendly, count in session['fleets'][params['fleet']].items()
                   for i in range(int(count))]
        friendlies = [lookup_item_by_code(friendly.split(',')[0]) for friendly in
                      session['fleets'][get_previous_fleet(params['fleet'])]]
    elif params['target'].startswith('fleet'):
        baddies = [lookup_item_by_code(friendly[1:]) for friendly, count in session['fleets'][params['target']].items()
                   for i in range(int(count))]
        friendlies = [lookup_item_by_code(friendly.split(',')[0]) for friendly in
                      session['fleets'][params['fleet']]]
    else:
        quest = lookup_quest(params['target'])
        tasks = get_tasks(quest)
        [task] = [t for t in tasks if t["_action"] == "fight"]
        enemy_fleet = lookup_item_by_code(task["_item"])
        baddies = [lookup_item_by_code(baddie_slot["-item"]) for baddie_slot in simple_list(enemy_fleet["baddie"])]
        friendlies = [lookup_item_by_code(friendly[1:]) for friendly, count in task["fleet"].items() for i in
                      range(int(count))]

    if "battle" not in session or not session["battle"]:
        baddie_strengths = [get_unit_max_strength(baddie, params) for baddie in baddies]
        friendly_strengths = [get_unit_max_strength(friendly) for friendly in friendlies]
        session["battle"] = (friendly_strengths, baddie_strengths)
    else:
        (friendly_strengths, baddie_strengths) = session["battle"]
    return friendlies, friendly_strengths, baddies, baddie_strengths


def get_previous_fleet(name):
    print("Using previous fleet as friendlies for ally comsumables")
    return name[:5] + str(int(name[5]) - 1) + name[6:]


def unit_roll(attacker_weak, defender_weak):
    if attacker_weak:
        return -2
    elif defender_weak:
        return 2
    else:
        return roll_random_between(0, 1)


def get_hit_value(type, defender_type):
    grade = get_combat_chain_grade(type, defender_type)

    [value] = [e for e in game_settings['settings']['combatHitValues']['value'] if e['-type'] == grade]

    return (float(value["-critical"]), float(value["-direct"]))


def get_combat_chain_grade(type, defender_type):
    # print("chain grade", type, defender_type)
    [chain] = [e for e in game_settings['settings']['combatChain']['chain'] if e['-type'] == type]
    if defender_type in chain.get('-great').split(','):
        grade = 'great'
    elif defender_type in chain.get('-poor').split(','):
        grade = 'poor'
    else:
        grade = 'good'
    return grade


def get_hit_chance(attacker, defender):
    return {
        'poor':0,
        'good':1,
        'great':2,
    }[get_combat_chain_grade(get_unit_type(attacker), get_unit_type(defender))]


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


def assign_consumable_response(params):
    friendlies, friendly_strengths, baddies, baddie_strengths = init_battle(params)

    selected_random_consumable = int(roll_random_between(0, 0)) # required roll fixed allyconsumable in tutorialstep

    targeted_baddie = round(roll_random_between(0, round(len(baddies) - 1))) if len(baddies) > 1 else 0

    baddie_strengths[targeted_baddie] = 0 # assume death baddie
    print("Consumable used to baddie:", targeted_baddie)

    meta = {"newPVE": 0}
    assign_consumable_response = {"errorType": 0, "userId": 1, "metadata": meta,
                          "data": []}
    return assign_consumable_response




    #state_UseSecondaryAbility  item has secondaryAbility => consumable TAssignConsumable

    # TODO ai rolls FindBestDefendingUnit  required roll
    # FindBestDefendingUnitAgainstAttackers  optional roll
    # all alive attackers select defender with best value and select attacker for that value if more attackers with same value (and not m_shouldFocusFire) then conditionally roll between len of those attackers
    # when m_shouldFocusFire(and a defender was found) then it's found and returns
    # FindBestDefendingUnitAgainstBestAttacker
    # best valued alive defender: required roll
    # FindBestDefendingUnit required roll combatAISwitchPercent 0.2
    #consumables used?


def ai_best_attack(player_units, player_units_strengths, baddies, baddies_strengths):
    first_random = roll_random_float()

    players_tuple = zip(player_units, player_units_strengths, range(len(player_units)))
    best_units = [ai_best_unit(baddies, baddies_strengths,  player_unit, first_random) + (i,) for player_unit, strength, i in players_tuple if strength > 0]
    max_grade = max([grade for baddie_index, grade, player_index in best_units])
    best_pairings = [(baddie_index, grade, player_index) for baddie_index, grade, player_index in best_units if grade == max_grade]
    best_pairing = best_pairings[round(roll_random_between(0, len(best_pairings) - 1)) if len(best_pairings) > 1 else 0]  #optional roll
    print("best AI pairing method 1 (baddie, grade, friendly)", repr(best_pairing))

    baddies_tuple = zip(baddies, baddies_strengths, range(len(baddies)))
    best_units_2 = [ai_best_unit(player_units, player_units_strengths,  baddie, first_random) + (i,) for baddie, strength, i in baddies_tuple if strength > 0]
    max_grade_2 = max([grade for player_index, grade, baddie_index  in best_units_2])
    best_player = [player_index for player_index, grade, baddie_index in best_units_2 if grade == max_grade_2][0]
    second_random = roll_random_float()
    best_pairing_2 = ai_best_unit(baddies, baddies_strengths, player_units[best_player], second_random) + (best_player,)
    print("best AI pairing method 2 (baddie, grade, friendly)", repr(best_pairing_2))

    #the poorer the better? if all units are poor against the best defender then select that one?
    ratio = best_pairing_2[1]/ max_grade if max_grade > 0 else 0
    third_random = roll_random_float()
    opposite_day =  third_random < 0.2
    if (ratio < 0.5) ^ opposite_day:  # basically only if either method 1 or 2 is poor
        print("Using basic method 1", "opposite day", opposite_day)
        used_pairing = best_pairing
    else:
        print("Using method 2", "opposite day", opposite_day)
        used_pairing = best_pairing_2

    return used_pairing


def ai_best_unit(first_units, first_units_strengths, second_unit, random):
    first_units_tuple = list(zip(first_units, first_units_strengths, range(len(first_units))))
    best_grade = max([get_hit_chance(first_unit, second_unit) for first_unit, strength, i in first_units_tuple if strength > 0])
    best_units = [i for first_unit, strength, i in first_units_tuple if strength > 0 and get_hit_chance(first_unit, second_unit) == best_grade]
    # print("AI best unit" ,repr((first_units, first_units_strengths, second_unit, random)),best_grade, repr(best_units))
    random_roll = round(random * (len(best_units) - 1))
    return best_units[random_roll], best_grade

def get_unit_type(unit):
    return unit["unit"].get("-type", ",").split(',')[0]


def get_unit_terrain(unit):
    return unit["unit"].get("-type", ",").split(',')[1]


def get_unit_max_strength(unit, params=None):
    strength = int(unit["unit"].get("-strength", "0"))

    if params and 'map' in params and  params['map'] and params['map'][0] == 'C':
        if 'campaign' in session and params['map'] in session['campaign']:
            map_item = lookup_item_by_code(params["map"])
            island = session['campaign'][params['map']]["island"]
            if "strength" in map_item["island"][island]:
                strengths = simple_list(map_item["island"][island]["strength"])
                strength = apply_map_mod_strength(unit, strength, strengths)
                # print("Mod strenghts",repr(strengths))

    return strength

def get_current_island(params):
    if params and 'map' in params and params['map'] and params['map'][0] == 'C':
        if 'campaign' in session and params['map'] in session['campaign']:
            map_item = lookup_item_by_code(params["map"])
            return session['campaign'][params['map']]["island"]
    return None


def apply_map_mod_strength(unit, strength, strengths):
    for e in strengths:
        if e["-code"] == unit["-code"]:
            strength *= float(e["-mult"])
            print("Mod strength", e["-code"], unit["-name"], "has strength", strength, "instead of", int(unit["unit"].get("-strength", "0")))
    return strength


def get_unit_weak(unit):
    return int(unit["unit"].get("-weak", "0"))

