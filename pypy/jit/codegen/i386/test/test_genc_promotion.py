import py
from pypy.jit.timeshifter.test import test_promotion
from pypy.jit.codegen.i386.test.test_genc_ts import I386TimeshiftingTestMixin

py.test.skip("in-progress")

class TestVList(I386TimeshiftingTestMixin,
                test_promotion.TestPromotion):

    # for the individual tests see
    # ====> ../../../timeshifter/test/test_promotion.py

    pass
