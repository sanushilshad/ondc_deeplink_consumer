
import pytest
import httpx
from ondc_deeplink_consumer.processor import BecknProcessor
mock_schema = {
    "type": "object",
    "properties": {
        "context": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "const": "mobility"},
                "version": {"type": "string"},
                "location": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string"},
                        "country": {"type": "string"},
                    },
                },
            },
        },
        "message": {
            "type": "object",
            "properties": {
                "intent": {"type": "string"},
                "dynamic_value": {"type": "string"},
            },
        },
    },
}

mock_yaml_content = """
context.version: "1.0.0"
context.location.city: "Bangalore"
context.location.country: "India"
message.intent: "search"
"""

@pytest.mark.asyncio
class TestBecknProcessorHttpxMox:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Create a temporary YAML file and assign its path to the instance."""
        file_path = tmp_path / "mock.yaml"
        file_path.write_text(mock_yaml_content)
        self.temp_yaml_file = str(file_path)

    async def test_full_workflow_static_and_dynamic_resolvers(self, monkeypatch):
        """
        Test the full workflow with static and dynamic resolvers,
        using httpx.MockTransport to intercept HTTP calls.
        """

        async def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == "http://api.example.com/value":
                return httpx.Response(200, text="dynamic api value")
   
            return httpx.Response(404, text="Not Found")


        transport = httpx.MockTransport(handler)


        original_async_client = httpx.AsyncClient
        monkeypatch.setattr(
            httpx,
            "AsyncClient",
            lambda **kwargs: original_async_client(transport=transport, **kwargs)
        )


        processor = BecknProcessor(self.temp_yaml_file, mock_schema)
        await processor.static_resolve()


        processor.add_dynamic_resolver("message.dynamic_value", httpx.URL("http://api.example.com/value"))
        await processor.dynamic_resolve()

        final_result = processor.get_parsed_usecase()
        expected_result = {
            "context": {
                "domain": "mobility",
                "version": "1.0.0",
                "location": {
                    "city": "Bangalore",
                    "country": "India"
                },
            },
            "message": {
                "intent": "search",
                "dynamic_value": "dynamic api value",
            },
        }
        assert final_result == expected_result

    async def test_multiple_dynamic_resolvers(self, monkeypatch):
        """
        Test multiple dynamic resolvers using a function-based resolver and a URL resolver,
        with httpx.MockTransport intercepting HTTP calls.
        """
        async def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == "http://api.example.com/city":
                return httpx.Response(200, text="api resolved value")
            return httpx.Response(404, text="Not Found")


        transport = httpx.MockTransport(handler)

        original_async_client = httpx.AsyncClient
        monkeypatch.setattr(
            httpx,
            "AsyncClient",
            lambda **kwargs: original_async_client(transport=transport, **kwargs)
        )

        processor = BecknProcessor(self.temp_yaml_file, mock_schema)
        await processor.static_resolve()
        async def function_resolver():
            return "function resolved value"

        processor.add_dynamic_resolver("message.dynamic_value", function_resolver)
        processor.add_dynamic_resolver("context.location.city", httpx.URL("http://api.example.com/city"))
        await processor.dynamic_resolve()

        result = processor.get_parsed_usecase()
        assert result["message"]["dynamic_value"] == "function resolved value"
        assert result["context"]["location"]["city"] == "api resolved value"