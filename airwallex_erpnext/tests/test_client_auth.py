import time

from airwallex_erpnext.client import AirwallexClient


class AuthClient(AirwallexClient):
    def _raw_request(self, method, path, params=None, body=None, headers=None):
        return {"token": "abc", "expires_at": int((time.time() + 1800) * 1000)}


def test_auth_token_cache():
    client = AuthClient("https://example.invalid", "id", "key")
    assert client.authenticate() == "abc"
    assert client.authenticate() == "abc"
