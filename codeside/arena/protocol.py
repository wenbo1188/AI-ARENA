"""Shared action validation for matches and participant self-checks."""
import math


def action_errors(msg, owned):
    if not isinstance(msg, dict) or not isinstance(msg.get("actions"), dict):
        return ["回复必须包含 actions 对象"]
    errors = []
    for uid, action in msg["actions"].items():
        if uid not in owned:
            errors.append("actions 含不属于己方的单位 ID: " + str(uid))
        if not isinstance(action, dict):
            errors.append("单位动作必须是对象")
            continue
        for key in ("jump", "jump_down", "shoot", "reload", "swap_weapon", "plant_mine"):
            if key in action and type(action[key]) is not bool:
                errors.append(key + " 必须是布尔值")
        nums = [action.get("velocity", 0)]
        aim = action.get("aim", {"x": 0, "y": 0})
        if isinstance(aim, dict) and "x" in aim and "y" in aim:
            nums += [aim["x"], aim["y"]]
        else:
            errors.append("aim 必须是含 x、y 的对象")
        if any(type(n) not in (int, float) or not math.isfinite(n) for n in nums):
            errors.append("velocity / aim 必须是有限数值")
    return errors


