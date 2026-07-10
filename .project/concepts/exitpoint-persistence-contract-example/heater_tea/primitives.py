"""Pydantic RootModel wrappers for primitive types.

UNCHANGED as a typing convenience: single-output modules still declare
ModuleBase[..., Float], and Float IS RootModel[float] (same class, same
"RootModel[float]" name).

DIFFERENT FROM TODAY: these wrappers no longer appear in
CUSTOM_SCHEMA_TYPES (see __init__.py). Their only reason for being there
was to feed the exit router a "RootModel[float]" write handler; the new
contract registers those handlers in TEAx's default router. Follow-up
ticket: codegen's _collect_exit_point_primitive_types() becomes removable.
"""
from pydantic import RootModel

Float = RootModel[float]
Int = RootModel[int]
String = RootModel[str]
Bool = RootModel[bool]

__all__ = ["Float", "Int", "String", "Bool"]
