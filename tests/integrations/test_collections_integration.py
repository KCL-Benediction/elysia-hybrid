import os
import pytest
import requests
from elysia.util.client import ClientManager

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
COLLECTIONS_URL = f"{BASE_URL}/collections"
INIT_URL = f"{BASE_URL}/init"

TEST_USER = "endpoint_collections_user"
TEST_COLLECTION = "example_verba_github_issues"


@pytest.fixture(scope="module", autouse=True)
def ensure_user():
    # Ensure the user exists before running tests
    requests.post(f"{INIT_URL}/user/{TEST_USER}")


def test_mapping_types():
    response = requests.get(f"{COLLECTIONS_URL}/mapping_types")
    assert response.status_code == 200
    data = response.json()
    assert "mapping_types" in data
    assert isinstance(data["mapping_types"], dict)


def test_collections_list():
    response = requests.get(f"{COLLECTIONS_URL}/{TEST_USER}/list")
    assert response.status_code == 200
    data = response.json()
    assert "collections" in data
    assert "error" in data
    assert data["error"] == ""
    assert isinstance(data["collections"], list)


def test_collections_list_user_not_exist():
    response = requests.get(f"{COLLECTIONS_URL}/nonexistent_user/list")
    assert response.status_code == 500
    data = response.json()
    assert "collections" in data
    assert "error" in data
    assert data["error"] != ""


def test_collection_metadata():
    response = requests.get(f"{COLLECTIONS_URL}/{TEST_USER}/metadata/{TEST_COLLECTION}")
    assert response.status_code == 200
    data = response.json()
    assert "metadata" in data
    assert "error" in data


def test_collection_metadata_collection_not_exist():
    response = requests.get(f"{COLLECTIONS_URL}/{TEST_USER}/metadata/doesnotexist")
    assert response.status_code == 200
    data = response.json()
    assert "metadata" in data
    assert "error" in data
    assert data["error"] != ""


def test_view_paginated_collection():
    payload = {
        "page_size": 10,
        "page_number": 1,
        "sort_on": "issue_created_at",
        "ascending": True,
        "filter_config": {},
    }
    response = requests.post(
        f"{COLLECTIONS_URL}/{TEST_USER}/view/{TEST_COLLECTION}", json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert "properties" in data
    assert "items" in data
    assert "error" in data
    assert isinstance(data["items"], list)


def test_view_paginated_collection_with_filter():
    payload = {
        "page_size": 10,
        "page_number": 1,
        "sort_on": "issue_created_at",
        "ascending": True,
        "filter_config": {
            "type": "all",
            "filters": [{"field": "issue_state", "operator": "equal", "value": "open"}],
        },
    }
    response = requests.post(
        f"{COLLECTIONS_URL}/{TEST_USER}/view/{TEST_COLLECTION}", json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert "error" in data


def test_view_paginated_collection_invalid_payload():
    # Missing required fields
    response = requests.post(
        f"{COLLECTIONS_URL}/{TEST_USER}/view/{TEST_COLLECTION}", json={}
    )
    assert response.status_code in (400, 422)


def test_get_object_and_invalid():
    client_manager = ClientManager()
    with client_manager.connect_to_client() as client:
        collection = client.collections.get(TEST_COLLECTION)
        response = collection.query.fetch_objects(limit=1)
        uuid = str(response.objects[0].uuid)

    response = requests.get(
        f"{COLLECTIONS_URL}/{TEST_USER}/get_object/{TEST_COLLECTION}/{uuid}"
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "properties" in data
    assert "error" in data
    assert data["error"] == ""

    # Test with invalid UUID
    response = requests.get(
        f"{COLLECTIONS_URL}/{TEST_USER}/get_object/{TEST_COLLECTION}/invalid"
    )
    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert data["error"] != ""


def test_update_metadata():
    # Get current metadata
    response = requests.get(f"{COLLECTIONS_URL}/{TEST_USER}/metadata/{TEST_COLLECTION}")
    assert response.status_code == 200
    metadata = response.json().get("metadata", {})
    # Prepare update payload
    if "named_vectors" in metadata:
        named_vectors = [
            {
                "name": name,
                "enabled": True,
                "description": f"Updated description for {name}",
            }
            for name in metadata["named_vectors"]
        ]
    else:
        named_vectors = []
    payload = {
        "named_vectors": named_vectors,
        "summary": "Updated summary via endpoint test",
        "mappings": metadata.get("mappings", {}),
        "fields": [
            {"name": k, "description": f"Updated description for {k}"}
            for k in metadata.get("fields", {})
        ],
    }
    response = requests.patch(
        f"{COLLECTIONS_URL}/{TEST_USER}/metadata/{TEST_COLLECTION}", json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert "metadata" in data
    assert "error" in data
    assert data["error"] == "" or isinstance(data["error"], str)


def test_update_metadata_collection_not_exist():
    payload = {
        "named_vectors": [],
        "summary": "Should fail",
        "mappings": {},
        "fields": [],
    }
    response = requests.patch(
        f"{COLLECTIONS_URL}/{TEST_USER}/metadata/doesnotexist", json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert data["error"] != ""
