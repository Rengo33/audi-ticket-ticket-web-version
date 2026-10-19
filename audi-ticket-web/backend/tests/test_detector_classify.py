from app.bot.release_detector import _classify

known = {"a": 100, "b": 200}
# old product reappearing with its old ID is not new
assert _classify(known, {"a": 100, "b": 200, "old": 150}) == ([], ["old"])
# ID above max is new; unknown ID is ignored
assert _classify(known, {"new": 201, "x": None}) == (["new"], ["x"])
# no known IDs yet (first scan / legacy list) -> seed only
assert _classify({"a": None}, {"z": 999}) == ([], [])
print("ok")
