from pypy.rpython.ootypesystem import ootype
from pypy.translator.oosupport.metavm import MicroInstruction
from pypy.translator.jvm.typesystem import JvmScalarType, JvmClassType
import pypy.translator.jvm.generator as jvmgen
import pypy.translator.jvm.typesystem as jvmtype
from pypy.translator.jvm.builtin import JvmBuiltInType

class _IndirectCall(MicroInstruction):
    def render(self, gen, op):
        interface = gen.db.lltype_to_cts(op.args[0].concretetype)
        method = interface.lookup_method('invoke')
        gen.emit(method)
IndirectCall = _IndirectCall()

class _JvmCallMethod(MicroInstruction):

    def _invoke_method(self, gen, db, jmethod, jactargs, args, jactres, res):
        assert len(args) == len(jactargs)
        for arg, jmthdty in zip(args, jactargs):
            # Load the argument on the stack:
            gen.load(arg)
            
            # Perform any boxing required:
            jargty = db.lltype_to_cts(arg.concretetype)
            if jargty != jmthdty:
                gen.prepare_generic_argument(arg.concretetype)
                
        gen.emit(jmethod)

        # Perform any unboxing required:
        jresty = db.lltype_to_cts(res.concretetype)
        if jresty != jactres:
            gen.prepare_generic_result(res.concretetype)
    
    def render(self, gen, op):

        method = op.args[0] # a FlowConstant string...
        this = op.args[1]

        # Locate the java method we will be invoking:
        thisjtype = gen.db.lltype_to_cts(this.concretetype)
        jmethod = thisjtype.lookup_method(method.value)

        # if this is a builtin-type, the signature is exact and we
        # need to keep Void values; else, the signature does not
        # include Void values, so we need to drop them.
        if isinstance(thisjtype, JvmBuiltInType):
            args = op.args[2:]
        else:
            args = [arg for arg in op.args[2:] if arg.concretetype is not ootype.Void]

        # Ugly: if jmethod ends up being a static method, then
        # peel off the first argument
        jactargs = jmethod.argument_types
        if jmethod.is_static():
            jactargs = jactargs[1:]

        # Iterate through the arguments, inserting casts etc as required
        gen.load(this)
        self._invoke_method(gen, gen.db, jmethod,
                            jactargs, args,
                            jmethod.return_type, op.result)
JvmCallMethod = _JvmCallMethod()

class _NewCustomDict(MicroInstruction):
    def _load_func(self, gen, fn, obj, method_name):
        db = gen.db
        if fn.value:
            # Standalone function: find the delegate class and
            # instantiate it.
            assert method_name.value is None
            smimpl = fn.value                      # ootype._static_meth
            db.record_delegate(smimpl._TYPE)       # _TYPE is a StaticMethod
            ty = db.record_delegate_standalone_func_impl(smimpl.graph)
            gen.new_with_jtype(ty)
        else:
            # Bound method: create a wrapper bound to the given
            # object, using the "bind()" static method that bound
            # method wrapper classes have.
            INSTANCE = obj.concretetype
            method_name = method_name.value
            ty = db.record_delegate_bound_method_impl(INSTANCE, method_name)
            gen.load(obj)
            gen.emit(ty.bind_method)
    def render(self, generator, op):
        self._load_func(generator, *op.args[1:4])
        self._load_func(generator, *op.args[4:7])
        generator.emit(jvmgen.CUSTOMDICTMAKE)
NewCustomDict = _NewCustomDict()

CASTS = {
#   FROM                      TO
    (ootype.Signed,           ootype.UnsignedLongLong): jvmgen.I2L,
    (ootype.SignedLongLong,   ootype.Signed):           jvmgen.L2I,
    (ootype.UnsignedLongLong, ootype.SignedLongLong):   None,
    }

class _CastPrimitive(MicroInstruction):
    def render(self, generator, op):
        FROM = op.args[0].concretetype
        TO = op.result.concretetype
        opcode = CASTS[(FROM, TO)]
        if opcode:
            generator.emit(opcode)
CastPrimitive = _CastPrimitive()

class _PushPyPy(MicroInstruction):
    """ Pushes the PyPy instance where our helper functions are found
    from the static field on the generated PyPyMain class """
    def render(self, generator, op):
        generator.push_pypy()
PushPyPy = _PushPyPy()
