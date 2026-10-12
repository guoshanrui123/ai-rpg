"""Authoritative, authored story progression; no external model or keys required."""

import re
import secrets

SKILLS = {"侦察": 36, "交涉": 45, "信用": 45, "图书馆使用": 60, "跑步": 23}
STRENGTH = {"1": 79, "2": 78, "3": 45}
LUCK = {"1": 66, "2": 66, "3": 40}
OPENING = "托马斯请你调查叔叔道格拉斯失踪与五本藏书失窃的联系。你来到旧宅书房，窗户没有锁，书架上留着五处空位。先检查书房，或去询问邻居。"
SCENES = {
    "house": [
        ("search", "搜索书房", "侦察"),
        ("neighbor", "询问邻居", None),
        ("cemetery", "前往公墓", None),
        ("library", "查阅图书馆", None),
    ],
    "neighbor": [
        ("talk", "与莱拉交涉", "交涉"),
        ("house", "返回旧宅", None),
        ("cemetery", "前往公墓", None),
        ("library", "查阅图书馆", None),
    ],
    "library": [("research", "查找旧报纸", "图书馆使用"), ("house", "返回旧宅", None), ("cemetery", "前往公墓", None)],
    "cemetery": [
        ("keeper", "取得看守信任", "信用"),
        ("watch", "夜间守候", "幸运"),
        ("track", "追踪墓地脚印", "跑步"),
        ("house", "返回旧宅", None),
    ],
    "entrance": [("open", "屏住呼吸推开石板", "力量"), ("wait", "在墓碑旁等到夜晚", None)],
    "meeting": [
        ("ask", "询问道格拉斯真相", None),
        ("peace", "尊重他的选择并离开", None),
        ("join", "随他进入地下", None),
        ("flee", "逃离公墓", None),
    ],
}
LOCATIONS = {
    "house": "旧宅书房",
    "neighbor": "邻居莱拉门前",
    "library": "镇立图书馆",
    "cemetery": "公墓",
    "entrance": "低矮墓碑",
    "meeting": "与道格拉斯交谈",
    "ended": "调查结束",
}
ARRIVALS = {
    "house": "你回到旧宅，窗边的书架缺了五本书。",
    "neighbor": "莱拉打开门，警惕地打量你。可以尝试交涉，询问道格拉斯过去常去的地方。",
    "library": "图书馆保留着《阿诺兹堡广告报》的旧报纸。你可以查找关于公墓的报道。",
    "cemetery": "公墓看守梅洛迪亚斯坐在小屋前。远处有许多低矮的墓碑。你可以争取他的信任、追踪脚印，或等到夜晚。",
}


def new_game():
    return {"scene": "house", "clues": [], "pending": None, "ending": None}


def view(game, card):
    choices = (
        []
        if game["ending"] or game["pending"]
        else [
            {"id": key, "label": label + (f"（{skill}检定）" if skill else "")}
            for key, label, skill in SCENES[game["scene"]]
        ]
    )
    return {
        "location": LOCATIONS[game["scene"]],
        "clues": list(game["clues"]),
        "actions": choices,
        "pending_check": game["pending"],
        "ending": game["ending"],
    }


def add_clue(game, text):
    if text not in game["clues"]:
        game["clues"].append(text)


def act(game, card, action):
    if game["ending"]:
        raise ValueError("调查已经结束，请点击重新开始。")
    if game["pending"]:
        raise ValueError("请先掷骰子完成当前检定。")
    available = {key: (label, skill) for key, label, skill in SCENES[game["scene"]]}
    if action not in available:
        raise ValueError("这个行动在当前场景不可用，请选择下方行动。")
    label, skill = available[action]
    if skill:
        threshold = STRENGTH[card] if skill == "力量" else LUCK[card] if skill == "幸运" else SKILLS[skill]
        game["pending"] = {"action": action, "skill": skill, "threshold": threshold}
        return f"你决定{label}。需要进行{skill}检定（目标值 {threshold}）；请点击掷骰子。"
    if action in ARRIVALS:
        game["scene"] = action
        return ARRIVALS[action]
    if action == "wait":
        game["scene"] = "meeting"
        return (
            "夜幕降临，一位抱着书的身影从地穴走出。他长着犬类般的面孔，却仍保留道格拉斯的轮廓。他停下来，等待你的回应。"
        )
    if action == "ask":
        add_clue(game, "道格拉斯仍有意识，自愿与地下的朋友生活，偷书只为了阅读。")
        return "道格拉斯说：‘我厌倦了人类社会的喧闹。地下的朋友让我安心阅读。这是我最后一次取书，入口就要关闭。请不要告诉托马斯我还在这里。’你可以选择离开或随他进入地下。"
    endings = {
        "peace": (
            "和平告别",
            "你尊重道格拉斯的选择。他带着书走下地穴，石板合拢。你向托马斯报告，盗窃不会再发生，却保留了叔叔的秘密。调查结束。",
        ),
        "join": (
            "地下的读者",
            "你跟随道格拉斯走入地下，石板在身后合拢。人类世界从此失去了你的踪迹；一段陌生的生活才刚刚开始。调查结束。",
        ),
        "flee": ("未解的秘密", "你选择离开公墓。托马斯的藏书再没有失窃，而那晚所见一直留在你的记忆里。调查结束。"),
    }
    title, text = endings[action]
    game["ending"] = {"title": title, "text": text}
    game["scene"] = "ended"
    return text


def roll(game):
    check = game["pending"]
    if check is None:
        raise ValueError("当前没有待完成的检定，请先选择调查行动。")
    number = secrets.randbelow(100) + 1
    passed = number <= check["threshold"]
    game["pending"] = None
    action = check["action"]
    if action == "search":
        if passed:
            add_clue(game, "日记提到‘地下的朋友们’，入口可能藏在公墓。")
        text = (
            "你发现道格拉斯的日记：他决定加入‘地下的朋友们’。线索指向公墓。"
            if passed
            else "你没找到日记，只发现窗台有泥土。可以询问邻居，或直接前往公墓调查。"
        )
    elif action == "talk":
        if passed:
            add_clue(game, "莱拉见过道格拉斯夹着书前往公墓。")
        text = (
            "莱拉告诉你，道格拉斯总夹着书向公墓走去。"
            if passed
            else "莱拉不愿多说，只让你去问公墓看守。你也可以查阅图书馆。"
        )
    elif action == "research":
        if passed:
            add_clue(game, "旧报纸记载公墓里曾出现半足半蹄的奇怪脚印。")
        text = (
            "旧报纸记载有人在公墓看见怪人，现场留下半足半蹄的脚印。"
            if passed
            else "报纸资料散乱，你没有找到报道。旧宅和公墓仍然可以继续调查。"
        )
    elif action in ("keeper", "track"):
        if passed:
            game["scene"] = "entrance"
            add_clue(game, "道格拉斯常坐的墓碑下有可移动的石板。")
        text = (
            "你找到道格拉斯常坐的低矮墓碑，石板边缘有明显的移动痕迹。"
            if passed
            else "你暂时没找到入口。可以换一种调查方式，或者夜间守候；失败并不会结束调查。"
        )
    elif action == "watch":
        if passed:
            game["scene"] = "meeting"
        text = (
            "一位抱书的人影从旧宅返回墓地。你喊出道格拉斯的名字，他停下脚步，坐到墓碑上。"
            if passed
            else "这一夜没有人影出现。你可以再守一晚，或追踪脚印、询问看守。"
        )
    else:  # open
        if passed:
            game["scene"] = "meeting"
        text = (
            "你屏住呼吸推开石板，在洞口遇见抱着藏书的道格拉斯。他看起来已不再是普通人。"
            if passed
            else "石板纹丝不动。你可以再次尝试，或在墓碑旁等到夜晚，与出来取书的人交谈。"
        )
    return f"{check['skill']}检定：{number}/{check['threshold']}，{'成功' if passed else '失败'}。\n{text}"


def interpret(game, message):
    # Questions and negated plans must not spend a turn or choose an ending.
    if re.search(r"[？?]|为什么|为何|怎么|是否|是什么|哪里|能否|吗$|告诉我|想知道|介绍|解释|说说", message):
        return None
    message = re.sub(r"(?:不要|不想|不去|别|不打算)[^，,。；;]*(?:[，,。；;]|$)", "", message)
    aliases = {
        "search": ("搜索", "书房", "日记"),
        "neighbor": ("邻居", "莱拉"),
        "cemetery": ("公墓", "墓地"),
        "library": ("图书馆",),
        "talk": ("交涉", "询问"),
        "research": ("报纸", "查阅"),
        "keeper": ("看守", "信任"),
        "watch": ("守夜", "守候"),
        "track": ("追踪", "脚印"),
        "open": ("推开", "石板"),
        "wait": ("等待", "等到"),
        "ask": ("真相", "为什么", "询问"),
        "peace": ("尊重", "告别"),
        "join": ("跟随", "加入", "进入地下"),
        "flee": ("逃离", "逃跑"),
        "house": ("返回旧宅",),
    }
    if game["ending"] or game["pending"]:
        return None
    for key, label, _ in SCENES[game["scene"]]:
        if message == label or any(word in message for word in aliases[key]):
            return key
    return None
