
import pytest
from unittest.mock import AsyncMock
from pytest_httpx import HTTPXMock

from ondc_deeplink_consumer.deeplink_resolver import DeeplinkResolver
from ondc_deeplink_consumer.host_mapping_cache import HostMappingCache



@pytest.mark.asyncio
class TestDeeplinkResolver:
    @pytest.fixture(autouse=True)
    def setup(self):
        """Clear mocks before each test."""
        HostMappingCache._instance = None 

    async def test_create_instance(self):
        """Test creating an instance with a deeplink."""
        deeplink = "beckn://resolver.beckn.org/12345"
        resolver = DeeplinkResolver(deeplink)
        assert isinstance(resolver, DeeplinkResolver)

    async def test_extract_resolver_and_uuid(self):
        """Test extracting resolver and UUID from deeplink."""
        deeplink = "beckn://resolver.beckn.org/12345"
        resolver = DeeplinkResolver(deeplink)
        assert resolver.extract_resolver_and_uuid() == ("resolver.beckn.org", "12345")

    async def test_fetch_usecase_complex_deeplink(self, httpx_mock: HTTPXMock):
        """Test handling complex deeplink structures with pytest_httpx."""
        
        mock_template = {"type": "object"}

        mock_cache = AsyncMock()
        mock_cache.get_resolver_host.return_value = "https://mapped.host"
        
        with pytest.MonkeyPatch().context() as monkeypatch:
            monkeypatch.setattr(HostMappingCache, "get_instance", lambda: mock_cache)

            httpx_mock.add_response(
                method="GET",
                url="https://mapped.host/12345-6789-0000",
                json=mock_template,
                status_code=200
            )

            deeplink = "beckn://sub.resolver.beckn.org/12345-6789-0000"
            resolver = DeeplinkResolver(deeplink)
            result = await resolver.fetch_usecase()

            assert result == mock_template