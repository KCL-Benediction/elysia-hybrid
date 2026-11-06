import os
import random
import pytest
import requests

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
INIT_URL = f"{BASE_URL}/init"
USER_CONFIG_URL = f"{BASE_URL}/user/config"
TREE_CONFIG_URL = f"{BASE_URL}/tree/config"

TEST_USER = "endpoint_config_user"
TEST_CONVO = "endpoint_config_convo"


@pytest.fixture(scope="module", autouse=True)
def ensure_user():
    # Ensure the user exists before running tests
    requests.post(f"{INIT_URL}/user/{TEST_USER}")


def test_get_user_config():
    response = requests.get(f"{USER_CONFIG_URL}/{TEST_USER}")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "config" in data
    assert isinstance(data["config"], dict)


def test_change_config_user():

    # get current config id
    response = requests.get(f"{USER_CONFIG_URL}/{TEST_USER}")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "config" in data
    assert isinstance(data["config"], dict)
    config_id = data["config"]["id"]

    payload = {
        "settings": {
            "BASE_MODEL": "gpt-4o-mini",
            "COMPLEX_MODEL": "gpt-4o",
            "BASE_PROVIDER": "openai",
            "COMPLEX_PROVIDER": "openai",
        },
        "style": "Professional",
        "agent_description": "You are a helpful assistant.",
        "end_goal": "Help users efficiently.",
        "branch_initialisation": "one_branch",
    }
    response = requests.post(f"{USER_CONFIG_URL}/{TEST_USER}/{config_id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "config" in data
    assert data["error"] == ""


def test_new_config_user():
    response = requests.post(f"{USER_CONFIG_URL}/{TEST_USER}/new")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "config" in data


def test_update_save_location():
    payload = {
        "config": {
            "save_location_wcd_url": os.getenv("WCD_URL"),
            "save_location_wcd_api_key": os.getenv("WCD_API_KEY"),
        }
    }
    response = requests.patch(
        f"{USER_CONFIG_URL}/frontend_config/{TEST_USER}", json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert "error" in data


def test_list_configs():
    response = requests.get(f"{USER_CONFIG_URL}/{TEST_USER}/list")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "configs" in data
    assert isinstance(data["configs"], list)


def test_save_and_load_config_user():

    # get config id
    response = requests.get(f"{USER_CONFIG_URL}/{TEST_USER}")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "config" in data
    assert isinstance(data["config"], dict)
    config_id = data["config"]["id"]

    save_payload = {
        "config_id": config_id,
    }

    config_payload = {
        "settings": {
            "BASE_MODEL": "gpt-4o-mini",
            "COMPLEX_MODEL": "gpt-4o",
            "BASE_PROVIDER": "openai",
            "COMPLEX_PROVIDER": "openai",
        },
        "style": "Technical",
        "agent_description": "You are a technical assistant.",
        "end_goal": "Provide technical answers.",
        "branch_initialisation": "multi_branch",
    }

    # Update config
    response = requests.post(
        f"{USER_CONFIG_URL}/{TEST_USER}/{config_id}", json=config_payload
    )
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert data["error"] == ""

    # Save config
    response = requests.post(
        f"{USER_CONFIG_URL}/{TEST_USER}/{config_id}", json=save_payload
    )
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert data["error"] == ""

    # Load config
    response = requests.post(f"{USER_CONFIG_URL}/{TEST_USER}/{config_id}/load")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "config" in data

    # Delete config
    response = requests.delete(f"{USER_CONFIG_URL}/{TEST_USER}/{config_id}")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data and data["error"] == ""


def test_get_tree_config_and_change():
    # Ensure tree exists
    requests.post(f"{INIT_URL}/user/{TEST_USER}")
    requests.post(
        f"{INIT_URL}/tree/{TEST_USER}/{TEST_CONVO}",
        json={"low_memory": True},
    )

    # Get config
    response = requests.get(f"{TREE_CONFIG_URL}/{TEST_USER}/{TEST_CONVO}")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data and data["error"] == ""
    assert "config" in data
    config_id = data["config"]["id"]

    # Change config
    payload = {
        "settings": {
            "BASE_MODEL": "gpt-3.5-turbo",
            "COMPLEX_MODEL": "gpt-4-turbo",
            "BASE_PROVIDER": "openai",
            "COMPLEX_PROVIDER": "openai",
        },
        "style": "Tree style",
        "agent_description": "Tree agent",
        "end_goal": "Tree goal",
        "branch_initialisation": "empty",
    }
    response = requests.post(
        f"{TREE_CONFIG_URL}/{TEST_USER}/{TEST_CONVO}", json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert "error" in data and data["error"] == ""
    assert "config" in data


def test_save_and_load_config_tree():

    # get config id
    response = requests.get(f"{USER_CONFIG_URL}/{TEST_USER}")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "config" in data
    assert isinstance(data["config"], dict)
    config_id = data["config"]["id"]

    config_payload = {
        "settings": {
            "BASE_MODEL": "gpt-4-turbo",
            "COMPLEX_MODEL": "gpt-4-vision",
            "BASE_PROVIDER": "openai",
            "COMPLEX_PROVIDER": "openai",
        },
        "style": "Tree Analytical",
        "agent_description": "Analytical assistant.",
        "end_goal": "Provide analyses.",
        "branch_initialisation": "empty",
    }

    # Update and save config
    response = requests.post(
        f"{USER_CONFIG_URL}/{TEST_USER}/{config_id}", json=config_payload
    )
    assert response.status_code == 200
    data = response.json()
    assert "error" in data and data["error"] == ""

    # Ensure tree exists
    requests.post(
        f"{INIT_URL}/tree/{TEST_USER}/{TEST_CONVO}",
        json={"low_memory": True},
    )
    # Load config to tree
    response = requests.post(
        f"{TREE_CONFIG_URL}/{TEST_USER}/{TEST_CONVO}/{config_id}/load"
    )
    assert response.status_code == 200
    data = response.json()
    assert "error" in data and data["error"] == ""
    assert "config" in data

    # Delete config
    response = requests.delete(f"{USER_CONFIG_URL}/{TEST_USER}/{config_id}")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data and data["error"] == ""


def test_list_configs_no_save_location():
    # Use a user that doesn't have a save location set
    user_id = "endpoint_user_no_save_location"
    requests.post(f"{INIT_URL}/user/{user_id}")

    response = requests.get(f"{USER_CONFIG_URL}/{user_id}/list")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "configs" in data

    # Should be empty list, not error
    assert isinstance(data["configs"], list)
