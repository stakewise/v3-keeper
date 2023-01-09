# StakeWise oracles keeper V3

## Keeper

Keeper are responsible for collecting votes from StakeWise v3 oracles, validating and sending to the oracle contract.

Keeper is an oracle that aggregates votes that were submitted by all the StakeWise v3 oracles and submits the update transaction.
It helps save the gas cost and stability as there is no need for every oracle to submit vote.
