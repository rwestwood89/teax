"""Auto-generated implementation for Area_Calc.

AUTO_IMPLEMENTED = True

SysML Source: root-0/excl_library.sysml:4

SysML Expressions:
    area = width * 3.0
"""

AUTO_IMPLEMENTED = True

from excl_only.modules.excl_library.area_calc import Area_CalcInput


def run_area_calc(inputs: Area_CalcInput) -> float:
    """Execute Area_Calc calculation.

SysML Source: root-0/excl_library.sysml:4

SysML Expressions:
    area = width * 3.0

Args:
    inputs: Input parameters validated against Area_CalcInput schema

Returns:
    float: area

Example:
    >>> inputs = Area_CalcInput(...)
    >>> result = run_area_calc(inputs)
    """
    return (inputs.width * 3.0)
