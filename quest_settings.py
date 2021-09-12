import json
import os

import mod_engine
from language_settings import language_strings
from save_engine import my_games_path

def read_quest_settings():
    with open(quest_settings_path, 'r') as f:
        return json.load(f)


def simple_list(raw_list):
    return (raw_list if isinstance(raw_list, list) else [raw_list]) if raw_list != '' else []

print("Loading Quest settings")
quest_settings_path = os.path.join(my_games_path(), "questsettings-converted.json")
quest_settings = json.loads(mod_engine.mod.get(quest_settings_path)()) if quest_settings_path in mod_engine.mod else read_quest_settings()
print("Loading sequels")
sequels = { q["_name"]:[t["_name"] for s in simple_list(q["sequels"]) for t in simple_list(s["sequel"])] for q in quest_settings['quests']['quest']}
print("Loading prequels")
#prequels = { q["_name"]:[p["_name"] for p in quest_settings['quests']['quest'] if q["_name"] in sequels[p["_name"]]] for q in quest_settings['quests']['quest']}
#oldprequels = { q:[p for p in sequels if q in sequels[p]] for q in sequels}

prequels = {}
for k , seq in sequels.items():
    for v in seq:
        prequels[v] = prequels.get(v, []) + [k]


print("Loading debut quests")
debut_quests = {g: [] for g in sequels if g not in prequels}

prequels.update(debut_quests)
print("Loading translations")

language_strings = language_strings()
quest_titles = {q["_name"]: language_strings.get(q["_title"].split(":")[-1], "No title") for q in quest_settings['quests']['quest']}

# print("quest_titles loaded", len(quest_titles))

print("Questsettings loaded: ",  len(quest_settings['quests']['quest']), " quests loaded")
