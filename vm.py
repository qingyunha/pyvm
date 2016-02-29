import dis, inspect, types
import sys, re
import logging

LOGGING_LEVEL=logging.DEBUG
LOGGING_LEVEL=logging.ERROR
logging.basicConfig(stream=sys.stderr, level=LOGGING_LEVEL)

class VirtualMachineError(Exception):
    pass

class Frame(object):
    def __init__(self, f_code, f_globals, f_locals, f_back):
        self.f_code = f_code
        self.f_globals = f_globals
        self.f_locals = f_locals
        self.f_back = f_back
        if hasattr(__builtins__, '__dict__'):
            self.f_builtins = __builtins__.__dict__ 
        else:
            self.f_builtins = __builtins__
        self.stack = []
        self.last_instr = 0
        self.running = True
        
        #refactor
        self.f_lasti = 0

    def update_env(self, env):
        self.f_locals.update(env)

class Function(object):
    def __init__(self, code, defaults, vm):
        self.func_code = code
        self.func_defaults = defaults
        self._vm = vm
        self._func = types.FunctionType(code, vm.frame.f_globals, 
                                              argdefs=tuple(defaults))


#nil = object()
class nil(object):
    pass


## now only a environment for all function 
class VirtualMachine(object):
    
    HAVE_ARGUMENT = 90

    def __init__(self):
        self._reset()

    def _reset(self):
        self.stack = []
        self.jump = False
        self.result = None
        self.frames = []
        self.frame = None


        #refactor
        self.return_value = None
        self.last_exception = None


    def run_code(self, code):
        frame = self.make_frame(code)
        val = self.run_frame(frame)
        # Check some invariants
        if self.frames:            # pragma: no cover
            raise VirtualMachineError("Frames left over!")
        if self.frame and self.frame.stack:             # pragma: no cover
            raise VirtualMachineError("Data left on stack! %r" % self.frame.stack)

        return val



    def run_frame(self, frame):
        self.push_frame(frame)
        while True:
            byteName, arguments, opoffset = self.parse_byte()
            why = self.dispatch(byteName, arguments)
            if why:
                break

        self.pop_frame()

        if why == 'exception':
            print>>sys.stderr, self.last_exception
            raise(self.last_exception)

        return self.return_value

    def parse_byte(self):
        f = self.frame
        opoffset = f.f_lasti
        byteCode = ord(f.f_code.co_code[opoffset])
        f.f_lasti += 1
        byteName = dis.opname[byteCode]
        arg = None
        arguments = []
        if byteCode >= dis.HAVE_ARGUMENT:
            arg = f.f_code.co_code[f.f_lasti:f.f_lasti+2]
            f.f_lasti += 2
            intArg = ord(arg[0]) + (ord(arg[1]) << 8)
            if byteCode in dis.hasconst:
                arg = f.f_code.co_consts[intArg]
            elif byteCode in dis.hasfree:
                if intArg < len(f.f_code.co_cellvars):
                    arg = f.f_code.co_cellvars[intArg]
                else:
                    var_idx = intArg - len(f.f_code.co_cellvars)
                    arg = f.f_code.co_freevars[var_idx]
            elif byteCode in dis.hasname:
                arg = f.f_code.co_names[intArg]
            elif byteCode in dis.hasjrel:
                arg = f.f_lasti + intArg
            elif byteCode in dis.hasjabs:
                arg = intArg
            elif byteCode in dis.haslocal:
                arg = f.f_code.co_varnames[intArg]
            else:
                arg = intArg
            arguments = [arg]

        return byteName, arguments, opoffset


    def dispatch(self, byteName, arguments):
        """ Dispatch by bytename to the corresponding methods.
        Exceptions are caught and set on the virtual machine."""
        sys.stderr.write(byteName + '\n')

        byteName = byteName.replace('+','')
        why = None
        #try:
        bytecode_fn = getattr(self,  byteName, None)
        if not bytecode_fn:            # pragma: no cover
            raise VirtualMachineError(
                "unknown bytecode type: %s" % byteName
            )
        why = bytecode_fn(*arguments)

        #except:
            # deal with exceptions encountered while executing the op.
            #self.last_exception = sys.exc_info()[:2] + (None,)
            #log.exception("Caught exception during execution")
            #why = 'exception'

        return why

    def _get_exec(self, code):
        self.frame.byte_to_instr = {}
        what_to_exec = {
                "instructions":[],
                "constants": code.co_consts,
                "names": code.co_names,
                }

        byte_codes = [ord(c) for c in code.co_code]
        
        i = j = 0
        while i < len(byte_codes):
            self.frame.byte_to_instr[i] = j
            byte_code = byte_codes[i]
            name = dis.opname[byte_code]
            if byte_code >= self.HAVE_ARGUMENT:
                arg = (byte_codes[i+2] << 8) + byte_codes[i+1]
                i += 2
            else:
                arg = None
            what_to_exec["instructions"].append((dis.opname[byte_code], arg))
            i += 1
            j += 1

        self.frame.instr_to_byte = dict(zip(self.frame.byte_to_instr.values(),
                                      self.frame.byte_to_instr.keys()))
        return what_to_exec

    
    def _parse_argument(self, instr, arg, what_to_exec):
        if arg is None:
            return nil
        byte_code = dis.opmap[instr]
        if byte_code in dis.hasconst:
            return what_to_exec['constants'][arg]
        elif byte_code in dis.hasname:
            return what_to_exec['names'][arg]
        else:
            return arg

    def make_frame(self, code, callargs={}, f_globals=None, f_locals=None):
        if f_globals is not None:
            f_globals = f_globals
            if f_locals is None:
                f_locals = f_globals
        elif self.frames:
            f_globals = self.frame.f_globals
            self.local_env = f_locals = {}
        else:
            self.env = f_globals = f_locals = {
                '__builtins__': __builtins__,
                '__name__': '__main__',
                '__doc__': None,
                '__package__': None,
            }
        f_locals.update(callargs)
        frame = Frame(code, f_globals, f_locals, self.frame)
        return frame

    def push_frame(self, frame):
        logging.debug('push frame')
        self.frames.append(self.frame)
        self.frame = frame

    def pop_frame(self):
        logging.debug('pop frame')
        self.frame = self.frames.pop()

    def pop(self, i=0):
        """Pop a value from the stack.

        Default to the top of the stack, but `i` can be a count from the top
        instead.

        """
        return self.stack.pop(-1-i)

    def push(self, *vals):
        """Push values onto the value stack."""
        self.stack.extend(vals)

    def popn(self, n):
        """Pop a number of values from the value stack.

        A list of `n` values is returned, the deepest value first.

        """
        if n:
            ret = self.stack[-n:]
            self.stack[-n:] = []
            return ret
        else:
            return []

    def peek(self, n):
        """Get a value `n` entries down in the stack, without changing the stack."""
        return self.stack[-n]
    
    ### byte instructions
    def LOAD_CONST(self, const):
        self.push(const)

    def LOAD_NAME(self, name):
        frame = self.frame
        if name in frame.f_locals:
            val = frame.f_locals[name]
        elif name in frame.f_globals:
            val = frame.f_globals[name]
        elif name in frame.f_builtins:
            val = frame.f_builtins[name]
        else:
            raise NameError("name '%s' is not defined" % name)
        self.push(val)
        

    def STORE_NAME(self, name):
        self.frame.f_locals[name] = self.pop()

    def LOAD_FAST(self, name):
        #name = self.frame.f_code.co_varnames[name]
        if name in self.frame.f_locals:
            val = self.frame.f_locals[name]
        else:
            raise UnboundLocalError(
                "local variable '%s' referenced before assignment" % name
            )
        self.push(val)
        

    def STORE_FAST(self, name):
        name = self.frame.f_code.co_varnames[name]
        self.frame.f_locals[name] = self.pop()

    def LOAD_GLOBAL(self, name):
        f = self.frame
        if name in f.f_globals:
            val = f.f_globals[name]
        elif name in f.f_builtins:
            val = f.f_builtins[name]
        else:
            raise NameError("global name '%s' is not defined" % name)
        self.push(val)

    def STORE_GLOBAL(self, name):
        self.frame.f_globals[name] = self.pop()

        

    def BINARY_ADD(self):
        v1 = self.stack.pop()
        v2 = self.stack.pop()
        self.stack.append(v2 + v1)

    def PRINT_EXPR(self):
        print self.stack.pop()

    def PRINT_ITEM(self):
        print self.stack.pop(),

    def PRINT_NEWLINE(self):
        print

    def RETURN_VALUE(self):
        self.frame.running = False
        self.return_value =  self.stack.pop()
        return 'return'

    def COMPARE_OP(self, arg):
        v1, v2 = self.popn(2)
        s = repr(v1) + dis.cmp_op[arg] + repr(v2)
        self.push(eval(s))

    def POP_JUMP_IF_TRUE(self, target):
        v = self.pop()
        if  v:
            self.frame.f_lasti = target 

    def POP_JUMP_IF_FALSE(self, target):
        v = self.pop()
        if not v:
            self.frame.f_lasti = target 

        
    def JUMP_FORWARD(self, step):
        self.frame.f_lasti = step 

    def JUMP_ABSOLUTE(self, target):
        self.frame.f_lasti = target 

    def GET_ITER(self):
        v = self.stack.pop()
        self.stack.append(iter(v))

    def FOR_ITER(self, step):
        v = self.stack[-1]
        try:
            self.stack.append(v.next())
        except StopIteration:
            self.stack.pop()
            self.frame.f_lasti = step

    def SETUP_LOOP(self, arg):
        pass

    def POP_BLOCK(self):
        pass


    def BUILD_LIST(self, num):
        r = []
        for i in range(num):
            r.insert(0, self.stack.pop())
        self.stack.append(r)

    def MAKE_FUNCTION(self, arg):
        code_obj = self.pop()
        defaults = self.popn(arg)
        self.push(Function(code_obj, defaults, self))


    def CALL_FUNCTION(self, argc):
        logging.debug('call_funciton')
        namedargs = {}
        posargs = []
        if argc:
            kwlen, poslen = divmod(argc, 256)
            logging.debug("poslen {}, kwlen {}".format(poslen, kwlen))
            for i in range(kwlen):
                key, val = self.popn(2)
                namedargs[key] = val
            posargs = self.popn(poslen)
        func = self.pop()
        if isinstance(func, Function):
            callargs = inspect.getcallargs(func._func, *posargs, **namedargs)
        else:
            r = func(*posargs, **namedargs)
            self.push(r)
            return
        frame = self.make_frame(func.func_code,callargs)
        r = self.run_frame(frame)
        self.push(r)

    def POP_TOP(self):
        self.stack.pop()

    #refactor
    def UNPACK_SEQUENCE(self, count):
        seq = self.pop()
        for val in reversed(seq):
            self.push(val)

    #inplace operation
    def INPLACE_POWER(self):
        v1, v = self.popn(2)
        self.push(v1 ** v)

    def INPLACE_ADD(self):
        v1, v = self.popn(2)
        self.push(v1 + v)

    def INPLACE_MULTIPLY(self):
        v1, v = self.popn(2)
        self.push(v1 * v)

    
    def INPLACE_DIVIDE(self):
        v1, v = self.popn(2)
        self.push(v1 / v)

    def INPLACE_FLOOR_DIVIDE(self):
        v1, v = self.popn(2)
        self.push(v1 // v)

    def INPLACE_MODULO(self):
        v1, v = self.popn(2)
        self.push(v1 % v)

    def INPLACE_SUBTRACT(self):
        v1, v = self.popn(2)
        self.push(v1 - v)

    def INPLACE_LSHIFT(self):
        v1, v = self.popn(2)
        self.push(v1 << v)

    def INPLACE_RSHIFT(self):
        v1, v = self.popn(2)
        self.push(v1 >> v)

    def INPLACE_AND(self):
        v1, v = self.popn(2)
        self.push(v1 & v)

    def INPLACE_XOR(self):
        v1, v = self.popn(2)
        self.push(v1 ^ v)

    def INPLACE_OR(self):
        v1, v = self.popn(2)
        self.push(v1 | v)



    #slice operation
    def SLICE3(self):
        l, r = self.popn(2)
        v = self.pop()
        self.push(v[l:r])

    def SLICE2(self):
        end = self.pop()
        v = self.pop()
        self.push(v[:end])

    def SLICE1(self):
        start = self.pop()
        v = self.pop()
        self.push(v[start:])

    def SLICE0(self):
        v = self.pop()
        self.push(v[:])

    def STORE_SLICE3(self):
        start, end = self.popn(2)
        l = self.pop()
        v = self.pop()
        l[start:end] = v

    def STORE_SLICE2(self):
        end = self.pop()
        l = self.pop()
        v = self.pop()
        l[:end] = v

    def STORE_SLICE1(self):
        start = self.pop()
        l = self.pop()
        v = self.pop()
        l[start:] = v

    def STORE_SLICE0(self):
        l = self.pop()
        v = self.pop()
        l[:] = v

    def BUILD_SLICE(self, argc):
        step = None
        if argc == 2:
            start, stop = self.popn(2)
        else:
            start, stop, step = self.popn(3)
        self.push(slice(start, stop, step))

    def BINARY_SUBSCR(self):
        v, s = self.popn(2)
        self.push(v[s])

    def RAISE_VARARGS(self, argc):
        # NOTE: the dis docs are completely wrong about the order of the
        # operands on the stack!
        exctype = val = tb = None
        if argc == 0:
            exctype, val, tb = self.last_exception
        elif argc == 1:
            exctype = self.pop()
        elif argc == 2:
            val = self.pop()
            exctype = self.pop()
        elif argc == 3:
            tb = self.pop()
            val = self.pop()
            exctype = self.pop()

        # There are a number of forms of "raise", normalize them somewhat.
        if isinstance(exctype, BaseException):
            val = exctype
            exctype = type(val)

        self.last_exception = (exctype, val, tb)

        if tb:
            return 'reraise'
        else:
            return 'exception'

if __name__ == '__main__':
    import unittest
    import sys

    class FILE(object):
        def __init__(self, s=None):
            self.s = s or ''

        def write(self, s):
            self.s += s

        def __str__(self):
            return self.s

        def __eq__(self, other):
            return self.s == other

        def clear(self):
            self.s = ''

    tmpfile = FILE()

    def change_stdout_to(f=sys.stdout):
        """ redirect standard output to f
            recover standard output if call it without argument
        """
        sys.stdout = f

    class TestVM(unittest.TestCase):
        
        vm = VirtualMachine()

        def setUp(self):
            change_stdout_to(tmpfile)

        def tearDown(self):
            change_stdout_to()
            tmpfile.clear()
            self.vm._reset()
            

        def test_get_exec_and_parse_argnment(self):
            o = compile('x = 5', '', 'exec')
            self.vm.frame = self.vm.make_frame(o)
            what = self.vm._get_exec(o)
            self.assertEqual(what['names'], ('x',))
            self.assertEqual(what['constants'],(5, None))
            self.assertEqual(what['instructions'], 
                                 [('LOAD_CONST',0), ('STORE_NAME',0), 
                                  ('LOAD_CONST',1), ('RETURN_VALUE', None)])
            
            instr, arg = what['instructions'][0]
            arg = self.vm._parse_argument(instr, arg, what)
            self.assertEqual(arg, 5)

            instr, arg = what['instructions'][1]
            arg = self.vm._parse_argument(instr, arg, what)
            self.assertEqual(arg, 'x')

            instr, arg = what['instructions'][2]
            arg = self.vm._parse_argument(instr, arg, what)
            self.assertEqual(arg, None)

            instr, arg = what['instructions'][3]
            arg = self.vm._parse_argument(instr, arg, what)
            self.assertEqual(arg, nil)


        def test_run_code(self):
            o = compile('4+7+9', '', 'single')
            r = self.vm.run_code(o)
            self.assertEqual(r, None)
            self.assertEqual(tmpfile.s, '20\n')


        def test_variable_and_BINARY_ADD(self):
            s = 'x=4\ny=5\nprint x+y\n'
            o = compile(s, '', 'exec')

            r = self.vm.run_code(o)
            self.assertEqual(r, None)
            self.assertEqual(tmpfile, '9\n')

        def test_conditions(self):
            def f():
                if 5 > 6:
                    return 5
                else:
                    return 6
            def g():
                if 5 >= 6:
                    return 5
                elif 5 == 6:
                    return 6
                else:
                    return 6
            r = self.vm.run_code(f.func_code)
            self.assertEqual(r, 6)
            self.vm._reset()
            r = self.vm.run_code(g.func_code)
            self.assertEqual(r, 6)

        def test_BUILD_LIST(self):
            def f():
                return [1,2,3]

            r = self.vm.run_code(f.func_code)
            self.assertEqual(r, [1,2,3])


        def test_inplace_add(self):
            s = 'x,y=3,4\nx += y\nassert x == 7'
            o = compile(s, '', 'exec')

            self.vm.run_code(o)
            
            self.assertEqual(self.vm.env['y'], 4)
            self.assertEqual(self.vm.env['x'], 7)


        def test_for_loop(self):
            s = 'x=0\nfor i in [1,2,3]:\n\tx = x + i\n\tprint x'
            o = compile(s, '', 'exec')

            r = self.vm.run_code(o)
            self.assertEqual(tmpfile.s, '1\n3\n6\n')

        def test_function_call(self):
            s = \
'''
def f():
    return 4 + 8
r = f()
'''
            o = compile(s, '', 'exec')
            r = self.vm.run_code(o)
            self.assertTrue(isinstance(self.vm.env['f'], Function))
            self.assertEqual(self.vm.env['r'], 12)


        def test_function_call2(self):
            s = \
'''
x = 1
def f():
    global x
    x = x + 1
for i in [1,2,3]:
    f()
'''
            o = compile(s, '', 'exec')
            r = self.vm.run_code(o)
            self.assertEqual(self.vm.env['x'], 4)

        
        def test_function_call_with_arg(self):
            s = \
'''
def f(x, y):
    return x + y

r = f(1, 2)
'''
            o = compile(s, '', 'exec')
            r = self.vm.run_code(o)
            self.assertEqual(self.vm.env['r'], 3)


        def test_function_call_with_arg2(self):
            s = \
'''
def f(x, *args, **kwargs):
    pass

f(0, 1, 2, 3, test='yes')
'''
            o = compile(s, '', 'exec')
            r = self.vm.run_code(o)
            self.assertEqual(self.vm.local_env['x'], 0)
            self.assertEqual(self.vm.local_env['args'], (1,2,3))
            self.assertEqual(self.vm.local_env['kwargs'], {'test': 'yes'})
            

        def test_function_call_with_default_arg(self):
            s = \
'''
def f(x, y=1, z=2):
    pass
f(0)
f(0, z=9)
'''
            o = compile(s, '', 'exec')
            r = self.vm.run_code(o)
            self.assertEqual(self.vm.local_env['x'], 0)
            self.assertEqual(self.vm.local_env['y'], 1)
            self.assertEqual(self.vm.local_env['z'], 9)

        def test_builtin_function(self):
            o = compile('r = len([1,2,3])', '', 'single')
            r = self.vm.run_code(o)
            self.assertEqual(self.vm.env['r'], 3)


            
    unittest.main()
