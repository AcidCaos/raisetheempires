import json

with open("questsettings-converted.json", 'r') as f:
    quest_settings = json.load(f)
    print("Questsettings loaded: ",  len(quest_settings['quests']['quest']), " quests loaded")

