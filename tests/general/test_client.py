import os

import pytest

from elysia.util.client import ClientManager


class TestConfig:

    @pytest.mark.asyncio
    async def test_client_manager_starts(self):
        try:
            client_manager = ClientManager()
        finally:
            await client_manager.close_clients()

    @pytest.mark.asyncio
    async def test_client_manager_starts_with_env_vars(self):
        try:
            client_manager = ClientManager()
            assert client_manager.wcd_url == os.getenv("WCD_URL")
            assert client_manager.wcd_api_key == os.getenv("WCD_API_KEY")
        finally:
            await client_manager.close_clients()

    @pytest.mark.asyncio
    async def test_client_manager_starts_with_api_keys(self):
        try:
            client_manager = ClientManager()

            if "OPENAI_API_KEY" in os.environ:
                assert "X-OpenAI-Api-Key" in client_manager.headers
                assert client_manager.headers["X-OpenAI-Api-Key"] == os.getenv(
                    "OPENAI_API_KEY"
                )
        finally:
            await client_manager.close_clients()

    @pytest.mark.asyncio
    async def test_clients_are_connected(self):
        try:
            client_manager = ClientManager()
            await client_manager.start_clients()
            assert client_manager.client.is_ready()
        finally:
            await client_manager.close_clients()

    @pytest.mark.asyncio
    async def test_sync_client_connects(self):
        try:
            client_manager = ClientManager()
            with client_manager.connect_to_client() as client:
                assert client_manager.sync_in_use_counter == 1
            assert client_manager.sync_in_use_counter == 0
        finally:
            await client_manager.close_clients()

    @pytest.mark.asyncio
    async def async_connect(self, client_manager: ClientManager):
        async with client_manager.connect_to_async_client() as client:
            assert client_manager.async_in_use_counter == 1
            pass
        assert client_manager.async_in_use_counter == 0

    @pytest.mark.asyncio
    async def test_async_client_connects(self):
        try:
            client_manager = ClientManager()
            await self.async_connect(client_manager)
        finally:
            await client_manager.close_clients()
