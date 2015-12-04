import dis

nil = object()

class VirtualMachine(object):
    
    HAVE_ARGUMENT = 90

    def __init__(self):
        self.stack = []

    def run_code(self, code):
        what_to_exec = self._get_exec(code)
        instructions = what_to_exec['instructions']

        for instr, arg in instructions:
            vm_instr = getattr(self, instr)
            vm_arg = self._parse_argument(instr, arg, what_to_exec)
            if vm_arg is nil:
                vm_instr()
            else:
                vm_instr(vm_arg)

    def _get_exec(self, code):
        what_to_exec = {
                "instructions":[],
                "constants": code.co_consts,
                "names": code.co_names,
                }

        byte_codes = [ord(c) for c in code.co_code]
        
        i = 0
        while i < len(byte_codes):
            byte_code = byte_codes[i]
            name = dis.opname[byte_code]
            if byte_code >= self.HAVE_ARGUMENT:
                arg = (byte_codes[i+2] >> 8) + byte_codes[i+1]
                i += 2
            else:
                arg = None
            what_to_exec["instructions"].append((dis.opname[byte_code], arg))
            i += 1

        return what_to_exec

    
    def _parse_argument(self, instr, arg, what_to_exec):
        if arg is None:
            return nil
        byte_code = dis.opmap[instr]
        if byte_code in dis.hasconst:
            return what_to_exec['constants'][arg]
        elif byte_code in dis.hasname:
            return what_to_exec['names'][arg]

    def LOAD_CONST(self, const):
        self.stack.append(const)

    def PRINT_EXPR(self):
        print self.stack.pop()

    def RETURN_VALUE(self):
        return self.stack.pop()

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
            f  = FILE()
            change_stdout_to(f)
            r = self.vm.run_code(o)
            change_stdout_to()
            self.assertEqual(r, None)
            self.assertEqual(f, '20\n')


    unittest.main()
