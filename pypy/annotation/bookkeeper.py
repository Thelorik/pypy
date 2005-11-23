"""
The Bookkeeper class.
"""

from __future__ import generators
import sys, types, inspect

from pypy.objspace.flow.model import Constant
from pypy.annotation.model import SomeString, SomeChar, SomeFloat, \
     SomePtr, unionof, SomeInstance, SomeDict, SomeBuiltin, SomePBC, \
     SomeInteger, SomeExternalObject, SomeOOInstance, TLS, SomeAddress, \
     SomeUnicodeCodePoint, SomeOOStaticMeth, s_None, s_ImpossibleValue, \
     SomeLLADTMeth, SomeBool, SomeTuple, SomeOOClass, SomeImpossibleValue, \
     SomeList, SomeObject
from pypy.annotation.classdef import ClassDef, InstanceSource
from pypy.annotation.listdef import ListDef, MOST_GENERAL_LISTDEF
from pypy.annotation.dictdef import DictDef, MOST_GENERAL_DICTDEF
from pypy.annotation import description
from pypy.interpreter.argument import Arguments, ArgErr
from pypy.rpython.rarithmetic import r_uint
from pypy.rpython.objectmodel import r_dict
from pypy.tool.algo.unionfind import UnionFind
from pypy.rpython.lltypesystem import lltype
from pypy.rpython.ootypesystem import ootype
from pypy.rpython.memory import lladdress

class Stats:

    def __init__(self, bookkeeper):
        self.bookkeeper = bookkeeper
        self.classify = {}

    def count(self, category, *args):
        for_category = self.classify.setdefault(category, {})
        classifier = getattr(self, 'consider_%s' % category, self.consider_generic)
        outcome = classifier(*args)
        for_category[self.bookkeeper.position_key] = outcome

    def indexrepr(self, idx):
        if idx.is_constant():
            if idx.const is None:
                return ''
            if isinstance(idx, SomeInteger):
                if idx.const >=0:
                    return 'pos-constant'
                else:
                    return 'Neg-constant'
            return idx.const
        else:
            if isinstance(idx, SomeInteger):
                if idx.nonneg:
                    return "non-neg"
                else:
                    return "MAYBE-NEG"
            else:
                return self.typerepr(idx)

    def steprepr(self, stp):
        if stp.is_constant():
            if stp.const in (1, None):
                return 'step=1'
            else:
                return 'step=%s?' % stp.const
        else:
            return 'non-const-step %s' % self.typerepr(stp)

    def consider_generic(self, *args):
        return tuple([self.typerepr(x) for x in args])

    def consider_newslice(self, s_start, s_stop, s_step):
        return ':'.join([self.indexrepr(s_start), self.indexrepr(s_stop), self.steprepr(s_step)])

    def consider_list_list_eq(self, obj1, obj2):
        return obj1, obj2

    def consider_contains(self, seq):
        return seq

    def consider_non_int_eq(self, obj1, obj2):
        if obj1.knowntype == obj2.knowntype == list:
            self.count("list_list_eq", obj1, obj2)
        return obj1.knowntype.__name__, obj2.knowntype.__name__

    def consider_non_int_comp(self, obj1, obj2):
        return obj1.knowntype.__name__, obj2.knowntype.__name__

    def typerepr(self, obj):
        if isinstance(obj, SomeInstance):
            return obj.classdef.name
        else:
            return obj.knowntype.__name__

    def consider_tuple_iter(self, tup):
        ctxt = "[%s]" % sys._getframe(4).f_code.co_name
        if tup.is_constant():
            return ctxt, tup.const
        else:
            return ctxt, tuple([self.typerepr(x) for x in tup.items])

    def consider_tuple_random_getitem(self, tup):
        return tuple([self.typerepr(x) for x in tup.items])

    def consider_list_index(self):
        return '!'

    def consider_list_getitem(self, idx):
        return self.indexrepr(idx)

    def consider_list_setitem(self, idx):
        return self.indexrepr(idx)

    def consider_list_delitem(self, idx):
        return self.indexrepr(idx)
    
    def consider_str_join(self, s):
        if s.is_constant():
            return repr(s.const)
        else:
            return "NON-CONSTANT"

    def consider_str_getitem(self, idx):
        return self.indexrepr(idx)

    def consider_strformat(self, str, args):
        if str.is_constant():
            s = repr(str.const)
        else:
            s = "?!!!!!!"
        if isinstance(args, SomeTuple):
            return (s, tuple([self.typerepr(x) for x in args.items]))
        else:
            return (s, self.typerepr(args))

    def consider_dict_getitem(self, dic):
        return dic

    def consider_dict_setitem(self, dic):
        return dic

    def consider_dict_delitem(self, dic):
        return dic
            

class Bookkeeper:
    """The log of choices that have been made while analysing the operations.
    It ensures that the same 'choice objects' will be returned if we ask
    again during reflowing.  Like ExecutionContext, there is an implicit
    Bookkeeper that can be obtained from a thread-local variable.

    Currently used for factories and user-defined classes."""

    def __setstate__(self, dic):
        self.__dict__.update(dic) # normal action
        delayed_imports()

    def __init__(self, annotator):
        self.annotator = annotator
        self.descs = {}          # map Python objects to their XxxDesc wrappers
        self.methoddescs = {}    # map (funcdesc, classdef) to the MethodDesc
        self.classdefs = []      # list of all ClassDefs
        self.pbctypes = {}
        self.seen_mutable = {}
        self.listdefs = {}       # map position_keys to ListDefs
        self.dictdefs = {}       # map position_keys to DictDefs
        self.immutable_cache = {}

        self.pbc_maximal_access_sets = UnionFind(description.AttrFamily)
        self.pbc_maximal_call_families = UnionFind(description.CallFamily)

        self.needs_hash_support = {}
        self.needs_generic_instantiate = {}

        self.stats = Stats(self)

        delayed_imports()

    def count(self, category, *args):
        self.stats.count(category, *args)

    def enter(self, position_key):
        """Start of an operation.
        The operation is uniquely identified by the given key."""
        self.position_key = position_key
        TLS.bookkeeper = self

    def leave(self):
        """End of an operation."""
        del TLS.bookkeeper
        del self.position_key

    def compute_at_fixpoint(self):
        # getbookkeeper() needs to work during this function, so provide
        # one with a dummy position
        self.enter(None)
        try:
            def call_sites():
                newblocks = self.annotator.added_blocks
                if newblocks is None:
                    newblocks = self.annotator.annotated  # all of them
                for block in newblocks:
                    for op in block.operations:
                        if op.opname in ('simple_call', 'call_args'):
                            yield op

            for call_op in call_sites():
                self.consider_call_site(call_op)

            for cls in self.needs_hash_support.keys():
                for cls2 in self.needs_hash_support:
                    if issubclass(cls, cls2) and cls is not cls2:
                        del self.needs_hash_support[cls]
                        break
        finally:
            self.leave()

    def consider_call_site(self, call_op):
        binding = self.annotator.binding
        s_callable = binding(call_op.args[0])
        args_s = [binding(arg) for arg in call_op.args[1:]]
        if isinstance(s_callable, SomeLLADTMeth):
            adtmeth = s_callable
            s_callable = self.immutablevalue(adtmeth.func)
            args_s = [SomePtr(adtmeth.ll_ptrtype)] + args_s
        if isinstance(s_callable, SomePBC):
            descs = s_callable.descriptions.keys()
            family = descs[0].getcallfamily()
            args = self.build_args(call_op.opname, args_s)
            s_callable.getKind().consider_call_site(self, family, descs, args)

    def getuniqueclassdef(self, cls):
        """Get the ClassDef associated with the given user cls.
        Avoid using this!  It breaks for classes that must be specialized.
        """
        if cls is object:
            return None
        desc = self.getdesc(cls)
        return desc.getuniqueclassdef()

    def getlistdef(self, **flags):
        """Get the ListDef associated with the current position."""
        try:
            listdef = self.listdefs[self.position_key]
        except KeyError:
            listdef = self.listdefs[self.position_key] = ListDef(self)
            listdef.listitem.__dict__.update(flags)
        return listdef

    def newlist(self, *s_values, **flags):
        """Make a SomeList associated with the current position, general
        enough to contain the s_values as items."""
        listdef = self.getlistdef(**flags)
        for s_value in s_values:
            listdef.generalize(s_value)
        return SomeList(listdef)

    def getdictdef(self):
        """Get the DictDef associated with the current position."""
        try:
            dictdef = self.dictdefs[self.position_key]
        except KeyError:
            dictdef = self.dictdefs[self.position_key] = DictDef(self)
        return dictdef

    def newdict(self, *items_s):
        """Make a SomeDict associated with the current position, general
        enough to contain the given (s_key, s_value) as items."""
        dictdef = self.getdictdef()
        for s_key, s_value in items_s:
            dictdef.generalize_key(s_key)
            dictdef.generalize_value(s_value)
        return SomeDict(dictdef)

    def immutablevalue(self, x):
        """The most precise SomeValue instance that contains the
        immutable value x."""
         # convert unbound methods to the underlying function
        if hasattr(x, 'im_self') and x.im_self is None:
            x = x.im_func
            assert not hasattr(x, 'im_self')
        if x is sys: # special case constant sys to someobject
            return SomeObject()
        tp = type(x)
        if tp is bool:
            result = SomeBool()
        elif tp is int:
            result = SomeInteger(nonneg = x>=0)
        elif tp is r_uint:
            result = SomeInteger(nonneg = True, unsigned = True)
        elif issubclass(tp, str): # py.lib uses annotated str subclasses
            if len(x) == 1:
                result = SomeChar()
            else:
                result = SomeString()
        elif tp is unicode and len(x) == 1:
            result = SomeUnicodeCodePoint()
        elif tp is tuple:
            result = SomeTuple(items = [self.immutablevalue(e) for e in x])
        elif tp is float:
            result = SomeFloat()
        elif tp is list:
            key = Constant(x)
            try:
                return self.immutable_cache[key]
            except KeyError:
                result = SomeList(ListDef(self, SomeImpossibleValue()))
                self.immutable_cache[key] = result
                for e in x:
                    result.listdef.generalize(self.immutablevalue(e))
        elif tp is dict or tp is r_dict:
            key = Constant(x)
            try:
                return self.immutable_cache[key]
            except KeyError:
                result = SomeDict(DictDef(self, 
                                          SomeImpossibleValue(),
                                          SomeImpossibleValue()))
                self.immutable_cache[key] = result
                if tp is r_dict:
                    s_eqfn = self.immutablevalue(x.key_eq)
                    s_hashfn = self.immutablevalue(x.key_hash)
                    result.dictdef.dictkey.update_rdict_annotations(s_eqfn,
                                                                    s_hashfn)
                for ek, ev in x.iteritems():
                    result.dictdef.generalize_key(self.immutablevalue(ek))
                    result.dictdef.generalize_value(self.immutablevalue(ev))
        elif ishashable(x) and x in BUILTIN_ANALYZERS:
            result = SomeBuiltin(BUILTIN_ANALYZERS[x], methodname="%s.%s" % (x.__module__, x.__name__))
        elif tp in EXTERNAL_TYPE_ANALYZERS:
            result = SomeExternalObject(tp)
        elif isinstance(x, lltype._ptr):
            result = SomePtr(lltype.typeOf(x))
        elif isinstance(x, lladdress.address):
            assert x is lladdress.NULL
            result= SomeAddress(is_null=True)
        elif isinstance(x, ootype._static_meth):
            result = SomeOOStaticMeth(ootype.typeOf(x))
        elif isinstance(x, ootype._class):
            result = SomeOOClass(x._INSTANCE)   # NB. can be None
        elif isinstance(x, ootype._instance):
            result = SomeOOInstance(ootype.typeOf(x))
        elif callable(x) or isinstance(x, staticmethod): # XXX
            if hasattr(x, '__self__') and x.__self__ is not None:
                # for cases like 'l.append' where 'l' is a global constant list
                s_self = self.immutablevalue(x.__self__)
                result = s_self.find_method(x.__name__)
                if result is None:
                    result = SomeObject()
            else:
                result = SomePBC([self.getdesc(x)])
        elif hasattr(x, '__class__') \
                 and x.__class__.__module__ != '__builtin__':
            # user-defined classes can define a method _freeze_(), which
            # is called when a prebuilt instance is found.  If the method
            # returns True, the instance is considered immutable and becomes
            # a SomePBC().  Otherwise it's just SomeInstance().
            frozen = hasattr(x, '_freeze_') and x._freeze_()
            if frozen:
                result = SomePBC([self.getdesc(x)])
            else:
                clsdef = self.getuniqueclassdef(x.__class__)
                if x not in self.seen_mutable: # avoid circular reflowing, 
                                               # see for example test_circular_mutable_getattr
                    self.seen_mutable[x] = True
                    self.event('mutable', x)
                    source = InstanceSource(self, x)
                    for attr in x.__dict__:
                        clsdef.add_source_for_attribute(attr, source) # can trigger reflowing
                result = SomeInstance(clsdef)
        elif x is None:
            return s_None
        else:
            result = SomeObject()
        result.const = x
        return result

    def getdesc(self, pyobj):
        # get the XxxDesc wrapper for the given Python object, which must be
        # one of:
        #  * a user-defined Python function
        #  * a Python type or class (but not a built-in one like 'int')
        #  * a user-defined bound or unbound method object
        #  * a frozen pre-built constant (with _freeze_() == True)
        #  * a bound method of a frozen pre-built constant
        try:
            return self.descs[pyobj]
        except KeyError:
            if isinstance(pyobj, types.FunctionType):
                result = description.FunctionDesc(self, pyobj)
            elif isinstance(pyobj, (type, types.ClassType)):
                if pyobj is object:
                    raise Exception, "ClassDesc for object not supported"
                result = description.ClassDesc(self, pyobj)
            elif isinstance(pyobj, types.MethodType):
                if pyobj.im_self is None:   # unbound
                    return self.getdesc(pyobj.im_func)
                elif (hasattr(pyobj.im_self, '_freeze_') and
                      pyobj.im_self._freeze_()):  # method of frozen
                    result = description.MethodOfFrozenDesc(self,
                        self.getdesc(pyobj.im_func),            # funcdesc
                        self.getdesc(pyobj.im_self))            # frozendesc
                else: # regular method
                    result = self.getmethoddesc(
                        self.getdesc(pyobj.im_func),            # funcdesc
                        self.getuniqueclassdef(pyobj.im_class), # classdef
                        name_of_meth(pyobj))
            else:
                # must be a frozen pre-built constant, but let's check
                assert pyobj._freeze_()
                result = description.FrozenDesc(self, pyobj)
                cls = result.knowntype
                if cls not in self.pbctypes:
                    self.pbctypes[cls] = True
                    # XXX what to do about this old check?:
                    #if cls in self.userclasses:
                    #    self.warning("making some PBC of type %r, which has "
                    #                 "already got a ClassDef" % (cls,))
            self.descs[pyobj] = result
            return result

    def getmethoddesc(self, funcdesc, classdef, name):
        try:
            return self.methoddescs[funcdesc, classdef, name]
        except KeyError:
            result = description.MethodDesc(self, funcdesc, classdef, name)
            self.methoddescs[funcdesc, classdef, name] = result
            return result

    def valueoftype(self, t):
        """The most precise SomeValue instance that contains all
        objects of type t."""
        assert isinstance(t, (type, types.ClassType))
        if t is bool:
            return SomeBool()
        elif t is int:
            return SomeInteger()
        elif t is r_uint:
            return SomeInteger(nonneg = True, unsigned = True)
        elif issubclass(t, str): # py.lib uses annotated str subclasses
            return SomeString()
        elif t is float:
            return SomeFloat()
        elif t is list:
            return SomeList(MOST_GENERAL_LISTDEF)
        elif t is dict:
            return SomeDict(MOST_GENERAL_DICTDEF)
        # can't do tuple
        elif t is types.NoneType:
            return s_None
        elif t in EXTERNAL_TYPE_ANALYZERS:
            return SomeExternalObject(t)
        elif t.__module__ != '__builtin__' and t not in self.pbctypes:
            classdef = self.getuniqueclassdef(t)
            return SomeInstance(classdef)
        else:
            o = SomeObject()
            if t != object:
                o.knowntype = t
            return o

    def pbc_getattr(self, pbc, s_attr):
        assert s_attr.is_constant()
        attr = s_attr.const

        descs = pbc.descriptions.keys()
        if not descs:
            return SomeImpossibleValue()
        first = descs[0]
        change = first.mergeattrfamilies(*descs[1:])
        attrfamily = first.getattrfamily()

        position = self.position_key
        attrfamily.read_locations[position] = True

        actuals = []
        for desc in attrfamily.descs:
            actuals.append(desc.s_read_attribute(attr))
        s_result = unionof(*actuals)

        attrfamily.attrs[attr] = s_result

        if change:
            for position in attrfamily.read_locations:
                self.annotator.reflowfromposition(position)
                
        return s_result

    def pbc_call(self, pbc, args, emulated=None):
        """Analyse a call to a SomePBC() with the given args (list of
        annotations).
        """
        descs = pbc.descriptions.keys()
        if not descs:
            return SomeImpossibleValue()
        first = descs[0]
        first.mergecallfamilies(*descs[1:])
        callfamily = first.getcallfamily()

        shape = args.rawshape()
        callfamily.patterns[shape] = True

        if emulated is None:
            whence = self.position_key
            # fish the existing annotation for the result variable,
            # needed by some kinds of specialization.
            fn, block, i = self.position_key
            op = block.operations[i]
            s_previous_result = self.annotator.binding(op.result,
                                                       extquery=True)
            if s_previous_result is None:
                s_previous_result = s_ImpossibleValue
        else:
            if emulated is True:
                whence = None
            else:
                whence = emulated # callback case
            s_previous_result = s_ImpossibleValue

        def schedule(graph, inputcells):
            return self.annotator.recursivecall(graph, whence, inputcells)

        results = []
        for desc in descs:
            results.append(desc.pycall(schedule, args, s_previous_result))
        s_result = unionof(*results)
        return s_result

    def emulate_pbc_call(self, unique_key, pbc, args_s, replace=[], callback=None):
        args = self.build_args("simple_call", args_s)
        if callback is None:
            emulated = True
        else:
            emulated = callback
        return self.pbc_call(pbc, args, emulated=emulated)

    def build_args(self, op, args_s):
        space = RPythonCallsSpace()
        if op == "simple_call":
            return Arguments(space, list(args_s))
        elif op == "call_args":
            return Arguments.fromshape(space, args_s[0].const, # shape
                                       list(args_s[1:]))

    def ondegenerated(self, what, s_value, where=None, called_from_graph=None):
        self.annotator.ondegenerated(what, s_value, where=where,
                                     called_from_graph=called_from_graph)
        
    def whereami(self):
        return self.annotator.whereami(self.position_key)

    def event(self, what, x):
        return self.annotator.policy.event(self, what, x)

    def warning(self, msg):
        return self.annotator.warning(msg)

def name_of_meth(boundmeth):
    func = boundmeth.im_func
    candname = func.func_name
    for cls in inspect.getmro(boundmeth.im_class):
        dict = cls.__dict__
        if dict.get(candname) is func:
            return candname
        for name, value in dict.iteritems():
            if value is func:
                return name
    raise Exception, "could not match bound-method to attribute name: %r" % (boundmeth,)

def ishashable(x):
    try:
        hash(x)
    except TypeError:
        return False
    else:
        return True

# for parsing call arguments
class RPythonCallsSpace:
    """Pseudo Object Space providing almost no real operation.
    For the Arguments class: if it really needs other operations, it means
    that the call pattern is too complex for R-Python.
    """
    def newtuple(self, items_s):
        return SomeTuple(items_s)

    def newdict(self, stuff):
        raise CallPatternTooComplex, "'**' argument"

    def unpackiterable(self, s_obj, expected_length=None):
        if isinstance(s_obj, SomeTuple):
            if (expected_length is not None and
                expected_length != len(s_obj.items)):
                raise ValueError
            return s_obj.items
        raise CallPatternTooComplex, "'*' argument must be SomeTuple"

class CallPatternTooComplex(Exception):
    pass

# get current bookkeeper

def getbookkeeper():
    """Get the current Bookkeeper.
    Only works during the analysis of an operation."""
    try:
        return TLS.bookkeeper
    except AttributeError:
        return None


def delayed_imports():
    # import ordering hack
    global BUILTIN_ANALYZERS, EXTERNAL_TYPE_ANALYZERS
    from pypy.annotation.builtin import BUILTIN_ANALYZERS
    from pypy.annotation.builtin import EXTERNAL_TYPE_ANALYZERS

