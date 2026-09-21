import random

import pytest
from web3 import Web3

from src.exits.crypto import decrypt_shard_with_aes_key

# Shard encrypted by eciespy 0.4.6 and its AES key derived the same way as the oracle does
AES_KEY = Web3.to_bytes(hexstr='0x1eeb74dcd9f69853dad58bc8ed94ed00da8d07f76758f871a20af5e6ce591116')
ENCRYPTED_SHARD = Web3.to_bytes(
    hexstr='0x048c05dcc0744a0d3b2a5300f9eba53a1dbc6b2f6d73d7fe8d02a74c078a6e745bd84fa7e220fa37a1'
    '67c562f832c18346fe4ed291937cd524dcfd945fce6d840f62e9dfce49514514763d774c73d4af27dae0579f1a03'
    '4686cee818306daf8434ef24d803106e422328e477f47e078bc259e3078e2a1339b7c1872a49c87ffa08666b4861'
    '9cd37ce7b13fa95f1055c1118723d5eb2eb570c8ca139b84ac5cc79d463219fa9a5af5c0c7cd0ad68cadf096d525'
    'da442ac0bbf305a57fbb7b90c363'
)
DECRYPTED_SHARD = bytes(range(96))


class TestDecryptShardWithAesKey:
    def test_decrypts_eciespy_shard(self):
        assert decrypt_shard_with_aes_key(AES_KEY, ENCRYPTED_SHARD) == DECRYPTED_SHARD

    def test_wrong_key_rejected(self):
        with pytest.raises(ValueError):
            decrypt_shard_with_aes_key(random.randbytes(32), ENCRYPTED_SHARD)

    def test_tampered_shard_rejected(self):
        tampered_shard = bytearray(ENCRYPTED_SHARD)
        tampered_shard[-1] ^= 1

        with pytest.raises(ValueError):
            decrypt_shard_with_aes_key(AES_KEY, bytes(tampered_shard))
