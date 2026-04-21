def test_social_buzz_scaling(monkeypatch):
    monkeypatch.setattr(
        "services.coinstats_api.requests.get",
        lambda *a, **k: type("Resp", (), {
            "raise_for_status": lambda self: None,
            "text": '{"result":[{"communityData":{"twitter":{"followersCount":500000},"reddit":{"subscribersCount":300000},"telegram":{"subscribersCount":200000}}}]}',
            "json": lambda self: {
                "result": [{
                    "communityData": {
                        "twitter": {"followersCount": 500_000},
                        "reddit":  {"subscribersCount": 300_000},
                        "telegram": {"subscribersCount": 200_000},
                    }
                }]
            }
        })()
    )

    from services.social_api import fetch_social_buzz
    out = fetch_social_buzz("SOL")
    assert out["score"] == 1.0
