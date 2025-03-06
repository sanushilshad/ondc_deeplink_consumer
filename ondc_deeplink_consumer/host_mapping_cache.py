import httpx
import requests
import threading
from typing import Dict, Optional


class HostMappingCache:
    _instance: Optional["HostMappingCache"] = None
    _lock: threading.Lock = threading.Lock()
    _resolver_host_mapping_url: str = (
        "https://raw.githubusercontent.com/ONDC-Official/deeplink-host-config/refs/heads/master/host_mapping.json"
    )

    def __init__(self) -> None:
        self.cache: Optional[Dict[str, str]] = None

    @classmethod
    def get_instance(cls) -> "HostMappingCache":
        """Returns the singleton instance of HostMappingCache."""
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def set_mapping_url(cls, url: str) -> None:
        """Sets a custom URL for fetching resolver host mappings."""
        cls._resolver_host_mapping_url = url

    @classmethod
    def get_mapping_url(cls) -> str:
        """Gets the resolver host mapping URL."""
        return cls._resolver_host_mapping_url

    async def fetch_mapping(self) -> None:
        """Asynchronously fetches and caches resolver host mappings from the configured URL."""
        async with httpx.AsyncClient() as client:
            response = await client.get(self._resolver_host_mapping_url)

        if response.status_code != 200:
            raise ValueError("Failed to fetch mapping data")

        self.cache = response.json()

    async def get_resolver_host(self, deeplink_host: str) -> Optional[str]:
        """Returns the resolver host for a given deeplink host asynchronously."""
        if self.cache is None:
            await self.fetch_mapping()
        return self.cache.get(deeplink_host)