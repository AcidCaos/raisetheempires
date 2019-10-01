from flask import session

from quest_engine import handle_quest_progress


def migrate(meta, version, target_version):
    if version == "0.02a" and version != target_version:
        for q in session["quests"]:
            if not q["complete"]:
                q["completedTasks"] = 0
                print("Reset quest completion")

        handle_quest_progress(meta, lambda task, progress, i, extra, *args: zero_yield(extra))

        version = "0.03a"
        session['save_version'] = version


def zero_yield(extra):
    extra["yield"] = 0
    return True

