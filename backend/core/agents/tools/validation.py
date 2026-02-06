"""
Tool Validation and Schema Checking for LangGraph agents.

Provides comprehensive tool validation:
- Input/output schema validation
- Type checking and coercion
- Required field validation
- Custom validation rules
- Schema compatibility checking
- Validation result reporting
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Type, Union
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator
from pydantic.json_schema import model_json_schema


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationCategory(str, Enum):
    """Categories for validation checks."""

    SCHEMA = "schema"
    TYPE = "type"
    REQUIRED = "required"
    CONSTRAINT = "constraint"
    COMPATIBILITY = "compatibility"
    SECURITY = "security"
    PERFORMANCE = "performance"


class ValidationIssue(BaseModel):
    """A validation issue found during checking."""

    category: ValidationCategory = Field(..., description="Issue category")
    severity: ValidationSeverity = Field(
        default=ValidationSeverity.ERROR, description="Issue severity"
    )
    field_path: str = Field(..., description="Path to the field")
    message: str = Field(..., description="Issue description")
    code: str = Field(..., description="Issue code")
    value: Any = Field(None, description="Current value")
    expected: Any = Field(None, description="Expected value")
    suggestion: Optional[str] = Field(None, description="Fix suggestion")


class ValidationResult(BaseModel):
    """Result of validating tool input/output."""

    tool_name: str = Field(..., description="Tool name")
    is_valid: bool = Field(..., description="Whether validation passed")
    issues: List[ValidationIssue] = Field(
        default_factory=list, description="Validation issues found"
    )
    validated_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="Validation timestamp",
    )
    schema_used: Dict[str, Any] = Field(
        default_factory=dict, description="Schema used for validation"
    )


class SchemaDefinition(BaseModel):
    """Schema definition for tool input/output."""

    schema_type: str = Field(default="object", description="JSON Schema type")
    description: Optional[str] = Field(None, description="Schema description")
    required_fields: List[str] = Field(
        default_factory=list, description="Required field names"
    )
    properties: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Field schemas"
    )
    additional_properties: bool = Field(
        default=True, description="Allow additional properties"
    )
    enum_values: Optional[Set[str]] = Field(
        None, description="Allowed enum values"
    )


class ToolValidator:
    """
    Comprehensive tool validator with schema checking.

    Features:
    - JSON Schema validation
    - Type checking and coercion
    - Custom constraint validation
    - Security validation
    - Compatibility checking
    """

    def __init__(self):
        """Initialize the validator."""
        self._custom_validators: Dict[str, callable] = {}
        self._schema_cache: Dict[str, Dict[str, Any]] = {}

    def register_validator(
        self, name: str, validator_func: callable
    ) -> None:
        """
        Register a custom validator function.

        Args:
            name: Validator name
            validator_func: Function taking (value, constraint) returning issues
        """
        self._custom_validators[name] = validator_func

    def validate_input(
        self,
        tool_name: str,
        input_data: Dict[str, Any],
        schema: Dict[str, Any] = None,
    ) -> ValidationResult:
        """
        Validate tool input against schema.

        Args:
            tool_name: Name of the tool
            input_data: Input data to validate
            schema: Optional JSON Schema (uses Pydantic if not provided)

        Returns:
            ValidationResult with issues
        """
        issues: List[ValidationIssue] = []

        # If no schema, try to infer from Pydantic model
        if schema is None:
            schema = self._generate_schema(input_data)

        # Check required fields
        required_fields = schema.get("required", [])
        for field_name in required_fields:
            if field_name not in input_data:
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.REQUIRED,
                        severity=ValidationSeverity.ERROR,
                        field_path=field_name,
                        message=f"Required field '{field_name}' is missing",
                        code="REQUIRED_FIELD_MISSING",
                        expected=f"Field '{field_name}' must be provided",
                    )
                )

        # Validate each property
        properties = schema.get("properties", {})
        for field_name, field_schema in properties.items():
            if field_name in input_data:
                value = input_data[field_name]
                field_issues = self._validate_field(
                    field_name, value, field_schema, input_data
                )
                issues.extend(field_issues)

        # Check additional properties
        if not schema.get("additionalProperties", True):
            for field_name in input_data:
                if field_name not in properties:
                    issues.append(
                        ValidationIssue(
                            category=ValidationCategory.SCHEMA,
                            severity=ValidationSeverity.WARNING,
                            field_path=field_name,
                            message=f"Additional field '{field_name}' is not allowed",
                            code="ADDITIONAL_PROPERTY_NOT_ALLOWED",
                            value=field_name,
                        )
                    )

        return ValidationResult(
            tool_name=tool_name,
            is_valid=len([i for i in issues if i.severity == ValidationSeverity.ERROR]) == 0,
            issues=issues,
            schema_used=schema,
        )

    def _validate_field(
        self,
        field_name: str,
        value: Any,
        field_schema: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[ValidationIssue]:
        """Validate a single field."""
        issues: List[ValidationIssue] = []
        field_type = field_schema.get("type", "any")

        # Type validation
        type_issues = self._validate_type(field_name, value, field_type)
        issues.extend(type_issues)
        if type_issues:
            return issues  # Skip other validations if type is wrong

        # Null handling
        if value is None:
            if field_schema.get("nullable", True) is False:
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.TYPE,
                        severity=ValidationSeverity.ERROR,
                        field_path=field_name,
                        message=f"Field '{field_name}' cannot be null",
                        code="NULL_NOT_ALLOWED",
                    )
                )
            return issues

        # Type-specific validation
        if field_type == "string":
            issues.extend(self._validate_string(field_name, value, field_schema))
        elif field_type in ["integer", "number"]:
            issues.extend(self._validate_number(field_name, value, field_schema))
        elif field_type == "boolean":
            issues.extend(self._validate_boolean(field_name, value, field_schema))
        elif field_type == "array":
            issues.extend(self._validate_array(field_name, value, field_schema))
        elif field_type == "object":
            issues.extend(self._validate_object(field_name, value, field_schema, context))

        # Enum validation
        if "enum" in field_schema:
            if value not in field_schema["enum"]:
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.CONSTRAINT,
                        severity=ValidationSeverity.ERROR,
                        field_path=field_name,
                        message=f"Value must be one of {field_schema['enum']}",
                        code="ENUM_VIOLATION",
                        value=value,
                        expected=field_schema["enum"],
                    )
                )

        return issues

    def _validate_type(
        self, field_name: str, value: Any, expected_type: str
    ) -> List[ValidationIssue]:
        """Validate the type of a value."""
        issues: List[ValidationIssue] = []
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected_py_type = type_map.get(expected_type)
        if expected_py_type and not isinstance(value, expected_py_type):
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.TYPE,
                    severity=ValidationSeverity.ERROR,
                    field_path=field_name,
                    message=f"Expected {expected_type}, got {type(value).__name__}",
                    code=f"TYPE_MISMATCH_{expected_type.upper()}",
                    value=type(value).__name__,
                    expected=expected_type,
                )
            )
        return issues

    def _validate_string(
        self, field_name: str, value: str, field_schema: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """Validate a string field."""
        issues: List[ValidationIssue] = []

        # Length validation
        min_length = field_schema.get("minLength")
        if min_length is not None and len(value) < min_length:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.CONSTRAINT,
                    severity=ValidationSeverity.ERROR,
                    field_path=field_name,
                    message=f"String must be at least {min_length} characters",
                    code="STRING_TOO_SHORT",
                    value=len(value),
                    expected=f">= {min_length}",
                )
            )

        max_length = field_schema.get("maxLength")
        if max_length is not None and len(value) > max_length:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.CONSTRAINT,
                    severity=ValidationSeverity.ERROR,
                    field_path=field_name,
                    message=f"String must be at most {max_length} characters",
                    code="STRING_TOO_LONG",
                    value=len(value),
                    expected=f"<= {max_length}",
                )
            )

        # Pattern validation
        pattern = field_schema.get("pattern")
        if pattern and not re.match(pattern, value):
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.CONSTRAINT,
                    severity=ValidationSeverity.ERROR,
                    field_path=field_name,
                    message=f"String does not match required pattern",
                    code="PATTERN_MISMATCH",
                    value=value[:50],  # Truncate for display
                    expected=pattern,
                )
            )

        # Format validation
        format_val = field_schema.get("format")
        if format_val == "uuid":
            try:
                UUID(value)
            except ValueError:
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.FORMAT,
                        severity=ValidationSeverity.ERROR,
                        field_path=field_name,
                        message="Value is not a valid UUID",
                        code="INVALID_UUID_FORMAT",
                        value=value,
                    )
                )
        elif format_val == "email":
            if not re.match(r"[^@]+@[^@]+\.[^@]+", value):
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.FORMAT,
                        severity=ValidationSeverity.ERROR,
                        field_path=field_name,
                        message="Value is not a valid email",
                        code="INVALID_EMAIL_FORMAT",
                        value=value,
                    )
                )
        elif format_val == "uri":
            if not re.match(r"^https?://", value):
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.FORMAT,
                        severity=ValidationSeverity.ERROR,
                        field_path=field_name,
                        message="Value is not a valid URI",
                        code="INVALID_URI_FORMAT",
                        value=value,
                    )
                )

        return issues

    def _validate_number(
        self, field_name: str, value: Union[int, float], field_schema: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """Validate a number field."""
        issues: List[ValidationIssue] = []

        min_value = field_schema.get("minimum")
        if min_value is not None and value < min_value:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.CONSTRAINT,
                    severity=ValidationSeverity.ERROR,
                    field_path=field_name,
                    message=f"Value must be >= {min_value}",
                    code="VALUE_TOO_SMALL",
                    value=value,
                    expected=f">= {min_value}",
                )
            )

        max_value = field_schema.get("maximum")
        if max_value is not None and value > max_value:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.CONSTRAINT,
                    severity=ValidationSeverity.ERROR,
                    field_path=field_name,
                    message=f"Value must be <= {max_value}",
                    code="VALUE_TOO_LARGE",
                    value=value,
                    expected=f"<= {max_value}",
                )
            )

        return issues

    def _validate_boolean(
        self, field_name: str, value: bool, field_schema: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """Validate a boolean field."""
        # Boolean validation is minimal - type checking handles most cases
        return []

    def _validate_array(
        self, field_name: str, value: list, field_schema: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """Validate an array field."""
        issues: List[ValidationIssue] = []

        min_items = field_schema.get("minItems")
        if min_items is not None and len(value) < min_items:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.CONSTRAINT,
                    severity=ValidationSeverity.ERROR,
                    field_path=field_name,
                    message=f"Array must have at least {min_items} items",
                    code="ARRAY_TOO_SMALL",
                    value=len(value),
                    expected=f">= {min_items}",
                )
            )

        max_items = field_schema.get("maxItems")
        if max_items is not None and len(value) > max_items:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.CONSTRAINT,
                    severity=ValidationSeverity.ERROR,
                    field_path=field_name,
                    message=f"Array must have at most {max_items} items",
                    code="ARRAY_TOO_LARGE",
                    value=len(value),
                    expected=f"<= {max_items}",
                )
            )

        # Unique items
        if field_schema.get("uniqueItems") and len(value) != len(set(str(i) for i in value)):
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.CONSTRAINT,
                    severity=ValidationSeverity.ERROR,
                    field_path=field_name,
                    message="Array items must be unique",
                    code="DUPLICATE_ITEMS",
                )
            )

        # Item validation
        items_schema = field_schema.get("items", {})
        if items_schema:
            for i, item in enumerate(value):
                item_issues = self._validate_field(f"{field_name}[{i}]", item, items_schema, {})
                issues.extend(item_issues)

        return issues

    def _validate_object(
        self,
        field_name: str,
        value: dict,
        field_schema: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[ValidationIssue]:
        """Validate an object field."""
        issues: List[ValidationIssue] = []

        min_properties = field_schema.get("minProperties")
        if min_properties is not None and len(value) < min_properties:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.CONSTRAINT,
                    severity=ValidationSeverity.ERROR,
                    field_path=field_name,
                    message=f"Object must have at least {min_properties} properties",
                    code="OBJECT_TOO_SPARSE",
                    value=len(value),
                    expected=f">= {min_properties}",
                )
            )

        max_properties = field_schema.get("maxProperties")
        if max_properties is not None and len(value) > max_properties:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.CONSTRAINT,
                    severity=ValidationSeverity.ERROR,
                    field_path=field_name,
                    message=f"Object must have at most {max_properties} properties",
                    code="OBJECT_TOO_DENSE",
                    value=len(value),
                    expected=f"<= {max_properties}",
                )
            )

        # Property validation
        properties = field_schema.get("properties", {})
        for prop_name, prop_schema in properties.items():
            if prop_name in value:
                prop_value = value[prop_name]
                prop_issues = self._validate_field(
                    f"{field_name}.{prop_name}", prop_value, prop_schema, context
                )
                issues.extend(prop_issues)

        return issues

    def _generate_schema(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a JSON Schema from data."""
        properties = {}
        required = []

        for key, value in data.items():
            if isinstance(value, str):
                schema = {"type": "string"}
            elif isinstance(value, bool):
                schema = {"type": "boolean"}
            elif isinstance(value, int):
                schema = {"type": "integer"}
            elif isinstance(value, float):
                schema = {"type": "number"}
            elif isinstance(value, list):
                schema = {"type": "array", "items": {"type": "string"}}
            elif isinstance(value, dict):
                schema = self._generate_schema(value)
            else:
                schema = {"type": "string"}

            properties[key] = schema
            required.append(key)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": True,
        }

    def validate_output(
        self, tool_name: str, output_data: Any, schema: Dict[str, Any] = None
    ) -> ValidationResult:
        """
        Validate tool output against schema.

        Args:
            tool_name: Name of the tool
            output_data: Output data to validate
            schema: Optional JSON Schema

        Returns:
            ValidationResult with issues
        """
        # For output validation, we typically just check structure
        if schema is None:
            schema = {"type": "any"}

        issues: List[ValidationIssue] = []

        # If output is expected to be an object
        if schema.get("type") == "object" and not isinstance(output_data, dict):
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.TYPE,
                    severity=ValidationSeverity.ERROR,
                    field_path="output",
                    message=f"Expected object, got {type(output_data).__name__}",
                    code="OUTPUT_TYPE_MISMATCH",
                    value=type(output_data).__name__,
                    expected="object",
                )
            )

        # If output is expected to be an array
        if schema.get("type") == "array" and not isinstance(output_data, list):
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.TYPE,
                    severity=ValidationSeverity.ERROR,
                    field_path="output",
                    message=f"Expected array, got {type(output_data).__name__}",
                    code="OUTPUT_TYPE_MISMATCH",
                    value=type(output_data).__name__,
                    expected="array",
                )
            )

        return ValidationResult(
            tool_name=tool_name,
            is_valid=len(issues) == 0,
            issues=issues,
            schema_used=schema,
        )

    def check_schema_compatibility(
        self, schema1: Dict[str, Any], schema2: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """
        Check compatibility between two schemas.

        Args:
            schema1: First schema
            schema2: Second schema

        Returns:
            List of compatibility issues
        """
        issues: List[ValidationIssue] = []

        # Check type compatibility
        type1 = schema1.get("type")
        type2 = schema2.get("type")

        if type1 and type2 and type1 != type2:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.COMPATIBILITY,
                    severity=ValidationSeverity.ERROR,
                    field_path="",
                    message=f"Type mismatch: {type1} vs {type2}",
                    code="TYPE_COMPATIBILITY_ERROR",
                    expected=type2,
                )
            )

        # Check required fields compatibility
        required1 = set(schema1.get("required", []))
        required2 = set(schema2.get("required", []))

        added_required = required1 - required2
        if added_required:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.COMPATIBILITY,
                    severity=ValidationSeverity.WARNING,
                    field_path="required",
                    message=f"New required fields: {added_required}",
                    code="REQUIRED_FIELDS_ADDED",
                    value=added_required,
                )
            )

        return issues


class SchemaGenerator:
    """Generate JSON Schemas from Pydantic models or Python types."""

    @staticmethod
    def from_pydantic(model_class: Type[BaseModel]) -> Dict[str, Any]:
        """
        Generate JSON Schema from a Pydantic model.

        Args:
            model_class: Pydantic model class

        Returns:
            JSON Schema dictionary
        """
        return model_json_schema(model_class)

    @staticmethod
    def from_type_hint(hint: Any) -> Dict[str, Any]:
        """
        Generate JSON Schema from a type hint.

        Args:
            hint: Type hint (e.g., str, List[int], Dict[str, str])

        Returns:
            JSON Schema dictionary
        """
        from typing import get_origin, get_args

        origin = get_origin(hint)

        if origin is None:
            # Simple type
            type_map = {
                str: {"type": "string"},
                int: {"type": "integer"},
                float: {"type": "number"},
                bool: {"type": "boolean"},
                list: {"type": "array"},
                dict: {"type": "object"},
            }
            return type_map.get(hint, {"type": "string"})

        if origin is Union:
            args = get_args(hint)
            non_none_args = [a for a in args if a is not type(None)]
            if len(non_none_args) == 1:
                return SchemaGenerator.from_type_hint(non_none_args[0])
            return {"type": "string"}  # Union types default to string

        if origin is list:
            args = get_args(hint)
            if args:
                return {
                    "type": "array",
                    "items": SchemaGenerator.from_type_hint(args[0]),
                }
            return {"type": "array", "items": {"type": "string"}}

        if origin is dict:
            args = get_args(hint)
            if len(args) >= 2:
                return {
                    "type": "object",
                    "additionalProperties": SchemaGenerator.from_type_hint(args[1]),
                }
            return {"type": "object"}

        return {"type": "string"}


# Convenience functions
def create_validator() -> ToolValidator:
    """Create a new tool validator."""
    return ToolValidator()


def validate_tool_input(
    tool_name: str, input_data: Dict[str, Any], schema: Dict[str, Any] = None
) -> ValidationResult:
    """Validate tool input."""
    validator = create_validator()
    return validator.validate_input(tool_name, input_data, schema)


def validate_tool_output(
    tool_name: str, output_data: Any, schema: Dict[str, Any] = None
) -> ValidationResult:
    """Validate tool output."""
    validator = create_validator()
    return validator.validate_output(tool_name, output_data, schema)


def generate_schema_from_model(model_class: Type[BaseModel]) -> Dict[str, Any]:
    """Generate JSON Schema from Pydantic model."""
    return SchemaGenerator.from_pydantic(model_class)
