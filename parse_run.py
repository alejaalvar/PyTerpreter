from lark import Lark, Token, ParseTree, Transformer
from lark.exceptions import VisitError
from pathlib import Path

from interp import (
    Add, Sub, Mul, Div, Neg, Lit, Let, Name,
    Or, And, Not, Eq, Lt, If,
    Cmd, Pipe, RedirectIn, RedirectOut, RedirectErr,
    Letfun, App,
    Expr, run,
)

parser = Lark(
    Path('expr.lark').read_text(),
    start='expr',
    parser='earley',
    ambiguity='explicit',
)


class ParseError(Exception):
    pass


class AmbiguousParse(Exception):
    pass


class ToExpr(Transformer[Token, Expr]):
    """Transform a Lark parse tree into an AST."""

    # ── ambiguity marker ──────────────────────────────────────────────────
    def _ambig(self, _) -> Expr:
        raise AmbiguousParse()

    # ── atoms ─────────────────────────────────────────────────────────────
    def id(self, args: tuple) -> Expr:
        name = str(args[0])
        if name == 'true':
            return Lit(True)
        if name == 'false':
            return Lit(False)
        return Name(name)

    def int(self, args: tuple) -> Expr:
        return Lit(int(args[0]))

    def cmd(self, args: tuple) -> Expr:
        # Strip surrounding backticks and split into name + args
        content = str(args[0])[1:-1].strip()
        parts = content.split()
        return Cmd(parts[0], parts[1:])

    # ── arithmetic ────────────────────────────────────────────────────────
    def neg(self, args: tuple) -> Expr:
        return Neg(args[0])

    def mul(self, args: tuple) -> Expr:
        return Mul(args[0], args[1])

    def div(self, args: tuple) -> Expr:
        return Div(args[0], args[1])

    def add(self, args: tuple) -> Expr:
        return Add(args[0], args[1])

    def sub(self, args: tuple) -> Expr:
        return Sub(args[0], args[1])

    # ── comparisons ───────────────────────────────────────────────────────
    def eq(self, args: tuple) -> Expr:
        return Eq(args[0], args[1])

    def lt(self, args: tuple) -> Expr:
        return Lt(args[0], args[1])

    # ── boolean ───────────────────────────────────────────────────────────
    # 'not', 'and', 'or' are Python keywords so they can't appear in a def
    # statement; we wire them up via setattr below the class definition.

    # ── control flow ──────────────────────────────────────────────────────
    def ite(self, args: tuple) -> Expr:
        return If(args[0], args[1], args[2])

    # ── binding / functions ───────────────────────────────────────────────
    def let(self, args: tuple) -> Expr:
        return Let(str(args[0]), args[1], args[2])

    def letfun(self, args: tuple) -> Expr:
        return Letfun(str(args[0]), str(args[1]), args[2], args[3])

    def app(self, args: tuple) -> Expr:
        return App(args[0], args[1])

    # ── shell DSL ─────────────────────────────────────────────────────────
    def pipe(self, args: tuple) -> Expr:
        return Pipe(args[0], args[1])

    def redirect_in(self, args: tuple) -> Expr:
        return RedirectIn(args[0], str(args[1])[1:-1])   # strip quotes

    def redirect_out(self, args: tuple) -> Expr:
        return RedirectOut(args[0], str(args[1])[1:-1])

    def redirect_err(self, args: tuple) -> Expr:
        return RedirectErr(args[0], str(args[1])[1:-1])


# 'not', 'and', 'or' are Python keywords and cannot be used in def statements.
# setattr takes plain strings, so Lark's getattr(self, rule_name) will find them.
setattr(ToExpr, 'not', lambda _, args: Not(args[0]))
setattr(ToExpr, 'and', lambda _, args: And(args[0], args[1]))
setattr(ToExpr, 'or',  lambda _, args: Or(args[0], args[1]))


def parse(s: str) -> ParseTree:
    try:
        return parser.parse(s)
    except Exception as e:
        raise ParseError(e)


def genAST(t: ParseTree) -> Expr:
    try:
        return ToExpr().transform(t)
    except VisitError as e:
        if isinstance(e.orig_exc, AmbiguousParse):
            raise AmbiguousParse()
        raise e


def parse_and_run(s: str) -> None:
    try:
        t = parse(s)
        ast = genAST(t)
        run(ast)
    except AmbiguousParse:
        print("parse error: ambiguous parse")
    except ParseError as e:
        print(f"parse error: {e}")


# ── Core language tests ───────────────────────────────────────────────────────
parse_and_run('1 + 2 * 3')                                     # 7
parse_and_run('let x = 10 in x - 4 end')                       # 6
parse_and_run('if true then 42 else 0')                        # 42
parse_and_run('if 3 < 5 then true else false')                 # True
parse_and_run('!false || true && false')                       # True
parse_and_run('letfun double(x) = x + x in double(7) end')    # 14
parse_and_run('letfun fact(n) = if n == 0 then 1 else n * fact(n - 1) in fact(5) end')  # 120

# ── Shell DSL tests ───────────────────────────────────────────────────────────
parse_and_run('`echo hello professor`')                        # executes echo
parse_and_run('`ls` | `wc -l`')                                # file count
parse_and_run('`ls` | `grep py` | `wc -l`')                    # .py file count
parse_and_run('`echo spam and eggs` > "spam_eggs.txt"')        # write file
parse_and_run('`cat` < "spam_eggs.txt"')                       # read and print file
parse_and_run('`ls nonexistent_dir` !> "err.txt"')             # stderr to file
parse_and_run('if 1 < 2 then `echo one is less` else `echo one is not less`')
parse_and_run('let p = `echo bound name` in p end')
