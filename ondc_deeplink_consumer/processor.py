import os
import copy
from typing import Any, Callable, Dict, Union
import httpx
import yaml
import asyncio
from pathlib import Path
from jsonschema import Draft7Validator
ResolverType = Union[httpx.URL, str, Callable[[], Union[str, asyncio.Future]]]

class BecknProcessor:
    def __init__(self, static_value_path: str, usecase_schema: dict[str, Any]):
        """
        Initialize the processor with a path to a static YAML file and a JSON schema.

        :param static_value_path: Path to the YAML file with static values.
        :param usecase_schema: A JSON Schema (as a dict) defining the usecase.
        """
        # Remove '$schema' if present, since jsonschema doesn't require it for validation.
        self.usecase_schema: Dict[str, Any] = {k: v for k, v in usecase_schema.items() if k != "$schema"}
        self.validator = Draft7Validator(self.usecase_schema)
        self.parsed_usecase: Dict[str, Any] = {}
        self.dynamic_resolvers: list[Dict[str, Any]] = []  # Each entry has keys 'path' and 'resolver'

        # Resolve the absolute path to the static values file.
        p = Path(static_value_path)
        if not p.is_absolute():
            p = Path(os.getcwd()) / p
        self.static_data: Dict[str, Any] = self.load_yaml_file(str(p))

    def load_yaml_file(self, file_path: str) -> Dict[str, Any]:
        """
        Load a YAML file and return its contents as a dictionary.

        :param file_path: Path to the YAML file.
        :raises IOError: If loading the file fails.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise IOError(f"Error loading YAML file at '{file_path}': {e}")

    def process_schema_with_const(self, schema: Dict[str, Any]) -> Any:
        """
        Recursively process the schema to produce a template.
        If a 'const' key is found, its value is returned.
        Otherwise, a template is built based on the schema's type.

        :param schema: A JSON schema as a dictionary.
        :return: A template value or structure based on the schema.
        """
        if "const" in schema:
            return schema["const"]

        schema_type = schema.get("type")
        if schema_type == "object" and "properties" in schema:
            return {key: self.process_schema_with_const(prop) for key, prop in schema["properties"].items()}

        if schema_type == "array" and "items" in schema:
            # Return a single-item list as a template.
            return [self.process_schema_with_const(schema["items"])]

        # For non-object and non-array types, return a dict summarizing the schema.
        result = {"type": schema_type}
        for key in ("properties", "items", "required", "oneOf", "additionalProperties"):
            if key in schema:
                result[key] = schema[key]
        return result

    @staticmethod
    def _set_nested_value(data: Dict[str, Any], key_path: str, value: Any) -> None:
        """
        Set a value in a nested dictionary using a dot-separated key path.
        
        :param data: The dictionary to update.
        :param key_path: Dot-separated string indicating the path.
        :param value: The value to set.
        """
        keys = key_path.split('.')
        current = data
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

    def apply_yaml_values(self) -> Dict[str, Any]:
        """
        Merge static YAML values into the parsed usecase template.
        The YAML file should use dot-separated keys (e.g. "a.b.c") to denote nested structure.
        
        :return: A new dictionary with YAML values applied.
        """
        result = copy.deepcopy(self.parsed_usecase)
        for key_path, value in self.static_data.items():
            self._set_nested_value(result, key_path, value)
        return result

    async def static_resolve(self) -> None:
        """
        Create a template from the schema (processing any 'const' definitions) and overlay 
        static values from the YAML file.
        """
        self.parsed_usecase = self.process_schema_with_const(self.usecase_schema)
        self.parsed_usecase = self.apply_yaml_values()

    def add_dynamic_resolver(self, path: str, resolver: ResolverType) -> None:
        """
        Add a dynamic resolver to update the usecase at a specified dot-separated path.
        
        :param path: Dot-separated path where the resolved value should be inserted.
        :param resolver: Either a URL string to fetch data from or a callable returning a string (or awaitable string).
        """
        self.dynamic_resolvers.append({'path': path, 'resolver': resolver})

    async def dynamic_resolve(self) -> None:
        """
        Process each dynamic resolver:
          - If the resolver is a URL string, fetch data from it using httpx.
          - If it's a callable, execute it (await if necessary).
          - If string use as it is.
        The resolved values are then inserted into the usecase template.
        """
        updated_template = copy.deepcopy(self.parsed_usecase)
        async with httpx.AsyncClient() as client:
            for entry in self.dynamic_resolvers:
                path_str = entry['path']
                resolver = entry['resolver']
                if isinstance(resolver, httpx.URL):
                    response = await client.get(resolver)
                    value = response.text
                elif isinstance(resolver, str):
                    value = resolver
                elif callable(resolver):
                    value = await resolver() if asyncio.iscoroutinefunction(resolver) else resolver()
                else:
                    raise TypeError("Resolver must be either a URL string or a callable function")
                
                self._set_nested_value(updated_template, path_str, value)
        self.parsed_usecase = updated_template

    def get_parsed_usecase(self) -> Dict[str, Any]:
        """
        Validate the parsed usecase against the schema.
        
        :return: The parsed usecase if validation passes.
        :raises ValueError: If validation fails.
        """
        errors = sorted(self.validator.iter_errors(self.parsed_usecase), key=lambda e: e.path)
        if errors:
            raise ValueError("Invalid data in schema",
                             {"validationErrors": errors, "currentParsedData": self.parsed_usecase})
        return self.parsed_usecase