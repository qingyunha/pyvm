# -*- coding: utf-8 -*-
from __future__ import print_function

import dis
import sys
import textwrap
import types
import unittest

import six

from vm import VirtualMachine, VirtualMachineError


CAPTURE_STDOUT = ('-s' not in sys.argv)
CAPTURE_EXCEPTION = 1


def dis_code(code):
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            dis_code(const)

    print("")
    print(code)
    dis.dis(code)


class VmTestCase(unittest.TestCase):

    def assert_ok(self, code, raises=None):

        code = textwrap.dedent(code)
        code = compile(code, "<%s>" % self.id(), "exec", 0, 1)


        # 使用myvm解释器运行
        real_stdout = sys.stdout

        vm_stdout = six.StringIO()
        if CAPTURE_STDOUT:             
            sys.stdout = vm_stdout
        vm = VirtualMachine()

        vm_value = vm_exc = None
        try:
            vm_value = vm.run_code(code)
        except VirtualMachineError:   
            raise
        except AssertionError:             
            raise
        except Exception as e:
            if not CAPTURE_EXCEPTION:       
                raise
            vm_exc = e
            sys.stderr.write("cat a exception in myvm")
        finally:
            real_stdout.write("-- stdout ----------\n")
            real_stdout.write(vm_stdout.getvalue())

        # 使用CPython解释器运行
        py_stdout = six.StringIO()
        sys.stdout = py_stdout

        py_value = py_exc = None
        globs = {}
        try:
            py_value = eval(code, globs, globs)
        except AssertionError:            
            raise
        except Exception as e:
            py_exc = e

        sys.stdout = real_stdout

        self.assert_same_exception(vm_exc, py_exc)
        self.assertEqual(vm_stdout.getvalue(), py_stdout.getvalue())
        self.assertEqual(vm_value, py_value)


        if raises:
            self.assertIsInstance(vm_exc, raises)
        else:
            self.assertIsNone(vm_exc)

    def assert_same_exception(self, e1, e2):
        self.assertEqual(str(e1), str(e2))
        self.assertIs(type(e1), type(e2))
