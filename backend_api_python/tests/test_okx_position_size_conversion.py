from app.services.pending_order_worker import PendingOrderWorker


class FakeOkxClient:
    def __init__(self, instrument=None):
        self.instrument = instrument or {}
        self.calls = []

    def get_instrument(self, *, inst_type, inst_id):
        self.calls.append({"inst_type": inst_type, "inst_id": inst_id})
        return self.instrument


def test_okx_position_size_uses_position_ct_val():
    client = FakeOkxClient({"ctVal": "999"})

    size = PendingOrderWorker._okx_position_contracts_to_base(
        client,
        "UP-USDT-SWAP",
        {"pos": "52", "ctVal": "10"},
    )

    assert size == 520.0
    assert client.calls == []


def test_okx_position_size_fetches_instrument_ct_val_when_missing():
    client = FakeOkxClient({"ctVal": "10"})

    size = PendingOrderWorker._okx_position_contracts_to_base(
        client,
        "UP-USDT-SWAP",
        {"pos": "52"},
    )

    assert size == 520.0
    assert client.calls == [{"inst_type": "SWAP", "inst_id": "UP-USDT-SWAP"}]


def test_okx_position_size_falls_back_to_raw_position_without_ct_val():
    client = FakeOkxClient({})

    size = PendingOrderWorker._okx_position_contracts_to_base(
        client,
        "UP-USDT-SWAP",
        {"pos": "52"},
    )

    assert size == 52.0
