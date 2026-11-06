import requests
import os
import pytest

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/init")


def test_initialise_user_new():
    user_id = "endpoint_test_user"
    response = requests.post(f"{BASE_URL}/user/{user_id}")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data and data["error"] == ""
    assert "user_exists" in data and data["user_exists"] is False
    assert "config" in data
    assert "settings" in data["config"]


def test_initialise_user_existing():
    user_id = "endpoint_test_user_existing"
    # First create the user
    requests.post(f"{BASE_URL}/user/{user_id}")
    # Now call again to check user_exists True
    response = requests.post(f"{BASE_URL}/user/{user_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["error"] == ""
    assert data["user_exists"] is True
    assert "config" in data


def test_initialise_tree_success():
    user_id = "endpoint_test_tree_user"
    conversation_id = "endpoint_test_tree_convo"
    # Ensure user exists
    requests.post(f"{BASE_URL}/user/{user_id}")
    payload = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "low_memory": True,
    }
    response = requests.post(
        f"{BASE_URL}/tree/{user_id}/{conversation_id}", json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data["error"] == ""
    assert data["conversation_id"] == conversation_id
    assert "tree" in data


def test_initialise_tree_user_not_exist():
    payload = {
        "user_id": "nonexistent_user",
        "conversation_id": "nonexistent_convo",
        "low_memory": True,
    }
    response = requests.post(
        f"{BASE_URL}/tree/nonexistent_user/nonexistent_convo", json=payload
    )
    assert response.status_code == 500
    data = response.json()
    assert data["error"] != ""
    assert data["conversation_id"] == "nonexistent_convo"
    assert "tree" in data
