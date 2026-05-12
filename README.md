# PyTerpreter — Shell DSL Expression Language

A Python-based interpreter for a functional expression language with a built-in
Shell DSL extension. Programs are written as expressions that evaluate to a value:
an integer, a boolean, a function closure, or a shell process description that
gets executed when the program runs.

---

## Project Structure

| File | Purpose |
|------|---------|
| `interp.py` | AST node definitions and evaluator |
| `expr.lark` | Lark grammar defining the concrete syntax |
| `parse_run.py` | Parser, transformer, and interactive REPL |

---

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install lark
```

---

## Running

**Run the test suite:**
```bash
python3 parse_run.py
```

**Launch the interactive REPL:**
```bash
python3 -c "from parse_run import driver; driver()"
```

Exit the REPL with `Ctrl+D`.

---

## Language Demo

### Arithmetic

```
> 1 + 2 * 3
result: 7

> (1 + 2) * 3
result: 9

> 10 / 2 - 3
result: 2
```

### Booleans

```
> true && false
result: False

> !false || true && false
result: True
```

### Comparisons

```
> 3 < 5
result: True

> 42 == 42
result: True
```

### Conditionals

```
> if 3 < 5 then 100 else 0
result: 100

> if true then if false then 1 else 2 else 3
result: 2
```

### Let Bindings

```
> let x = 10 in x * x end
result: 100

> let x = 5 in let y = 3 in x + y end end
result: 8
```

### Functions

```
> letfun double(x) = x + x in double(7) end
result: 14

> letfun square(x) = x * x in square(5) end
result: 25
```

### Recursive Functions

```
> letfun fact(n) = if n == 0 then 1 else n * fact(n - 1) in fact(6) end
result: 720
```

### Shell Commands

Shell command literals are written between backticks. They evaluate to a process
description that is executed when the program runs.

```
> `echo hello world`
hello world

> `ls` | `wc -l`
11

> `ls` | `grep py` | `wc -l`
5
```

### Shell Redirections

```
> `echo hello` > "out.txt"       -- write stdout to a file
> `cat` < "out.txt"              -- read stdin from a file
hello

> `ls nonexistent` !> "err.txt"  -- redirect stderr to a file
```

### Combining Core Language with Shell DSL

The shell operators are first-class expressions — they compose freely with the
rest of the language.

```
> if 1 < 2 then `echo yes` else `echo no`
yes

> let cmd = `echo stored` in cmd end
stored

> letfun greet(x) = `echo hello` in greet(0) end
hello
```

---

## Language Reference

| Form | Syntax | Example |
|------|--------|---------|
| Integer literal | `n` | `42` |
| Boolean literal | `true` / `false` | `true` |
| Arithmetic | `e + e`, `e - e`, `e * e`, `e / e`, `-e` | `1 + 2 * 3` |
| Boolean logic | `e \|\| e`, `e && e`, `!e` | `!false \|\| true` |
| Comparison | `e == e`, `e < e` | `x < 10` |
| Conditional | `if e then e else e` | `if x < 0 then 0 else x` |
| Let binding | `let x = e in e end` | `let x = 5 in x + 1 end` |
| Function def | `letfun f(x) = e in e end` | `letfun f(x) = x * 2 in f(3) end` |
| Function call | `f(e)` | `f(42)` |
| Shell command | `` `cmd args` `` | `` `ls -la` `` |
| Pipe | `e \| e` | `` `ls` \| `wc -l` `` |
| Stdin redirect | `e < "file"` | `` `cat` < "input.txt"`` |
| Stdout redirect | `e > "file"` | `` `echo hi` > "out.txt"`` |
| Stderr redirect | `e !> "file"` | `` `ls x` !> "err.txt"`` |
