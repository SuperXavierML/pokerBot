"""Tournament entry for xavBotOne.

This file mirrors the standalone legacy entry in ``my_bots/xavBotOne.py`` and
keeps the submission in the format required by the starter README.
"""

import math
import random
import time

try:
    from treys import Card, Evaluator
except ImportError:
    Card = None
    Evaluator = None

RANKS = "23456789TJQKA"
VALUES = {r: i + 2 for i, r in enumerate(RANKS)}
SUITS = "shdc"
EVALUATOR = Evaluator() if Evaluator else None
STATS = {}
SEEN = set()


def _hand(cards):
    a, b = cards
    x, y = VALUES.get(a[0], 2), VALUES.get(b[0], 2)
    return max(x, y), min(x, y), x == y, a[1] == b[1], abs(x - y)


def _score(cards):
    high, low, pair, suited, gap = _hand(cards)
    if pair:
        return 40 + 5 * high
    return high * 3 + low * 1.35 + (4.5 if suited else 0) + (3 if gap <= 1 else 1 if gap == 2 else 0) + (3 if high >= 12 and low >= 10 else 0) + (4 if high == 14 else 0)


def _opp(state):
    return next((p for p in state.get("players", []) if p.get("bot_id") != state.get("your_bot_id")), {})


def _eff(state):
    bb = max(1, state.get("blinds", {}).get("bb", 100))
    return min(state.get("your_stack", 0), _opp(state).get("stack", state.get("your_stack", 0))) / bb


def _preflop(state):
    score = _score(state["your_cards"])
    high, low, pair, suited, gap = _hand(state["your_cards"])
    owed, pot, effective = state.get("amount_owed", 0), max(1, state.get("pot", 1)), _eff(state)
    button = state.get("seat_to_act") == state.get("button_seat")
    actions = state.get("action_log", [])
    raises = sum(a.get("action") in ("raise", "all_in") for a in actions)
    calls = sum(a.get("action") == "call" for a in actions)
    if raises >= 2:
        context = "4bet"
    elif raises:
        context = "3bet" if calls else "open"
    else:
        context = "limp" if calls else ("button_open" if button else "bb_open")

    if effective <= 10:
        cutoff = (46 if button else 54) - (7 if effective <= 8 else 0)
        if score >= cutoff:
            if owed and state.get("current_bet", 0) >= state.get("your_stack", 0):
                need = owed / max(1, pot + owed)
                return {"action": "call"} if score >= 67 + 15 * need else {"action": "fold"}
            return {"action": "all_in"}
        if not owed:
            return {"action": "check"}
        return {"action": "call"} if score >= 62 + 18 * owed / max(1, pot + owed) else {"action": "fold"}

    cutoff = {"button_open": 34, "bb_open": 40, "limp": 31, "open": 48, "3bet": 62, "4bet": 76}[context]
    cutoff += max(0, 100 - effective) * .035
    if suited and gap <= 1:
        cutoff -= 1.5
    if context == "4bet" and not (pair or high >= 13):
        cutoff += 4
    if score >= cutoff + 8 or abs(score - cutoff) <= 4 and random.random() < .60:
        if owed and context in ("3bet", "4bet") and score < cutoff + 14:
            return {"action": "call"} if score >= cutoff - 5 else {"action": "fold"}
        amount = max(state.get("min_raise_to", 0), state.get("current_bet", 0) * 2)
        return {"action": "raise", "amount": max(amount, state.get("current_bet", 0) + pot // 2)}
    if not owed:
        return {"action": "check"}
    need = owed / max(1, pot + owed)
    return {"action": "call"} if score >= cutoff - 5 and score / 100 >= need * .85 else {"action": "fold"}


def _equity(state):
    hero, board = state.get("your_cards", []), state.get("community_cards", [])
    if not EVALUATOR or len(hero) != 2 or len(board) < 3:
        return .5
    deck = [r + s for r in RANKS for s in SUITS if r + s not in set(hero + board)]
    wins, start = 0., time.perf_counter()
    for _ in range(160):
        if time.perf_counter() - start > .20:
            break
        run = random.sample(deck, 7 - len(board))
        try:
            b = [Card.new(c) for c in board + run[2:]]
            h = EVALUATOR.evaluate(b, [Card.new(c) for c in hero])
            v = EVALUATOR.evaluate(b, [Card.new(c) for c in run[:2]])
            wins += 1 if h < v else .5 if h == v else 0
        except (ValueError, TypeError):
            wins += .5
    return wins / 160


def _fold_rate(state, fraction):
    key = (state.get("street", "flop"), "large" if fraction >= .75 else "small")
    alpha, beta = STATS.get(key, (2., 3.))
    mean = alpha / (alpha + beta)
    return max(.02, min(.95, mean - .67 * math.sqrt(mean * (1 - mean) / (alpha + beta + 1))))


def _postflop(state):
    for index, item in enumerate(state.get("match_action_log", [])[-200:]):
        key = (item.get("hand_num"), index, item.get("bot_id"), item.get("action"))
        if key in SEEN:
            continue
        SEEN.add(key)
        if item.get("action") in ("fold", "call", "raise", "all_in"):
            fraction = item.get("amount", 0) / max(1, state.get("pot", 1))
            bucket = "large" if fraction >= .75 else "small"
            stat = STATS.setdefault((item.get("street", "unknown"), bucket), [2., 3.])
            stat[0 if item.get("action") == "fold" else 1] += 1
    equity = _equity(state)
    pot, owed, stack = max(1, state.get("pot", 1)), state.get("amount_owed", 0), state.get("your_stack", 0)
    equity *= 1.02 if state.get("seat_to_act") == state.get("button_seat") else .86
    if owed:
        need = owed / max(1, pot + owed)
        if equity < need * .9:
            return {"action": "fold"} if equity < .35 or random.random() >= .25 else {"action": "raise", "amount": min(stack, max(state.get("min_raise_to", 0), pot // 2))}
        return {"action": "raise", "amount": min(stack, max(state.get("min_raise_to", 0), pot * 2 // 3))} if equity > .62 and random.random() < .18 else {"action": "call"}
    if equity < .28:
        return {"action": "check"}
    best, bet = equity * pot, 0
    for fraction in (.33, .5, .75, 1.):
        size = min(stack, max(1, int(pot * fraction)))
        fold = _fold_rate(state, fraction)
        value = fold * pot + (1 - fold) * (max(0, equity - .05) * (pot + 2 * size) - size)
        if value > best and value > 0:
            best, bet = value, size
    return {"action": "raise", "amount": max(state.get("min_raise_to", 0), bet)} if bet else {"action": "check"}


def decide(game_state: dict) -> dict:
    if game_state.get("type") == "warmup":
        return {"action": "check"}
    try:
        return _preflop(game_state) if game_state.get("street") == "preflop" else _postflop(game_state)
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError):
        return {"action": "check"} if game_state.get("can_check") else {"action": "fold"}
