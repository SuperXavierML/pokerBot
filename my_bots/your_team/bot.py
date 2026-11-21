"""
Bot template. Copy this folder to my_bots/<your_team>/ and write decide().

  - decide() is called once per decision and has 2 seconds to return, or your
    bot folds. Crashes and invalid actions also fold; your bot stays in the game.
  - You may use the Python 3.10 standard library, eval7, numpy, scipy, treys
    and scikit-learn. Nothing else is installed in the sandbox.
  - No network, no file writes, no subprocesses, no eval/exec. You may read
    your own data/ folder, at import time only.
  - Check your bot before submitting:  make validate BOT=my_bots/<your_team>

The full list of what decide() receives is in the README ("What your bot
sees"); the most useful keys are summarised below.

RETURN FORMAT:
  {"action": "fold"}
  {"action": "check"}                       # only when can_check is True
  {"action": "call"}
  {"action": "raise", "amount": 1200}       # amount = your TOTAL bet this street
  {"action": "all_in"}

CARDS are strings like "As" (ace of spades) or "Td" (ten of diamonds).
"""

import random  # noqa: F401  (seeded per match, so a seeded match replays exactly)


def decide(game_state: dict) -> dict:
    """
    game_state (the most useful keys):
      your_cards        ["Ah", "Kh"]
      community_cards   [] preflop, then 3, 4, 5 cards
      street            "preflop" | "flop" | "turn" | "river"
      pot, current_bet, min_raise_to, amount_owed, can_check
      your_stack, your_bet_this_street, your_bot_id
      blinds            {"sb", "bb", "ante"} for this hand (they rise every 20 hands)
      hand_num          hand number in this match, from 0
      button_seat, sb_seat, bb_seat, seat_to_act
      players           public info per seat: seat, bot_id, stack, state, bet_this_street, ...
      action_log        every action this hand: {"seat", "bot_id", "action", "amount", "street"}
      match_action_log  the last 200 actions across the match, with "hand_num", plus
                        {"action": "show", "cards": [...]} for each player at a showdown

    Debugging: anything you print() is saved with the decision, and you can add
    a JSON-serialisable "debug" value to what you return, e.g.
    {"action": "call", "debug": {"equity": 0.4}}. Run with: python3 play.py --show
    """
    if game_state.get("type") == "warmup":     # one call before hand 1; load things here if you like
        return {"action": "check"}

    # ── Your strategy goes here. This example is deliberately simple. ──────────
    cards = game_state["your_cards"]
    pot = game_state["pot"]
    owed = game_state["amount_owed"]

    ranks = [c[0] for c in cards]
    if ranks[0] == ranks[1] and ranks[0] in "AKQJ":           # big pocket pair: raise
        raise_to = max(game_state["min_raise_to"], game_state["current_bet"] + pot)
        return {"action": "raise", "amount": raise_to}
    if game_state["can_check"]:
        return {"action": "check"}
    if owed <= pot * 0.25:                                     # cheap to continue: call
        return {"action": "call"}
    return {"action": "fold"}


def is_flush(cards: list[str], community_cards: list[str]) -> int:
    """
    Return the best five-card flush encoding, or the closest known suited cards.
    """
    encoded_cards = [
        card_to_int(card) for card in cards + community_cards
    ]
    if not encoded_cards:
        return 0

    suit_values = {mask(value, 1111) for value in encoded_cards}
    suited_cards = [
        sorted(
            (value for value in encoded_cards if mask(value, 1111) == suit),
            reverse=True,
        )
        for suit in suit_values
    ]
    best_suit = max(
        suited_cards,
        key=lambda values: (len(values), sum(values[:5])),
    )
    return sum(best_suit[:5])


def is_straight(cards: list[str], community_cards: list[str]) -> int:
    """Return the best straight encoding, or the closest known rank run."""
    best_card_by_rank = {}
    for card in cards + community_cards:
        rank = "23456789TJQKA".index(card[0])
        encoded_card = card_to_int(card)
        if rank not in best_card_by_rank or encoded_card > best_card_by_rank[rank]:
            best_card_by_rank[rank] = encoded_card

    rank_windows = [
        (tuple(range(start, start + 5)), start + 4)
        for start in range(9)
    ]
    rank_windows.append(((12, 0, 1, 2, 3), 3))

    best_window, _ = max(
        rank_windows,
        key=lambda window: (
            sum(rank in best_card_by_rank for rank in window[0]),
            window[1],
            sum(
                best_card_by_rank[rank]
                for rank in window[0]
                if rank in best_card_by_rank
            ),
        ),
    )
    return sum(
        best_card_by_rank[rank]
        for rank in best_window
        if rank in best_card_by_rank
    )


def mask(value: int, bitmask: int) -> int:
    """Keep decimal digit positions selected by a 0/1 mask."""
    value_digits = str(value)
    mask_digits = str(bitmask)
    if value < 0 or bitmask < 0:
        raise ValueError("value and bitmask must be non-negative")
    if len(mask_digits) > len(value_digits):
        raise ValueError("bitmask cannot have more digits than value")
    mask_digits = mask_digits.zfill(len(value_digits))
    if any(bit not in "01" for bit in mask_digits):
        raise ValueError("bitmask must contain only 0 and 1")
    return int("".join(
        digit if bit == "1" else "0"
        for digit, bit in zip(value_digits, mask_digits)
    ))


def card_to_int(card: str) -> int:
    rank = card[0]
    suit = card[1]
    rank_value = "23456789TJQKA".index(rank)
    suit_value = "hdsc".index(suit)
    return (111100000000000000000) + 10000 * (10 ** rank_value) + (10 ** suit_value)