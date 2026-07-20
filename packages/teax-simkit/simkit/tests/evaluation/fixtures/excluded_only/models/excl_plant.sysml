package excl_plant {
    private import ScalarValues::*;
    private import excl_library::*;

    part def 'Excl Plant' {
        attribute width_design : Real = 4.0;
        attribute is_on : Boolean = true;
        calc area_calc : 'Area Calc' {
            in width = width_design;
        }
        assert constraint flag_ok : 'Flag Set' {
            in flag = is_on;
        }
    }

    part exclPlant : 'Excl Plant';
}
