# Ability System

## Core Idea

This project handles timing-based effects with an event-driven queue.

1. A game event occurs.
2. The engine emits an `AbilityEvent`.
3. Matching abilities are collected.
4. Abilities resolve one by one in FIFO order.
5. If resolution creates new events, they are appended to the queue.

This keeps timing rules explicit and makes it easier to extend card support one card at a time.

## Why This Shape Works

The hard part in card game engines is usually not the effect itself, but the order of:

- when a trigger is created
- when players may choose targets or costs
- when combat continues after a change in board state

Using an event queue lets us separate:

- event detection
- player choice requests
- effect resolution
- follow-up events

## Current Player Choice Model

Whenever the engine needs player input, it uses `choice_request`.

Current uses:

- targeted abilities
- hand discard cost selection
- blocker selection
- intercept selection

For tests or simple local runs, the first legal option can be auto-selected.

## Current Implemented Events

- `unit_entered`
- `unit_attacked`
- `player_attack_success`
- `unit_overclocked`
- `turn_end`

## Current Resolution Rules

- Attack-triggered abilities resolve immediately after attack declaration.
- Blocker selection happens only after those attack-triggered abilities finish.
- If no legal blocker remains at that point, the battle is treated as `no_block`.
- Intercepts are only offered when a battle is actually going to happen.
- Intercepts are requested with `choice_request`, attacker first and defender second.
- After that, attacker and defender continue alternating until both pass consecutively.
- A used intercept leaves `trigger_zone` and moves to the discard pile after resolution.

## Current Implemented Effect Shapes

- on-enter damage
- on-enter BP gain
- on-enter enemy BP reduction
- on-attack BP gain
- on-attack damage
- discard-cost-then-buff
- player attack success consuming enemy trigger zone
- overclock stat change
- end-turn readiness recovery
- battle-time intercept BP modifiers

## Trigger Rules Implemented

- Trigger cards are checked from left to right.
- A trigger that resolves successfully is consumed and sent to discard.
- A trigger that would have no effect stays in `trigger_zone`.

## Practical Extension Strategy

When adding a new card, implement it in this order:

1. Define the event timing that should create the effect.
2. Define whether player choice is needed.
3. Define the exact board mutation.
4. Add a focused regression test for timing and resolution order.

This keeps the engine understandable even as the card pool grows.
