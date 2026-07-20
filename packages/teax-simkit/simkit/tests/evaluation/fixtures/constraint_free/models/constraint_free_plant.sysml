package constraint_free_plant {
    private import ScalarValues::*;
    private import constraint_free_library::*;

    part def 'Free Plant' {
        doc /* Constraint-free: one calc, a real entry channel via a design
        attribute, and no `assert constraint` at all. */
        attribute width_design : Real = 4.0;
        calc area_calc : 'Area Calc' {
            in width = width_design;
        }
    }

    part freePlant : 'Free Plant';
}
