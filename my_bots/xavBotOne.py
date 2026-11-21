"""Heads-up hold'em bot for the starter-kit runner.

The implementation is intentionally self-contained: it uses only the standard
library and the optional ``treys`` package supplied by the sandbox.
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
RANK_VALUE = {r: i + 2 for i, r in enumerate(RANKS)}
SUITS = "shdc"
EVALUATOR = Evaluator() if Evaluator else None
SEEN_LOG = set()
FOLD_STATS = {}


def _info(cards):
    a, b = cards[0], cards[1]
    x, y = RANK_VALUE.get(a[0], 2), RANK_VALUE.get(b[0], 2)
    return max(x, y), min(x, y), x == y, len(a) > 1 and len(b) > 1 and a[1] == b[1], abs(x - y)


def _matrix_score(cards):
    """Score the equivalent of a 13x13 starting-hand matrix."""
    high, low, pair, suited, gap = _info(cards)
    if pair:
        return 40 + high * 5
    score = high * 3 + low * 1.35
    score += 4.5 if suited else 0
    score += 3 if gap <= 1 else 1 if gap == 2 else 0
    score += 3 if high >= 12 and low >= 10 else 0
    return score + (4 if high == 14 else 0)


def _opponent(state):
    return next((p for p in state.get("players", []) if p.get("bot_id") != state.get("your_bot_id")), {})


def _effective_bb(state):
    bb = max(1, state.get("blinds", {}).get("bb", 100))
    return min(state.get("your_stack", 0), _opponent(state).get("stack", state.get("your_stack", 0))) / bb


def _context(state):
    actions = state.get("action_log", [])
    raises = sum(a.get("action") in ("raise", "all_in") for a in actions)
    calls = sum(a.get("action") == "call" for a in actions)
    if raises >= 2:
        return "4bet"
    if raises == 1:
        return "3bet" if calls else "open"
    return "limp" if calls else ("button_open" if state.get("seat_to_act") == state.get("button_seat") else "bb_open")


def _preflop(state):
    score = _matrix_score(state["your_cards"])
    high, low, pair, suited, gap = _info(state["your_cards"])
    owed = int(state.get("amount_owed", 0))
    pot = max(1, int(state.get("pot", 1)))
    effective = _effective_bb(state)
    button = state.get("seat_to_act") == state.get("button_seat")
    context = _context(state)

    # Approximate heads-up Nash push/fold thresholds for short stacks.
    if effective <= 10:
        cutoff = 46 if button else 54
        if effective <= 8:
            cutoff -= 7
        if score >= cutoff:
            if owed and state.get("current_bet", 0) >= state.get("your_stack", 0):
                needed = owed / max(1, pot + owed)
                return {"action": "call"} if score >= 67 + 15 * needed else {"action": "fold"}
            return {"action": "all_in"}
        if not owed:
            return {"action": "check"}
        needed = owed / max(1, pot + owed)
        return {"action": "call"} if score >= 62 + 18 * needed else {"action": "fold"}

    cutoff = {"button_open": 34, "bb_open": 40, "limp": 31, "open": 48, "3bet": 62, "4bet": 76}[context]
    cutoff += max(0, 100 - effective) * 0.035
    if suited and gap <= 1:
        cutoff -= 1.5
    if context == "4bet" and not (pair or high >= 13):
        cutoff += 4

    # Borderline hands are mixed so the bot is not exploitable by a fixed
    # threshold.  Raises specify the total bet on this street.
    if score >= cutoff + 8 or (abs(score - cutoff) <= 4 and random.random() < 0.60):
        if owed and context in ("3bet", "4bet") and score < cutoff + 14:
            return {"action": "call"} if score >= cutoff - 5 else {"action": "fold"}
        minimum = int(state.get("min_raise_to", 0))
        amount = max(minimum, int(state.get("current_bet", 0)) * 2)
        return {"action": "raise", "amount": max(amount, int(state.get("current_bet", 0)) + pot // 2)}
    if not owed:
        return {"action": "check"}
    needed = owed / max(1, pot + owed)
    return {"action": "call"} if score >= cutoff - 5 and score / 100 >= needed * 0.85 else {"action": "fold"}


def _equity(state, samples=160):
    hero = state.get("your_cards", [])
    board = state.get("community_cards", [])
    if EVALUATOR is None or len(hero) != 2 or len(board) < 3:
        return 0.5
    known = set(hero + board)
    deck = [r + s for r in RANKS for s in SUITS if r + s not in known]
    wins, started = 0.0, time.perf_counter()
    for _ in range(samples):
        if time.perf_counter() - started > 0.20:
            break
        run = random.sample(deck, 7 - len(board))
        villain, final_board = run[:2], board + run[2:]
        try:
            b = [Card.new(c) for c in final_board]
            h = EVALUATOR.evaluate(b, [Card.new(c) for c in hero])
            v = EVALUATOR.evaluate(b, [Card.new(c) for c in villain])
            wins += 1 if h < v else 0.5 if h == v else 0
        except (ValueError, TypeError):
            wins += 0.5
    return wins / max(1, samples)


def _update_fold_model(state):
    for index, item in enumerate(state.get("match_action_log", [])[-200:]):
        key = (item.get("hand_num"), index, item.get("bot_id"), item.get("action"))
        if key in SEEN_LOG:
            continue
        SEEN_LOG.add(key)
        if item.get("action") not in ("fold", "call", "raise", "all_in"):
            continue
        street = item.get("street", "unknown")
        fraction = item.get("amount", 0) / max(1, state.get("pot", 1))
        stat = FOLD_STATS.setdefault((street, "large" if fraction >= 0.75 else "small"), [2.0, 3.0])
        stat[0 if item.get("action") == "fold" else 1] += 1


def _fold_rate(state, fraction):
    stat = FOLD_STATS.get((state.get("street", "flop"), "large" if fraction >= 0.75 else "small"), [2.0, 3.0])
    mean = stat[0] / sum(stat)
    uncertainty = math.sqrt(max(0, mean * (1 - mean) / (sum(stat) + 1)))
    return max(0.02, min(0.95, mean - 0.67 * uncertainty))


def _postflop(state):
    _update_fold_model(state)
    equity = _equity(state)
    pot = max(1, int(state.get("pot", 1)))
    owed = int(state.get("amount_owed", 0))
    stack = int(state.get("your_stack", 0))
    in_position = state.get("seat_to_act") == state.get("button_seat")
    adjusted = equity * (1.02 if in_position else 0.86)

    if owed:
        needed = owed / max(1, pot + owed)
        if adjusted < needed * 0.90:
            if adjusted < 0.35:
                return {"action": "fold"}
            if random.random() < 0.25:
                amount = min(stack, max(int(state.get("min_raise_to", 0)), pot // 2))
                return {"action": "raise", "amount": amount}
            return {"action": "fold"}
        if adjusted > 0.62 and random.random() < 0.18:
            amount = min(stack, max(int(state.get("min_raise_to", 0)), pot * 2 // 3))
            return {"action": "raise", "amount": amount}
        return {"action": "call"}

    if adjusted < 0.28:
        return {"action": "check"}
    best_ev, best_bet = adjusted * pot, 0
    for fraction in (0.33, 0.50, 0.75, 1.00):
        bet = min(stack, max(1, int(pot * fraction)))
        fold = _fold_rate(state, fraction)
        called_equity = max(0, adjusted - 0.05)
        ev = fold * pot + (1 - fold) * (called_equity * (pot + 2 * bet) - bet)
        if ev > best_ev and ev > 0:
            best_ev, best_bet = ev, bet
    if best_bet:
        return {"action": "raise", "amount": max(int(state.get("min_raise_to", 0)), best_bet)}
    return {"action": "check"}


def decide(game_state: dict) -> dict:
    if game_state.get("type") == "warmup":
        return {"action": "check"}
    try:
        if game_state.get("street") == "preflop":
            return _preflop(game_state)
        return _postflop(game_state)
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError):
        return {"action": "check"} if game_state.get("can_check") else {"action": "fold"}
