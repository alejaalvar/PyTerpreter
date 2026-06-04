"""
parse_run.py — Parser and transformer for the Shell DSL expression language.

Loads the Lark grammar from expr.lark and uses it to parse concrete syntax
strings into Lark parse trees. The ToExpr transformer then walks each parse
tree bottom-up, calling a dedicated method per grammar rule to convert each
node into the corresponding AST dataclass defined in interp.py.

The top-level entry point is parse_and_run(), which runs the full pipeline:
    string → parse tree → AST → evaluated result

A driver() REPL is also provided for interactive use.
"""

from lark import Lark, Token, ParseTree, Transformer
from lark.exceptions import VisitError
from pathlib import Path

from interp import (
    Add,
    Sub,
    Mul,
    Div,
    Neg,
    Lit,
    Let,
    Name,
    Or,
    And,
    Not,
    Eq,
    Lt,
    If,
    Cmd,
    Pipe,
    RedirectIn,
    RedirectOut,
    RedirectErr,
    Letfun,
    App,
    Expr,
    run,
    Assign,
    Seq,
)

parser = Lark(
    Path("expr.lark").read_text(),
    start="expr",
    parser="earley",
    ambiguity="explicit",
)


class ParseError(Exception):
    pass


class AmbiguousParse(Exception):
    pass


class ToExpr(Transformer[Token, Expr]):
    """Transform a Lark parse tree into an AST."""

    def seq(self, args: tuple[Expr, Expr]) -> Expr:
        return Seq(args[0], args[1])

    def assign(self, args: tuple) -> Expr:
        """
        Handles an assignment
        """
        return Assign(str(args[0]), args[1])

    # ── ambiguity marker ──────────────────────────────────────────────────
    def _ambig(self, _):
        """
        Called by Lark when the Earley parser finds multiple valid parse trees
        for the same input (an ambiguous grammar). Raises AmbiguousParse to
        signal this upstream. The parameter is required by Lark's Transformer
        interface but unused since we raise unconditionally
        """
        raise AmbiguousParse()

    # ── atoms ─────────────────────────────────────────────────────────────
    def id(self, args: tuple) -> Expr:
        """Handles an identifier token. Converts the boolean literals
        'true' and 'false' to Lit nodes since the lexer cannot distinguish
        them from ordinary identifiers. All other identifiers become Name
        nodes (variable references).

        Args:
            args (tuple): single-element tuple containing the ID token

        Returns:
            Expr: Lit(True), Lit(False), or Name(identifier)
        """
        name = str(args[0])
        if name == "true":
            return Lit(True)
        if name == "false":
            return Lit(False)
        return Name(name)

    def int(self, args: tuple) -> Expr:
        """Handles an integer token. Converts the token
        into a Python int and wraps it in a Lit node.

        Args:
            args (tuple): single-element tuple containing the INT token

        Returns:
            Expr: Lit(int)
        """
        return Lit(int(args[0]))

    def cmd(self, args: tuple) -> Expr:
        """Handles a BACKTICK_CMD token. Strips the surrounding backticks,
        splits the content on whitespace, and constructs a Cmd node where
        the first word is the command name and the remaining words are its
        arguments. For example, `ls -la` becomes Cmd('ls', ['-la']).

        Args:
            args (tuple): single-element tuple containing the BACKTICK_CMD token

        Returns:
            Expr: Cmd(name, args)
        """
        # Strip surrounding backticks and split into name + args
        content = str(args[0])[1:-1].strip()
        parts = content.split()
        return Cmd(parts[0], parts[1:])

    # ── arithmetic ────────────────────────────────────────────────────────
    def neg(self, args: tuple) -> Expr:
        """Handles a unary negation. Wraps the already-transformed
        sub-expression in a Neg node.

        Args:
            args (tuple): single-element tuple containing the operand Expr

        Returns:
            Expr: Neg(Expr)
        """
        return Neg(args[0])

    def mul(self, args: tuple) -> Expr:
        """Handles a multiplication. Wraps two already-transformed
        sub-expressions in a Mul node.

        Args:
            args (tuple): two-element tuple of (left Expr, right Expr)

        Returns:
            Expr: Mul(Expr, Expr)
        """
        return Mul(args[0], args[1])

    def div(self, args: tuple) -> Expr:
        """Handles a division. Wraps two already-transformed
        sub-expressions in a Div node.

        Args:
            args (tuple): two-element tuple of (left Expr, right Expr)

        Returns:
            Expr: Div(Expr, Expr)
        """
        return Div(args[0], args[1])

    def add(self, args: tuple) -> Expr:
        """Handles an addition. Wraps two already-transformed
        sub-expressions in an Add node.

        Args:
            args (tuple): two-element tuple of (left Expr, right Expr)

        Returns:
            Expr: Add(Expr, Expr)
        """
        return Add(args[0], args[1])

    def sub(self, args: tuple) -> Expr:
        """Handles a subtraction. Wraps two already-transformed
        sub-expressions in a Sub node.

        Args:
            args (tuple): two-element tuple of (left Expr, right Expr)

        Returns:
            Expr: Sub(Expr, Expr)
        """
        return Sub(args[0], args[1])

    # ── comparisons ───────────────────────────────────────────────────────
    def eq(self, args: tuple) -> Expr:
        """Handles an equality comparison. Operands can be of any type
        (int, bool, or Proc); cross-type comparisons always evaluate to false.

        Args:
            args (tuple): two-element tuple of (left Expr, right Expr)

        Returns:
            Expr: Eq(Expr, Expr)
        """
        return Eq(args[0], args[1])

    def lt(self, args: tuple) -> Expr:
        """Handles a less-than comparison. Operands must evaluate to
        integers at runtime.

        Args:
            args (tuple): two-element tuple of (left Expr, right Expr)

        Returns:
            Expr: Lt(Expr, Expr)
        """
        return Lt(args[0], args[1])

    # ── boolean ───────────────────────────────────────────────────────────
    # 'not', 'and', 'or' are Python keywords so they can't appear in a def
    # statement; we wire them up via setattr below the class definition.

    # ── control flow ──────────────────────────────────────────────────────
    def ite(self, args: tuple) -> Expr:
        """Handles an if-then-else expression. Constructs an If node from
        three already-transformed sub-expressions: the condition, the then
        branch, and the else branch.

        Args:
            args (tuple): three-element tuple of (condition Expr, then Expr, else Expr)

        Returns:
            Expr: If(condition, then, else)
        """
        return If(args[0], args[1], args[2])

    # ── binding / functions ───────────────────────────────────────────────
    def let(self, args: tuple) -> Expr:
        """Handles a let-binding. Binds a name to a definition expression,
        making it available inside the body expression.

        Args:
            args (tuple): three-element tuple of (name Token, definition Expr, body Expr)

        Returns:
            Expr: Let(name, definition, body)
        """
        return Let(str(args[0]), args[1], args[2])

    def letfun(self, args: tuple) -> Expr:
        """Handles a function definition. Binds a function name to a
        single-parameter closure, making it available (including recursively)
        inside the in-expression.

        Args:
            args (tuple): four-element tuple of (function name Token,
                          parameter name Token, body Expr, in-expression Expr)

        Returns:
            Expr: Letfun(name, param, body, inexpr)
        """
        return Letfun(str(args[0]), str(args[1]), args[2], args[3])

    def app(self, args: tuple) -> Expr:
        """Handles a function application. Applies a function expression
        to an argument expression.

        Args:
            args (tuple): two-element tuple of (function Expr, argument Expr)

        Returns:
            Expr: App(function, argument)
        """
        return App(args[0], args[1])

    # ── shell DSL ─────────────────────────────────────────────────────────
    def pipe(self, args: tuple) -> Expr:
        """Handles the shell pipe operator. Connects the stdout of the
        left process to the stdin of the right process.

        Args:
            args (tuple): two-element tuple of (left Expr, right Expr)

        Returns:
            Expr: Pipe(left, right)
        """
        return Pipe(args[0], args[1])

    def redirect_in(self, args: tuple) -> Expr:
        """Handles stdin redirection. Redirects a file's contents to the
        process's stdin. Strips surrounding quotes from the filename token.

        Args:
            args (tuple): two-element tuple of (process Expr, filename ESCAPED_STRING token)

        Returns:
            Expr: RedirectIn(process, filename)
        """
        return RedirectIn(args[0], str(args[1])[1:-1])  # strip quotes

    def redirect_out(self, args: tuple) -> Expr:
        """Handles stdout redirection. Redirects the process's stdout to a file.
        Strips surrounding quotes from the filename token.

        Args:
            args (tuple): two-element tuple of (process Expr, filename ESCAPED_STRING token)

        Returns:
            Expr: RedirectOut(process, filename)
        """
        return RedirectOut(args[0], str(args[1])[1:-1])

    def redirect_err(self, args: tuple) -> Expr:
        """Handles stderr redirection. Redirects the process's stderr to a file.
        Strips surrounding quotes from the filename token.

        Args:
            args (tuple): two-element tuple of (process Expr, filename ESCAPED_STRING token)

        Returns:
            Expr: RedirectErr(process, filename)
        """
        return RedirectErr(args[0], str(args[1])[1:-1])


"""
'not', 'and', 'or' are Python keywords and cannot be used in def statements.
setattr takes plain strings, so Lark's getattr(self, rule_name) will find them.
this dynamically sets the attributes 'not,and,or' to corresponding
lambda functions to get around the keyword issue
"""
setattr(ToExpr, "not", lambda _, args: Not(args[0]))  # returns a simple Not node
setattr(
    ToExpr, "and", lambda _, args: And(args[0], args[1])
)  # returns a simple And node
setattr(ToExpr, "or", lambda _, args: Or(args[0], args[1]))  # returns a simple Or node


def parse(s: str) -> ParseTree:
    """Generate a parse tree given a program represented as a string

    Args:
        s (str): the program to parse

    Raises:
        ParseError: raised when the program is malformed

    Returns:
        ParseTree: the resulting parse tree
    """
    try:
        return parser.parse(s)
    except Exception as e:
        raise ParseError(e)


def genAST(t: ParseTree) -> Expr:
    """Generate an abstract syntax tree given a parse tree

    Args:
        t (ParseTree): the parse tree to read

    Raises:
        AmbiguousParse: raised when the parse tree admits more than one valid AST

    Returns:
        Expr: the resulting AST
    """
    try:
        return ToExpr().transform(t)
    except VisitError as e:
        if isinstance(e.orig_exc, AmbiguousParse):
            raise AmbiguousParse()
        raise e


def parse_and_run(s: str) -> None:
    """Pass a string to the parser to create a parse tree, pass that
    parse tree to the transformer to generate an abstract syntax tree,
    and then give the AST to the interpreter. Parse and ambiguity errors
    are caught and printed rather than propagated.

    Args:
        s (str): the program represented as a string

    Returns:
        None
    """
    try:
        t = parse(s)
        ast = genAST(t)
        run(ast)
    except AmbiguousParse:
        print("parse error: ambiguous parse")
    except ParseError as e:
        print(f"parse error: {e}")


def driver():
    """Runs an interactive REPL loop, repeatedly prompting the user for
    an expression, parsing it, and running it. Exits cleanly on Ctrl+D
    (EOF).

    Returns:
        None
    """
    while True:
        try:
            s = input("> ")
            parse_and_run(s)
        except EOFError:
            break


# ── Core language tests ───────────────────────────────────────────────────────
parse_and_run("1 + 2 * 3")  # 7
parse_and_run("let x = 10 in x - 4 end")  # 6
parse_and_run("if true then 42 else 0")  # 42
parse_and_run("if 3 < 5 then true else false")  # True
parse_and_run("!false || true && false")  # True
parse_and_run("letfun double(x) = x + x in double(7) end")  # 14
parse_and_run(
    "letfun fact(n) = if n == 0 then 1 else n * fact(n - 1) in fact(5) end"
)  # 120

# ── Shell DSL tests ───────────────────────────────────────────────────────────
parse_and_run("`echo hello professor`")  # executes echo
parse_and_run("`ls` | `wc -l`")  # file count
parse_and_run("`ls` | `grep py` | `wc -l`")  # .py file count
parse_and_run('`echo spam and eggs` > "spam_eggs.txt"')  # write file
parse_and_run('`cat` < "spam_eggs.txt"')  # read and print file
parse_and_run('`ls nonexistent_dir` !> "err.txt"')  # stderr to file
parse_and_run("if 1 < 2 then `echo one is less` else `echo one is not less`")
parse_and_run("let p = `echo bound name` in p end")
