# Week 3: Mixed strategies

## Mixed strategies

A mixed strategy $\sigma_i$ is a probability distribution over $S_i$. Payoffs are expected payoffs:
$$u_i(\sigma) = \sum_{s \in S} \Big(\prod_{j \in N} \sigma_j(s_j)\Big)\, u_i(s).$$
A mixed-strategy Nash equilibrium is a profile $\sigma^*$ in which every $\sigma_i^*$ is a best response to $\sigma_{-i}^*$.

**Theorem (Nash, 1950).** Every finite game has at least one Nash equilibrium in mixed strategies.

## The indifference principle

If $\sigma_i^*$ puts positive probability on several pure strategies, player $i$ must be indifferent between all of them, given $\sigma_{-i}^*$. Otherwise shifting weight to the better one would raise the payoff.

## Recipe for a 2x2 game with a fully mixed equilibrium

Let player 1 play the top row with probability $p$ and player 2 play the left column with probability $q$.
1. Choose $p$ so that **player 2** is indifferent between left and right.
2. Choose $q$ so that **player 1** is indifferent between top and bottom.
3. Equilibrium payoffs follow by plugging $p$ and $q$ into the expected payoffs.

Note the swap: each player's probability is pinned down by the *other* player's indifference.

## Example: Matching pennies

Player 2 is indifferent when $-p + (1-p) = p - (1-p)$, so $p = 1/2$. By symmetry $q = 1/2$. Both players get expected payoff $0$.

## Example: Battle of the sexes

|       | O    | F    |
|-------|------|------|
| **O** | 3, 1 | 0, 0 |
| **F** | 0, 0 | 1, 3 |

Pure equilibria: (O, O) and (F, F). Mixed: player 2 indifferent when $1 \cdot p = 3(1-p)$, so $p = 3/4$; player 1 indifferent when $3q = 1 - q$, so $q = 1/4$. Expected payoff of player 1 in the mixed equilibrium: $3q = 3/4$.
