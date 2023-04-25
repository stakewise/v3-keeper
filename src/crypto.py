from eth_typing.bls import BLSSignature
from py_ecc.bls.g2_primitives import G2_to_signature, signature_to_G2
from py_ecc.optimized_bls12_381.optimized_curve import Z2, add, curve_order, multiply
from py_ecc.utils import prime_field_inv

PRIME = curve_order


def reconstruct_shared_bls_signature(
    signatures: dict[int, BLSSignature]
) -> BLSSignature:
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
