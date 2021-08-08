import math

from flask import session

from game_settings import lookup_item_by_code, game_settings, get_zid, lookup_items_by_type, \
    lookup_items_by_type_and_subtype
from logger import report_battle_log
from quest_engine import lookup_quest, get_tasks, simple_list, get_seed_w, get_seed_z, roll_random_between, \
    handle_quest_progress, progress_action, roll_random_float, all_lambda, progress_parameter_equals, do_rewards, \
    roll_reward_random_float, progress_battle_damage_count,progress_useAOA_consumable,progress_useGeneral_consumable
from save_engine import get_saves, store_session


def battle_complete_response(params):
    friendlies, friendly_strengths, baddies, baddie_strengths, active_consumables = init_battle(params)
    meta = {"newPVE": 0}

    if 'id' in params:
        [player_unit_id, enemy_unit_id] = params['id']  #player turn
        player_turn = True
    else:
        player_turn = False
        enemy_unit_id, _, player_unit_id = ai_best_attack(friendlies, friendly_strengths, baddies, baddie_strengths, active_consumables)

    if enemy_unit_id is not None and player_unit_id is not None:
        ally_target = ("ally", player_unit_id)
        enemy_target = ("enemy", enemy_unit_id)
        first_target = ally_target if player_turn else enemy_target
        second_target = enemy_target if player_turn else ally_target

        # print("repr baddies", baddies)
        baddie_max_strength = get_unit_max_strength(baddies[enemy_unit_id], False, params)
        baddie_weak = get_unit_weak(baddies[enemy_unit_id])
        baddie_unit_type = get_unit_type(baddies[enemy_unit_id])

        friendly_max_strength = get_unit_max_strength(friendlies[player_unit_id], True)
        friendly_weak = get_unit_weak(friendlies[player_unit_id])
        friendly_unit_type = get_unit_type(friendlies[player_unit_id])

        friendly_strength = friendly_strengths[player_unit_id]
        baddie_strength = baddie_strengths[enemy_unit_id]

        init_seed = ["init seed", get_seed_w(), get_seed_z()]
        roll = unit_roll(friendly_weak if player_turn else baddie_weak, baddie_weak if player_turn else friendly_weak)

        crit, direct = get_hit_value(friendly_unit_type if player_turn else baddie_unit_type, baddie_unit_type if player_turn else friendly_unit_type)
        if player_turn:
            crit, direct = handle_accurancy_upgrades(crit, direct, friendlies, player_unit_id)

        accuracy = (get_consumable_accuracy(first_target, active_consumables) - get_consumable_evasion(second_target, active_consumables)) * 0.01
        crit -= accuracy
        direct -= accuracy

        hit = roll >= direct

        base_damage = 25 # TODO tier difference & increments

        if player_turn:
            damage = base_damage * (3 * friendly_max_strength + baddie_strength) / (3 * baddie_strength + friendly_max_strength)
            damage = damage / 100 * baddie_max_strength
        else:
            damage = base_damage * (3 * baddie_max_strength + friendly_strength) / (3 * friendly_strength + baddie_max_strength)
            damage = damage / 100 * friendly_max_strength


        consumable_extra_damage = \
            get_consumable_damage(first_target, active_consumables) - \
            get_consumable_shield(second_target, active_consumables)
        damage += max(consumable_extra_damage, -damage) # can't get negative damage by shield

        if consumable_extra_damage:
            print("Consumable extra damage", max(consumable_extra_damage, -damage))

        if player_turn:
            damage = handle_damage_upgrades(damage, friendlies, player_unit_id)

        damage = math.floor(damage * 10 ** 3) / 10 ** 3

        glance = 0.10
        critter = 1.5

        hit_type = "directhit"

        if not hit:
            damage *= glance
            hit_type = "glancinghit"
        elif roll != 2 and roll >= crit:
            damage *= critter
            hit_type = "criticalhit"

        damage = math.ceil(damage)

        if player_turn:
            baddie_strengths[enemy_unit_id] -= damage
            if baddie_strengths[enemy_unit_id] == 1:
                damage +=1
                baddie_strengths[enemy_unit_id] -= 1
                print("Enemy inced to prevent 1 strength")
            if baddie_strengths[enemy_unit_id] <= 0:
                baddie_strengths[enemy_unit_id] = 0 #dead
                print("Enemy unit", enemy_unit_id, "down")
                hit_type = "kill" if hit_type != "criticalhit" else "criticalkill"
                handle_quest_progress(meta, progress_battle_damage_count("battleKill", 1, friendlies[player_unit_id], baddies[enemy_unit_id]))
                # session["battle"] = None
            print("Attacking for", damage , "damage, enemy hp:", baddie_strengths[enemy_unit_id], roll, "after seed", get_seed_w(),get_seed_z(), repr(init_seed))
            doBattleRewards(hit_type, baddie_max_strength, damage, friendly_max_strength)
            handle_quest_progress(meta, progress_battle_damage_count("battleDamage", damage, friendlies[player_unit_id], baddies[enemy_unit_id]))

        elif damage > 0 and is_shielded(ally_target, active_consumables) == True:
            consume_shield(ally_target, active_consumables)

        else:
            friendly_strengths[player_unit_id] -= damage
            if friendly_strengths[player_unit_id] <= 0:
                friendly_strengths[player_unit_id] = 0  # dead
                print("Player unit", player_unit_id, "down")
                # session["battle"] = None
            print("Taken", damage, "damage, player hp:", friendly_strengths[player_unit_id], roll, "after seed", get_seed_w(),get_seed_z(), repr(init_seed))
    else:
        print("Stun skipped turn")
        player_unit_id = next((i for strength, i in zip(friendly_strengths,range(len(friendly_strengths))) if strength > 0), None)
        enemy_unit_id = next((i for strength, i in zip(baddie_strengths,range(len(baddie_strengths))) if strength > 0), None)
        ally_target = ("ally", player_unit_id)
        roll = 0

    result = {"attackerStunned": None, "psh": 1 if is_shielded(ally_target, active_consumables) else 0, "esh": 0, "ps": friendly_strengths[player_unit_id], "es": baddie_strengths[enemy_unit_id], "hv": None, "ur": roll,
     "playerUnit": player_unit_id, "enemyUnit": enemy_unit_id, "seeds": {"w": get_seed_w(), "z": get_seed_z()},
     "energy": None}

    process_consumable_end_turn(active_consumables, baddie_strengths, friendly_strengths, player_turn)
    handle_win(baddie_strengths, meta, params, friendlies, friendly_strengths)
    handle_loss(friendly_strengths)

    report_battle_log(friendly_strengths, baddie_strengths, player_turn, player_unit_id, enemy_unit_id, active_consumables)
    if not player_turn:
        consume_consumables(active_consumables)
    battle_complete_response = {"errorType": 0, "userId": 1, "metadata": meta, "data": result}
    return battle_complete_response

#             "-disable": "stun",
# "-attack": "-99", accurancy debuff
# "-attack": "99",  buff accurancy
# "-shield": "5", BuffHunkerDown
#              "-defend": "99", BuffEvasive
# "-dot": "5" , PoisonGas

def process_consumable_end_turn(active_consumables, baddie_strengths, friendly_strengths, player_turn):
    for consumable_tuple in active_consumables:
        (consumable, target, tries) = consumable_tuple

        if not player_turn: # enemy dot after enemy turn
            if target == ("enemy", None):
                # apply to all baddies
                for selected_baddie in range(len(baddie_strengths)):
                    apply_dot_damage(consumable, selected_baddie, baddie_strengths, "Baddie")
            elif target[0] == "enemy":
                # apply to target[1]
                apply_dot_damage(consumable, target[1], baddie_strengths, "Baddie")
        else: # player dot after player turn
            if target == ("ally", None):
                for selected_friendly in range(len(friendly_strengths)):
                    apply_dot_damage(consumable, selected_friendly, friendly_strengths, "Friendly")
            elif target[0] == "ally":  #if  target[0] == "ally":
                apply_dot_damage(consumable, target[1], friendly_strengths, "Friendly")

    # active_consumables[:] = [(consumable, target, tries - (1 if is_consumable_for_turn(target, player_turn) else 0)) for consumable, target, tries
    #                          in active_consumables if tries > (1 if is_consumable_for_turn(target, player_turn) else 0)]


def consume_consumables(active_consumables):
    active_consumables[:] = [(consumable, target, tries - 1) for consumable, target, tries
                             in active_consumables if tries > 1]



def is_consumable_for_turn(target, player_turn):
    return (target[0] == "ally" and player_turn) or (target[0] in ["enemy", "AI"] and not player_turn)


def apply_dot_damage(consumable, selected_unit, strengths, target_description):
    dot_damage = int(consumable["consumable"].get("-dot", "0"))
    if dot_damage:
        print("Applying", dot_damage, "damage over time")

        if strengths[selected_unit] > 0:
            strengths[selected_unit] -= dot_damage
            print(target_description, selected_unit, "strength", strengths[selected_unit])
            if strengths[selected_unit] <= 0:
                strengths[selected_unit] = 0
                print(target_description, selected_unit, "down by consumable")


def handle_loss(friendly_strengths):
    if sum(friendly_strengths) == 0:
        print("Player defeated")
        session["battle"] = None


def handle_win(baddie_strengths, meta, params, friendlies, friendly_strengths):
    if sum(baddie_strengths) == 0:
        print("Enemy defeated")
        session["battle"] = None
        handle_quest_progress(meta, progress_action("fight"))
        map_name, current_island, map_item = get_current_island(params)
        if current_island is not None:
            handle_quest_progress(meta, all_lambda(progress_action("islandWin"),
                                                   progress_parameter_equals("_island", str(current_island))))
            do_rewards("Campaign", map_item['island'][current_island].get("reward"), meta)
            do_rewards("Liberty Bond", {"_type": "item", "_item": "xk01", "_count": "1"}, meta)

            next_island_id = map_item['island'][current_island].get('-unlocks')
            if next_island_id is not None:
                print("Activating next island", map_name, next_island_id)
                set_active_island_by_map(map_name, int(next_island_id))
            else:
                print("Current island group finished", map_name)
                set_active_island_by_map(map_name, len(map_item['island']))
        elif "attackHostId" in params:
            print("challenge won")
            invasion_complete(params["attackHostId"], params, friendlies, friendly_strengths)
        elif params.get('target') == "FleetName":
            if get_next_fleet(params["fleet"]).get("invaded_uid"):
                print("neighbor repel won")
                neighbor_repelled(get_next_fleet(params["fleet"]))
            else:
                print("repel won")
                fleet_name = params["fleet"]
                del session['user_object']["pvp"]["invaders"]["u" + get_next_fleet(fleet_name)["uid"]]
        elif params.get('name') == "FleetName":
            [(fleet_name, enemy_fleet)] = [(k, v) for k, v in session['fleets'].items() if isinstance(v, dict) and v.get('name') == "FleetName"]
            if enemy_fleet["invader"]:
                if enemy_fleet.get("invaded_uid"):
                    print("neighbor repel with consumable won")
                    neighbor_repelled(enemy_fleet)
                else:
                    print("repel with consumable won")
                    del session['user_object']["pvp"]["invaders"]["u" + enemy_fleet['uid']]
            else:
                print("challenge with consumable won")
                invasion_complete(enemy_fleet['uid'], params, friendlies, friendly_strengths)


def neighbor_repelled(enemy_fleet):
    [save] = [save for save in get_saves() if
              str(save['user_object']["userInfo"]["player"]["uid"]) == str(enemy_fleet.get("invaded_uid"))]
    save['user_object']["pvp"]["invaders"]["u" + str(enemy_fleet.get("uid"))]["dID"] = get_zid()
    store_session(save)


def invasion_complete(enemy_fleet_uid, params, friendlies, friendly_strengths):
    [save] = [save for save in get_saves() if
              str(save['user_object']["userInfo"]["player"]["uid"]) == str(enemy_fleet_uid)]
    save['user_object']["pvp"]["invaders"]["u" + str(get_zid())]["status"] = 2
    save['user_object']["pvp"]["invaders"]["u" + str(get_zid())]["attacker_fleet"] = [format_player_fleet(friendlies[i]["-code"]) for i in get_alive_unit_index(friendly_strengths)]
    store_session(save)


def cancel_unstarted_invasions():
    for save in get_saves():
        if save['user_object']["pvp"]["invaders"].get("u" + str(get_zid()), {}).get("status") == 1:
            del save['user_object']["pvp"]["invaders"]["u" + str(get_zid())]
            store_session(save)


def get_next_fleet(fleet_name):
    return session['fleets'][get_next_fleet_name(fleet_name)]


def handle_damage_upgrades(damage, friendlies, player_unit_id):
    research = session['user_object']["userInfo"]["world"]["research"]
    upgrades = research.get(friendlies[player_unit_id]["-code"], [])
    for upgrade in upgrades:
        upgrade_item = lookup_item_by_code(upgrade)
        mod_damage = upgrade_item["modifier"].get("-damage")
        if mod_damage:
            if upgrade_item["modifier"].get("-percent"):
                damage *= 1 + float(mod_damage) / 100
                print("Applying damage upgrade for", mod_damage, "percent")
            else:
                damage += int(mod_damage)
                print("Applying damage upgrade for", mod_damage, "more")
    return damage


def handle_accurancy_upgrades(crit, direct, friendlies, player_unit_id):
    research = session['user_object']["userInfo"]["world"]["research"]
    upgrades = research.get(friendlies[player_unit_id]["-code"], [])
    for upgrade in upgrades:
        upgrade_item = lookup_item_by_code(upgrade)
        mod_accuracy = upgrade_item["modifier"].get("-accuracy")
        if mod_accuracy:
            crit -= float(mod_accuracy) / 100
            direct -= float(mod_accuracy) / 100
            print("Applying hit chance upgrade for", mod_accuracy, "percent")

    return crit, direct


def handle_strength_upgrades(strength, unit):
    research = session['user_object']["userInfo"]["world"]["research"]
    upgrades = research.get(unit["-code"], [])
    for upgrade in upgrades:
        upgrade_item = lookup_item_by_code(upgrade)
        mod_damage = upgrade_item["modifier"].get("-strength")
        if mod_damage:
            if upgrade_item["modifier"].get("-percent"):
                strength *= 1 + float(mod_damage) / 100
                print("Applying strength upgrade for", mod_damage, "percent")
            else:
                strength += int(mod_damage)
                print("Applying strength upgrade for", mod_damage, "more")
    return strength


def init_battle(params):
    if 'target' not in params:
        if params.get("name") == "AI":
            print("AI fleet")
            future_enemy_fleet = get_new_enemy_fleet_name()
            friendlies = [lookup_item_by_code(friendly.split(',')[0]) for friendly in
                          session['fleets'][get_previous_fleet_name(get_previous_fleet_name(get_previous_fleet_name(future_enemy_fleet)))]]
            baddies = [lookup_item_by_code(baddy[1:]) for sub_fleet in
                       simple_list(
                           session['fleets'][get_previous_fleet_name(get_previous_fleet_name(future_enemy_fleet))])
                       for baddy, count in sub_fleet.items()
                       for i in range(int(count))]
        elif params['name'] == "FleetName":
            print("Invader target consumable")
            [(fleet_name, enemy_fleet)] = [(k, v) for k, v in session['fleets'].items() if isinstance(v, dict) and v.get('name') == "FleetName"]
            baddies = [lookup_item_by_code(baddy.split(',')[0])
                       for baddy in enemy_fleet["units"]]
            friendlies = [lookup_item_by_code(friendly.split(',')[0]) for friendly in
                          session['fleets'][get_previous_fleet_name(fleet_name) if get_previous_fleet_name(fleet_name) in session['fleets'] else get_previous_fleet_name(get_previous_fleet_name(fleet_name))]]
        elif isinstance(simple_list(session['fleets'][params['fleet'] if params['fleet'] else params['name']])[0], str):
            print("Ally direct target")
            friendlies = [lookup_item_by_code(friendly.split(',')[0]) for friendly in
                          session['fleets'][params['fleet'] if params['fleet'] else params['name']]]
            if simple_list(session['fleets'][get_next_fleet_name(params['fleet'] if params['fleet'] else params['name'])])[0].get("name") == "FleetName":
                baddies = [lookup_item_by_code(baddy.split(',')[0]) for sub_fleet in
                           simple_list(session['fleets'][get_next_fleet_name(params['fleet'] if params['fleet'] else params['name'])])
                           for baddy in sub_fleet["units"]]
            else:
                baddies = [lookup_item_by_code(baddy[1:]) for sub_fleet in
                           simple_list(session['fleets'][get_next_fleet_name(params['fleet'] if params['fleet'] else params['name'])])
                           for baddy, count in sub_fleet.items()
                           for i in range(int(count))]
        else :
            baddies = [lookup_item_by_code(baddy[1:]) for sub_fleet in simple_list(session['fleets'][params['fleet'] if params['fleet'] else params['name']])
                       for baddy, count in sub_fleet.items()
                       for i in range(int(count))]
            friendlies = [lookup_item_by_code(friendly.split(',')[0]) for friendly in
                          session['fleets'][get_previous_fleet_name(params['fleet'] if params['fleet'] else params['name'])]]
    elif params['target'].startswith('fleet'):
        baddies = [lookup_item_by_code(baddy[1:]) for sub_fleet in simple_list(session['fleets'][params['target']])
                   for baddy, count in sub_fleet.items()
                   for i in range(int(count))]
        friendlies = [lookup_item_by_code(friendly.split(',')[0]) for friendly in
                      session['fleets'][params['fleet']]]
    elif params['target'] == "FleetName":
        print("Invader target")
        baddies = [lookup_item_by_code(baddy.split(',')[0]) for sub_fleet in
                   simple_list(session['fleets'][get_next_fleet_name(params['fleet'])])
                   for baddy in sub_fleet["units"]]
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
        baddie_strengths = [get_unit_max_strength(baddie, False, params) for baddie in baddies]
        friendly_strengths = [get_unit_max_strength(friendly, True) for friendly in friendlies]
        active_consumables = []
        session["battle"] = (friendly_strengths, baddie_strengths, active_consumables)
    else:
        (friendly_strengths, baddie_strengths, active_consumables) = session["battle"]
    return friendlies, friendly_strengths, baddies, baddie_strengths, active_consumables


def get_previous_fleet_name(name):
    print("Using previous fleet as friendlies for ally consumables")
    return name[:5] + str(int(name[5:name.index('_')]) - 1) + name[name.index('_'):]


def get_next_fleet_name(name):
    print("Using next fleet as baddies for ally targeted consumables")
    return name[:5] + str(int(name[5:name.index('_')]) + 1) + name[name.index('_'):]


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
    if defender_type in chain.get('-great', '').split(','):
        grade = 'great'
    elif defender_type in chain.get('-poor', '').split(','):
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


def next_campaign_response(params):
    meta = {"newPVE": 0}

    # map_item = lookup_item_by_code(map["map"])
    #
    # if map["map"] not in session['campaign'] or not session['campaign'][map["map"]]:
    #     session['campaign'][map["map"]] = {"island": -1}
    #
    # session['campaign'][map["map"]]["island"] += 1
    #
    # island = session['campaign'][map["map"]]["island"]
    #

    map_name, island, map_item = get_current_island(params)

    if island is None:
        island = 0

    next_campaign_response = {"errorType": 0, "userId": 1, "metadata": meta,
                              "data": {"map": params["map"], "island": island}}

    if 'fleets' not in session:
        session["fleets"] = {}

    enemy_fleet = map_item["island"][island]['fleet']
    #TODO what if defeated?
    fleet_name = get_new_enemy_fleet_name()

    session["fleets"][fleet_name] = enemy_fleet
    print("Enemy fleet:", enemy_fleet)

    return next_campaign_response



def register_random_fleet(fleet):
    if 'fleets' not in session:
        session["fleets"] = {}

    enemy_fleet = fleet
    fleet_name = get_new_enemy_fleet_name()

    session["fleets"][fleet_name] = enemy_fleet
    print("Random Enemy fleet:", enemy_fleet)


def get_new_enemy_fleet_name():
    i = 1
    fleet_name = "fleet1_" + str(get_zid())
    while fleet_name in session["fleets"]:
        i += 2
        fleet_name = "fleet" + str(i) + "_" + str(get_zid())
    return fleet_name


# new TAssignConsumable("AI",null,0,0,null) 2nd ability
#getRandomConsumableForMercenary=merc getRandomConsumableForPlayer=ally steele?
# getRandomConsumableForLevel(param1:int, param2:String, param3:String, param4:String) : ConsumableItem
#new TAssignConsumable(param2,MERC_CONSUMABLE_ITEM_CODE,_loc5_,param1,param3),true)  A0A
def assign_consumable_response(params):
    friendlies, friendly_strengths, baddies, baddie_strengths, active_consumables = init_battle(params)
    meta = {"newPVE": 0}
    targeted = False
    enemy_turn = False
    casting_ai = False

    consumables = lookup_items_by_type_and_subtype("consumable", "consumable")
    if params["code"] == "A0A":   # Ally / merc
        damaged = any([strength < get_unit_max_strength(unit, True) for unit, strength in zip(friendlies, friendly_strengths)])
        if params.get('name') == "-1":
            level = session["user_object"]["userInfo"]["player"]["level"] + 5  #steele = player level + 5
        else:
            level = 6
            if params.get('name', '0')[0].isalpha():
                merc = lookup_item_by_code(params["name"])
                level = int(merc["level"])
            else:
                for neighbor in session['user_object']["neighbors"]:
                    if neighbor["uid"] == int(params.get('name', '0')):
                        level = neighbor["level"]
        valid_consumables = [c for c in consumables if "-secondary" not in c and \
                             int(c.get("requiredLevel", "0")) <= level and \
                             (damaged or c["consumable"].get("-target") == 'enemy' or c["consumable"].get("-target") == 'enemy' or int(c["consumable"].get("-di","0")) >= 0) and \
                             'requiredDate' not in c and \
                             c["consumable"].get("-allypower", "true") != "false"]

        if session['user_object']["userInfo"]["player"]["tutorialProgress"] == 'tut_step_krunsch1AllyUsed':
            print("During tut_step_krunsch1AllyUsed: fixed N04 Air Strike")
            # only one occurrence of fixed allyConsumable uses an N04
            valid_consumables = [lookup_item_by_code("N04")]

        selected_random_consumable_roll = roll_random_between(0, len(valid_consumables) - 1)

        selected_random_consumable = round(selected_random_consumable_roll) # required roll fixed allyconsumable in tutorialstep
        selected_consumable = valid_consumables[selected_random_consumable]
        handle_quest_progress(meta, progress_useAOA_consumable(selected_consumable))
    elif params.get("name") == "AI":
        secondaries = [get_unit_secondary(b) for b, i in zip(baddies, range(len(baddies))) if get_unit_secondary(b) is not None and not is_stunned(("enemy", i), active_consumables)]
        if len(secondaries) > 1:
            print("WARN: more that one secondary", repr(secondaries))
        if not secondaries:
            print("ERROR: no secondary", repr(secondaries))
            raise Exception("ERROR: no secondary", repr(secondaries))

        selected_consumable = lookup_item_by_code(secondaries[0])
        enemy_turn = True

        cast_chance = roll_random_float()
        cast_percent = float(selected_consumable["consumable"]["-castpercent"])

        print(("Not c" if cast_chance >= cast_percent else "C") + "asting secondary power", cast_chance, ">=", cast_percent)
        selected_consumable = None #second targeted call will be made

        casting_ai = cast_chance < cast_percent

        #selected_consumable = None
    else:
        selected_consumable = lookup_item_by_code(params["code"])
        targeted = True
        enemy_turn = is_affected_by_consumable(("AI", None), {"consumable":{}}, active_consumables)
        handle_quest_progress(meta, progress_useGeneral_consumable(selected_consumable,enemy_turn))



    # TODO: AI secondary abily Z-units
    if selected_consumable is not None:
        if selected_consumable["consumable"].get("-type") != "all":
            if (selected_consumable["consumable"].get("-target") == 'enemy') ^ enemy_turn:
                live_baddies_index = get_alive_unit_index(baddie_strengths)
                if targeted:
                    targeted_baddie = int(params["id"])
                #TODO enemy support heals, accuracy,...
                else:
                    targeted_baddie = live_baddies_index[round(roll_random_between(0, round(len(live_baddies_index) - 1)))] if len(live_baddies_index) > 1 else live_baddies_index[0]
                apply_consumable_direct_impact(meta, selected_consumable, targeted_baddie, baddies, baddie_strengths, params, False, active_consumables)
                    # session["battle"] = None`
                # handle_win(baddie_strengths, meta, {})  #TODO next map?
                # handle_loss()

                target = ('enemy', targeted_baddie)
            else:
                live_friendly_index = get_alive_unit_index(friendly_strengths)
                if targeted:
                    targeted_friendly = int(params["id"])
                elif enemy_turn:
                    targeted_friendly = next(
                        i for s, i in zip(friendly_strengths, range(len(friendly_strengths))) if
                        s > 0 and not is_affected_by_consumable(("ally", i), selected_consumable, active_consumables))
                else:
                    targeted_friendly = live_friendly_index[
                        round(roll_random_between(0, round(len(live_friendly_index) - 1)))] if len(
                        live_friendly_index) > 1 else live_friendly_index[0]
                apply_consumable_direct_impact(meta, selected_consumable, targeted_friendly, friendlies, friendly_strengths,
                                               params, True, active_consumables)
                target = ('ally', targeted_friendly)
        else:

            # TODO: more consumables




            print("Consumable", selected_consumable["-code"], selected_consumable["consumable"].get("-diweapon", ""), "affects all")

            if (selected_consumable["consumable"].get("-target") == 'enemy') ^ enemy_turn:
                for i in range(len(baddies)):
                    apply_consumable_direct_impact(meta, selected_consumable, i, baddies, baddie_strengths, params, False, active_consumables)
                if not targeted and not enemy_turn and len(get_alive_unit_index(baddie_strengths)) > 1:
                    roll_random_float() #required roll
                target = ('enemy', None)
            else:
                print("target allies")
                for i in range(len(friendlies)):
                    apply_consumable_direct_impact(meta, selected_consumable, i, friendlies, friendly_strengths, params, True, active_consumables)
                if not targeted and not enemy_turn and len(get_alive_unit_index(friendly_strengths)) > 1:
                    roll_random_float()
                target = ('ally', None)

            # for i in range(len(baddie_strengths)):
                # baddie_strengths[i] -= 15
                # print("Baddie", i, "strength", baddie_strengths[i])
                # if baddie_strengths[i] <= 0:
                #     baddie_strengths[i] = 0
                #     print("Baddie", i, "down by consumable")


        if int(selected_consumable["consumable"].get("-duration", "0")) > 0:
            active_consumables.append((selected_consumable, target, int(selected_consumable["consumable"].get("-duration", "0"))))

        if selected_consumable["-name"] == "consumable75":
            print(selected_consumable)
            defenseshield_activate(friendlies, active_consumables, selected_consumable)

        if targeted and enemy_turn:
            print("Consumable use ends enemy turn")
            process_consumable_end_turn(active_consumables, baddie_strengths, friendly_strengths, False)
        elif not enemy_turn:
            process_consumable_end_turn(active_consumables, baddie_strengths, friendly_strengths, True)

        handle_win(baddie_strengths, meta, params, friendlies, friendly_strengths)
        handle_loss(friendly_strengths)

        report_battle_log(friendly_strengths, baddie_strengths, not enemy_turn, None, None,
                          active_consumables)

        if targeted and enemy_turn:
            consume_consumables(active_consumables)
    if casting_ai:
        active_consumables.append(({"consumable": {}}, ("AI", None), -1))

    assign_consumable_response = {"errorType": 0, "userId": 1, "metadata": meta,
                          "data": []}
    return assign_consumable_response


def get_alive_unit_index(strengths):
    return [i for s, i in zip(strengths, range(len(strengths))) if s > 0]


def apply_consumable_direct_impact(meta, selected_consumable, targeted_unit, units, units_strengths, params, ally, active_consumables):
    unit_current_strength = units_strengths[targeted_unit]
    direct_impact = int(selected_consumable["consumable"].get("-di", 0))
    damage = direct_impact
    against = simple_list(selected_consumable["consumable"].get("against", ''))
    # TODO: also units have against mod damage: Man_O_War_Battleship, Spec_Ops_Man_O_War_Battleship, LE_Elite_ManOWar_Battleship,
    # pirateship04(npc), pirateship03(npc), pirateinfantry02 PU2(npc), pirateInfantry02 PU4(npc), pirateAntiAir02(npc), pirateAntiAir03(npc),
    # pirateBalloon01(npc), pirateFighter01, pirateBomber01, pirateFighter02, pirateBomber02, pirateFighter03,pirateBomber03, pirateFighter05, pirateBomber05,
    # pirateUBoat03, pirateCaptainKrunsch and many more
    for a in against:
        if a['-type'] in (get_unit_type(units[targeted_unit]), get_unit_terrain(units[targeted_unit])):
            damage *= float(a['-mod'])
    if damage > 0 and is_shielded(("ally" if ally else "enemy",targeted_unit), active_consumables) == True:
        consume_shield(("ally" if ally else "enemy",targeted_unit), active_consumables)

    elif units_strengths[targeted_unit] > 0: #can't damage/heal dead units

        if selected_consumable["consumable"].get("-type") == "all" and selected_consumable["-subtype"] == "secondary":
            if "-percent" in selected_consumable["consumable"]:
                if roll_random_float() > int(selected_consumable["consumable"]["-percent"])/100:
                   damage =0

        units_strengths[targeted_unit] -= damage
        if not ally and 1 >= units_strengths[targeted_unit] > 0:
            units_strengths[targeted_unit] = 0
            print("Enemy inced to prevent 1 strength")
        if units_strengths[targeted_unit] <= 0:
            units_strengths[targeted_unit] = 0  # dead
            print("Enemy unit" if not ally else "Friendly unit", targeted_unit, "down")
            if ally:
                handle_quest_progress(meta, progress_battle_damage_count("battleKill", 1, {},
                                                                         units[targeted_unit]))
                doBattleRewards("kill", unit_current_strength, unit_current_strength, 0)

        if units_strengths[targeted_unit] > get_unit_max_strength(units[targeted_unit], ally, params):
            print("Limiting heal to max strength")
            units_strengths[targeted_unit] = get_unit_max_strength(units[targeted_unit], ally, params)
        print("Consumable", selected_consumable["-code"], selected_consumable["consumable"].get("-diweapon", ""), "used to " + ("friendly" if ally else "baddie:"), targeted_unit, "di", direct_impact, "damage", damage)
    else:
        print("Consumable", selected_consumable["-code"], selected_consumable["consumable"].get("-diweapon", ""), "not used to dead " + ("friendly" if ally else "baddie:"), targeted_unit, "di", direct_impact, "damage", damage)

    if "-chipFactor" in selected_consumable["consumable"]:
        # dead units are removed from battle side so units adjacent to the dead unit are now counted as adjacent to
        # each other for collateral damage
        live_index = get_alive_unit_index(units_strengths)
        for i in range(len(live_index)):
            collateral_unit_current_strength = units_strengths[live_index[i]]
            colateral_damage = math.ceil(get_adjacent_factor(targeted_unit, i, len(live_index)) *
                                         int(selected_consumable["consumable"]["-chipFactor"]) *
                                         int(selected_consumable["consumable"].get("-di", 0)) / 100)
            for a in against:
                if a['-type'] in (get_unit_type(units[live_index[i]]), get_unit_terrain(units[live_index[i]])):
                    colateral_damage *= float(a['-mod'])
            units_strengths[live_index[i]] -= colateral_damage
            if not ally and 1 >= units_strengths[live_index[i]] > 0:
                units_strengths[live_index[i]] = 0
                print("Enemy inced to prevent 1 strength")
            print("Enemy unit" if not ally else "Friendly unit suffered", collateral_unit_current_strength - units_strengths[live_index[i]], "collateral damage")
            if units_strengths[live_index[i]] <= 0:
                units_strengths[live_index[i]] = 0  # dead
                print("Enemy unit" if not ally else "Friendly unit", live_index[i], "down by collateral damage")
                if ally:
                    handle_quest_progress(meta, progress_battle_damage_count("battleKill", 1, {},
                                                                             units[live_index[i]]))
                    doBattleRewards("kill", collateral_unit_current_strength, collateral_unit_current_strength, 0)


def get_adjacent_factor(unit_1, unit_2, count):
    print(type(unit_1))
    print(type(unit_2))
    if unit_1 == unit_2 or count == 1:
        return 0
    elif count == 2:
        return 4
    elif count == 3:
        return [[0,4,3],[4,0,3],[3,4,0]][unit_1][unit_2]
    elif count == 4:
        return [[0,4,0,0],[4,0,3,0],[0,4,0,3],[0,0,4,0]][unit_1][unit_2]
    elif count == 5:
        return [[0,4,3,0,0],[4,0,3,2,0],[4,3,0,2,1],[0,4,3,0,2],[0,0,4,3,0]][unit_1][unit_2]


def is_stunned(target, active_consumables):
    for consumable, consumable_target, tries in active_consumables:
        if (consumable_target == target or consumable_target == (target[0], None)) and consumable["consumable"].get("-disable") == "stun":
            return True
    return False

def is_affected_by_consumable(target, used_consumable, active_consumables):
    for consumable, consumable_target, tries in active_consumables:
        if (consumable_target == target or consumable_target == (target[0], None)) and consumable == used_consumable:
            return True
    return False

def get_consumable_damage(target, active_consumables):
    return get_consumable_int(target, active_consumables, "-damage")


def get_consumable_shield(target, active_consumables):
    return get_consumable_int(target, active_consumables, "-shield")


def get_consumable_accuracy(target, active_consumables):
    return get_consumable_int(target, active_consumables, "-attack")


def get_consumable_evasion(target, active_consumables):
    return get_consumable_int(target, active_consumables, "-defend")


def get_consumable_int(target, active_consumables, field):
    damage = 0
    for consumable, consumable_target, tries in active_consumables:
        if consumable_target == target or consumable_target == (target[0], None):
            damage += int(consumable["consumable"].get(field, "0"))
    return damage


# state_UseSecondaryAbility  item has secondaryAbility => consumable TAssignConsumable

# TODO ai rolls FindBestDefendingUnit  required roll
# FindBestDefendingUnitAgainstAttackers  optional roll
# all alive attackers select defender with best value and select attacker for that value if more attackers with same value (and not m_shouldFocusFire) then conditionally roll between len of those attackers
# when m_shouldFocusFire(and a defender was found) then it's found and returns
# FindBestDefendingUnitAgainstBestAttacker
# best valued alive defender: required roll
# FindBestDefendingUnit required roll combatAISwitchPercent 0.2
# consumables used?
def ai_best_attack(player_units, player_units_strengths, baddies, baddies_strengths, active_consumables):
    first_random = roll_random_float()

    players_tuple = zip(player_units, player_units_strengths, range(len(player_units)))
    best_units = [ai_best_unit(baddies, baddies_strengths, player_unit, first_random, active_consumables, "enemy") + (i,) for player_unit, strength, i in players_tuple if strength > 0]
    max_grade = max([grade for baddie_index, grade, player_index in best_units])
    best_pairings = [(baddie_index, grade, player_index) for baddie_index, grade, player_index in best_units if grade == max_grade and grade >= 0]
    if best_pairings:
        best_pairing = best_pairings[round(roll_random_between(0, len(best_pairings) - 1)) if len(best_pairings) > 1 else 0]  #optional roll
        best_pairing = (best_pairings[0][0],) + best_pairing[1:]  # bugged pairings
        print("best AI pairing method 1 (baddie, grade, friendly)", repr(best_pairing))
    else:
        best_pairing = None, 0, None

    baddies_tuple = zip(baddies, baddies_strengths, range(len(baddies)))
    best_units_2 = [ai_best_unit(player_units, player_units_strengths,  baddie, first_random, active_consumables, "ally") + (i,) for baddie, strength, i in baddies_tuple if strength > 0]
    max_grade_2 = max([grade for player_index, grade, baddie_index  in best_units_2])
    best_players = [player_index for player_index, grade, baddie_index in best_units_2 if grade == max_grade_2]
    if best_players:
        best_player = best_players[0]
        second_random = roll_random_float()
        best_pairing_2 = ai_best_unit(baddies, baddies_strengths, player_units[best_player], second_random, active_consumables, "enemy") + (best_player,)
        print("best AI pairing method 2 (baddie, grade, friendly)", repr(best_pairing_2))
    else:
        best_pairing_2 = None, 0, None

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


def ai_best_unit(first_units, first_units_strengths, second_unit, random, active_consumables, target_group):
    first_units_tuple = list(zip(first_units, first_units_strengths, range(len(first_units))))
    best_grade = max([get_hit_chance(first_unit, second_unit) for first_unit, strength, i in first_units_tuple if strength > 0 and not is_stunned((target_group, i), active_consumables)] + [-1])
    best_units = [i for first_unit, strength, i in first_units_tuple if strength > 0 and not is_stunned((target_group, i), active_consumables) and get_hit_chance(first_unit, second_unit) == best_grade]
    # print("AI best unit" ,repr((first_units, first_units_strengths, second_unit, random)),best_grade, repr(best_units))
    if best_units:
        random_roll = round(random * (len(best_units) - 1))
        print(best_units[random_roll])
        return best_units[random_roll], best_grade
    else:
        return None, -1


def get_unit_type(unit):
    return unit["unit"].get("-type", ",").split(',')[0]


def get_unit_terrain(unit):
    return unit["unit"].get("-type", ",").split(',')[1]


def get_unit_secondary(unit):
    return unit["unit"].get("-secondary")


def get_unit_max_strength(unit, ally, params=None):
    strength = int(unit["unit"].get("-strength", "0"))
    _, island, map_item = get_current_island(params)
    if not ally and island != None and "strength" in map_item["island"][island]:
        strengths = simple_list(map_item["island"][island]["strength"])
        strength = apply_map_mod_strength(unit, strength, strengths)
        # print("Mod strenghts",repr(strengths))
    elif ally:
        strength = handle_strength_upgrades(strength, unit)
    return strength


# def get_current_island(params):
#     if params and 'map' in params and params['map'] and params['map'][0] == 'C':
#         if 'campaign' in session and params['map'] in session['campaign']:
#             map_item = lookup_item_by_code(params["map"])
#             return session['campaign'][params['map']]["island"], map_item
#     return None, None

def get_current_island(params):
    if params and 'map' in params and params['map'] and params['map'][0] == 'C':
        map_item = lookup_item_by_code(params["map"])
        return get_active_island_by_map(params['map']) + (map_item,)
    return None, None, None

def get_active_island_by_map(map_name):
    campaign = session['user_object']['userInfo']['world']['campaign']
    if map_name not in campaign['active'].keys():
        campaign['active'][map_name] = {"status": 0, "fleets": []}

    status = campaign['active'][map_name]["status"]
    island_id = (status & 4293918720) >> 20
    return map_name, island_id

def set_active_island_by_map(map_name, island_id):
    campaign = session['user_object']['userInfo']['world']['campaign']
    if map_name not in campaign['active'].keys():
        campaign['active'][map_name] = {"status": island_id << 20, "fleets": []}
    else:
        status = campaign['active'][map_name]["status"]
        status = (status & 1048575) | (island_id << 20)
        campaign['active'][map_name]["status"] = status


#
# def get_current_island_from_session():
#     campaign = session['user_object']['userInfo']['world']['campaign']
#     if 'current' in campaign:
#         return get_active_island_by_map()
#     return None, None


def apply_map_mod_strength(unit, strength, strengths):
    for e in strengths:
        if e["-code"] == unit["-code"]:
            strength *= float(e["-mult"])
            print("Mod strength", e["-code"], unit["-name"], "has strength", strength, "instead of", int(unit["unit"].get("-strength", "0")))
    return strength


def get_unit_weak(unit):
    return int(unit["unit"].get("-weak", "0"))

# unused?
# def getAbsolute(baddie_strength):
#     base_damage = 25  # TODO tier difference & increments
#
#     # if player_turn:
#     damage = base_damage * (3 * friendly_max_strength + baddie_strength) / (
#                 3 * baddie_strength + friendly_max_strength)
#     damage = damage / 100 * baddie_max_strength
#     # else:
#     #     damage = base_damage * (3 * baddie_max_strength + friendly_strength) / (
#     #                 3 * friendly_strength + baddie_max_strength)
#     #     damage = damage / 100 * friendly_max_strength
#
#     damage = math.floor(damage * 10 ** 3) / 10 ** 3



#TODO: fix kill has more coins?
def doBattleRewards(hit_type, max_strength, damage, friendly_max_strength):
    #mod strength?
    coin_amount = math.ceil(max_strength * damage * 0.01)  # * unit mult * ammo experiment
    rare_amount = math.ceil(max_strength * damage * 0.0001)  # * unit mult * ammo experiment
    rare_count = 0
    xp = 1
    energy = 0
    # TODO: energyRewardModVariant
    # TODO combat losses

    rare_type = int(friendly_max_strength % 5)

    if hit_type == "glancinghit":
        coin_amount = 0
    elif hit_type == "criticalkill":
        coin_amount *= 3
        rare_count = 3
        xp = 3
        energy = 1 if roll_reward_random_float() <= 0.8 else 0
        energy += 1 if roll_reward_random_float() <= 0.2 else 0

    elif hit_type == "criticalhit":
        rare_count = 1
        energy = 1 if roll_reward_random_float() <= 0.25 else 0

    rare_amount *= rare_count

    world = session['user_object']["userInfo"]["world"]
    resources = world['resources']
    resources['coins'] += coin_amount

    player = session['user_object']["userInfo"]["player"]
    player['xp'] += xp

    print("Combat rewards", hit_type ,  "coins:", coin_amount, "(" + str(resources['coins']) + ")")
    if rare_amount:
        resource_order = world['resourceOrder']
        resources[resource_order[rare_type]] += rare_amount
        print("Combat rewards", hit_type ,  "rare" + str(rare_type) + ":", rare_amount, "(" + str(resources[resource_order[rare_type]]) + ")")
        #Todo quest added

    print("Combat rewards", hit_type ,  "xp:", xp, "(" + str(player['xp']) + ")")

    if energy:
        player['energy'] += energy
        resources['energy'] += energy # needed?
        print("Combat rewards", hit_type ,  "energy:", energy, "(" + str(player['energy']) + ")")


def defenseshield_activate(friendlies, active_consumables, selected_consumable):
    for i in range(len(friendlies)):
        active_consumables.append((selected_consumable, ('ally',i), 9999999))
        print('ally: ' , i)



def consume_shield(hit_target, active_consumables):
    active_consumables[:] = [(consumable, target, tries) for consumable, target, tries
                             in active_consumables if consumable.get("consumable",{}).get("-givesAbility") != "shield" or target != hit_target]



def is_shielded(target, active_consumables):
    for consumable, consumable_target, tries in active_consumables:
        if (consumable_target == target or consumable_target == (target[0], None)) and consumable.get("consumable",{}).get("-givesAbility") == "shield":
            return True
    return False


def format_player_fleet(code):
    return code + ",,,,"
