"""
Data models: ArgumentType enum, ArgumentSpec and EntryPointSpec dataclasses.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class ArgumentType(Enum):
    """Supported argument types in Ansible"""

    STR = "str"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    LIST = "list"
    DICT = "dict"
    PATH = "path"
    RAW = "raw"


@dataclass
class ArgumentSpec:
    """Represents a single argument specification"""

    name: str
    type: str = "str"
    required: bool = False
    default: Optional[Any] = None
    choices: Optional[List[str]] = None
    description: Optional[str] = None
    elements: Optional[str] = None
    options: Optional[Dict[str, Any]] = None
    version_added: Optional[str] = None
    no_log: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for YAML output"""
        result = {}

        if self.description:
            result["description"] = self.description

        result["type"] = self.type

        if self.required:
            result["required"] = self.required

        if self.default is not None:
            result["default"] = self.default

        if self.choices:
            result["choices"] = self.choices

        if self.elements:
            result["elements"] = self.elements

        if self.options:
            result["options"] = self.options

        if self.version_added:
            result["version_added"] = self.version_added

        if self.no_log:
            result["no_log"] = True

        return result

    @classmethod
    def from_existing_dict(cls, name: str, data: Dict[str, Any]) -> "ArgumentSpec":
        """Build an ArgumentSpec from a previously written option dict."""
        if not isinstance(data, dict):
            return cls(name=name, description=str(data) if data else None)

        return cls(
            name=name,
            type=data.get("type", "str"),
            required=data.get("required", False),
            default=data.get("default"),
            choices=data.get("choices"),
            description=data.get("description"),
            elements=data.get("elements"),
            options=data.get("options"),
            version_added=data.get("version_added"),
            no_log=data.get("no_log"),
        )


@dataclass
class EntryPointSpec:
    """Represents an entry point specification"""

    name: str = "main"
    short_description: str = ""
    description: List[str] = None
    author: List[str] = None
    options: Dict[str, ArgumentSpec] = None
    required_if: List[List[str]] = None
    required_one_of: List[List[str]] = None
    mutually_exclusive: List[List[str]] = None
    required_together: List[List[str]] = None

    def __post_init__(self):
        if self.description is None:
            self.description = []
        if self.author is None:
            self.author = []
        if self.options is None:
            self.options = {}

    @classmethod
    def from_existing_dict(cls, name: str, data: Dict[str, Any]) -> "EntryPointSpec":
        """Load all supported fields without dropping validation constraints."""
        if not isinstance(data, dict):
            raise ValueError(f"Entry point '{name}' must be a mapping")
        options = data.get("options", {})
        if not isinstance(options, dict):
            raise ValueError(f"Options for '{name}' must be a mapping")
        for option, value in options.items():
            if not isinstance(value, dict):
                raise ValueError(f"Option '{name}.{option}' must be a mapping")
        return cls(
            name=name,
            short_description=data.get("short_description", ""),
            description=data.get("description", []),
            author=data.get("author", []),
            options={
                key: ArgumentSpec.from_existing_dict(key, value)
                for key, value in options.items()
            },
            required_if=data.get("required_if"),
            required_one_of=data.get("required_one_of"),
            mutually_exclusive=data.get("mutually_exclusive"),
            required_together=data.get("required_together"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for YAML output"""
        result = {}

        if self.short_description:
            result["short_description"] = self.short_description

        if self.description:
            if isinstance(self.description, list):
                result["description"] = list(self.description)
            else:
                result["description"] = [self.description]

        if self.author:
            result["author"] = list(self.author)

        if self.options:
            result["options"] = {
                name: spec.to_dict() for name, spec in sorted(self.options.items())
            }

        if self.required_if:
            result["required_if"] = self.required_if

        if self.required_one_of:
            result["required_one_of"] = self.required_one_of

        if self.mutually_exclusive:
            result["mutually_exclusive"] = self.mutually_exclusive

        if self.required_together:
            result["required_together"] = self.required_together

        return result
