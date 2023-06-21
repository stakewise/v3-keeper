from prometheus_client import Counter, Gauge, Info, start_http_server

from src import _get_project_meta
from src.accounts import keeper_account
from src.config.settings import METRICS_HOST, METRICS_PORT


class Metrics:
    def __init__(self):
        self.app_version = Info('app_version', 'V3 Keeper version')
        self.keeper_account = Info('keeper_account', 'V3 Keeper account')
        self.epoch = Gauge('epoch', 'Chain finalized head: Epoch')
        self.consensus_block = Gauge('consensus_block', 'Chain finalized head: Consensus Block')
        self.execution_block = Gauge('execution_block', 'Chain finalized head: Execution Block')
        self.execution_ts = Gauge('execution_ts', 'Chain finalized head: Execution Timestamp')
        self.oracle_avg_rewards_per_second = Gauge(
            'oracle_avg_rewards_per_second',
            'Oracle AVG rewards per second',
            labelnames=['oracle_address'],
        )
        self.oracle_update_timestamp = Gauge(
            'oracle_update_timestamp',
            'Oracle update timestamp',
            labelnames=['oracle_address'],
        )
        self.processed_exits = Counter('processed_exits', 'Number of exits keeper processed')
        self.keeper_balance = Gauge('keeper_balance', 'Keeper balance')

    def set_app_version(self):
        self.app_version.info({'version': _get_project_meta()['version']})

    def set_keeper_account(self):
        self.keeper_account.info({'keeper_account': keeper_account.address})


metrics = Metrics()
metrics.set_app_version()
metrics.set_keeper_account()


async def metrics_server() -> None:
    start_http_server(METRICS_PORT, METRICS_HOST)
