from app.data_sources.crypto import CryptoDataSource


class DummyExchange:
    id = "okx"

    def __init__(self, markets):
        self.markets = markets

    def load_markets(self, reload=False):
        return self.markets


def make_source(markets):
    source = CryptoDataSource.__new__(CryptoDataSource)
    source.exchange = DummyExchange(markets)
    source._markets_loaded = False
    source._markets_cache = None
    return source


def test_preserves_ccxt_swap_symbol_when_market_exists():
    source = make_source({
        "USELESS/USDT:USDT": {
            "active": True,
            "type": "swap",
        }
    })

    assert source._normalize_symbol("USELESS/USDT:USDT") == (
        "USELESS/USDT:USDT",
        "USELESS",
    )
    assert source._normalize_symbol_for_exchange("USELESS/USDT:USDT") == "USELESS/USDT:USDT"


def test_okx_swap_id_is_converted_to_ccxt_swap_symbol():
    source = make_source({
        "OPENAI/USDT:USDT": {
            "active": True,
            "type": "swap",
        }
    })

    assert source._normalize_symbol("OPENAI-USDT-SWAP") == (
        "OPENAI/USDT:USDT",
        "OPENAI",
    )
    assert source._normalize_symbol_for_exchange("OPENAI-USDT-SWAP") == "OPENAI/USDT:USDT"


def test_falls_back_to_swap_when_spot_pair_is_missing():
    source = make_source({
        "SPACEX/USDT:USDT": {
            "active": True,
            "type": "swap",
        }
    })

    assert source._normalize_symbol_for_exchange("SPACEX/USDT") == "SPACEX/USDT:USDT"


def test_prefers_spot_when_spot_and_swap_both_exist():
    source = make_source({
        "BTC/USDT": {
            "active": True,
            "type": "spot",
        },
        "BTC/USDT:USDT": {
            "active": True,
            "type": "swap",
        },
    })

    assert source._normalize_symbol_for_exchange("BTC/USDT") == "BTC/USDT"
