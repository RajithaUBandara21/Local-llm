from typing import Type, Tuple, Optional
from pydantic import BaseModel, ValidationError

class OutputValidator:
    """Handles parsing and structural validation of LLM outputs."""
    
    @staticmethod
    def validate_json(response_text: str, schema_class: Type[BaseModel]) -> Tuple[bool, Optional[dict], Optional[str]]:
        """
        Validates text against a provided Pydantic schema.
        Returns: (is_valid_boolean, parsed_data_dict, error_message_string)
        """
        if not response_text:
            return False, None, "Empty response received from the model."
            
        try:
            validated_data = schema_class.model_validate_json(response_text)
            return True, validated_data.model_dump(), None
        except ValidationError as e:
            return False, None, f"Pydantic Validation Error: {e}"
        except Exception as e:
            return False, None, f"Unexpected Parsing Error: {e}"