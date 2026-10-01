"""Pure UNO rules (no Telegram, no database) so they can be unit-tested.

Cards are strings "color:value". Colors: red green blue yellow. Values: 0-9, skip,
reverse, draw2. Wilds are "wild:*" and "wild:draw4".

A game is a plain dict (stored as-is in MongoDB):
  players [uid], hands {str(uid): [card]}, deck [card], discard [card], top card,
  color (active color), turn (index), direction (1/-1), drawn (card the current
  player just drew, or None), seq (increments on every change), status.
"""
from __future__ import annotations

import random
from typing import Optional

COLORS = ("red", "green", "blue", "yellow")
COLOR_EMOJI = {"red": "🔴", "green": "🟢", "blue": "🔵", "yellow": "🟡", "wild": "🌈"}
VALUE_LABEL = {"skip": "⛔ Skip", "reverse": "🔄 Reverse", "draw2": "+2", "*": "Wild", "draw4": "Wild +4"}


def new_deck(rng: random.Random | None = None) -> list[str]:
    deck: list[str] = []
    for c in COLORS:
        deck.append(f"{c}:0")
        for v in [str(i) for i in range(1, 10)] + ["skip", "reverse", "draw2"]:
            deck += [f"{c}:{v}"] * 2
    deck += ["wild:*"] * 4 + ["wild:draw4"] * 4
    (rng or random).shuffle(deck)
    return deck


def split(card: str) -> tuple[str, str]:
    c, v = card.split(":", 1)
    return c, v


def label(card: str, color: Optional[str] = None) -> str:
    c, v = split(card)
    if c == "wild":
        base = VALUE_LABEL[v]
        return f"🌈 {base}" + (f" → {COLOR_EMOJI[color]}" if color in COLORS else "")
    return f"{COLOR_EMOJI[c]} {VALUE_LABEL.get(v, v)}"


def short(card: str) -> str:
    """Compact form for callback alerts (200 char limit)."""
    c, v = split(card)
    tail = {"skip": "⛔", "reverse": "🔄", "draw2": "+2", "*": "W", "draw4": "W+4"}.get(v, v)
    return f"{COLOR_EMOJI[c]}{tail}"


def new_game(players: list[int], rng: random.Random | None = None, hand_size: int = 7) -> dict:
    rng = rng or random.Random()
    deck = new_deck(rng)
    hands = {str(p): [deck.pop() for _ in range(hand_size)] for p in players}
    # The first face-up card is always a plain number card.
    while True:
        top = deck.pop()
        if split(top)[0] != "wild" and split(top)[1].isdigit():
            break
        deck.insert(0, top)
    return {
        "players": list(players), "hands": hands, "deck": deck, "discard": [top], "top": top,
        "color": split(top)[0], "turn": 0, "direction": 1, "drawn": None, "seq": 0,
        "status": "active", "winner": None,
    }


def current(game: dict) -> int:
    return game["players"][game["turn"] % len(game["players"])]


def _next_index(game: dict, steps: int = 1) -> int:
    return (game["turn"] + game["direction"] * steps) % len(game["players"])


def can_play(game: dict, card: str) -> bool:
    c, v = split(card)
    if c == "wild":
        return True
    tc, tv = split(game["top"])
    return c == game["color"] or v == tv


def playable(game: dict, uid: int) -> list[str]:
    hand = game["hands"].get(str(uid), [])
    if game.get("drawn"):
        return [game["drawn"]] if game["drawn"] in hand else []
    return [c for c in hand if can_play(game, c)]


def _draw_cards(game: dict, uid: int, n: int, rng: random.Random | None = None) -> list[str]:
    got: list[str] = []
    for _ in range(n):
        if not game["deck"]:
            rest = game["discard"][:-1]
            game["discard"] = game["discard"][-1:]
            (rng or random).shuffle(rest)
            game["deck"] = rest
            if not game["deck"]:
                break  # nothing left anywhere
        got.append(game["deck"].pop())
    game["hands"][str(uid)] = game["hands"].get(str(uid), []) + got
    return got


def _res(ok: bool, error: str = "", events: list[str] | None = None, **extra) -> dict:
    return {"ok": ok, "error": error, "events": events or [], **extra}


def play(game: dict, uid: int, card: str, color: Optional[str] = None, rng=None) -> dict:
    if game.get("status") != "active":
        return _res(False, "The game is not running.")
    if current(game) != uid:
        return _res(False, "It's not your turn.")
    hand = game["hands"].get(str(uid), [])
    if card not in hand:
        return _res(False, "You don't have that card.")
    if game.get("drawn") and card != game["drawn"]:
        return _res(False, "You can only play the card you just drew, or pass.")
    if not can_play(game, card):
        return _res(False, "That card doesn't match the top card.")
    c, v = split(card)
    if c == "wild" and color not in COLORS:
        return _res(False, "Pick a color for the wild card.")

    hand.remove(card)
    game["discard"].append(card)
    game["top"] = card
    game["color"] = color if c == "wild" else c
    game["drawn"] = None
    events = [f"played {label(card, game['color'] if c == 'wild' else None)}"]

    if not hand:
        game["status"], game["winner"] = "finished", uid
        game["seq"] += 1
        return _res(True, events=events, winner=uid)
    if len(hand) == 1:
        events.append("UNO! 🔔 one card left")

    steps, victim_draw = 1, 0
    if v == "skip":
        steps = 2
    elif v == "reverse":
        if len(game["players"]) == 2:
            steps = 2  # with two players reverse acts like skip
        else:
            game["direction"] *= -1
    elif v == "draw2":
        steps, victim_draw = 2, 2
    elif v == "draw4":
        steps, victim_draw = 2, 4

    if victim_draw:
        victim = game["players"][_next_index(game, 1)]
        got = _draw_cards(game, victim, victim_draw, rng)
        events.append(f"next player draws {len(got)} and is skipped")
        game["_victim"] = victim
    game["turn"] = _next_index(game, steps)
    game["seq"] += 1
    return _res(True, events=events, victim=game.pop("_victim", None))


def draw(game: dict, uid: int, rng=None) -> dict:
    if game.get("status") != "active":
        return _res(False, "The game is not running.")
    if current(game) != uid:
        return _res(False, "It's not your turn.")
    if game.get("drawn"):
        return _res(False, "You already drew. Play that card or pass.")
    got = _draw_cards(game, uid, 1, rng)
    if not got:
        game["turn"] = _next_index(game)
        game["seq"] += 1
        return _res(True, events=["couldn't draw (deck empty) and passes"], card=None, passed=True)
    card = got[0]
    if can_play(game, card):
        game["drawn"] = card
        game["seq"] += 1
        return _res(True, events=["drew a card and may play it or pass"], card=card, passed=False)
    game["turn"] = _next_index(game)
    game["seq"] += 1
    return _res(True, events=["drew a card and passes"], card=card, passed=True)


def pass_turn(game: dict, uid: int) -> dict:
    if game.get("status") != "active":
        return _res(False, "The game is not running.")
    if current(game) != uid:
        return _res(False, "It's not your turn.")
    if not game.get("drawn"):
        return _res(False, "Draw a card first.")
    game["drawn"] = None
    game["turn"] = _next_index(game)
    game["seq"] += 1
    return _res(True, events=["passes"])


def force_skip(game: dict, uid: int, rng=None) -> dict:
    """Used by the idle timer: draw one card (if not already drawn) and pass."""
    if game.get("status") != "active" or current(game) != uid:
        return _res(False, "stale")
    if not game.get("drawn"):
        _draw_cards(game, uid, 1, rng)
    game["drawn"] = None
    game["turn"] = _next_index(game)
    game["seq"] += 1
    return _res(True, events=["was idle: drew a card and was skipped"])


def remove_player(game: dict, uid: int) -> None:
    """Remove a player (idle kick); their cards go under the deck."""
    if uid not in game["players"]:
        return
    idx = game["players"].index(uid)
    game["deck"] = game["hands"].pop(str(uid), []) + game["deck"]
    was_current = idx == game["turn"] % len(game["players"])
    game["players"].pop(idx)
    if not game["players"]:
        return
    if idx < game["turn"]:
        game["turn"] -= 1
    if game["direction"] == 1 and was_current:
        game["turn"] = idx % len(game["players"])  # the next player slid into this slot
    game["turn"] %= len(game["players"])
    game["drawn"] = None
    game["seq"] += 1
