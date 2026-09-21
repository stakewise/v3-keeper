from Crypto.Cipher import AES  # nosec B413 - pycryptodome, same as eciespy
from eth_typing.bls import BLSSignature
from py_ecc.bls.g2_primitives import G2_to_signature, signature_to_G2
from py_ecc.optimized_bls12_381.optimized_curve import Z2, add, curve_order, multiply
from py_ecc.utils import prime_field_inv

PRIME = curve_order

# Shard layout produced by eciespy 0.4.6 with default settings:
# ephemeral public key (65) + nonce (16) + tag (16) + AES-256-GCM encrypted data.
ECIES_EPHEMERAL_PUBLIC_KEY_LENGTH = 65
ECIES_NONCE_LENGTH = 16
ECIES_TAG_LENGTH = 16


def decrypt_shard_with_aes_key(aes_key: bytes, encrypted_shard: bytes) -> bytes:
    """
    Decrypts the eciespy shard with its one-time AES-256-GCM key, not with the oracle private key.
    The oracle derives the AES key from its private key and the shard ephemeral public key.
    Raises `ValueError` when the key is wrong or the shard was tampered with.
    """
    nonce_start = ECIES_EPHEMERAL_PUBLIC_KEY_LENGTH
    tag_start = nonce_start + ECIES_NONCE_LENGTH
    data_start = tag_start + ECIES_TAG_LENGTH

    nonce = encrypted_shard[nonce_start:tag_start]
    tag = encrypted_shard[tag_start:data_start]
    encrypted_data = encrypted_shard[data_start:]

    cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(encrypted_data, tag)


def reconstruct_shared_bls_signature(signatures: dict[int, BLSSignature]) -> BLSSignature:
    """
    Reconstructs shared BLS private key signature.
    Copied from https://github.com/dankrad/python-ibft/blob/master/bls_threshold.py
    """
    r = Z2
    for i, sig in signatures.items():
        sig_point = signature_to_G2(sig)
        coef = 1
        for j in signatures:
            if j != i:
                coef = -coef * (j + 1) * prime_field_inv(i - j, PRIME) % PRIME
        r = add(r, multiply(sig_point, coef))
    return G2_to_signature(r)
