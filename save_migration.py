from flask import session

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


def zero_yield(extra):
    extra["yield"] = 0
    return True

