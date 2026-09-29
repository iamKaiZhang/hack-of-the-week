# Week 2: Nash equilibrium

## Definition

A strategy profile $s^* = (s_1^*, \dots, s_n^*)$ is a (pure-strategy) **Nash equilibrium** if no player can gain by deviating alone:
$$u_i(s_i^*, s_{-i}^*) \ge u_i(s_i, s_{-i}^*) \quad \text{for all } i \in N \text{ and all } s_i \in S_i.$$
Equivalently, every $s_i^*$ is a best response to $s_{-i}^*$.

## Finding pure equilibria in a matrix

Underline player 1's best payoff in each column and player 2's best payoff in each row. Cells where both payoffs are underlined are the pure Nash equilibria.

## Examples

**Coordination game.** Two equilibria, (A, A) and (B, B).

|       | A    | B    |
|-------|------|------|
| **A** | 2, 2 | 0, 0 |
| **B** | 0, 0 | 1, 1 |

**Matching pennies.** No pure-strategy equilibrium.

|       | H     | T     |
|-------|-------|-------|
| **H** | 1, -1 | -1, 1 |
| **T** | -1, 1 | 1, -1 |

## Relation to dominance

- A strictly dominated strategy is never part of a Nash equilibrium.
- Every Nash equilibrium survives IESDS.
- If every player has a strictly dominant strategy, the profile of these strategies is a Nash equilibrium. (Exercise: show that it is the only one.)

A game can have zero, one, or several pure equilibria, so "the" equilibrium only makes sense once uniqueness is established.
