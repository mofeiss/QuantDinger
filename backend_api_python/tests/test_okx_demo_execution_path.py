from app.services import exchange_execution
from app.services import pending_order_worker as worker_mod
from app.services.live_trading.base import LiveOrderResult, RetryableLiveTradingError
from app.services.live_trading.okx import OkxClient


def _patch_worker_db_side_effects(monkeypatch, worker):
    monkeypatch.setattr(worker, "_sync_positions_best_effort", lambda *args, **kwargs: None)
    monkeypatch.setattr(worker, "_load_notification_config", lambda *args, **kwargs: {})
    monkeypatch.setattr(worker_mod, "append_strategy_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(worker_mod, "apply_fill_to_local_position", lambda *args, **kwargs: (None, {}))
    monkeypatch.setattr(worker_mod, "record_trade", lambda *args, **kwargs: None)


def _okx_strategy_config(*, exchange_config):
    return {
        "strategy_id": 122,
        "user_id": 1,
        "exchange_config": exchange_config,
        "trading_config": {
            "market_type": "swap",
            "trade_direction": "short",
            "bot_type": "trend",
        },
        "market_type": "swap",
        "leverage": 1,
        "execution_mode": "live",
        "market_category": "Crypto",
    }


def _okx_order_payload():
    return {
        "strategy_id": 122,
        "symbol": "AMZN/USDT",
        "signal_type": "open_short",
        "amount": 0.01,
        "ref_price": 263.45,
        "market_type": "swap",
        "order_mode": "market",
    }


def test_live_worker_okx_order_uses_demo_header_from_referenced_credential(monkeypatch):
    def fake_load_credential_config(credential_id, user_id=1):
        return {
            "exchange_id": "okx",
            "api_key": "api-key",
            "secret_key": "secret-key",
            "passphrase": "passphrase",
            "enable_demo_trading": True,
        }

    monkeypatch.setattr(exchange_execution, "_load_credential_config", fake_load_credential_config)
    monkeypatch.setattr(
        worker_mod,
        "load_strategy_configs",
        lambda strategy_id: _okx_strategy_config(
            exchange_config={
                "credential_id": 7,
                "exchange_id": "okx",
                "enable_demo_trading": False,
            }
        ),
    )

    real_create_client = worker_mod.create_client
    observed = {}

    def fake_create_client(exchange_config, *, market_type="swap"):
        client = real_create_client(exchange_config, market_type=market_type)
        assert isinstance(client, OkxClient)
        observed["client"] = client
        observed["headers_before_order"] = client._headers("2026-01-01T00:00:00.000Z", "signed")
        client.set_leverage = lambda *args, **kwargs: True
        client.place_market_order = lambda *args, **kwargs: LiveOrderResult(
            exchange_id="okx",
            exchange_order_id="ord-demo",
            filled=0.0,
            avg_price=0.0,
            raw={"data": [{"ordId": "ord-demo"}]},
        )
        client.wait_for_fill = lambda *args, **kwargs: {
            "filled": 0.01,
            "avg_price": 263.45,
            "fee": 0.0,
            "fee_ccy": "",
        }
        return client

    monkeypatch.setattr(worker_mod, "create_client", fake_create_client)

    worker = worker_mod.PendingOrderWorker()
    _patch_worker_db_side_effects(monkeypatch, worker)
    sent = {}
    failures = []
    monkeypatch.setattr(worker, "_mark_sent", lambda **kwargs: sent.update(kwargs))
    monkeypatch.setattr(worker, "_mark_failed", lambda **kwargs: failures.append(kwargs))

    payload = _okx_order_payload()
    worker._execute_live_order(order_id=2703, order_row=payload, payload=payload)

    assert observed["client"].simulated_trading is True
    assert observed["headers_before_order"]["x-simulated-trading"] == "1"
    assert sent["exchange_id"] == "okx"
    assert failures == []


def test_live_worker_retries_okx_retryable_market_order_error(monkeypatch):
    monkeypatch.setattr(
        worker_mod,
        "load_strategy_configs",
        lambda strategy_id: _okx_strategy_config(
            exchange_config={
                "exchange_id": "okx",
                "api_key": "api-key",
                "secret_key": "secret-key",
                "passphrase": "passphrase",
                "enable_demo_trading": True,
            }
        ),
    )
    monkeypatch.setattr(worker_mod.time, "sleep", lambda *args, **kwargs: None)

    real_create_client = worker_mod.create_client
    attempts = {"market": 0}

    def fake_create_client(exchange_config, *, market_type="swap"):
        client = real_create_client(exchange_config, market_type=market_type)
        assert isinstance(client, OkxClient)
        client.set_leverage = lambda *args, **kwargs: True

        def fake_place_market_order(*args, **kwargs):
            attempts["market"] += 1
            if attempts["market"] == 1:
                raise RetryableLiveTradingError("OKX system busy (retryable, code 50013)")
            return LiveOrderResult(
                exchange_id="okx",
                exchange_order_id="ord-retry",
                filled=0.0,
                avg_price=0.0,
                raw={"data": [{"ordId": "ord-retry"}]},
            )

        client.place_market_order = fake_place_market_order
        client.wait_for_fill = lambda *args, **kwargs: {
            "filled": 0.01,
            "avg_price": 263.45,
            "fee": 0.0,
            "fee_ccy": "",
        }
        return client

    monkeypatch.setattr(worker_mod, "create_client", fake_create_client)

    worker = worker_mod.PendingOrderWorker()
    _patch_worker_db_side_effects(monkeypatch, worker)
    sent = {}
    failures = []
    monkeypatch.setattr(worker, "_mark_sent", lambda **kwargs: sent.update(kwargs))
    monkeypatch.setattr(worker, "_mark_failed", lambda **kwargs: failures.append(kwargs))

    payload = _okx_order_payload()
    worker._execute_live_order(order_id=2704, order_row=payload, payload=payload)

    assert attempts["market"] == 2
    assert sent["exchange_order_id"] == "ord-retry"
    assert failures == []
