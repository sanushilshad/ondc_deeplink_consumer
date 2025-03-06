from typing import Any, Dict, Tuple

import httpx

from ondc_deeplink_consumer.host_mapping_cache import HostMappingCache



class DeeplinkResolver:
    def __init__(self, deeplink: str) -> None:
        self.deeplink: str = deeplink

    def extract_resolver_and_uuid(self) -> Tuple[str, str]:
        """Extracts the resolver and UUID from the deeplink."""
        try:
            parts = self.deeplink.split("://")[1].split("/")
            if len(parts) < 2:
                raise ValueError("Invalid deeplink format")
            return parts[0], parts[1]
        except IndexError:
            raise ValueError("Invalid deeplink format")

    async def fetch_usecase(self) -> Dict[str, Any]:
        """Fetches the JSON schema for the given deeplink."""
        resolver, uuid = self.extract_resolver_and_uuid()

        host_mapping_cache = HostMappingCache.get_instance()
        resolver_host = await host_mapping_cache.get_resolver_host(resolver)

        if not resolver_host:
            raise ValueError("Resolver host not found")

        url= f"{resolver_host}/{uuid}"
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(url)
        except Exception as e:
            print(e)
            pass
        if response.status_code != 200:
            raise ValueError(f"Error fetching usecase: HTTP {response.status_code}")

        return response.json()