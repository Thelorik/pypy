import sys
from pypy.interpreter.baseobjspace import W_Root, ObjSpace, Wrappable, \
    Arguments
from pypy.interpreter.error import OperationError, wrap_oserror, \
    operationerrfmt
from pypy.interpreter.gateway import interp2app, NoneNotWrapped, unwrap_spec
from pypy.interpreter.typedef import TypeDef, GetSetProperty
#
from pypy.rpython.lltypesystem import lltype, rffi
#
from pypy.rlib import jit
from pypy.rlib import libffi
from pypy.rlib.rdynload import DLOpenError
from pypy.rlib.rarithmetic import intmask

class W_FFIType(Wrappable):
    def __init__(self, name, ffitype):
        self.name = name
        self.ffitype = ffitype

    @unwrap_spec('self', ObjSpace)
    def str(self, space):
        return space.wrap('<ffi type %s>' % self.name)



W_FFIType.typedef = TypeDef(
    'FFIType',
    __str__ = interp2app(W_FFIType.str),
    )


class W_types(Wrappable):
    pass

def build_ffi_types():
    from pypy.rlib.clibffi import FFI_TYPE_P
    tdict = {}
    for key, value in libffi.types.__dict__.iteritems():
        if key == 'getkind' or key.startswith('__'):
            continue
        assert lltype.typeOf(value) == FFI_TYPE_P
        tdict[key] = W_FFIType(key, value)
    return tdict
    
W_types.typedef = TypeDef(
    'types',
    **build_ffi_types())

# ========================================================================

class W_FuncPtr(Wrappable):

    _immutable_fields_ = ['func']
    
    def __init__(self, func):
        self.func = func

    @jit.unroll_safe
    def build_argchain(self, space, argtypes, args_w):
        expected = len(argtypes)
        given = len(args_w)
        if given != expected:
            arg = 'arguments'
            if len(argtypes) == 1:
                arg = 'argument'
            raise operationerrfmt(space.w_TypeError,
                                  '%s() takes exactly %d %s (%d given)',
                                  self.func.name, expected, arg, given)
        #
        argchain = libffi.ArgChain()
        for i in range(expected):
            argtype = argtypes[i]
            w_arg = args_w[i]
            kind = libffi.types.getkind(argtype)
            if kind == 'i':
                argchain.arg(space.int_w(w_arg))
            elif kind == 'u':
                argchain.arg(intmask(space.uint_w(w_arg)))
            elif kind == 'f':
                argchain.arg(space.float_w(w_arg))
            else:
                assert False, "Argument kind '%s' not supported" % kind
        return argchain

    @unwrap_spec('self', ObjSpace, 'args_w')
    def call(self, space, args_w):
        self = jit.hint(self, promote=True)
        argchain = self.build_argchain(space, self.func.argtypes, args_w)
        reskind = libffi.types.getkind(self.func.restype)
        if reskind == 'i':
            intres = self.func.call(argchain, rffi.LONG)
            return space.wrap(intres)
        elif reskind == 'u':
            intres = self.func.call(argchain, rffi.ULONG)
            return space.wrap(intres)
        elif reskind == 'f':
            floatres = self.func.call(argchain, rffi.DOUBLE)
            return space.wrap(floatres)
        else:
            voidres = self.func.call(argchain, lltype.Void)
            assert voidres is None
            return space.w_None

    @unwrap_spec('self', ObjSpace)
    def getaddr(self, space):
        """
        Return the physical address in memory of the function
        """
        return space.wrap(rffi.cast(rffi.LONG, self.func.funcsym))

W_FuncPtr.typedef = TypeDef(
    'FuncPtr',
    __call__ = interp2app(W_FuncPtr.call),
    getaddr = interp2app(W_FuncPtr.getaddr),
    )



# ========================================================================

class W_CDLL(Wrappable):
    def __init__(self, space, name):
        try:
            self.cdll = libffi.CDLL(name)
        except DLOpenError, e:
            raise operationerrfmt(space.w_OSError, '%s: %s', name,
                                  e.msg or 'unspecified error')
        self.name = name
        self.space = space

    def ffitype(self, w_argtype, allow_void=False):
        res = self.space.interp_w(W_FFIType, w_argtype).ffitype
        if res is libffi.types.void and not allow_void:
            space = self.space
            msg = 'void is not a valid argument type'
            raise OperationError(space.w_TypeError, space.wrap(msg))
        return res

    @unwrap_spec('self', ObjSpace, str, W_Root, W_Root)
    def getfunc(self, space, name, w_argtypes, w_restype):
        argtypes = [self.ffitype(w_argtype) for w_argtype in
                    space.listview(w_argtypes)]
        restype = self.ffitype(w_restype, allow_void=True)
        func = self.cdll.getpointer(name, argtypes, restype)
        return W_FuncPtr(func)


@unwrap_spec(ObjSpace, W_Root, str)
def descr_new_cdll(space, w_type, name):
    return space.wrap(W_CDLL(space, name))


W_CDLL.typedef = TypeDef(
    'CDLL',
    __new__     = interp2app(descr_new_cdll),
    getfunc     = interp2app(W_CDLL.getfunc),
    )

# ========================================================================
