package constraint_free_library {
    private import ScalarValues::*;

    calc def 'Area Calc' {
        doc /* A calc with an `in` parameter -> a real entry channel. The package
        has NO constraints anywhere, so codegen emits no constraint report. */
        in attribute width : Real;
        out attribute area : Real = width * 3.0;
    }
}
