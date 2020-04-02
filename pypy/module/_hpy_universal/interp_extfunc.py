from rpython.rtyper.lltypesystem import lltype, rffi
from pypy.interpreter.error import oefmt
from pypy.interpreter.baseobjspace import W_Root
from pypy.interpreter.typedef import TypeDef, interp2app

from pypy.module._hpy_universal import llapi, handles
from pypy.module._hpy_universal.state import State


class W_ExtensionFunction(W_Root):
    _immutable_fields_ = ["flags", "name"]

    def __init__(self, ml, w_self):
        self.ml = ml
        self.w_self = w_self
        self.name = rffi.constcharp2str(self.ml.c_ml_name)
        self.flags = rffi.cast(lltype.Signed, self.ml.c_ml_flags)
        # fetch the real HPy function pointer, by calling ml_meth, which
        # is a function that returns it and also the CPython-only trampoline
        with lltype.scoped_alloc(
                rffi.CArray(llapi.HPyMeth_O), 1) as funcptr:
            with lltype.scoped_alloc(
                    rffi.CArray(llapi._HPyCPyCFunction), 1) as ignored_trampoline:
                ml.c_ml_meth(funcptr, ignored_trampoline)
                self.cfuncptr = funcptr[0]

    def call_noargs(self, space):
        state = space.fromcache(State)
        with handles.using(space, self.w_self) as h_self:
            h_result = self.cfuncptr(state.ctx, h_self, 0)
        # XXX check for exceptions
        return handles.consume(space, h_result)

    def call_o(self, space, w_arg):
        state = space.fromcache(State)
        with handles.using(space, self.w_self) as h_self:
            with handles.using(space, w_arg) as h_arg:
                h_result = self.cfuncptr(state.ctx, h_self, h_arg)
        # XXX check for exceptions
        return handles.consume(space, h_result)

    def call_varargs_kw(self, space, __args__, has_keywords):
        # this function is more or less the equivalent of
        # ctx_CallRealFunctionFromTrampoline in cpython-universal
        n = len(__args__.arguments_w)

        # XXX this looks inefficient: ideally, we would like the equivalent of
        # alloca(): do we have it in RPython? The alternative is to wrap
        # arguments_w in a tuple, convert to handle and pass it to a C
        # function whichs calls alloca() and the forwards everything to the
        # functpr
        with handles.using(space, self.w_self) as h_self:
            with lltype.scoped_alloc(rffi.CArray(llapi.HPy), n) as args_h:
                for i, w_obj in enumerate(__args__.arguments_w):
                    args_h[i] = handles.new(space, w_obj)

                if has_keywords:
                    h_result = self.call_keywords(space, h_self, args_h, n, __args__)
                else:
                    h_result = self.call_varargs(space, h_self, args_h, n)

                # XXX this should probably be in a try/finally. We should add a
                # test to check that we don't leak handles
                for i in range(n):
                    handles.close(space, args_h[i])

        return handles.consume(space, h_result)

    def call_varargs(self, space, h_self, args_h, n):
        state = space.fromcache(State)
        # XXX: is it correct to use rffi.cast instead of some kind of
        # lltype.cast_*?
        fptr = rffi.cast(llapi.HPyMeth_VarArgs, self.cfuncptr)
        return fptr(state.ctx, h_self, args_h, n)

    def call_keywords(self, space, h_self, args_h, n, __args__):
        state = space.fromcache(State)
        # XXX: if there are no keywords, should we pass HPy_NULL or an empty
        # dict?
        h_kw = 0
        if __args__.keywords:
            w_kw = space.newdict()
            for i in range(len(__args__.keywords)):
                key = __args__.keywords[i]
                w_value = __args__.keywords_w[i]
                space.setitem_str(w_kw, key, w_value)
            h_kw = handles.new(space, w_kw)

        fptr = rffi.cast(llapi.HPyMeth_Keywords, self.cfuncptr)
        try:
            return fptr(state.ctx, h_self, args_h, n, h_kw)
        finally:
            if h_kw:
                handles.consume(space, h_kw)


    def descr_call(self, space, __args__):
        flags = self.flags
        length = len(__args__.arguments_w)

        if flags == llapi.HPy_METH_KEYWORDS:
            return self.call_varargs_kw(space, __args__, has_keywords=True)

        if __args__.keywords:
            raise oefmt(space.w_TypeError,
                        "%s() takes no keyword arguments", self.name)

        if flags == llapi.HPy_METH_NOARGS:
            if length == 0:
                return self.call_noargs(space)
            raise oefmt(space.w_TypeError,
                        "%s() takes no arguments", self.name)

        if flags == llapi.HPy_METH_O:
            if length != 1:
                raise oefmt(space.w_TypeError,
                            "%s() takes exactly one argument (%d given)",
                            self.name, length)
            return self.call_o(space, __args__.arguments_w[0])

        if flags == llapi.HPy_METH_VARARGS:
            return self.call_varargs_kw(space, __args__, has_keywords=False)
        else:  # shouldn't happen!
            raise oefmt(space.w_RuntimeError, "unknown calling convention")



W_ExtensionFunction.typedef = TypeDef(
    'extension_function',
    __call__ = interp2app(W_ExtensionFunction.descr_call),
    )
W_ExtensionFunction.typedef.acceptable_as_base_class = False