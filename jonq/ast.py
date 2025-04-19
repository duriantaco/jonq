from enum import Enum
from dataclasses import dataclass
from typing import List, Any

class PathType(Enum):
    FIELD = 1
    ARRAY = 2
    ARRAY_INDEX = 3

@dataclass
class PathElement:
    type: PathType
    value: str

@dataclass
class Path:
    elements: List[PathElement]

class ExprType(Enum):
    FIELD = 1
    AGGREGATION = 2
    LITERAL = 3
    OPERATION = 4
    BINARY_CONDITION = 5

@dataclass
class Expression:
    type: ExprType
    value: Any
    args: List[Any] = None

@dataclass
class Condition:
    expr: Expression

@dataclass
class AndCondition:
    left: 'Condition'
    right: 'Condition'

@dataclass
class OrCondition:
    left: 'Condition'
    right: 'Condition'

@dataclass
class BetweenCondition:
    field: str
    low: Any
    high: Any