import py
py.test.skip("port me")
from pypy.jit.timeshifter.test import test_promotion
from pypy.jit.codegen.i386.test.test_genc_ts import I386TimeshiftingTestMixin

class TestPromotion(I386TimeshiftingTestMixin,
                test_promotion.TestLLType):

    # for the individual tests see
    # ====> ../../../timeshifter/test/test_promotion.py
    pass
