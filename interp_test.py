import unittest
import os
import tempfile
from unittest import TestCase

import contextlib
with contextlib.redirect_stdout(None), contextlib.redirect_stderr(None):
    import interp
    from interp import (
        Cmd, Pipe, RedirectOut, RedirectIn, RedirectErr,
        RedirectAppend, Tee,
        Proc, EvalError, eval, emptyEnv, evalInEnv,
    )


class TestRedirectAppend(TestCase):

    def test_redirect_append_returns_proc(self):
        # `echo hello` >> "out.txt"  =>  Proc with stdout_append set
        expr = RedirectAppend(Cmd("echo", ["hello"]), "out.txt")
        result = eval(expr)
        self.assertIsInstance(result, Proc)
        self.assertEqual(result.stdout_append, "out.txt")
        self.assertIsNone(result.stdout)

    def test_redirect_append_does_not_set_stdout(self):
        # stdout should remain None; stdout_append carries the filename
        expr = RedirectAppend(Cmd("echo", ["hi"]), "f.txt")
        result = eval(expr)
        self.assertIsNone(result.stdout)
        self.assertEqual(result.stdout_append, "f.txt")

    def test_redirect_append_error_on_non_proc(self):
        # 1 >> "out.txt"  =>  error (not a Proc)
        expr = RedirectAppend(interp.Lit(1), "out.txt")
        with self.assertRaises(EvalError):
            eval(expr)

    def test_redirect_append_error_if_stdout_already_set(self):
        # (`echo hi` > "a.txt") >> "b.txt"  =>  error (stdout conflict)
        expr = RedirectAppend(RedirectOut(Cmd("echo", ["hi"]), "a.txt"), "b.txt")
        with self.assertRaises(EvalError):
            eval(expr)

    def test_redirect_append_error_if_stdout_append_already_set(self):
        # (`echo hi` >> "a.txt") >> "b.txt"  =>  error (can't append to two files)
        expr = RedirectAppend(RedirectAppend(Cmd("echo", ["hi"]), "a.txt"), "b.txt")
        with self.assertRaises(EvalError):
            eval(expr)

    def test_redirect_append_error_if_tee_already_set(self):
        # (`echo hi` tee "a.txt") >> "b.txt"  =>  error (conflicting stdout destinations)
        expr = RedirectAppend(Tee(Cmd("echo", ["hi"]), "a.txt"), "b.txt")
        with self.assertRaises(EvalError):
            eval(expr)

    def test_pipe_blocked_if_left_has_stdout_append(self):
        # (`echo hi` >> "a.txt") | `cat`  =>  error (left side stdout already redirected)
        expr = Pipe(RedirectAppend(Cmd("echo", ["hi"]), "a.txt"), Cmd("cat", []))
        with self.assertRaises(EvalError):
            eval(expr)


class TestTee(TestCase):

    def test_tee_returns_proc(self):
        # `echo hello` tee "out.txt"  =>  Proc with tee set
        expr = Tee(Cmd("echo", ["hello"]), "out.txt")
        result = eval(expr)
        self.assertIsInstance(result, Proc)
        self.assertEqual(result.tee, "out.txt")
        self.assertIsNone(result.stdout)

    def test_tee_does_not_set_stdout(self):
        # stdout should remain None; tee carries the filename
        expr = Tee(Cmd("echo", ["hi"]), "f.txt")
        result = eval(expr)
        self.assertIsNone(result.stdout)
        self.assertEqual(result.tee, "f.txt")

    def test_tee_error_on_non_proc(self):
        # true tee "out.txt"  =>  error (not a Proc)
        expr = Tee(interp.Lit(True), "out.txt")
        with self.assertRaises(EvalError):
            eval(expr)

    def test_tee_error_if_stdout_already_set(self):
        # (`echo hi` > "a.txt") tee "b.txt"  =>  error
        expr = Tee(RedirectOut(Cmd("echo", ["hi"]), "a.txt"), "b.txt")
        with self.assertRaises(EvalError):
            eval(expr)

    def test_tee_error_if_stdout_append_already_set(self):
        # (`echo hi` >> "a.txt") tee "b.txt"  =>  error
        expr = Tee(RedirectAppend(Cmd("echo", ["hi"]), "a.txt"), "b.txt")
        with self.assertRaises(EvalError):
            eval(expr)

    def test_tee_error_if_tee_already_set(self):
        # (`echo hi` tee "a.txt") tee "b.txt"  =>  error (can't tee to two files)
        expr = Tee(Tee(Cmd("echo", ["hi"]), "a.txt"), "b.txt")
        with self.assertRaises(EvalError):
            eval(expr)

    def test_pipe_blocked_if_left_has_tee(self):
        # (`echo hi` tee "a.txt") | `cat`  =>  error (left side stdout occupied by tee)
        expr = Pipe(Tee(Cmd("echo", ["hi"]), "a.txt"), Cmd("cat", []))
        with self.assertRaises(EvalError):
            eval(expr)


if __name__ == "__main__":
    unittest.main()
