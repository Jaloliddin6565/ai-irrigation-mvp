from fastapi.testclient import TestClient


def test_config_options_lists_expected_enums(client: TestClient) -> None:
    response = client.get("/api/config/options")
    assert response.status_code == 200
    body = response.json()

    assert set(body["crops"].keys()) == {"cotton", "wheat", "orchard", "vineyard", "vegetables"}
    assert set(body["soils"].keys()) == {
        "sand",
        "sandy_loam",
        "loam",
        "clay_loam",
        "clay",
        "unknown",
    }
    assert set(body["irrigation_methods"].keys()) == {
        "drip",
        "sprinkler",
        "furrow",
        "basin",
        "unknown",
    }
    assert body["methodology_version"] == "0.1.0"
