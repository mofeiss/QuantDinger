import json

from app.routes.credentials import _credential_name_from_payload
from app.services import exchange_execution
from app.services.live_trading.factory import create_client, exchange_demo_mode_enabled
from app.services.live_trading.base import RetryableLiveTradingError
from app.services.live_trading.okx import OkxClient


def test_credential_name_accepts_form_aliases():
    assert _credential_name_from_payload({"name": " Main OKX "}) == "Main OKX"
    assert _credential_name_from_payload({"account_name": " Paper OKX "}) == "Paper OKX"
    assert _credential_name_from_payload({"accountName": " Camel OKX "}) == "Camel OKX"
    assert _credential_name_from_payload({"name": " ", "accountName": "Fallback"}) == "Fallback"
    assert _credential_name_from_payload({}) == ""


def test_okx_simulated_trading_adds_required_header():
    client = OkxClient(
        api_key="api-key",
        secret_key="secret-key",
        passphrase="passphrase",
        simulated_trading=True,
    )

    headers = client._headers("2026-01-01T00:00:00.000Z", "signed")

    assert headers["x-simulated-trading"] == "1"


def test_okx_live_trading_omits_simulated_header():
    client = OkxClient(
        api_key="api-key",
        secret_key="secret-key",
        passphrase="passphrase",
        simulated_trading=False,
    )

    headers = client._headers("2026-01-01T00:00:00.000Z", "signed")

    assert "x-simulated-trading" not in headers


def test_okx_factory_enables_simulated_trading_from_credential_flag():
    client = create_client(
        {
            "exchange_id": "okx",
            "api_key": "api-key",
            "secret_key": "secret-key",
            "passphrase": "passphrase",
            "enable_demo_trading": True,
        },
        market_type="spot",
    )

    assert isinstance(client, OkxClient)
    assert client.simulated_trading is True


def test_resolve_exchange_config_keeps_demo_flag_from_credential_when_strategy_overlay_false(monkeypatch):
    def fake_load_credential_config(credential_id, user_id=1):
        assert credential_id == 7
        assert user_id == 1
        return {
            "exchange_id": "okx",
            "api_key": "api-key",
            "secret_key": "secret-key",
            "passphrase": "passphrase",
            "enable_demo_trading": True,
        }

    monkeypatch.setattr(exchange_execution, "_load_credential_config", fake_load_credential_config)

    resolved = exchange_execution.resolve_exchange_config(
        {
            "credential_id": 7,
            "exchange_id": "okx",
            # Frontend strategy forms may carry default false values. A referenced
            # credential's environment must remain authoritative for live execution.
            "enable_demo_trading": False,
        },
        user_id=1,
    )

    assert resolved["enable_demo_trading"] is True


def test_resolve_exchange_config_keeps_demo_environment_alias_from_credential(monkeypatch):
    def fake_load_credential_config(credential_id, user_id=1):
        return {
            "exchange_id": "okx",
            "api_key": "api-key",
            "secret_key": "secret-key",
            "passphrase": "passphrase",
            "environment": "demo",
        }

    monkeypatch.setattr(exchange_execution, "_load_credential_config", fake_load_credential_config)

    resolved = exchange_execution.resolve_exchange_config(
        {
            "credential_id": 7,
            "exchange_id": "okx",
            "environment": "live",
            "enable_demo_trading": False,
        },
        user_id=1,
    )

    assert resolved["environment"] == "demo"
    assert exchange_demo_mode_enabled(resolved) is True


def test_okx_environment_mismatch_message_points_to_demo_toggle(monkeypatch):
    client = OkxClient(
        api_key="api-key",
        secret_key="secret-key",
        passphrase="passphrase",
        simulated_trading=False,
    )

    def fake_request(*args, **kwargs):
        return (
            401,
            {"msg": "APIKey does not match current environment.", "code": "50101"},
            json.dumps({"msg": "APIKey does not match current environment.", "code": "50101"}),
        )

    monkeypatch.setattr(client, "_request", fake_request)

    try:
        client.get_balance()
    except Exception as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected OKX environment mismatch to raise")

    assert "environment mismatch" in message
    assert "enable demo/testnet trading" in message


def test_okx_system_busy_order_response_is_retryable(monkeypatch):
    client = OkxClient(
        api_key="api-key",
        secret_key="secret-key",
        passphrase="passphrase",
        simulated_trading=True,
    )

    monkeypatch.setattr(
        client,
        "_request",
        lambda *args, **kwargs: (
            200,
            {
                "code": "1",
                "msg": "All operations failed",
                "data": [
                    {
                        "ordId": "",
                        "sCode": "50013",
                        "sMsg": "Systems are busy. Please try again later.",
                    }
                ],
            },
            "",
        ),
    )

    try:
        client._signed_request("POST", "/api/v5/trade/order", json_body={"instId": "BTC-USDT-SWAP"})
    except RetryableLiveTradingError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected OKX 50013 response to be retryable")

    assert "retryable" in message
    assert "50013" in message
    assert "simulated" in message
