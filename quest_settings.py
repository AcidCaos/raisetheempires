import json
import os

import mod_engine
from save_engine import my_games_path

def read_quest_settings():
    with open(quest_settings_path, 'r') as f:
        return json.load(f)

quest_settings_path = os.path.join(my_games_path(), "questsettings-converted.json")
quest_settings = json.loads(mod_engine.mod.get(quest_settings_path)()) if quest_settings_path in mod_engine.mod else read_quest_settings()
print("Questsettings loaded: ",  len(quest_settings['quests']['quest']), " quests loaded")
