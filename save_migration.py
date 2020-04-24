from flask import session
from save_engine import lookup_object
from game_settings import unlock_expansion
from quest_engine import handle_quest_progress
from save_engine import create_backup


def migrate(meta, version, target_version):
    if version == "0.02a" and version != target_version:
        for q in session["quests"]:
            if not q["complete"]:
                q["completedTasks"] = 0
                print("Reset quest completion")

        handle_quest_progress(meta, lambda task, progress, i, extra, *args: zero_yield(extra))

        session['user_object']["userInfo"]["player"]["expansions"]["data"] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        unlock_expansion(156)
        unlock_expansion(157)
        unlock_expansion(181)
        unlock_expansion(182)
        unlock_expansion(206)
        unlock_expansion(207)

        version = "0.03a"
        session['save_version'] = version
    if version == "0.03a" and version != target_version:
        create_backup("Update to 0.04a")
        version = "0.04a"
        session['save_version'] = version
    if version == "0.04a" and version != target_version:
        create_backup("Update to 0.05a")
        version = "0.05a"
        session['save_version'] = version
    if version and version.startswith("0.05a") and version != target_version: # upcoming 0.06
        #create_backup("Update to 0.06a")#  for release
        #version = "0.06a"
        #govt_fixer()
        session['user_object']["experiments"]["empire_decorations_master"] = 2
        #session['save_version'] = version
    if version == "0.06a" and version != target_version: # upcoming 0.07
        # create_backup("Update to 0.06a") # for release
        # version = "0.07a"
        #
        pass
        # session['user_object']["experiments"]["empire_decorations_master"] = 2



def zero_yield(extra):
    extra["yield"] = 0
    return True


def govt_fixer():
    govt_staff = {"Parliament": 3,
                  "Executive Mansion": 4,
                  "Federal Courthouse": 4,
                  "Treasury": 5,
                  "Maritime Academy": 6,
                  "National Archives": 7,
                  "Prison": 8,
                  "State Media": 10,
                  "Opera House": 11,
                  "Mint": 12,
                  "Intelligence HQ" : 11,
                  "Space Agency" : 12,
                  "Satellite_Tracking_Center" : 12,
                  "Engineering_Office" : 12
                  }

    for decoration in session['user_object']["userInfo"]["world"]["objects"]:
        if "crewInfo" not in decoration and decoration["itemName"] in govt_staff \
            and int(decoration.get("state")) >= 8 :

            for reapet_number in range(govt_staff.get(decoration["itemName"])):
                decoration["crewInfo"] = decoration.get("crewInfo", []) + [-1]


