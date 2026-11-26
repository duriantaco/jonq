from enum import Enum
from dataclasses import dataclass
from typing import List, Any, Union


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
    from_parent: bool = False


class ExprType(Enum):
    FIELD = 1
    AGGREGATION = 2
    LITERAL = 3
    OPERATION = 4
    BINARY_CONDITION = 5
    FUNCTION = 6
    CASE = 7


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
    left: "Predicate"
    right: "Predicate"


@dataclass
class OrCondition:
    left: "Predicate"
    right: "Predicate"


@dataclass
class BetweenCondition:
    field: Union[str, Path]
    low: Any
    high: Any


@dataclass
class InCondition:
    field: Union[str, Path]
    values: List[Any]


@dataclass
class NotCondition:
    condition: "Predicate"


Predicate = Union[Condition, AndCondition, OrCondition, BetweenCondition, InCondition, NotCondition]
