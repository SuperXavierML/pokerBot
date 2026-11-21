"""Heads-up bot: bounded weighted equity and observed opponent responses.

Tables are snapshots of starting_hand_rankings.txt and pushfold_10bb.txt.
Embedded data keep this single-file entry portable inside the tournament sandbox.
Only the supplied 10bb chart is available; using it below 10bb is an approximation.
No files are read or written during decisions. Strategy weights are heuristics,
not a solved equilibrium.
"""
import math
import random
import time
from collections import Counter, defaultdict
from itertools import combinations

try:
    from treys import Card, Evaluator
except ImportError:
    Card = Evaluator = None

RANKS = "23456789TJQKA"
SUITS = "shdc"
DECK = tuple(r + s for r in RANKS for s in SUITS)
CARD_CODES = {c: Card.new(c) for c in DECK} if Card else {}
EVALUATOR = Evaluator() if Evaluator else None
# hand -> (win percentage, tie percentage, cumulative dealt percentage)
STARTING_HAND_RANKINGS = {
    "AA": (84.93, 0.54, 0.45),
    "KK": (82.11, 0.55, 0.90),
    "QQ": (79.63, 0.58, 1.35),
    "JJ": (77.15, 0.63, 1.80),
    "TT": (74.66, 0.70, 2.26),
    "99": (71.66, 0.78, 2.71),
    "88": (68.71, 0.89, 3.16),
    "AKs": (66.21, 1.65, 3.46),
    "77": (65.72, 1.02, 3.92),
    "AQs": (65.31, 1.79, 4.22),
    "AJs": (64.39, 1.99, 4.52),
    "AKo": (64.46, 1.70, 5.42),
    "ATs": (63.48, 2.22, 5.73),
    "AQo": (63.50, 1.84, 6.63),
    "AJo": (62.53, 2.05, 7.54),
    "KQs": (62.40, 1.98, 7.84),
    "66": (62.70, 1.16, 8.29),
    "A9s": (61.50, 2.54, 8.59),
    "ATo": (61.56, 2.30, 9.50),
    "KJs": (61.47, 2.18, 9.80),
    "A8s": (60.50, 2.87, 10.10),
    "KTs": (60.58, 2.40, 10.40),
    "KQo": (60.43, 2.04, 11.31),
    "A7s": (59.38, 3.19, 11.61),
    "A9o": (59.44, 2.64, 12.51),
    "KJo": (59.44, 2.25, 13.42),
    "55": (59.64, 1.36, 13.87),
    "QJs": (59.07, 2.37, 14.17),
    "K9s": (58.63, 2.70, 14.47),
    "A5s": (58.06, 3.71, 14.78),
    "A6s": (58.17, 3.45, 15.08),
    "A8o": (58.37, 2.99, 15.98),
    "KTo": (58.49, 2.48, 16.89),
    "QTs": (58.17, 2.59, 17.19),
    "A4s": (57.13, 3.79, 17.49),
    "A7o": (57.16, 3.34, 18.40),
    "K8s": (56.79, 3.04, 18.70),
    "A3s": (56.33, 3.77, 19.00),
    "QJo": (56.90, 2.45, 19.90),
    "K9o": (56.40, 2.80, 20.81),
    "A5o": (55.74, 3.90, 21.71),
    "A6o": (55.87, 3.62, 22.62),
    "Q9s": (56.22, 2.88, 22.92),
    "K7s": (55.84, 3.38, 23.22),
    "JTs": (56.15, 2.74, 23.52),
    "A2s": (55.50, 3.74, 23.83),
    "QTo": (55.94, 2.68, 24.73),
    "44": (56.25, 1.53, 25.18),
    "A4o": (54.73, 3.99, 26.09),
    "K6s": (54.80, 3.67, 26.39),
    "K8o": (54.43, 3.17, 27.30),
    "Q8s": (54.41, 3.20, 27.60),
    "A3o": (53.85, 3.97, 28.50),
    "K5s": (53.83, 3.91, 28.80),
    "J9s": (54.11, 3.10, 29.11),
    "Q9o": (53.86, 2.99, 30.01),
    "JTo": (53.82, 2.84, 30.92),
    "K7o": (53.41, 3.54, 31.82),
    "A2o": (52.94, 3.96, 32.73),
    "K4s": (52.88, 3.99, 33.03),
    "Q7s": (52.52, 3.55, 33.33),
    "K6o": (52.29, 3.85, 34.23),
    "K3s": (52.07, 3.96, 34.53),
    "T9s": (52.37, 3.30, 34.84),
    "J8s": (52.31, 3.40, 35.14),
    "33": (52.83, 1.70, 35.59),
    "Q6s": (51.67, 3.86, 35.89),
    "Q8o": (51.93, 3.33, 36.80),
    "K5o": (51.25, 4.12, 37.70),
    "J9o": (51.63, 3.22, 38.61),
    "K2s": (51.23, 3.94, 38.91),
    "Q5s": (50.71, 4.11, 39.21),
    "T8s": (50.50, 3.65, 39.51),
    "K4o": (50.22, 4.20, 40.42),
    "J7s": (50.45, 3.74, 40.72),
    "Q4s": (49.76, 4.18, 41.02),
    "Q7o": (49.90, 3.72, 41.93),
    "T9o": (49.81, 3.43, 42.83),
    "J8o": (49.71, 3.55, 43.74),
    "K3o": (49.33, 4.18, 44.64),
    "Q6o": (48.99, 4.05, 45.55),
    "Q3s": (48.93, 4.16, 45.85),
    "98s": (48.85, 3.88, 46.15),
    "T7s": (48.65, 3.97, 46.45),
    "J6s": (48.57, 4.06, 46.75),
    "K2o": (48.42, 4.17, 47.66),
    "22": (49.38, 1.89, 48.11),
    "Q2s": (48.10, 4.13, 48.41),
    "Q5o": (47.95, 4.32, 49.32),
    "J5s": (47.82, 4.33, 49.62),
    "T8o": (47.81, 3.80, 50.52),
    "J7o": (47.72, 3.91, 51.43),
    "Q4o": (46.92, 4.40, 52.33),
    "97s": (46.99, 4.25, 52.63),
    "J4s": (46.86, 4.40, 52.94),
    "T6s": (46.80, 4.28, 53.24),
    "J3s": (46.04, 4.37, 53.54),
    "Q3o": (46.02, 4.38, 54.44),
    "98o": (46.06, 4.05, 55.35),
    "87s": (45.68, 4.50, 55.65),
    "T7o": (45.82, 4.15, 56.56),
    "J6o": (45.71, 4.26, 57.46),
    "96s": (45.15, 4.55, 57.76),
    "J2s": (45.20, 4.35, 58.06),
    "Q2o": (45.10, 4.37, 58.97),
    "T5s": (44.93, 4.55, 59.27),
    "J5o": (44.90, 4.55, 60.18),
    "T4s": (44.20, 4.65, 60.48),
    "97o": (44.07, 4.45, 61.38),
    "86s": (43.81, 4.84, 61.68),
    "J4o": (43.86, 4.63, 62.59),
    "T6o": (43.84, 4.48, 63.49),
    "95s": (43.31, 4.81, 63.80),
    "T3s": (43.37, 4.62, 64.10),
    "76s": (42.82, 5.08, 64.40),
    "J3o": (42.96, 4.61, 65.30),
    "87o": (42.69, 4.71, 66.21),
    "T2s": (42.54, 4.59, 66.51),
    "85s": (41.99, 5.10, 66.81),
    "96o": (42.10, 4.77, 67.72),
    "J2o": (42.04, 4.59, 68.62),
    "T5o": (41.85, 4.78, 69.53),
    "94s": (41.40, 4.90, 69.83),
    "75s": (40.97, 5.39, 70.13),
    "T4o": (41.05, 4.89, 71.04),
    "93s": (40.80, 4.91, 71.34),
    "86o": (40.69, 5.08, 72.24),
    "65s": (40.34, 5.57, 72.54),
    "84s": (40.10, 5.19, 72.85),
    "95o": (40.13, 5.06, 73.75),
    "T3o": (40.15, 4.87, 74.66),
    "92s": (39.97, 4.88, 74.96),
    "76o": (39.65, 5.33, 75.86),
    "74s": (39.10, 5.48, 76.16),
    "T2o": (39.23, 4.85, 77.07),
    "54s": (38.53, 5.84, 77.37),
    "85o": (38.74, 5.37, 78.28),
    "64s": (38.48, 5.70, 78.58),
    "83s": (38.28, 5.18, 78.88),
    "94o": (38.08, 5.17, 79.78),
    "75o": (37.67, 5.67, 80.69),
    "82s": (37.67, 5.18, 80.99),
    "73s": (37.30, 5.46, 81.29),
    "93o": (37.42, 5.18, 82.20),
    "65o": (37.01, 5.86, 83.10),
    "53s": (36.75, 5.86, 83.40),
    "63s": (36.68, 5.69, 83.71),
    "84o": (36.70, 5.47, 84.61),
    "92o": (36.51, 5.16, 85.52),
    "43s": (35.72, 5.82, 85.82),
    "74o": (35.66, 5.77, 86.72),
    "72s": (35.43, 5.43, 87.02),
    "54o": (35.07, 6.16, 87.93),
    "64o": (35.00, 6.01, 88.83),
    "52s": (34.92, 5.83, 89.14),
    "62s": (34.83, 5.66, 89.44),
    "83o": (34.74, 5.46, 90.34),
    "42s": (33.91, 5.82, 90.64),
    "82o": (34.08, 5.48, 91.55),
    "73o": (33.71, 5.76, 92.45),
    "53o": (33.16, 6.19, 93.36),
    "63o": (33.06, 6.01, 94.26),
    "32s": (33.09, 5.78, 94.57),
    "43o": (32.06, 6.15, 95.47),
    "72o": (31.71, 5.74, 96.38),
    "52o": (31.19, 6.18, 97.28),
    "62o": (31.07, 5.99, 98.19),
    "42o": (30.11, 6.16, 99.09),
    "32o": (29.23, 6.12, 100.00),
}
SB_OPEN_SHOVE_10BB = frozenset("AA AKs AQs AJs ATs A9s A8s A7s A6s A5s A4s A3s A2s AKo KK KQs KJs KTs K9s K8s K7s K6s K5s K4s K3s K2s AQo KQo QQ QJs QTs Q9s Q8s Q7s Q6s Q5s Q4s Q3s Q2s AJo KJo QJo JJ JTs J9s J8s J7s J6s J5s J4s J3s ATo KTo QTo JTo TT T9s T8s T7s T6s T5s T4s A9o K9o Q9o J9o T9o 99 98s 97s 96s 95s A8o K8o Q8o J8o T8o 98o 88 87s 86s 85s 84s A7o K7o 97o 87o 77 76s 75s 74s A6o K6o 76o 66 65s 64s 63s A5o K5o 65o 55 54s 53s A4o K4o 44 43s A3o K3o 33 A2o K2o 22".split())
BB_CALL_SHOVE_10BB = frozenset("AA AKs AQs AJs ATs A9s A8s A7s A6s A5s A4s A3s A2s AKo KK KQs KJs KTs K9s K8s K7s K6s K5s K4s K3s K2s AQo KQo QQ QJs QTs Q9s Q8s Q7s Q6s AJo KJo QJo JJ JTs J9s J8s ATo KTo QTo JTo TT T9s A9o K9o Q9o J9o 99 A8o K8o 88 A7o K7o 77 A6o K6o 66 A5o 55 A4o 44 A3o 33 A2o 22".split())
PUSHFOLD_CHARTS = {10: (SB_OPEN_SHOVE_10BB, BB_CALL_SHOVE_10BB)}
OPPONENT_STATS = defaultdict(Counter)
RESPONSE_STATS = defaultdict(Counter)
RANGE_INFO = {}
PENDING = []
DIAGNOSTICS = Counter()
LAST_EQUITY = {}
DATA_STATUS = {}


def _hand_label(cards):
    a, b = sorted(cards, key=lambda c: RANKS.index(c[0]), reverse=True)
    return a[0] + b[0] + ("" if a[0] == b[0] else "s" if a[1] == b[1] else "o")


def _matrix_score(cards):
    win, tie, _ = STARTING_HAND_RANKINGS[_hand_label(cards)]
    return win + tie / 2


def _validate_data():
    expected = {_hand_label(c) for c in combinations(DECK, 2)}
    DATA_STATUS.update(rankings=set(STARTING_HAND_RANKINGS) == expected,
                       shove_grid=len(SB_OPEN_SHOVE_10BB) == 114,
                       call_grid=len(BB_CALL_SHOVE_10BB) == 70, treys=False)
    if EVALUATOR:
        board = [CARD_CODES[c] for c in ("2c", "3d", "7h", "9s", "Tc")]
        DATA_STATUS["treys"] = (
            EVALUATOR.evaluate(board, [CARD_CODES["As"], CARD_CODES["Ah"]])
            < EVALUATOR.evaluate(board, [CARD_CODES["Ks"], CARD_CODES["Qh"]]))
    for name, valid in DATA_STATUS.items():
        if not valid:
            DIAGNOSTICS["data_" + name] += 1


_validate_data()


def _opponent(state):
    return next((p for p in state.get("players", [])
                 if p.get("bot_id") != state.get("your_bot_id")), {})


def _safe(state):
    return {"action": "check" if state.get("amount_owed", 0) == 0
            and state.get("can_check", True) else "fold"}


def _effective_bb(state):
    """Reconstruct starting stacks from public contributions, including antes."""
    contributions = Counter()
    street_bets = Counter()
    for a in state.get("action_log", []):
        who, street = a.get("bot_id"), a.get("street", "preflop")
        key = (who, street)
        amount, action = int(a.get("amount", 0)), a.get("action")
        if action in ("raise", "all_in"):
            contributions[who] += max(0, amount - street_bets[key])
            street_bets[key] = max(street_bets[key], amount)
        elif action in ("call", "small_blind", "big_blind", "ante"):
            contributions[who] += amount
            if action != "ante":
                street_bets[key] += amount
    hero = state.get("your_bot_id")
    opp = _opponent(state)
    own = state.get("your_stack", 0) + max(
        contributions[hero], state.get("your_bet_this_street", 0))
    other = opp.get("stack", state.get("your_stack", 0)) + max(
        contributions[opp.get("bot_id")], opp.get("bet_this_street", 0))
    return min(own, other) / max(1, state.get("blinds", {}).get("bb", 100))


def _context(state):
    highest, raises, calls = 0, 0, 0
    for a in state.get("action_log", []):
        if a.get("street", "preflop") != "preflop":
            continue
        action, amount = a.get("action"), a.get("amount", 0)
        if action in ("small_blind", "big_blind"):
            highest = max(highest, amount)
        elif action in ("raise", "all_in"):
            if amount > highest:
                raises += 1
                highest = amount
            elif raises == 0:
                calls += 1
        elif action == "call" and raises == 0:
            calls += 1
    if raises >= 3:
        return "4bet"
    if raises == 2:
        return "3bet"
    if raises == 1:
        return "limp_raise" if calls else "open"
    return "limp" if calls else (
        "button_open" if state.get("seat_to_act") == state.get("button_seat") else "bb_open")


def _facing_shove(state):
    opp = _opponent(state)
    return bool(state.get("amount_owed", 0) and
                (opp.get("is_all_in") or opp.get("state") == "all_in"
                 or opp.get("stack") == 0
                 or state.get("amount_owed", 0) >= state.get("your_stack", 0)))


def _legal_raise(state, desired):
    opp = _opponent(state)
    current = int(state.get("current_bet", 0))
    maximum = int(state.get("your_stack", 0)) + int(state.get("your_bet_this_street", 0))
    if maximum <= current or opp.get("is_all_in") or opp.get("state") == "all_in" or opp.get("stack") == 0:
        return None
    return min(maximum, max(current + 1, int(state.get("min_raise_to", 0)), int(desired)))


def _raise_action(state, total):
    maximum = state.get("your_stack", 0) + state.get("your_bet_this_street", 0)
    return {"action": "all_in"} if total >= maximum else {"action": "raise", "amount": total}


def _raise_probability(score, cutoff):
    return max(0.0, min(1.0, (score - cutoff + 4) / 12))


def _preflop(state):
    score = _matrix_score(state["your_cards"])
    hand = _hand_label(state["your_cards"])
    depth, context = _effective_bb(state), _context(state)
    owed, pot = _call_geometry(state)
    button = state.get("seat_to_act") == state.get("button_seat")
    debug = dict(method="preflop_table", samples=0, equity=score / 100,
                 fold_probability=0., action_evs={"fold": 0.})
    # An effective all-in is a call/fold decision, at ANY stack depth.
    if _facing_shove(state):
        equity = _preflop_shove_equity(state)
        ev = equity * (pot + owed) - owed
        result = {"action": "call"} if ev >= 0 else _safe(state)
        result["debug"] = dict(LAST_EQUITY, pot_odds=owed / max(1, pot + owed),
                               fold_probability=0., action_evs={"fold": 0., "call": round(ev, 3)})
        return result
    if depth <= 10 and button and context == "button_open":
        result = {"action": "all_in"} if hand in PUSHFOLD_CHARTS[10][0] else _safe(state)
        result["debug"] = dict(debug, method="pushfold_10bb")
        return result
    cutoff = {"button_open": 42, "bb_open": 45, "limp": 44,
              "open": 53, "limp_raise": 55, "3bet": 62, "4bet": 72}[context]
    bb = max(1, state.get("blinds", {}).get("bb", 100))
    raised = context in ("open", "limp_raise", "3bet", "4bet")
    desired = 2.25 * bb if context in ("button_open", "bb_open") else (
        3 * bb if context == "limp" else
        (3 if button else 3.75) * state.get("current_bet", bb))
    total = _legal_raise(state, desired)
    premium = hand in ("AA", "KK", "QQ", "AKs", "AKo")
    if hand == "AA" and context == "4bet":
        total = _legal_raise(state, state.get("your_stack", 0) + state.get("your_bet_this_street", 0)
                             if depth <= 40 else 2.5 * state.get("current_bet", bb))
    allow_raise = True
    if 10 < depth <= 25 and raised and total is not None:
        geometry = _bet_geometry(state, total)
        commitment = geometry["risk"] / max(1, state.get("your_stack", 0))
        remaining_spr = max(0, state.get("your_stack", 0) - geometry["risk"]) / geometry["final_pot"]
        debug.update(proposed_total=total, commitment=commitment, remaining_spr=remaining_spr)
        if premium and (commitment >= .3 or remaining_spr <= 1):
            total = _legal_raise(state, state.get("your_stack", 0) + state.get("your_bet_this_street", 0))
        elif commitment >= .25 or remaining_spr <= 1.5:
            # Marginal hands do not commit themselves with an automatic 3.75x raise.
            allow_raise = score >= 60
            total = _legal_raise(state, (2.2 if button else 2.5) * state.get("current_bet", bb))
    if raised and EVALUATOR is not None and DATA_STATUS.get("treys"):
        candidates = [total] if total is not None and allow_raise else []
        equities = _equity_estimates(state, candidates, samples=480)
        call_ev = equities[0] * (pot + owed) - owed
        best_ev = max(0., call_ev)
        result = {"action": "call"} if call_ev >= 0 else _safe(state)
        action_evs = {"fold": 0., "call": round(call_ev, 3)}
        fold = 0.
        details = {}
        if candidates:
            geometry = _bet_geometry(state, total)
            fold, call, raise_p = _response_probabilities(state, geometry)
            future = min(state.get("your_stack", 0), owed + _opponent(state).get("stack", 0))
            reraised_ev = max(-geometry["risk"], equities[2] * (pot + 2 * future - owed) - future)
            ev = (fold * pot + call * (equities[1] * geometry["final_pot"] - geometry["risk"])
                  + raise_p * reraised_ev)
            action_evs["raise_" + str(total)] = round(ev, 3)
            details[str(total)] = dict(geometry, fold_probability=fold, ev=ev)
            if ev > best_ev:
                result = _raise_action(state, total)
        result["debug"] = dict(debug, **{k: v for k, v in LAST_EQUITY.items() if k not in debug})
        result["debug"].update(LAST_EQUITY, action_evs=action_evs,
                               fold_probability=fold if result["action"] in ("raise", "all_in") else 0.,
                               candidates=details)
        return result
    if total is not None and allow_raise and (
            premium or random.random() < _raise_probability(score, cutoff)):
        result = _raise_action(state, total)
    elif not owed:
        result = _safe(state)
    else:
        # Table equity is a reference, not a claim of equity against a tight raise.
        reference = max(0., score / 100 - (.08 if raised else 0.))
        ev = reference * (pot + owed) - owed
        debug["action_evs"]["call"] = round(ev, 3)
        result = {"action": "call"} if score >= cutoff - 5 and ev >= 0 else _safe(state)
    result["debug"] = debug
    return result


def _call_geometry(state):
    owed = min(state.get("your_stack", 0), state.get("amount_owed", 0))
    capacity = state.get("your_bet_this_street", 0) + state.get("your_stack", 0)
    uncalled = max(0, _opponent(state).get("bet_this_street", state.get("current_bet", 0)) - capacity)
    return owed, max(0, state.get("pot", 0) - uncalled)


def _preflop_shove_equity(state):
    if EVALUATOR is not None and DATA_STATUS.get("treys"):
        return _equity_estimates(state, samples=640)[0]
    # Explicit conservative range proxy, NOT the random-hand table probability.
    hand = _hand_label(state["your_cards"])
    equity = {"AA": .78, "KK": .64, "QQ": .54, "JJ": .48,
              "AKs": .46, "AKo": .43}.get(hand, max(.12, _matrix_score(state["your_cards"]) / 100 - .25))
    LAST_EQUITY.clear()
    LAST_EQUITY.update(method="preflop_conservative_no_treys", samples=0, equity=equity,
                       exact=False, computation_fallback=True)
    DIAGNOSTICS["computation_fallback"] += 1
    return equity

def _signature(a):
    return (a.get("bot_id"), a.get("street"), a.get("action"), int(a.get("amount", 0)))


def _bucket(fraction):
    return min((0.33, 0.5, 0.75, 1.0, 2.0), key=lambda x: abs(x - fraction))


def _update_fold_model(state):
    """Consume pending responses once, including terminal actions next hand."""
    current_key = state.get("hand_id")
    current_num = state.get("hand_num")
    for pending in list(PENDING):
        same = (pending["hand_id"] == current_key if pending["hand_id"] is not None
                else pending["hand_num"] == current_num)
        actions = state.get("action_log", []) if same else [
            a for a in state.get("match_action_log", [])
            if pending["hand_num"] is not None and a.get("hand_num") == pending["hand_num"]]
        signatures = [_signature(a) for a in actions]
        anchor = pending["anchor"]
        matches = [i for i in range(len(signatures) - len(anchor) + 1)
                   if signatures[i:i + len(anchor)] == anchor]
        if len(matches) == 1:
            start = matches[0] + len(anchor)
            for a in actions[start:]:
                if a.get("street") != pending["street"]:
                    break
                if a.get("bot_id") != pending["opponent"]:
                    continue
                response = a.get("action")
                if response == "all_in":
                    response = "raise" if a.get("amount", 0) > pending["total"] else "call"
                if response in ("fold", "call", "raise"):
                    key = (pending["opponent"], pending["street"], pending["bucket"])
                    OPPONENT_STATS[key][response] += 1
                    OPPONENT_STATS[key]["opportunities"] += 1
                    cohort = RESPONSE_STATS[pending["response_key"]]
                    cohort[response] += 1
                    cohort["opportunities"] += 1
                    PENDING.remove(pending)
                    break
        if pending in PENDING and not same:
            DIAGNOSTICS["unknown_response"] += 1
            PENDING.remove(pending)


def _remember_decision(state, result):
    if result.get("action") not in ("raise", "all_in"):
        return
    if state.get("hand_id") is None and state.get("hand_num") is None:
        DIAGNOSTICS["untracked_hand"] += 1
        return
    total = result.get("amount", state.get("your_stack", 0) + state.get("your_bet_this_street", 0))
    if total <= state.get("current_bet", 0):
        return
    own = {"bot_id": state.get("your_bot_id"), "street": state.get("street"),
           "action": "all_in" if total >= state.get("your_stack", 0) + state.get("your_bet_this_street", 0) else "raise",
           "amount": total}
    anchor = [_signature(a) for a in state.get("action_log", [])[-3:]] + [_signature(own)]
    PENDING.append(dict(hand_id=state.get("hand_id"), hand_num=state.get("hand_num"),
                        opponent=_opponent(state).get("bot_id"), street=state.get("street"),
                        anchor=anchor, total=total,
                        response_key=_response_key(state, _bet_geometry(state, total)),
                        bucket=_bucket((total - state.get("your_bet_this_street", 0))
                                       / max(1, state.get("pot", 0)))))


def _bet_geometry(state, total):
    """One shared accounting model for risk, opponent price and final pot."""
    opp = _opponent(state)
    invested = state.get("your_bet_this_street", 0)
    opponent_bet = opp.get("bet_this_street", state.get("current_bet", 0))
    opponent_call = min(opp.get("stack", 0), max(0, total - opponent_bet))
    matched_total = min(total, opponent_bet + opp.get("stack", 0))
    risk = min(state.get("your_stack", 0), max(0, matched_total - invested))
    final_pot = max(1, state.get("pot", 0) + risk + opponent_call)
    return dict(risk=risk, opponent_call=opponent_call, final_pot=final_pot,
                opponent_pot_odds=opponent_call / final_pot,
                kind="raise" if state.get("amount_owed", 0) else "bet")


def _response_key(state, geometry):
    calls = sum(a["action"] == "call" for a in _opponent_actions(state))
    return (_opponent(state).get("bot_id"), state.get("street"),
            geometry["kind"], min(calls, 2), round(geometry["opponent_pot_odds"] * 10))


def _response_probabilities(state, geometry):
    """Price-sensitive conservative prior, shrunk toward observed responses."""
    if not isinstance(geometry, dict):
        total = state.get("your_bet_this_street", 0) + geometry * state.get("pot", 0)
        geometry = _bet_geometry(state, total)
    price = geometry["opponent_pot_odds"]
    if geometry["opponent_call"] <= 0:
        return 0., 1., 0.
    actions = _opponent_actions(state)
    calls = sum(a["action"] == "call" for a in actions)
    aggression = sum(a["action"] == "raise" and a["street"] != "preflop" for a in actions)
    prior_fold = ((.10 if geometry["kind"] == "bet" else .055) + .65 * price)
    prior_fold *= .62 ** min(calls, 3) * .78 ** min(aggression, 2)
    overall = Counter()
    for (who, street, bucket), counts in OPPONENT_STATS.items():
        if who == _opponent(state).get("bot_id"):
            overall.update(counts)
    # Broad observations influence, but cannot erase the actual price/sequence.
    general = (overall["fold"] + 12 * prior_fold) / (overall["opportunities"] + 12)
    prior_fold = .8 * prior_fold + .2 * general
    local = RESPONSE_STATS[_response_key(state, geometry)]
    fold = (local["fold"] + 20 * prior_fold) / (local["opportunities"] + 20)
    prior_raise = .06 if geometry["kind"] == "bet" else .09
    raise_p = (local["raise"] + 20 * prior_raise) / (local["opportunities"] + 20)
    fold = max(.005, min(.85, fold))
    raise_p = min(1 - fold, raise_p)
    if (geometry["opponent_call"] >= _opponent(state).get("stack", 0)
            or geometry["risk"] >= state.get("your_stack", 0)):
        raise_p = 0.
    return fold, 1 - fold - raise_p, raise_p

def _features(cards, board):
    """Relative pair strength and kicker, with draws involving a hole card."""
    if not board:
        return _matrix_score(cards) / 100, 0.
    codes = [CARD_CODES[c] for c in board]
    score = EVALUATOR.evaluate(codes, [CARD_CODES[c] for c in cards])
    category = EVALUATOR.get_rank_class(score)
    ranks = [RANKS.index(c[0]) + 2 for c in cards]
    public = [RANKS.index(c[0]) + 2 for c in board]
    highest = max(public)
    if category == 8:
        if ranks[0] == ranks[1]:
            paired = ranks[0]
            strength = .70 if paired > highest else .43 if paired > min(public) else .28
            kicker = paired / 14
        else:
            paired = max((r for r in ranks if r in public), default=0)
            if paired:
                strength = .59 if paired == highest else .41 if paired > min(public) else .29
                kicker = max(r for r in ranks if r != paired) / 14
            else:
                strength, kicker = .18, max(ranks) / 14  # only the BOARD is paired
        strength += .055 * kicker
    elif category == 9:
        strength = .08 + .12 * max(ranks) / 14 + .025 * min(ranks) / 14
    else:
        strength = {0: 1., 1: 1., 2: .99, 3: .96, 4: .91,
                    5: .84, 6: .77, 7: .66}[category]
        strength += .025 * (1 - score / 7462)
        # Two pairs entirely on board are not a strong private holding.
        if category == 7 and sum(v >= 2 for v in Counter(public).values()) >= 2:
            if not any(r in public for r in ranks):
                strength = .22 + .04 * max(ranks) / 14
    draw = 0.
    if len(board) < 5:
        suits = Counter(c[1] for c in cards + board)
        if any(n == 4 and any(c[1] == suit for c in cards) for suit, n in suits.items()):
            draw += .17
        values = set(ranks + public)
        if 14 in values:
            values.add(1)
        hole_values = set(ranks) | ({1} if 14 in ranks else set())
        if any(len(values.intersection(range(low, low + 5))) == 4
               and hole_values.intersection(range(low, low + 5))
               and not set(range(low, low + 5)).intersection(hole_values).issubset(set(public))
               for low in range(1, 11)):
            draw += .10
    return min(1., strength), draw

def _opponent_actions(state):
    """Replay public amounts; annotate the action's price and prior aggression."""
    pot, bets, actions = 0, Counter(), []
    opponent = _opponent(state).get("bot_id")
    raises = Counter()
    own_raises = Counter()
    for a in state.get("action_log", []):
        street = a.get("street", "preflop")
        key = (a.get("bot_id"), street)
        action, amount = a.get("action"), a.get("amount", 0)
        highest = max((v for (who, s), v in bets.items() if s == street), default=0)
        added = max(0, amount - bets[key]) if action in ("raise", "all_in") else (
            amount if action in ("call", "small_blind", "big_blind", "ante") else 0)
        is_raise = action in ("raise", "all_in") and amount > highest
        if a.get("bot_id") == opponent and action in ("call", "raise", "all_in"):
            actions.append(dict(street=street, action="raise" if is_raise else "call",
                                size=added / max(1, pot), price=added / max(1, pot + added),
                                raises=raises[street], previous_bet=own_raises[street] > 0,
                                all_in=action == "all_in" or (a is state.get("action_log", [])[-1]
                                    and _opponent(state).get("is_all_in", False))))
            if is_raise:
                own_raises[street] += 1
        if is_raise:
            raises[street] += 1
        pot += added
        if action != "ante":
            bets[key] += added
    return actions


def _sigmoid(value):
    return 1 / (1 + math.exp(-max(-40, min(40, value))))


def _action_weight(state, cards, action, board):
    strength, draw = _features(cards, board)
    if action["street"] == "preflop":
        percentile = STARTING_HAND_RANKINGS[_hand_label(cards)][2]
        if action["all_in"] or (_facing_shove(state) and state.get("street") == "preflop"):
            depth = _effective_bb(state)
            if depth <= 10:
                return .95 if _hand_label(cards) in SB_OPEN_SHOVE_10BB else .02
            top = 8 if depth > 40 else 14 if depth > 25 else 24
            return .002 + _sigmoid((top - percentile) / 3)
        top = (65 if _opponent(state).get("seat") == state.get("button_seat") else 45)
        if action["raises"] >= 1:
            top = 18 if action["action"] == "raise" else 35
        return .025 + _sigmoid((top - percentile) / 10)
    # Each factor only describes THIS action. Prior street information is retained.
    threshold = .48 if action["action"] == "raise" else .32
    threshold += .13 * min(action["size"], 1.5)
    threshold += .07 * min(action["raises"], 2)
    if action["action"] == "call" and action["previous_bet"]:
        threshold += .10  # bet/call of a raise is a materially stronger line
    value = strength + .65 * draw
    bluff_floor = .025 if action["action"] == "raise" else .012
    return bluff_floor + _sigmoid((value - threshold) / .085)


def _combo_row(state, combo, actions):
    cards, board = list(combo), state.get("community_cards", [])
    weight = 1.
    for action in actions:
        visible = board[:{"preflop": 0, "flop": 3, "turn": 4, "river": 5}.get(action["street"], 0)]
        weight *= _action_weight(state, cards, action, visible)
    # Missing logs do not turn a deep shove into a random range.
    if not actions and state.get("street") == "preflop" and _facing_shove(state):
        weight *= _action_weight(state, cards, dict(street="preflop", all_in=True), [])
    strength, draw = _features(cards, board)
    return combo, max(1e-12, weight), strength, draw


def _range(state, deadline):
    board = state.get("community_cards", [])
    available = [c for c in DECK if c not in state["your_cards"] + board]
    combos = list(combinations(available, 2))
    random.shuffle(combos)  # Any interrupted subset is random, never a rank-ordered prefix.
    actions, rows = _opponent_actions(state), []
    for combo in combos:
        if time.perf_counter() >= deadline:
            break
        rows.append(_combo_row(state, combo, actions))
    RANGE_INFO.update(complete=len(rows) == len(combos), combinations=len(combos))
    return rows



def _equity_estimates(state, totals=(), samples=1600):
    """Weighted common samples; reserve time for a legal random fallback."""
    started = time.perf_counter()
    budget = min(.65, max(.002, state.get("time_limit_ms", 2000) / 1000 * .60))
    deadline, primary_deadline = started + budget, started + budget * .72
    hero, board = state.get("your_cards", []), state.get("community_cards", [])
    LAST_EQUITY.clear()
    RANGE_INFO.clear()
    if EVALUATOR is None or not DATA_STATUS.get("treys"):
        raise ValueError("treys_unavailable")
    if len(hero) != 2 or len(board) not in (0, 3, 4, 5):
        raise ValueError("invalid_cards")
    rows = _range(state, started + budget * .40)
    range_complete = RANGE_INFO.get("complete", True)
    used_fallback = not rows or not range_complete
    deck = [c for c in DECK if c not in hero + board]
    hero_codes, board_codes = [CARD_CODES[c] for c in hero], [CARD_CODES[c] for c in board]
    river = len(board) == 5
    hero_river = EVALUATOR.evaluate(board_codes, hero_codes) if river else None
    sums = [[0., 0.] for _ in range(1 + 2 * len(totals))]
    completed, total_mass, squared_mass = 0, 0., 0.
    geometries = [_bet_geometry(state, total) for total in totals]
    if river or not range_complete:
        selected = list(rows)
        random.shuffle(selected)
        importance = True
    else:
        selected = random.choices(rows, weights=[r[1] for r in rows], k=samples) if rows else []
        importance = False
    def accumulate(row, weighted):
        nonlocal completed, total_mass, squared_mass
        combo, prior, strength, draw = row
        try:
            future = [] if river else random.sample([c for c in deck if c not in combo], 5 - len(board))
            final = board_codes + [CARD_CODES[c] for c in future]
            h = hero_river if river else EVALUATOR.evaluate(final, hero_codes)
            v = EVALUATOR.evaluate(final, [CARD_CODES[c] for c in combo])
            outcome = 1. if h < v else .5 if h == v else 0.
        except (ValueError, TypeError, KeyError):
            DIAGNOSTICS["invalid_simulation"] += 1
            return
        base_weight = prior if weighted else 1.
        weights = [base_weight]
        for geometry in geometries:
            threshold = .25 + .9 * geometry["opponent_pot_odds"]
            if geometry["kind"] == "raise":
                threshold += .12
            continuation = .015 + _sigmoid((strength + .65 * draw - threshold) / .09)
            raising = .005 + _sigmoid((strength - .79) / .055) + draw * .18
            weights.extend((base_weight * continuation, base_weight * raising))
        for accumulator, weight in zip(sums, weights):
            accumulator[0] += weight * outcome
            accumulator[1] += weight
        total_mass += base_weight
        squared_mass += base_weight * base_weight
        completed += 1
    for row in selected:
        if time.perf_counter() >= primary_deadline:
            used_fallback = True
            break
        accumulate(row, importance)
        # Worst-case standard error; precision for small weighted samples uses ESS.
        ess = total_mass * total_mass / max(1e-20, squared_mass)
        if not river and completed >= 400 and ess >= 400:
            break
    exact = river and range_complete and completed == len(rows) and bool(rows)
    if not completed:
        # Fresh UNIFORM legal combos, importance-weighted; unused reserved budget.
        actions = _opponent_actions(state)
        for _ in range(96):
            if time.perf_counter() >= deadline:
                break
            combo = tuple(random.sample(deck, 2))
            accumulate(_combo_row(state, combo, actions), True)
        used_fallback = True
    if not completed:
        # No fabricated equity: caller gets an explicit diagnostic safe decision.
        raise ValueError("no_valid_simulations")
    values = [max(0., min(1., win / mass)) if mass else .5 for win, mass in sums]
    method = ("river_exact" if exact else "river_random_sample" if river else
              "sampled_range_mc" if used_fallback else "weighted_mc")
    if used_fallback:
        DIAGNOSTICS["computation_fallback"] += 1
    LAST_EQUITY.update(method=method, samples=completed, exact=exact,
                       computation_fallback=used_fallback, equity=values[0],
                       effective_samples=round(total_mass ** 2 / max(1e-20, squared_mass), 1),
                       elapsed_ms=round(1000 * (time.perf_counter() - started), 2))
    return values

def _equity(state, samples=2000):
    try:
        return _equity_estimates(state, samples=samples)[0]
    except ValueError:
        return .5


def _candidate_totals(state):
    pot = max(1, state.get("pot", 0))
    current = state.get("current_bet", 0)
    owed = state.get("amount_owed", 0)
    return sorted({total for fraction in (.33, .5, .75, 1.)
                   for total in [_legal_raise(state, current + fraction * (pot + owed))]
                   if total is not None})


def _postflop(state):
    owed, pot = _call_geometry(state)
    totals = _candidate_totals(state)
    estimates = _equity_estimates(state, totals)
    equity = estimates[0]
    passive_ev = equity * (pot + owed) - owed
    best_ev = max(0., passive_ev) if owed else passive_ev
    best = ({"action": "call"} if passive_ev >= 0 else _safe(state)) if owed else _safe(state)
    action_evs = {"fold": 0.}
    action_evs["call" if owed else "check"] = round(passive_ev, 3)
    candidate_details = {}
    for index, total in enumerate(totals):
        geometry = _bet_geometry(state, total)
        risk, opponent_cost = geometry["risk"], geometry["opponent_call"]
        fold, call, raise_prob = _response_probabilities(state, geometry)
        called, raised = estimates[1 + 2 * index:3 + 2 * index]
        # If raised again: choose fold or continue against the stronger raise range.
        future = min(state.get("your_stack", 0), owed + _opponent(state).get("stack", 0))
        continue_ev = raised * (pot + 2 * future - owed) - future
        raise_ev = max(-risk, continue_ev)
        ev = fold * pot + call * (called * geometry["final_pot"] - risk) + raise_prob * raise_ev
        action_evs["raise_" + str(total)] = round(ev, 3)
        candidate_details[str(total)] = dict(geometry, fold_probability=round(fold, 5),
                                             call_equity=round(called, 5), raise_equity=round(raised, 5),
                                             ev=round(ev, 3),
                                             pure_bluff_break_even=risk / max(1, pot + risk))
        # A weak pair is only converted into a bluff when it beats check/call EV.
        if ev > best_ev:
            best_ev, best = ev, _raise_action(state, total)
    selected = best.get("amount", state.get("your_stack", 0) + state.get("your_bet_this_street", 0))
    selected_fold = candidate_details.get(str(selected), {}).get("fold_probability", 0.)
    best["debug"] = dict(LAST_EQUITY, ev=round(best_ev, 3), action_evs=action_evs,
                         fold_probability=selected_fold, candidates=candidate_details)
    return best

def decide(game_state: dict) -> dict:
    if game_state.get("type") == "warmup":
        return {"action": "check", "debug": {"data_status": DATA_STATUS}}
    try:
        _update_fold_model(game_state)
        if not all(DATA_STATUS.get(k) for k in ("rankings", "shove_grid", "call_grid")):
            raise ValueError("startup_data_invalid")
        result = _preflop(game_state) if game_state.get("street") == "preflop" else _postflop(game_state)
        if result.get("action") == "check" and game_state.get("amount_owed", 0):
            DIAGNOSTICS["illegal_check_prevented"] += 1
            result = _safe(game_state)
        _remember_decision(game_state, result)
        result.setdefault("debug", {})["diagnostics"] = dict(DIAGNOSTICS)
        return result
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError) as exc:
        DIAGNOSTICS["fallback"] += 1
        return dict(_safe(game_state), debug={"fallback": type(exc).__name__ + ": " + str(exc),
                                              "data_status": DATA_STATUS})
