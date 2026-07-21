"""Auto-generated implementation for Area_Calc.

AUTO_IMPLEMENTED = True

SysML Source: root-0/constraint_free_library.sysml:4

SysML Expressions:
    area = width * 3.0
    
Documentation:
A calc with an `in` parameter -> a real entry channel. The package
has NO constraints anywhere, so codegen emits no constraint report.
"""

AUTO_IMPLEMENTED = True

from constraint_free.modules.constraint_free_library.area_calc import Area_CalcInput


def run_area_calc(inputs: Area_CalcInput) -> float:
    """Execute Area_Calc calculation.

A calc with an `in` parameter -> a real entry channel. The package
has NO constraints anywhere, so codegen emits no constraint report.

SysML Source: root-0/constraint_free_library.sysml:4

SysML Expressions:
    area = width * 3.0
    
Documentation:
A calc with an `in` parameter -> a real entry channel. The package
has NO constraints anywhere, so codegen emits no constraint report.

Args:
    inputs: Input parameters validated against Area_CalcInput schema

Returns:
    float: area

Example:
    >>> inputs = Area_CalcInput(...)
    >>> result = run_area_calc(inputs)
    """
    return (inputs.width * 3.0)
