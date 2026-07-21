package excl_library {
    private import ScalarValues::*;

    calc def 'Area Calc' {
        in attribute width : Real;
        out attribute area : Real = width * 3.0;
    }

    constraint def 'Flag Set' {
        doc /* A non-numerical (boolean) predicate: codegen cannot lower it to a
        numeric margin, so it is excluded -> the package has a constraint report
        aggregator with zero eligible entries -> headline not_assessed. */
        in attribute flag : Boolean;
        flag == true
    }
}
