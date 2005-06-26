from pypy.translator.translator import Translator
from pypy.rpython.lltype import *
from pypy.rpython.rstr import parse_fmt_string
from pypy.rpython.rtyper import RPythonTyper
from pypy.rpython.test.test_llinterp import interpret


def test_simple():
    def fn(i):
        s = 'hello'
        return s[i]
    for i in range(5):
        res = interpret(fn, [i])
        assert res == 'hello'[i]


def test_nonzero():
    def fn(i, j):
        s = ['', 'xx'][j]
        if i < 0:
            s = None
        if i > -2:
            return bool(s)
        else:
            return False
    for i in [-2, -1, 0]:
        for j in range(2):
            res = interpret(fn, [i, j])
            assert res is fn(i, j)

def test_hash():
    def fn(i):
        if i == 0:
            s = ''
        else:
            s = "xxx"
        return hash(s)
    res = interpret(fn, [0])
    assert res == -1
    res = interpret(fn, [1])
    assert typeOf(res) == Signed

def test_concat():
    def fn(i, j):
        s1 = ['', 'a', 'ab']
        s2 = ['', 'x', 'xy']
        return s1[i] + s2[j]
    for i in range(3):
        for j in range(3):
            res = interpret(fn, [i,j])
            assert ''.join(res.chars) == fn(i, j)

def test_iter():
    def fn(i):
        s = ['', 'a', 'hello'][i]
        i = 0
        for c in s:
            if c != s[i]:
                return False
            i += 1
        if i == len(s):
            return True
        return False

    for i in range(3):
        res = interpret(fn, [i])
        assert res is True
        
def test_char_constant():
    def fn(s):
        return s + '.'
    res = interpret(fn, ['x'])
    assert len(res.chars) == 2
    assert res.chars[0] == 'x'
    assert res.chars[1] == '.'

def test_char_isspace():
    def fn(s):
        return s.isspace() 
    res = interpret(fn, ['x']) 
    assert res == False 
    res = interpret(fn, [' '])
    assert res == True 

def test_char_compare():
    res = interpret(lambda c1, c2: c1 == c2,  ['a', 'b'])
    assert res is False
    res = interpret(lambda c1, c2: c1 == c2,  ['a', 'a'])
    assert res is True
    res = interpret(lambda c1, c2: c1 <= c2,  ['z', 'a'])
    assert res is False

def test_str_compare():
    def fn(i, j):
        s1 = ['one', 'two']
        s2 = ['one', 'two', 'o', 'on', 'twos', 'foobar']
        return s1[i] == s2[j]
    for i in range(2):
        for j in range(6):
            res = interpret(fn, [i,j])
            assert res is fn(i, j)

    def fn(i, j):
        s1 = ['one', 'two']
        s2 = ['one', 'two', 'o', 'on', 'twos', 'foobar']
        return s1[i] != s2[j]
    for i in range(2):
        for j in range(6):
            res = interpret(fn, [i, j])
            assert res is fn(i, j)

    def fn(i, j):
        s1 = ['one', 'two']
        s2 = ['one', 'two', 'o', 'on', 'twos', 'foobar']
        return s1[i] < s2[j]
    for i in range(2):
        for j in range(6):
            res = interpret(fn, [i,j])
            assert res is fn(i, j)

    def fn(i, j):
        s1 = ['one', 'two']
        s2 = ['one', 'two', 'o', 'on', 'twos', 'foobar']
        return s1[i] <= s2[j]
    for i in range(2):
        for j in range(6):
            res = interpret(fn, [i,j])
            assert res is fn(i, j)

    def fn(i, j):
        s1 = ['one', 'two']
        s2 = ['one', 'two', 'o', 'on', 'twos', 'foobar']
        return s1[i] >= s2[j]
    for i in range(2):
        for j in range(6):
            res = interpret(fn, [i,j])
            assert res is fn(i, j)

    def fn(i, j):
        s1 = ['one', 'two']
        s2 = ['one', 'two', 'o', 'on', 'twos', 'foobar']
        return s1[i] > s2[j]
    for i in range(2):
        for j in range(6):
            res = interpret(fn, [i,j])
            assert res is fn(i, j)

def test_startswith():
    def fn(i, j):
        s1 = ['one', 'two']
        s2 = ['one', 'two', 'o', 'on', 'ne', 'e', 'twos', 'foobar', 'fortytwo']
        return s1[i].startswith(s2[j])
    for i in range(2):
        for j in range(9):
            res = interpret(fn, [i,j])
            assert res is fn(i, j)

def test_endswith():
    def fn(i, j):
        s1 = ['one', 'two']
        s2 = ['one', 'two', 'o', 'on', 'ne', 'e', 'twos', 'foobar', 'fortytwo']
        return s1[i].endswith(s2[j])
    for i in range(2):
        for j in range(9):
            res = interpret(fn, [i,j])
            assert res is fn(i, j)

def test_join():
    res = interpret(lambda: ''.join([]), [])
    assert ''.join(res.chars) == ""
    
    def fn(i, j):
        s1 = [ '', ',', ' and ']
        s2 = [ [], ['foo'], ['bar', 'baz', 'bazz']]
        return s1[i].join(s2[j])
    for i in range(3):
        for j in range(3):
            res = interpret(fn, [i,j])
            assert ''.join(res.chars) == fn(i, j)

def test_parse_fmt():
    assert parse_fmt_string('a') == ['a']
    assert parse_fmt_string('%s') == [('s',)]
    assert parse_fmt_string("name '%s' is not defined") == ["name '", ("s",), "' is not defined"]

def test_strformat():
    def percentS(s):
        return "before %s after" % (s,)

    res = interpret(percentS, ['1'])
    assert ''.join(res.chars) == 'before 1 after'

    def percentD(i):
        return "bing %d bang" % (i,)
    
    res = interpret(percentD, [23])
    assert ''.join(res.chars) == 'bing 23 bang'

    def percentX(i):
        return "bing %x bang" % (i,)
    
    res = interpret(percentX, [23])
    assert ''.join(res.chars) == 'bing 17 bang'

    res = interpret(percentX, [-123])
    assert ''.join(res.chars) == 'bing -7b bang'

    def moreThanOne(s, d, x):
        return "string: %s decimal: %d hex: %x" % (s, d, x)

    args = 'a', 2, 3
    res = interpret(moreThanOne, list(args))
    assert ''.join(res.chars) == moreThanOne(*args)

def test_strformat_nontuple():
    def percentD(i):
        return "before %d after" % i

    res = interpret(percentD, [1])
    assert ''.join(res.chars) == 'before 1 after'

    def percentS(i):
        return "before %s after" % i

    res = interpret(percentS, ['D'])
    assert ''.join(res.chars) == 'before D after'

def test_str_slice():
    def fn():
        s = 'hello'
        s1 = s[:3]
        s2 = s[3:]
        return s1+s2 == s and s2+s1 == 'lohel'
    res = interpret(fn, ())
    assert res

def test_strformat_instance():
    class C:
        pass
    class D(C):
        pass
    def dummy(i):
        if i:
            x = C()
        else:
            x = D()
        return str(x)
        
    res = interpret(dummy, [1])
    assert ''.join(res.chars) == '<C object>'

    res = interpret(dummy, [0])
    assert ''.join(res.chars) == '<D object>'

def test_percentformat_instance():
    class C:
        pass
    class D(C):
        pass
    
    def dummy(i):
        if i:
            x = C()
            y = D()
        else:
            x = D()
            y = C()
        return "what a nice %s, much nicer than %r"%(x, y)
        
    res = interpret(dummy, [1])
    assert ''.join(res.chars) == 'what a nice <C object>, much nicer than <D object>'

    res = interpret(dummy, [0])
    assert ''.join(res.chars) == 'what a nice <D object>, much nicer than <C object>'

def test_split():
    def fn(i):
        s = ['', '0.1.2.4.8', '.1.2', '1.2.', '.1.2.4.'][i]
        l = s.split('.')
        sum = 0
        for num in l:
             if len(num):
                 sum += ord(num) - ord('0')
        return sum + len(l) * 100
    for i in range(5):
        res = interpret(fn, [i])
        assert res == fn(i)

def test_contains():
    def fn(i):
        s = 'Hello world'
        return chr(i) in s
    for i in range(256):
        res = interpret(fn, [i])
        assert res == fn(i)

