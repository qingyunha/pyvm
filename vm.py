import dis
import sys
import logging

#LOGGING_LEVEL=logging.DEBUG
LOGGING_LEVEL=logging.ERROR
logging.basicConfig(stream=sys.stderr, level=LOGGING_LEVEL)

class Frame(object):
    def __init__(self, code_obj, prev_frame, env=None):
        self.code_obj = code_obj
        self.prev_frame = prev_frame
        if env:
            self.env = env 
        elif prev_frame:
            self.env = prev_frame.env
        else:
            self.env = {} 
        self.stack = []
        self.last_instr = 0
        self.running = True

class Function(object):
    def __init__(self, code):
        self.func_code = code

#nil = object()
class nil(object):
    pass

class VirtualMachine(object):
    
    HAVE_ARGUMENT = 90

    def __init__(self):
        self._reset()

    def _reset(self):
        self.stack = []
        self.env = {}
        self.jump = False
        self.result = None
        self.frames = []
        self.frame = None

    def run_code(self, code):
        frame = self.make_frame(code)
        self.push_frame(frame)
        return self.run_frame(self.frame)



    def run_frame(self, frame):
        what_to_exec = self._get_exec(frame.code_obj)
        instructions = what_to_exec['instructions']

        while frame.last_instr < len(instructions) and frame.running:
            instr, arg = instructions[frame.last_instr]
            vm_instr = getattr(self, instr)
            vm_arg = self._parse_argument(instr, arg, what_to_exec)
            logging.debug(instr + '  ' + str(vm_arg))
            if vm_arg is nil:
                r = vm_instr()
            else:
                r = vm_instr(vm_arg)

            if self.jump:
                self.jump = False
            else:
                frame.last_instr += 1

        return r


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
                arg = (byte_codes[i+2] >> 8) + byte_codes[i+1]
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

    def make_frame(self, code):
        return  Frame(code, self.frame)

    def push_frame(self, frame):
        logging.debug('push frame')
        self.frames.append(self.frame)
        self.frame = frame

    def pop_frame(self):
        logging.debug('pop frame')
        self.frame = self.frames.pop()

    ### byte instructions
    def LOAD_CONST(self, const):
        self.stack.append(const)

    def LOAD_NAME(self, name):
        val = self.env[name]
        self.stack.append(val)

    def STORE_NAME(self, name):
        val = self.stack.pop()
        self.env[name] = val
    
    def LOAD_FAST(self, name):
        name = self.frame.code_obj.co_varnames[name]
        val = self.env[name]
        self.stack.append(val)

    def STORE_FAST(self, name):
        name = self.frame.code_obj.co_varnames[name]
        val = self.stack.pop()
        self.env[name] = val

    def LOAD_GLOBAL(self, name):
        val = self.env[name]
        self.stack.append(val)

    def BINARY_ADD(self):
        v1 = self.stack.pop()
        v2 = self.stack.pop()
        self.stack.append(v1 + v2)

    def PRINT_EXPR(self):
        print self.stack.pop()

    def PRINT_ITEM(self):
        print self.stack.pop(),

    def PRINT_NEWLINE(self):
        print

    def RETURN_VALUE(self):
        self.frame.running = False
        return self.stack.pop()

    def COMPARE_OP(self, arg):
        v1 = self.stack.pop()
        v2 = self.stack.pop()
        s = repr(v1) + dis.cmp_op[arg] + repr(v2)
        self.stack.append(eval(s))

    def POP_JUMP_IF_FALSE(self, target):
        v = self.stack.pop()
        if v:
            self.frame.last_instr = self.frame.byte_to_instr[target] 
            self.jump = True
        
    def JUMP_FORWARD(self, step):
        self.frame.last_instr = self.last_to_instr + step - 1
        self.jump = True

    def JUMP_ABSOLUTE(self, target):
        self.frame.last_instr = self.frame.byte_to_instr[target]
        self.jump = True

    def GET_ITER(self):
        v = self.stack.pop()
        self.stack.append(iter(v))

    def FOR_ITER(self, step):
        v = self.stack[-1]
        try:
            self.stack.append(v.next())
        except StopIteration:
            self.stack.pop()
            target = self.frame.instr_to_byte[self.frame.last_instr] + step
            self.frame.last_instr = self.frame.byte_to_instr[target]

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
        o = self.stack.pop()
        self.stack.append(Function(o))


    def CALL_FUNCTION(self, arg):
        logging.debug('call_funciton')

        f = self.stack.pop()
        frame = self.make_frame(f.func_code)
        self.push_frame(frame)
        r = self.run_frame(frame)
        self.stack.append(r)
        self.pop_frame()

    def POP_TOP(self):
        self.stack.pop()


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
            self.vm.run_code(o)
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

        def test_for_loop(self):
            s = 'x=0\nfor i in [1,2,3]:\n\tx = x + i\n\tprint x'
            o = compile(s, '', 'exec')

            r = self.vm.run_code(o)
            self.assertEqual(tmpfile.s, '1\n3\n6\n')

        def test_function_call(self):
            s = '''
def f():
    return 4 + 8
r = f()
'''
            o = compile(s, '', 'exec')
            r = self.vm.run_code(o)
            self.assertTrue(isinstance(self.vm.env['f'], Function))
            self.assertEqual(self.vm.env['r'], 12)

        def test_function_call2(self):
            s = '''\
x = 1
def f():
    x = x + 1
for i in [1,2,3]:
    f()
'''
            o = compile(s, '', 'exec')
            r = self.vm.run_code(o)
            self.assertEqual(self.vm.env['x'], 4)

                
     
    unittest.main()
