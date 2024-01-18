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
    if version and version.startswith("0.05a") and version != target_version: # 0.06
        create_backup("Update to 0.06a")
        version = "0.06a"
        govt_fixer()
        session['user_object']["experiments"]["empire_decorations_master"] = 2
        session['user_object']["experiments"]["empire_doober_pickup"] = 3
        session['user_object']["experiments"]["empires_consumable_2"] = 3
        session['user_object']["experiments"]["empire_research_shield_upgrade"] = 2
        session['user_object']["experiments"]["empires_support_units"] = 5
        session['user_object']["experiments"]["empire_buildable_zrig_master"] = 3
        session['save_version'] = version
    if version and version.startswith("0.06a") and version != target_version:  # 0.07
        create_backup("Update to 0.07a")
        version = "0.07a"
        session['save_version'] = version
    if version and ((version.startswith("0.07a") and version != target_version) or is_0_08a_preview(version)): # 0.08 and
        # includes from preview 0.08a with same version number
        create_backup("Update to 0.08a full")
        # version = "0.08a"
        version = target_version  # remove before release
        crew_fixer()
        session['user_object']["experiments"]["empire_request2_master"] = 2
        session['user_object']["experiments"]["empire_mfs_uili"] = 4
        session['user_object']["experiments"]["empire_survivalmode3_master"] = 3
        session['user_object']["experiments"]["empire_survivalMode_master"] = 2
        session['user_object']["experiments"]["empire_survivalmode_enhancements"] = 2
        session['user_object']["experiments"]["empire_mech_fight_master"] = 3
        session['user_object']["experiments"]["empire_mech_fight_gate_flat"] = 5
        session['user_object']["experiments"]["empire_mech_lab_master"] = 3
        session['user_object']["experiments"]["empire_titanresearch_master"] = 2
        session['user_object']["experiments"]["empire_tier_8"] = 4
        session['user_object']["experiments"]["empire_campv2_enabled"] = 2
        session['user_object']["experiments"]["empire_campaign_mastery"] = 2
        session['save_version'] = version
    if version and version.startswith("0.08a") and version != target_version:  # upcoming
        pass


def is_0_08a_preview(version):
    return version == "0.08a" and "empire_mech_lab_master" not in session['user_object']["experiments"]


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

def crew_fixer():
    for decoration in session['user_object']["userInfo"]["world"]["objects"]:
        if "crewInfo" in decoration:
            old_crew = decoration.get("crewInfo", [])
            decoration["crewInfo"] = [str(x) for x in old_crew]

