from typing import Any, TypeVar

from pydantic import BaseModel

_ModelT = TypeVar("_ModelT", bound=BaseModel)

class SchemaSpec:
    prompt_schema: str
    schema: dict[str, Any]
    model_name: str

def build_schema_spec(model: type[BaseModel]) -> SchemaSpec: ...
def parse_structured_text(text: str, model: type[_ModelT]) -> _ModelT: ...
