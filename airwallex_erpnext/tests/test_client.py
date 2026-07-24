from airwallex_erpnext.client import AirwallexClient


class FakeClient(AirwallexClient):
    def __init__(self, pages):
        super().__init__("https://example.invalid", "id", "key")
        self.pages = iter(pages)

    def request(self, method, path, params=None, body=None, headers=None):
        return next(self.pages)


def test_bookmark_pagination():
    client = FakeClient([
        {"items": [{"id": 1}], "page_after": "next"},
        {"items": [{"id": 2}], "page_after": None},
    ])
    assert [x["id"] for x in client.paginate_bookmark("/x")] == [1, 2]


def test_numbered_pagination_stops_on_short_page():
    client = FakeClient([{"items": [{"id": 1}]}])
    assert [x["id"] for x in client.paginate_numbered("/x", page_size=100)] == [1]
