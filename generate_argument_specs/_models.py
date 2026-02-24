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

        return result


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
