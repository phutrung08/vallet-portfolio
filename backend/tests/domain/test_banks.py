from app.domain.banks import BANKS, find_bank


def test_the_list_holds_the_transfer_capable_banks_with_unique_six_digit_bins() -> None:
    bins = [bank.bin for bank in BANKS]

    assert len(BANKS) == 48
    assert len(set(bins)) == len(bins)
    assert all(len(b) == 6 and b.isdigit() for b in bins)
    assert all(bank.code and bank.short_name for bank in BANKS)


def test_lookup_by_bin() -> None:
    vietcombank = find_bank("970436")

    assert vietcombank is not None
    assert (vietcombank.code, vietcombank.short_name) == ("VCB", "Vietcombank")
    assert find_bank("000000") is None
