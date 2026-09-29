# Week 1: Strategic games and dominance

## Strategic (normal-form) games

A strategic game consists of
- a finite set of players $N = \{1, \dots, n\}$,
- for each player $i$ a nonempty set of strategies $S_i$,
- for each player $i$ a payoff function $u_i : S \to \mathbb{R}$, where $S = S_1 \times \dots \times S_n$.

We write $s = (s_i, s_{-i})$ to separate player $i$'s strategy from the strategies of all other players.
Two-player games with finite strategy sets are written as payoff matrices: the row player is player 1, the column player is player 2, and each cell lists $(u_1, u_2)$.

## Best responses

Strategy $s_i$ is a best response to $s_{-i}$ if $u_i(s_i, s_{-i}) \ge u_i(s_i', s_{-i})$ for all $s_i' \in S_i$.

## Dominance

- $s_i$ **strictly dominates** $s_i'$ if $u_i(s_i, s_{-i}) > u_i(s_i', s_{-i})$ for every $s_{-i}$.
- $s_i$ **weakly dominates** $s_i'$ if $u_i(s_i, s_{-i}) \ge u_i(s_i', s_{-i})$ for every $s_{-i}$, with strict inequality for at least one $s_{-i}$.
- $s_i$ is **strictly dominant** if it strictly dominates every other strategy of player $i$.

A rational player never plays a strictly dominated strategy.

## Iterated elimination of strictly dominated strategies (IESDS)

1. Remove every strictly dominated strategy of every player.
2. Repeat on the reduced game until no strategy is strictly dominated.

The set of strategies that survives IESDS does not depend on the order of elimination.
This is **not** true for weak dominance: the outcome of iterated elimination of weakly dominated strategies can depend on the order, and it can remove Nash equilibria. In this course, "IESDS" always means strict dominance.

## Example: Prisoner's dilemma

|       | C      | D      |
|-------|--------|--------|
| **C** | -1, -1 | -3, 0  |
| **D** | 0, -3  | -2, -2 |

D strictly dominates C for both players, so IESDS leaves the single profile (D, D).
