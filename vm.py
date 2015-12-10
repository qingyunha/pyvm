import dis

nil = object()

class VirtualMachine(object):
    
    HAVE_ARGUMENT = 90

    def __init__(self):
        self._reset()

    def _reset(self):
        self.stack = []
        self.env = {}
        self.last_instr = 0
        self.jump = False
        self.running = True
        self.result = None

    def run_code(self, code):
        what_to_exec = self._get_exec(code)
        instructions = what_to_exec['instructions']

        '''
        for instr, arg in instructions:
            print >> sys.stderr, instr
            vm_instr = getattr(self, instr)
            vm_arg = self._parse_argument(instr, arg, what_to_exec)
            if vm_arg is nil:
                vm_instr()
            else:
                vm_instr(vm_arg)
        '''
        while self.last_instr < len(instructions) and self.running:
            instr, arg = instructions[self.last_instr]
            print >> sys.stderr, instr
            vm_instr = getattr(self, instr)
            vm_arg = self._parse_argument(instr, arg, what_to_exec)
            if vm_arg is nil:
                r = vm_instr()
            else:
                r = vm_instr(vm_arg)

            if self.jump:
                self.jump = False
            else:
                self.last_instr += 1

        self._reset()
        return r


    def _get_exec(self, code):
        self.byte_to_instr = {}
        what_to_exec = {
                "instructions":[],
                "constants": code.co_consts,
                "names": code.co_names,
                }

        byte_codes = [ord(c) for c in code.co_code]
        
        i = j = 0
        while i < len(byte_codes):
            self.byte_to_instr[i] = j
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

    def LOAD_CONST(self, const):
        self.stack.append(const)

    def LOAD_NAME(self, name):
        val = self.env[name]
        self.stack.append(val)

    def STORE_NAME(self, name):
        val = self.stack.pop()
        self.env[name] = val

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
        self.running = False
        return self.stack.pop()

    def COMPARE_OP(self, arg):
        v1 = self.stack.pop()
        v2 = self.stack.pop()
        s = repr(v1) + dis.cmp_op[arg] + repr(v2)
        self.stack.append(eval(s))

    def POP_JUMP_IF_FALSE(self, target):
        v = self.stack.pop()
        if v:
            self.last_instr = self.byte_to_instr[target] 
            self.jump = True
        
    def JUMP_FORWARD(self, step):
        self.last_instr = self.last_to_instr + step - 1
        self.jump = True


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

        def test_get_exec_and_parse_argnment(self):
            o = compile('x = 5', '', 'exec')
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
            change_stdout_to(tmpfile)
            r = self.vm.run_code(o)
            change_stdout_to()
            self.assertEqual(r, None)
            self.assertEqual(tmpfile, '20\n')

            tmpfile.clear()

        def test_variable_and_BINARY_ADD(self):
            s = 'x=4\ny=5\nprint x+y\n'
            o = compile(s, '', 'exec')

            change_stdout_to(tmpfile)
            r = self.vm.run_code(o)
            change_stdout_to()
            self.assertEqual(r, None)
            self.assertEqual(tmpfile, '9\n')

            tmpfile.clear()

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
            r = self.vm.run_code(g.func_code)
            self.assertEqual(r, 6)


    unittest.main()
