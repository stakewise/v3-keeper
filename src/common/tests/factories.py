from sw_utils.tests.factories import faker
from sw_utils.typings import Oracle


def create_oracle(num_endpoints: int = 1) -> Oracle:
    return Oracle(
        public_key=faker.ecies_public_key(),
        endpoints=[f'https://example{i}.com' for i in range(num_endpoints)],
    )
