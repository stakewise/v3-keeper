# StakeWise V3 keeper

## Introduction

Keeper is responsible for collecting votes from StakeWise v3 oracles, validating and sending them to the Keeper contract.

Keeper is a service that aggregates votes that were submitted by all the StakeWise v3 oracles and submits the resulted transaction.
It helps save gas cost and stability as there is no need for every oracle to submit a vote.

The voting process consists of the following steps:

1. Oracles prepare and sign a vote
2. Keeper fetches oracles configuration from contacts and fetches every oracle vote
3. Keeper validates votes, concat them and submit transaction into the contract

## Dependencies

### Execution node

The execution node is used to fetch oracles configuration from Oracle's contract and to submit transactions.
Any execution client that supports [ETH Execution API specification](https://ethereum.github.io/execution-apis/api-documentation/) can be used:

- [Nethermind](https://launchpad.ethereum.org/en/nethermind) (Ethereum, Gnosis)
- [Besu](https://launchpad.ethereum.org/en/besu) (Ethereum)
- [Erigon](https://launchpad.ethereum.org/en/erigon) (Ethereum)
- [Geth](https://launchpad.ethereum.org/en/geth) (Ethereum)


## Usage

### Step 1. Generate hot wallet

The hot wallet is used to submit reward votes transactions. You must send some ETH (DAI for Gnosis) to
the wallet for the gas expenses.

You can use any of the tools available for generating the hot wallet. For example,

- [Metamask](https://metamask.io/)
    1. [Generate wallet](https://metamask.zendesk.com/hc/en-us/articles/360015289452-How-to-create-an-additional-account-in-your-wallet)
    2. [Export wallet](https://metamask.zendesk.com/hc/en-us/articles/360015289632-How-to-export-an-account-s-private-key)
- [MyEtherWallet Offline](https://help.myetherwallet.com/en/articles/6512619-using-mew-offline-current-mew-version-6)
- [Vanity ETH](https://github.com/bokub/vanity-eth)

### Step 2. Prepare .env file

Copy [.env.example](./.env.example) file to `.env` file and fill it with correct values

### Step 3. Deploy keeper

#### Option 1. Use Docker image
Pull Docker image from [here](https://europe-west4-docker.pkg.dev/stakewiselabs/private/v3-keeper) and start the container with the following command:

```sh
docker run --restart on-failure:10 --env-file ./.env europe-west4-docker.pkg.dev/stakewiselabs/private/v3-keeper
```

### Option 2. Use Kubernetes helm chart

You can use [Keeper V3 helm chart](https://github.com/stakewise/helm-charts/tree/main/charts/v3-keeper) to host keeper
in Kubernetes

### Option 3. Build from source

Build requirements:

- [Python 3.10+](https://www.python.org/downloads/)
- [Poetry](https://python-poetry.org/docs/)


Install dependencies and start keeper processes:
```sh
poetry install --no-dev
PYTHONPATH="." python src/main.py
```

## Monitoring Keeper with Prometheus

Keeper supports monitoring using Prometheus by providing a `/metrics` endpoint that Prometheus can scrape to gather various metrics.

### Prerequisites:

1. Keeper application running and accessible.
1. Prometheus server installed and running.
1. Basic knowledge of how to configure Prometheus targets.

Setup Keeper for Monitoring:

Keeper provides the flexibility to define the host and port for the metrics endpoint via environment variables:

- `METRICS_HOST`: This defines the hostname or IP on which the metrics endpoint will be available.
- `METRICS_PORT`: This defines the port on which the metrics endpoint will be available.

Ensure that these environment variables are set as per your requirements.

For example:

```bash
export METRICS_HOST=0.0.0.0
export METRICS_PORT=9100
```

Now, Keeper's metrics will be available at http://[METRICS_HOST]:[METRICS_PORT]/metrics.

Configure Prometheus:

To monitor Keeper, you will need to configure Prometheus to scrape metrics from the exposed `/metrics` endpoint.

Add the following job configuration in your Prometheus configuration file (`prometheus.yml`):

```yaml
scrape_configs:
  - job_name: 'keeper'
    scrape_interval: 30s
    static_configs:
      - targets: ['<METRICS_HOST>:<METRICS_PORT>']
```

Replace `<METRICS_HOST>` and `<METRICS_PORT>` with the values you've set in Keeper.

This configuration tells Prometheus to scrape metrics from Keeper every 30 seconds.

# Contacts
- Dmitri Tsumak - dmitri@stakewise.io
- Alexander Sysoev - alexander@stakewise.io
- Evgeny Gusarov - evgeny@stakewise.io
