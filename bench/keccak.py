"""keccak.py -- Keccak-256, so function selectors are computed rather than remembered.

Ethereum's function selector is the first four bytes of Keccak-256 of the signature.
Python's hashlib has sha3_256, which is **not** the same thing: SHA3 uses a different
padding byte, and using it here would produce four bytes that look entirely plausible and
match nothing on any chain. That is exactly the failure mode this project keeps paying
for, so the primitive is implemented rather than approximated, and checked against
selectors anyone can verify independently.

No dependency, ~60 lines, and it runs on Pyodide.
"""

_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]
_ROT = [
    [0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56], [27, 20, 39, 8, 14],
]
_MASK = (1 << 64) - 1


def _rotl(x, n):
    return ((x << n) | (x >> (64 - n))) & _MASK


def _keccak_f(a):
    for rnd in range(24):
        c = [a[x][0] ^ a[x][1] ^ a[x][2] ^ a[x][3] ^ a[x][4] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rotl(c[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                a[x][y] ^= d[x]

        b = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                b[y][(2 * x + 3 * y) % 5] = _rotl(a[x][y], _ROT[x][y])

        for x in range(5):
            for y in range(5):
                a[x][y] = b[x][y] ^ ((~b[(x + 1) % 5][y]) & _MASK) & b[(x + 2) % 5][y]

        a[0][0] ^= _RC[rnd]
    return a


def keccak256(data):
    """Keccak-256 digest of bytes. Returns bytes of length 32."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    rate = 136  # 1088 bits, the rate for Keccak-256

    # Keccak padding is 0x01 ... 0x80. SHA3 uses 0x06; that one byte is the whole
    # difference between a correct selector and a number that matches nothing.
    padded = bytearray(data)
    padded.append(0x01)
    while len(padded) % rate != 0:
        padded.append(0x00)
    padded[-1] |= 0x80

    a = [[0] * 5 for _ in range(5)]
    for off in range(0, len(padded), rate):
        block = padded[off:off + rate]
        for i in range(rate // 8):
            lane = int.from_bytes(block[i * 8:(i + 1) * 8], "little")
            a[i % 5][i // 5] ^= lane
        a = _keccak_f(a)

    out = bytearray()
    for i in range(4):  # 32 bytes = 4 lanes
        out += a[i % 5][i // 5].to_bytes(8, "little")
    return bytes(out[:32])


def selector(signature):
    """The 4-byte function selector for a Solidity signature, as lowercase hex."""
    return keccak256(signature)[:4].hex()


if __name__ == "__main__":
    # Selectors anyone can check against a block explorer.
    known = {
        "transfer(address,uint256)": "a9059cbb",
        "balanceOf(address)": "70a08231",
        "approve(address,uint256)": "095ea7b3",
        "totalSupply()": "18160ddd",
        "owner()": "8da5cb5b",
        "transferOwnership(address)": "f2fde38b",
        "token0()": "0dfe1681",
    }
    bad = 0
    for sig, want in known.items():
        got = selector(sig)
        ok = got == want
        bad += 0 if ok else 1
        print("  %-32s %s %s" % (sig, got, "" if ok else "!= %s" % want))
    print("\n%s" % ("all known selectors match" if not bad else "%d MISMATCH" % bad))
    raise SystemExit(1 if bad else 0)
