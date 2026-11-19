"""Vietnamese banks and wallets that take NAPAS 247 transfers by VietQR.

Static reference data, never fetched at runtime. Source: the public VietQR bank list,
https://api.vietqr.io/v2/banks, fetched 2026-11-15; every entry with ``transferSupported`` 1
(48 of 76), in the source's order. ``bin`` is the 6-digit NAPAS BIN that a VietQR payload carries.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Bank:
    bin: str
    code: str
    short_name: str


BANKS: tuple[Bank, ...] = (
    Bank("970415", "ICB", "VietinBank"),
    Bank("970436", "VCB", "Vietcombank"),
    Bank("970418", "BIDV", "BIDV"),
    Bank("970405", "VBA", "Agribank"),
    Bank("970448", "OCB", "OCB"),
    Bank("970422", "MB", "MBBank"),
    Bank("970407", "TCB", "Techcombank"),
    Bank("970416", "ACB", "ACB"),
    Bank("970432", "VPB", "VPBank"),
    Bank("970423", "TPB", "TPBank"),
    Bank("970403", "STB", "Sacombank"),
    Bank("970437", "HDB", "HDBank"),
    Bank("970454", "VCCB", "VietCapitalBank"),
    Bank("970429", "SCB", "SCB"),
    Bank("970441", "VIB", "VIB"),
    Bank("970443", "SHB", "SHB"),
    Bank("970431", "EIB", "Eximbank"),
    Bank("970426", "MSB", "MSB"),
    Bank("546034", "CAKE", "CAKE"),
    Bank("546035", "Ubank", "Ubank"),
    Bank("963388", "TIMO", "Timo"),
    Bank("970400", "SGICB", "SaigonBank"),
    Bank("970409", "BAB", "BacABank"),
    Bank("971133", "PVDB", "PVcomBank Pay"),
    Bank("971025", "momo", "MoMo"),
    Bank("970412", "PVCB", "PVcomBank"),
    Bank("970414", "MBV", "MBV"),
    Bank("970419", "NCB", "NCB"),
    Bank("970424", "SHBVN", "ShinhanBank"),
    Bank("970425", "ABB", "ABBANK"),
    Bank("970427", "VAB", "VietABank"),
    Bank("970428", "NAB", "NamABank"),
    Bank("970430", "PGB", "PGBank"),
    Bank("970433", "VIETBANK", "VietBank"),
    Bank("970438", "BVB", "BaoVietBank"),
    Bank("970440", "SEAB", "SeABank"),
    Bank("970446", "COOPBANK", "COOPBANK"),
    Bank("970449", "LPB", "LPBank"),
    Bank("970452", "KLB", "KienLongBank"),
    Bank("668888", "KBank", "KBank"),
    Bank("971101", "ZALOPAY", "ZaloPay"),
    Bank("971032", "MVAS", "MVAS"),
    Bank("970434", "IVB", "IndovinaBank"),
    Bank("422589", "CIMB", "CIMB"),
    Bank("970444", "CBB", "CBBank"),
    Bank("970457", "WVN", "Woori"),
    Bank("970462", "KBHN", "KookminHN"),
    Bank("970463", "KBHCM", "KookminHCM"),
)

_BY_BIN = {bank.bin: bank for bank in BANKS}


def find_bank(bin_code: str) -> Bank | None:
    return _BY_BIN.get(bin_code)
