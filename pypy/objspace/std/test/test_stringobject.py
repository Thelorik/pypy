import autopath
from pypy.tool import test
from pypy.objspace.std import stringobject
from pypy.objspace.std.stringobject import \
     string_richcompare, W_StringObject, EQ, LT, GT, NE, LE, GE


class TestW_StringObject(test.TestCase):

    def setUp(self):
        self.space = test.objspace('std')

    def tearDown(self):
        pass

    def test_order_rich(self):
        space = self.space
        def w(txt):
             return W_StringObject(space, txt)
        strs = ['ala', 'bla', 'ala', 'alaaa', '', 'b']
        ops = [ 'EQ', 'LT', 'GT', 'NE', 'LE', 'GE' ]

        while strs[1:]:
            str1 = strs.pop()
            for op in ops:
                 #original python function
                orf = getattr(str1, '__%s__' % op.lower()) 
                pypyconst = getattr(stringobject, op)
                for str2 in strs:   
                    if orf(str2):
                         self.failUnless_w(
                             string_richcompare(space,
                                                w(str1),
                                                w(str2),
                                                pypyconst))
                    else:
                         self.failIf_w(
                             string_richcompare(space,
                                                w(str1),
                                                w(str2),
                                                pypyconst))
        
    def test_equality(self):
        w = self.space.wrap 
        self.assertEqual_w(w('abc'), w('abc'))
        self.assertNotEqual_w(w('abc'), w('def'))

    def test_order_cmp(self):
        space = self.space
        w = space.wrap
        self.failUnless_w(space.lt(w('a'), w('b')))
        self.failUnless_w(space.lt(w('a'), w('ab')))
        self.failUnless_w(space.le(w('a'), w('a')))
        self.failUnless_w(space.gt(w('a'), w('')))

    def test_truth(self):
        w = self.space.wrap
        self.failUnless_w(w('non-empty'))
        self.failIf_w(w(''))

    def test_getitem(self):
        space = self.space
        w = space.wrap
        w_str = w('abc')
        self.assertEqual_w(space.getitem(w_str, w(0)), w('a'))
        self.assertEqual_w(space.getitem(w_str, w(-1)), w('c'))
        self.assertRaises_w(space.w_IndexError,
                            space.getitem,
                            w_str,
                            w(3))

    def test_slice(self):
        space = self.space
        w = space.wrap
        w_str = w('abc')

        w_slice = space.newslice(w(0), w(0), None)
        self.assertEqual_w(space.getitem(w_str, w_slice), w(''))

        w_slice = space.newslice(w(0), w(1), None)
        self.assertEqual_w(space.getitem(w_str, w_slice), w('a'))

        w_slice = space.newslice(w(0), w(10), None)
        self.assertEqual_w(space.getitem(w_str, w_slice), w('abc'))

        w_slice = space.newslice(space.w_None, space.w_None, None)
        self.assertEqual_w(space.getitem(w_str, w_slice), w('abc'))

        w_slice = space.newslice(space.w_None, w(-1), None)
        self.assertEqual_w(space.getitem(w_str, w_slice), w('ab'))

        w_slice = space.newslice(w(-1), space.w_None, None)
        self.assertEqual_w(space.getitem(w_str, w_slice), w('c'))

    def test_extended_slice(self):
        space = self.space
        if self.space.__class__.__name__.startswith('Trivial'):
            import sys
            if sys.version < (2, 3):
                return
        w_None = space.w_None
        w = space.wrap
        w_str = w('hello')

        w_slice = space.newslice(w_None, w_None, w(1))
        self.assertEqual_w(space.getitem(w_str, w_slice), w('hello'))

        w_slice = space.newslice(w_None, w_None, w(-1))
        self.assertEqual_w(space.getitem(w_str, w_slice), w('olleh'))

        w_slice = space.newslice(w_None, w_None, w(2))
        self.assertEqual_w(space.getitem(w_str, w_slice), w('hlo'))

        w_slice = space.newslice(w(1), w_None, w(2))
        self.assertEqual_w(space.getitem(w_str, w_slice), w('el'))


#AttributeError: W_StringObject instance has no attribute 'ljust'
#    def test_ljust(self):
#        w = self.space.wrap         
#        s = "abc"
#
#        self.assertEqual_w(w(s).ljust(2), w(s))
#        self.assertEqual_w(w(s).ljust(3), w(s))
#        self.assertEqual_w(w(s).ljust(4), w(s + " "))
#        self.assertEqual_w(w(s).ljust(5), w(s + "  "))    

class TestStringObject(test.AppTestCase):
    def test_split(self):
        self.assertEquals("".split(), [])
        self.assertEquals("a".split(), ['a'])
        self.assertEquals(" a ".split(), ['a'])
        self.assertEquals("a b c".split(), ['a','b','c'])

    def test_split_splitchar(self):
        self.assertEquals("/a/b/c".split('/'), ['','a','b','c'])

    def test_title(self):
        self.assertEquals("brown fox".title(), "Brown Fox")

    def test_capitalize(self):
        self.assertEquals("brown fox".capitalize(), "Brown fox")

    def test_rjust(self):
        s = "abc"
        self.assertEquals(s.rjust(2), s)
        self.assertEquals(s.rjust(3), s)
        self.assertEquals(s.rjust(4), " " + s)
        self.assertEquals(s.rjust(5), "  " + s)

    def test_ljust(self):
        s = "abc"
        self.assertEquals(s.ljust(2), s)
        self.assertEquals(s.ljust(3), s)
        self.assertEquals(s.ljust(4), s + " ")
        self.assertEquals(s.ljust(5), s + "  ")

    def test_strip(self):
        s = " a b "
        self.assertEquals(s.strip(), "a b")
        self.assertEquals(s.rstrip(), " a b")
        self.assertEquals(s.lstrip(), "a b ")
            
    def test_center(self):
        s="a b"
        self.assertEquals(s.center(0), "a b")
        self.assertEquals(s.center(1), "a b")
        self.assertEquals(s.center(2), "a b")
        self.assertEquals(s.center(3), "a b")
        self.assertEquals(s.center(4), "a b ")
        self.assertEquals(s.center(5), " a b ")
        self.assertEquals(s.center(6), " a b  ")
        self.assertEquals(s.center(7), "  a b  ")
        self.assertEquals(s.center(8), "  a b   ")
        self.assertEquals(s.center(9), "   a b   ")
        
    def test_count(self):
        self.assertEquals("".count("x"),0)
        self.assertEquals("".count(""),1)
        self.assertEquals("Python".count(""),7)
        self.assertEquals("ab aaba".count("ab"),2)
    
    
    def test_startswith(self):
        self.assertEquals('ab'.startswith('ab'),1)
        self.assertEquals('ab'.startswith('a'),1)
        self.assertEquals('ab'.startswith(''),1)
        self.assertEquals('x'.startswith('a'),0)
        self.assertEquals('x'.startswith('x'),1)
        self.assertEquals(''.startswith(''),1)
        self.assertEquals(''.startswith('a'),0)
        self.assertEquals('x'.startswith('xx'),0)
        self.assertEquals('y'.startswith('xx'),0)
                

    def test_endswith(self):
        self.assertEquals('ab'.endswith('ab'),1)
        self.assertEquals('ab'.endswith('b'),1)
        self.assertEquals('ab'.endswith(''),1)
        self.assertEquals('x'.endswith('a'),0)
        self.assertEquals('x'.endswith('x'),1)
        self.assertEquals(''.endswith(''),1)
        self.assertEquals(''.endswith('a'),0)
        self.assertEquals('x'.endswith('xx'),0)
        self.assertEquals('y'.endswith('xx'),0)
   
   
    def test_expandtabs(self):
        s = '\txy\t'
        self.assertEquals(s.expandtabs(),'        xy        ')
        self.assertEquals(s.expandtabs(1),' xy ')
        self.assertEquals('xy'.expandtabs(),'xy')
        self.assertEquals(''.expandtabs(),'')


    def test_split_maxsplit(self):
        self.assertEquals("/a/b/c".split('/', 2), ['','a','b/c'])
        self.assertEquals("a/b/c".split("/"), ['a', 'b', 'c'])
        self.assertEquals(" a ".split(None, 0), ['a '])
        self.assertEquals(" a ".split(None, 1), ['a'])
        self.assertEquals(" a a ".split(" ", 0), [' a a '])
        self.assertEquals(" a a ".split(" ", 1), ['', 'a a '])

    def test_join(self):
        self.assertEquals(", ".join(['a', 'b', 'c']), "a, b, c")
        self.assertEquals("".join([]), "")
        self.assertEquals("-".join(['a', 'b']), 'a-b')

    def test_lower(self):
        self.assertEquals("aaa AAA".lower(), "aaa aaa")
        self.assertEquals("".lower(), "")

    def test_upper(self):
        self.assertEquals("aaa AAA".upper(), "AAA AAA")
        self.assertEquals("".upper(), "")

if __name__ == '__main__':
    test.main()
