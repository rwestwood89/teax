package toy_plant {
    private import ScalarValues::*;

    // The F1 arithmetic fixture, as a MODEL.
    //
    // It used to be built programmatically by `generate_fixture.py`, which called
    // `sysml_codegen.analysis.constraint_lowering` and `analysis.parameter_groups`. The
    // codegen cutover recovery deleted both, so that construction cannot run at any current
    // codegen revision — refreshing the script's pins was necessary but not sufficient.
    //
    // Authoring the same three predicates as source puts this fixture on the same route as
    // every other one: elaborate -> project -> generate -> seal, reproducible by
    // `sysml-codegen generate` with no bespoke script and no retired API.
    //
    // The three predicates are unchanged from the programmatic originals:
    //   f1_division_check   a / b  > 0.0
    //   f2_power_check      a ** b > 0.0
    //   f3_nested_check     (a / b > 0.0) and (a > -1.0)
    //
    // The defaults are the `safe_satisfied` case: every predicate holds. The other four
    // committed cases drive division by zero, exponent overflow, non-finite operands, and a
    // zero/negative power by overriding entry points, exactly as before.
    part def 'Toy Plant' {
        attribute division_a : Real = 2.0;
        attribute division_b : Real = 1.0;
        attribute power_a : Real = 2.0;
        attribute power_b : Real = 2.0;
        attribute nested_a : Real = 2.0;
        attribute nested_b : Real = 1.0;

        assert constraint f1_division_check {
            division_a / division_b > 0.0
        }

        assert constraint f2_power_check {
            power_a ** power_b > 0.0
        }

        assert constraint f3_nested_check {
            (nested_a / nested_b > 0.0) and (nested_a > -1.0)
        }
    }

    part fixture : 'Toy Plant';
}
