import json

from app.routes.credentials import _credential_name_from_payload
from app.services.live_trading.factory import create_client
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
