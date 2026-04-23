import subprocess
from dataclasses import dataclass, replace

type Expr = Add | Sub | Mul | Div | Neg | Lit | Let | Name | Or | And | Not | Eq | Lt | If | Cmd | Pipe | RedirectIn | RedirectOut | RedirectErr
type Value = int | bool | Proc


@dataclass
class RedirectIn:
    proc: Expr
    filename: str


@dataclass
class RedirectOut:
    proc: Expr
    filename: str


@dataclass
class RedirectErr:
    proc: Expr
    filename: str


@dataclass
class Pipe:
    left: Expr
    right: Expr

    def __str__(self) -> str:
        return f"({self.left} | {self.right})"


@dataclass
class Cmd:
    name: str
    args: list[str]

    def __str__(self) -> str:
        return f"`{self.name} {' '.join(self.args)}`"


@dataclass
class Proc:
    stages: list[tuple[str, list[str]]]  # one tuple per pipeline stage
    stdin: str | None = None
    stdout: str | None = None
    stderr: str | None = None

    def __str__(self) -> str:
        pipeline = " | ".join(f"{name} {' '.join(args)}" for name, args in self.stages)
        redirs = ""
        if self.stdin:
            redirs += f" < {self.stdin}"
        if self.stdout:
            redirs += f" > {self.stdout}"
        if self.stderr:
            redirs += f" 2> {self.stderr}"
        return f"`{pipeline}{redirs}`"


@dataclass
class If:
    cond: Expr
    thenexpr: Expr
    elseexpr: Expr

    def __str__(self) -> str:
        return f"(if {self.cond} then {self.thenexpr} else {self.elseexpr})"


@dataclass
class Lt:
    left: Expr
    right: Expr

    def __str__(self) -> str:
        return f"({self.left} < {self.right})"


@dataclass
class Eq:
    left: Expr
    right: Expr

    def __str__(self) -> str:
        return f"({self.left} == {self.right})"


@dataclass
class Or:
    left: Expr
    right: Expr

    def __str__(self) -> str:
        return f"({self.left} || {self.right})"


@dataclass
class And:
    left: Expr
    right: Expr

    def __str__(self) -> str:
        return f"({self.left} && {self.right})"


@dataclass
class Not:
    subexpr: Expr

    def __str__(self) -> str:
        return f"(not {self.subexpr})"


@dataclass
class Add:
    left: Expr
    right: Expr

    def __str__(self) -> str:
        return f"({self.left} + {self.right})"


@dataclass
class Sub:
    left: Expr
    right: Expr

    def __str__(self) -> str:
        return f"({self.left} - {self.right})"


@dataclass
class Mul:
    left: Expr
    right: Expr

    def __str__(self) -> str:
        return f"({self.left} * {self.right})"


@dataclass
class Div:
    left: Expr
    right: Expr

    def __str__(self) -> str:
        return f"({self.left} / {self.right})"


@dataclass
class Neg:
    subexpr: Expr

    def __str__(self) -> str:
        return f"(- {self.subexpr})"


@dataclass
class Lit:
    value: int | bool

    def __str__(self) -> str:
        return f"{self.value}"


@dataclass
class Let:
    name: str
    defexpr: Expr
    bodyexpr: Expr

    def __str__(self) -> str:
        return f"(let {self.name} = {self.defexpr} in {self.bodyexpr})"


@dataclass
class Name:
    name: str

    def __str__(self) -> str:
        return self.name


type Binding[V] = tuple[str, V]  # this tuple type is always a pair
type Env[V] = tuple[Binding[V], ...]  # this tuple type has arbitrary length

from typing import Any

emptyEnv: Env[Any] = ()  # the empty environment has no bindings


def extendEnv[V](name: str, value: V, env: Env[V]) -> Env[V]:
    """Return a new environment that extends the input environment
    env with a new binding from name to value"""
    return ((name, value),) + env


def lookupEnv[V](name: str, env: Env[V]) -> V | None:
    """Return the first value bound to name in the input environment env
    (or raise an exception if there is no such binding)"""
    match env:
        case ((n, v), *rest):
            if n == name:
                return v
            else:
                return lookupEnv(name, rest)  # type: ignore
        case _:
            return None


class EvalError(Exception):
    pass


def eval(e: Expr) -> Value:
    return evalInEnv(emptyEnv, e)


def isInt(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)  # bool is subtype of int


def isBool(v) -> bool:
    return isinstance(v, bool)


def isProc(v) -> bool:
    return isinstance(v, Proc)


def opsAreDiffTypes(l, r) -> bool:
    return type(l) is not type(r)


def procEq(lv, rv) -> bool:
    """
    It is possible to return lv == rv directly in the
    match case statement because dataclasses provides
    field by field comparison for free, but I opt for
    a function here in case the functionality is changed
    in the future, in which case it is easier to modify
    one function
    """
    return lv == rv


def evalInEnv(env: Env[Value], e: Expr) -> Value:
    match e:
        case Pipe(l, r):
            lv = evalInEnv(env, l)
            rv = evalInEnv(env, r)
            if not isProc(lv):
                raise EvalError("cannot pipe: left side is not a process")
            if not isProc(rv):
                raise EvalError("cannot pipe: right side is not a process")
            if lv.stdout is not None:
                raise EvalError("cannot pipe: left side already has stdout redirected")
            if rv.stdin is not None:
                raise EvalError("cannot pipe: right side already has stdin redirected")
            if lv.stderr is not None and rv.stderr is not None:
                raise EvalError("cannot pipe: both sides have stderr redirected")
            return Proc(
                stages=lv.stages + rv.stages,
                stdin=lv.stdin,
                stdout=rv.stdout,
                stderr=lv.stderr or rv.stderr,
            )
        case RedirectErr(p, f):
            pv = evalInEnv(env, p)
            if not isProc(pv):
                raise EvalError("cannot redirect: input is not a process")
            if pv.stderr is not None:
                raise EvalError("cannot redirect stderr twice")
            return replace(pv, stderr=f)
        case RedirectIn(p, f):
            pv = evalInEnv(env, p)
            if not isProc(pv):
                raise EvalError("cannot redirect: input is not a process")
            if pv.stdin is not None:
                raise EvalError("cannot redirect stdin twice")
            return replace(pv, stdin=f)
        case RedirectOut(p, f):
            pv = evalInEnv(env, p)
            if not isProc(pv):
                raise EvalError("cannot redirect: input is not a process")
            if pv.stdout is not None:
                raise EvalError("cannot redirect stdout twice")
            return replace(pv, stdout=f)
        case Cmd(name, args):
            return Proc(stages=[(name, args)])
        case And(l, r):
            lv = evalInEnv(env, l)
            if not isBool(lv):
                raise EvalError("'and' on non-boolean")
            if not lv:
                return False
            rv = evalInEnv(env, r)
            if not isBool(rv):
                raise EvalError("'and' on non-boolean")
            return rv
        case Or(l, r):
            lv = evalInEnv(env, l)
            if not isBool(lv):
                raise EvalError("'or' on non-boolean")
            if lv:
                return True
            rv = evalInEnv(env, r)
            if not isBool(rv):
                raise EvalError("'or' on non-boolean")
            return rv
        case Not(s):
            sv = evalInEnv(env, s)
            if not isBool(sv):
                raise EvalError("'not' on non-boolean")
            return not sv
        case Add(l, r):
            lv = evalInEnv(env, l)
            rv = evalInEnv(env, r)
            if not (isInt(lv) and isInt(rv)):
                raise EvalError("arithmetic on non-integer")
            return lv + rv
        case Sub(l, r):
            lv = evalInEnv(env, l)
            rv = evalInEnv(env, r)
            if not (isInt(lv) and isInt(rv)):
                raise EvalError("arithmetic on non-integer")
            return lv - rv
        case Mul(l, r):
            lv = evalInEnv(env, l)
            rv = evalInEnv(env, r)
            if not (isInt(lv) and isInt(rv)):
                raise EvalError("arithmetic on non-integer")
            return lv * rv
        case Div(l, r):
            lv = evalInEnv(env, l)
            rv = evalInEnv(env, r)
            if not (isInt(lv) and isInt(rv)):
                raise EvalError("arithmetic on non-integer")
            if rv == 0:
                raise EvalError("division by zero")
            return lv // rv
        case Neg(s):
            sv = evalInEnv(env, s)
            if not (isInt(sv)):
                raise EvalError("negation on non-integer")
            return -sv
        case Eq(l, r):
            lv = evalInEnv(env, l)
            rv = evalInEnv(env, r)
            if isInt(lv) and isInt(rv):
                return lv == rv
            if isBool(lv) and isBool(rv):
                return lv == rv
            if isProc(lv) and isProc(rv):
                return procEq(lv, rv)
            return False
        case Lt(l, r):
            lv = evalInEnv(env, l)
            rv = evalInEnv(env, r)
            if not (isInt(lv) and isInt(rv)):
                raise EvalError("comparison on non-integer")
            return lv < rv
        case Lit(v):
            return v
        case Name(n):
            v = lookupEnv(n, env)
            if v is None:
                raise EvalError(f"unbound name {n}")
            return v
        case Let(n, d, b):
            v = evalInEnv(env, d)
            newEnv = extendEnv(n, v, env)
            return evalInEnv(newEnv, b)
        case If(cond, thenexpr, elseexpr):
            cv = evalInEnv(env, cond)
            if not isBool(cv):
                raise EvalError("'if' condition is non-boolean")
            if cv:
                return evalInEnv(env, thenexpr)
            else:
                return evalInEnv(env, elseexpr)


def execProc(v):
    name, args = v.stages[0]

    stdin_file = open(v.stdin, "r") if v.stdin else None
    stdout_file = open(v.stdout, "w") if v.stdout else None
    stderr_file = open(v.stderr, "w") if v.stderr else None

    try:
        proc = subprocess.Popen(
            [name] + args,
            stdin=stdin_file,
            stdout=stdout_file,
            stderr=stderr_file,
        )
        proc.wait()

    except FileNotFoundError as e:
        print(f"execution error: {e}")
    finally:
        if stdin_file:
            stdin_file.close()
        if stdout_file:
            stdout_file.close()
        if stderr_file:
            stderr_file.close()


def run(e: Expr) -> None:
    print(f"running: {e}")
    try:
        v = eval(e)
        if isProc(v):
            print(f"result: {v}")
            execProc(v)
        else:
            print(f"result: {v}")
    except EvalError as err:
        print(err)


run(RedirectOut(Cmd("echo", ["hello from my DSL"]), "output.txt"))
run(RedirectIn(RedirectOut(Cmd("cat", []), "copy.txt"), "output.txt"))
