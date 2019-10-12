import json
import os

from save_engine import my_games_path

with open(os.path.join(my_games_path() ,"questsettings-converted.json"), 'r') as f:
    quest_settings = json.load(f)
    print("Questsettings loaded: ",  len(quest_settings['quests']['quest']), " quests loaded")
    print(quest_settings['quests']['quest'][5]['_name'])
    print(quest_settings['quests']['quest'][5])
