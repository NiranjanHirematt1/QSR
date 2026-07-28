"""Independent, list-based reference implementations of every indicator.

These are written from the textbook formulas, deliberately *not* reusing the
streaming (incremental) code, so that asserting streaming == reference at every
bar catches bugs in the incremental state machines (off-by-one, wrong seeding,
carry-over errors). Conventions match the production classes:
  * EMA/Wilder seeded with the SMA of the first `period` inputs.
  * True range needs a prior close (first bar emits nothing).
  * Bollinger uses population standard deviation.
"""
from __future__ import annotations

from math import sqrt


def sma_ref(closes, period):
    out = [None] * len(closes)
    for i in range(len(closes)):
        if i + 1 >= period:
            out[i] = sum(closes[i + 1 - period:i + 1]) / period
    return out


def ema_ref(closes, period):
    out = [None] * len(closes)
    alpha = 2 / (period + 1)
    ema = None
    for i, x in enumerate(closes):
        if ema is None:
            if i + 1 >= period:
                ema = sum(closes[i + 1 - period:i + 1]) / period
                out[i] = ema
        else:
            ema = alpha * x + (1 - alpha) * ema
            out[i] = ema
    return out


def vwma_ref(closes, vols, period):
    out = [None] * len(closes)
    for i in range(len(closes)):
        if i + 1 >= period:
            pv = sum(closes[j] * vols[j] for j in range(i + 1 - period, i + 1))
            vv = sum(vols[i + 1 - period:i + 1])
            out[i] = pv / vv if vv else None
    return out


def rsi_ref(closes, period):
    out = [None] * len(closes)
    gains, losses = [], []
    ag = al = None
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        g, l = max(ch, 0.0), max(-ch, 0.0)
        if ag is None:
            gains.append(g); losses.append(l)
            if len(gains) == period:
                ag = sum(gains) / period; al = sum(losses) / period
        else:
            ag = (ag * (period - 1) + g) / period
            al = (al * (period - 1) + l) / period
        if ag is not None:
            out[i] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
    return out


def _tr_series(H, L, C):
    trs = []
    prev = None
    for i in range(len(C)):
        if prev is None:
            trs.append(None)
        else:
            trs.append(max(H[i] - L[i], abs(H[i] - prev), abs(L[i] - prev)))
        prev = C[i]
    return trs


def _wilder(seq, period):
    """Wilder-smooth a list that may start with leading None (undefined) items."""
    out = [None] * len(seq)
    buf = []
    val = None
    for i, x in enumerate(seq):
        if x is None:
            continue
        if val is None:
            buf.append(x)
            if len(buf) == period:
                val = sum(buf) / period
                out[i] = val
        else:
            val = (val * (period - 1) + x) / period
            out[i] = val
    return out


def atr_ref(H, L, C, period):
    return _wilder(_tr_series(H, L, C), period)


def macd_ref(closes, fast, slow, signal):
    ef, es = ema_ref(closes, fast), ema_ref(closes, slow)
    macd = [None if (ef[i] is None or es[i] is None) else ef[i] - es[i] for i in range(len(closes))]
    # signal = EMA(signal) over the defined macd values
    sig = [None] * len(closes)
    alpha = 2 / (signal + 1)
    buf = []
    s = None
    for i, m in enumerate(macd):
        if m is None:
            continue
        if s is None:
            buf.append(m)
            if len(buf) == signal:
                s = sum(buf) / signal
                sig[i] = s
        else:
            s = alpha * m + (1 - alpha) * s
            sig[i] = s
    return [(macd[i], sig[i], (macd[i] - sig[i]) if sig[i] is not None else None)
            for i in range(len(closes))]


def bollinger_ref(closes, period, k):
    out = [None] * len(closes)
    for i in range(len(closes)):
        if i + 1 >= period:
            w = closes[i + 1 - period:i + 1]
            m = sum(w) / period
            sd = sqrt(sum((v - m) ** 2 for v in w) / period)
            out[i] = (m + k * sd, m, m - k * sd)
    return out


def donchian_ref(H, L, period):
    out = [None] * len(H)
    for i in range(len(H)):
        if i + 1 >= period:
            u = max(H[i + 1 - period:i + 1]); lo = min(L[i + 1 - period:i + 1])
            out[i] = (u, (u + lo) / 2, lo)
    return out


def adx_ref(H, L, C, period):
    n = len(C)
    pdm = [None] * n; mdm = [None] * n; tr = [None] * n
    for i in range(1, n):
        up = H[i] - H[i - 1]
        dn = L[i - 1] - L[i]
        pdm[i] = up if (up > dn and up > 0) else 0.0
        mdm[i] = dn if (dn > up and dn > 0) else 0.0
        tr[i] = max(H[i] - L[i], abs(H[i] - C[i - 1]), abs(L[i] - C[i - 1]))
    spdm = _wilder(pdm, period); smdm = _wilder(mdm, period); str_ = _wilder(tr, period)
    out = [None] * n
    dx = [None] * n
    for i in range(n):
        if spdm[i] is None or str_[i] in (None, 0):
            continue
        pdi = 100 * spdm[i] / str_[i]
        mdi = 100 * smdm[i] / str_[i]
        s = pdi + mdi
        dx[i] = 0.0 if s == 0 else 100 * abs(pdi - mdi) / s
        out[i] = (pdi, mdi)
    adx = _wilder(dx, period)
    return [None if (adx[i] is None or out[i] is None) else (adx[i], out[i][0], out[i][1])
            for i in range(n)]


def supertrend_ref(H, L, C, period, mult):
    atr = atr_ref(H, L, C, period)
    n = len(C)
    out = [None] * n
    st = None                 # previous supertrend line
    pfu = pfl = None          # previous final upper / lower bands
    for i in range(n):
        if atr[i] is None:
            continue
        hl2 = (H[i] + L[i]) / 2
        bu = hl2 + mult * atr[i]
        bl = hl2 - mult * atr[i]
        if st is None:        # first ready bar: initialise
            pfu, pfl = bu, bl
            st = bu if C[i] <= bu else bl
            out[i] = (st, -1 if st == bu else 1)
            continue
        pc = C[i - 1]
        fu = bu if (bu < pfu or pc > pfu) else pfu
        fl = bl if (bl > pfl or pc < pfl) else pfl
        if st == pfu:
            st = fu if C[i] <= fu else fl
        else:
            st = fl if C[i] >= fl else fu
        out[i] = (st, 1 if st == fl else -1)
        pfu, pfl = fu, fl
    return out
