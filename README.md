# stateless

Statically typed, purely functional effects for Python.

# Motivation
Programming with side-effects is hard: To reason about a unit in your code, like a function, you need to know what the other units in the program are doing to the program state, and understand how that affects what you're trying to achieve.

Programming without side-effects is _less_ hard: To reason about a unit in your code, like a function, you can focus on what _that_ function is doing, since the units it interacts with don't affect the state of the program in any way.

But of course side-effects can't be avoided, since what we ultimately care about in programming are the side effects, such as printing to the console or writing to a database.

Functional effect systems like `stateless` aim to make programming with side-effects less hard. We do this by separating the specification of side-effects from the interpretation, such that functions that need to perform side effects do so indirectly via the effect system.

As a result, "business logic" code never performs side-effects, which makes it easier to reason about, test and re-use.

# Quickstart

## Install


```console
> pip install stateless
```


## Usage


```python
from typing import Any, Never

from stateless import Effect, Need, need, throws, catch, run, supply


# stateless.Effect is just an alias for:
#
# from typing import Generator, Any
# from stateless import Ability
#
# type Effect[A: Ability, E: Exception, R] = Generator[A | E, Any, R]


class Files:
    def read_file(self, path: str) -> str:
        with open(path) as f:
            return f.read()


class Console:
    def print(self, value: Any) -> None:
        print(value)


# Effects are generators that yield abilities that can be handled up the call stack.
# `stateless.Need` is a built-in ability that is used for type-safe dependency injection.
def print_(value: Any) -> Effect[Need[Console], Never, None]:
    console = yield from need(Console)
    console.print(value)


# Effects can yield exceptions. 'stateless.throws' will catch exceptions
# for you and yield them to other functions so you can handle them with
# type safety. The return type of the decorated function in this
# example is: ´Effect[Need[Files], OSError, str]`
@throws(OSError)
def read_file(path: str) -> Effect[Need[Files], Never, str]:
    files = yield from need(Files)
    return files.read_file(path)


# Simple effects can be combined into complex ones by
# depending on multiple abilities.
def print_file(path: str) -> Effect[Need[Files] | Need[Console], Never, None]:
    # catch will return exceptions yielded by other functions
    result = yield from catch(OSError)(read_file)(path)
    match result:
        case OSError() as error:
            yield from print_(f"error: {error}")
        case _ as content:
            yield from print_(content)


# Before an effect can be executed, all of its abilities must be handled.
# The `Need` ability is handled using `stateless.supply`.
effect = supply(Files(), Console())(print_file)('foo.txt')
# Effects are run using `stateless.run`.
run(effect)
```

# Guide


## Effects, Abilities & Handlers
`stateless` is a functional effect system for Python built around a pattern using [generator functions](https://docs.python.org/3/reference/datamodel.html#generator-functions). When programming with `stateless` you will describe your program's side-effects using the `stateless.Effect` type. `Effect` is in fact just a type alias for a generator:


```python
from typing import Any, Generator

from stateless import Ability


type Effect[A: Ability, E: Exception, R] = Generator[A | E, Any, R]
```
In other words, an `Effect` is a generator that can yield values of type `A` or error values of type `E`, can be sent anything, and returns results of type `R`. Let's break that down a bit further:

-  The type parameter `A` stands for _"Ability"_. This is the type of value, or types of values, that must be handled in order for the effect to produce its result.

 - The type parameter `E` stands for _"Error"_. This the type of error, or types of errors, that an effect might fail with.

 - The type parameter `R` stands for _"Result"_. This is the type of value that an `Effect` will produce if no errors occur.


`A` and `E` of `stateless.Effect` are often parameterized with `Never`, so
stateless provides the following type aliases to save you some typing:

```python
from typing import Never

from stateless import Ability, Effect


type Depend[A: Ability, R] = Effect[A, Never, R]  # for effects that depend on A but don't fail
type Try[E: Exception, R] = Effect[Never, E, R]   # for effects that might fail but do not need Abilities
type Success[R] = Effect[Never, Never, R]         # for effects that don't fail and do not need Abilities
```


Let's define a simple ability. `stateless.Ability` is defined as:

```python
from typing import Self


class Ability[R]:
    def __iter__(self: Self) -> Generator[Self, R, R]: ...
```

The `R` type parameter represents the expected result of handling the effect. For example:

```python
from dataclasses import dataclass

from stateless import Ability


@dataclass
class Greet(Ability[str]):
    name: str
```

When `Greet` inherits from `Ability[str]`, it means that when a function yields an instance of `Greet`, the function should expect that the result of handling `Greet` has type `str`.

You may recall that the "send" type of `stateless.Effect` is `Any`. This is because functions that return effects may depend on multiple abilities that return different types of values when handled,
so in general we can't say what the "send" type should be.

The `Abilities.__iter__` method is a way to get around this. The send and return types are `R`, which allows your type-checker to correctly infer the type of handling an ability by using `yield from`.

Let's use `Greet`:

```python
from typing import Never

from stateless import Effect


def hello_world() -> Effect[Greet, Never, None]:
    greeting = yield from Greet(name="world")
    print(greeting)
```

When `hello_world` has return type `Effect[Greet, Never, None]`, it means that it depends on the `Greet` ability (`A` is parameterized with `Greet`). It doesn't produce errors (`E` is parameterized with `Never`), and it doesn't return a value (`R` is parameterized with `None`).

To run an `Effect` that depends on abilities, you need to handle all of the abilities yielded by that effect. Abilities are handled using `stateless.Handler`, defined as:

```python
from stateless import Ability, Effect


class Handler[A: Ability]:
    def __call__[**P, A2: Ability, E: Exception, R](
        self,
        f: Callable[P, Effect[A | A2, E, R]]
    ) -> Callable[P, Effect[A2, E, R]]:
    ...
```

Just like the parameter `A` of `Effect`, The type parameter `A` of `Handler` stands for "Ability". This is the type of abilities that this `Handler` instance can handle.

`Handler.__call__` is a decorator that accepts a function that returns a `stateless.Effect` that depends on abilities `A` and `A2`, and returns a new function that returns
an effect that only depends on ability `A2`. In other words, the ability `A` is handled by `Handler` and the decorated function now produces an effect that no longer depends on `A`.

For example, we can use `Handler` to handle the `Greet` ability required by `hello_world`. `stateless.handle` is a straight-forward way to create handlers:

```python
from stateless import handle


def greet(ability: Greet) -> str:
    return f"Hello, {ability.name}!"


effect = handle(greet)(hello_world)()
reveal_type(effect)  # revealed type is: Success[None]
```

We can see in the revealed type how `handle(greet)` has eliminated the `Greet` ability from the effect returned by `hello_world`, so that it is now a `Success[None]` (or `Effect[Never, Never, None]`), meaning the new effect does not require any abilities.

To run effects you'll use `stateless.run`. Its type signature is:


```python
def run[R](effect: Effect[Async, Exception, R]) -> R:
    ...
```

In words: the effect passed to `run` must depend **only** on the built-in `Async` ability (Don't worry about the `Async` ability for now, we'll explain it later). All other abilities must have been handled before calling `run`. The result of running `effect` is the result type `R`.

If we try to do:
```python
from stateless import run


run(hello_world())  # type-checker error!
```

We'll get a type-checker error since we can't run an effect with unhandled abilities.

Let's try this instead:

```python
effect = handle(greet)(hello_world)()
run(effect)  # outputs: Hello, world!
```
Since we've handled the `Greet` ability for `hello_world`, we can now run the resulting effect with no type checker errors.


To access the result type of an effect from another effect, use `yield from`:


```python
def f() -> Success[float]: ...

def g() -> Success[float]:
    number = yield from f()
    return number * 2
```

Simple effects can be combined into complex effects by depending on multiple abilities:

```python
def depend_on_some_ability() -> Depend[SomeAbility, None]: ...

def depend_on_another_ability() -> Depend[AnotherAbility, None]: ...

def depend_on_both_abilities() -> Depend[SomeAbility | AnotherAbility, None]:
    yield from f()
    yield from g()
```

One way to think about abilities is as a generalization of exceptions: when a function needs to have an ability handled it passes the ability up the call stack until an appropriate handler is found, similar to how a raised exception travels up the call stack. In contrast with exception handling however, once the ability is handled, the result of handling the ability is returned to the function that yielded it in the first place, and execution resumes.

Like exceptions, abilities can be partially handled (with type-safety):

```python
handle_some_ability: Handler[SomeAbility] = ...
effect = handle_some_ability(depend_on_both_abilities)()
reveal_type(effect)  #  Revealed type is: Depend[AnotherAbility, None]
```

The revealed type indicates that `handle_some_ability` has handled `SomeAbility` of `depend_on_both_abilities`, so it now only depends on `AnotherAbility`.

## Error Handling

So far we haven't used the error type `E` for anything: We've simply parameterized it with `typing.Never`. We've claimed that this means that the effect doesn't fail. This is of course not literally true, as exceptions can still occur even if we parameterize `E` with `Never.`

The intended use of `E` is to model recoverable errors so that users of your API can handle them with type safety.

The main way to turn exceptions into errors of effects is using `stateless.throws`. Its signature is:


```python
from typing import Type, Callable
from stateless import Effect, Try


def throws[E2: Exception, E: Exception, A: Ability, R](
    *errors: Type[E],
) -> Callable[
    [Callable[P, Effect[A, E2, R] | R]],
    Callable[P, Effect[A, E | E2, R] | Try[E2, R]]
]:
    ...
```
In words, `throws` returns a decorator that catches exceptions of type `E` raised by the decorated function, and yields them.


Let's use `throws` to model the potential errors when reading a file.
```python
from stateless import Effect, throws

@throws(FileNotFoundError, PermissionError)
def read_file(path: str) -> str:
    with open(path) as f:
        return f.read()


reveal_type(read_file)  # Revealed type is: Callable[[str], Try[FileNotFoundError | PermissionError, str]]
```

Error handling in `stateless` is done using the `stateless.catch` decorator. Its signature is:

```python
from typing import Type
from stateless import Effect


def catch[**P, A, E: Exception, E2: Exception, R](
    *errors: Type[E]
) -> Callable[
    [Callable[P, Effect[A, E | E2, R]]],
    Callable[P, Effect[A, E2, E | R]]
]:
    ...
```

In words, the `catch` decorator catches errors of type `E` and moves the error from the error type `E` of the `Effect` produced by the decorated function, to the result type `R` of the effect of the return function.

For example:


```python
from typing import reveal_type

from stateless import Success


def handle_errors() -> Success[str]:
    result = yield from catch(FileNotFoundError, PermissionError)(read_file)('foo.txt')
    reveal_type(result)  # Revealed type is: FileNotFoundError | PermissionError | str
    match result:
        case FileNotFoundError() | PermissionError():
            return 'default value'
        case _:
            return result
```
Consequently you can use your type checker to avoid unintentionally unhandled errors, or ignore them with type-safety as you please.


`catch` can also catch a subset of errors produced by effects, and pass other errors up the call stack, just like when using try/except. But unlike when using try/except,
your type checker can see and understand which errors are handled where:

```python
def handle_subset_of_errors() -> Try[PermissionError, str]:
    result = yield from catch(FileNotFoundError)(read_file)('foo.txt')
    match result:
        case FileNotFoundError():
            return 'default value'
        case _:
            return result
```

This means that:
- You can't neglect to report an error in the signature for `handle_subset_of_errors` without a type-checker error, since your type checker can tell that `yield from catch(...)(fails_in_multiple_ways)` will still yield `PermissionError`
- You can't neglect to handle errors in your code without a type-checker error because your type checker can tell that `result` may be `FileNotFoundError` or `str`.

## Built-in Abilities

### Need

`Need` is an ability for type-safe dependency injection. By "type-safe" we mean:

- Functions with dependencies can't fail to report a dependency in its type signature without a type-checker error.
- You can't run effects with dependencies without handling them without a type-checker error.

`Need` is used by calling the `need` function. Its signature is:

```python
from typing import Type

from stateless import Need, Depend


def need[T](t: Type[T]) -> Depend[Need[T], T]: ...
```

`T` could be anything, but will often be types that can perform side-effects.

Let's define a type we'll call `Console` for writing to the console:

```python
from stateless import Depend, Need, need


class Console:
    def print(self, line: str) -> None:
        print(line)


def say_hello() -> Depend[Need[Console], None]:
    console = yield from need(Console)
    console.print(f"Hello, world!")
```

A major purpose of dependency injection is to vary the injected ability to change the behavior of the effect. For example, we
might want to change the behavior of `say_hello` in tests. Let's define a subtype of `Console` to use in a test:


```python
class MockConsole(Console):
    def print(self, line: str) -> None:
        pass
```
When trying to handle `Need[Console]` with `supply(MockConsole())`, you may need to explicitly tell your type checker that `supply(MockConsole())` has type `Handler[Console]`. For some type checkers this can be done with an explicit annotation. If you use a type checker that uses local type narrowing however, such as pyright, this is harder than you might expect.

To assist with type inference for type checkers with local type narrowing, stateless supplies a utility function `as_type`, that tells your type checker to treat a subtype as a supertype in a certain context.

`as_type` has type:


```python
from typing import Type, Callable


def as_type[T](t: Type[T]) -> Callable[[T], T]: ...
```

Let's use `as_type` with `supply`:
```python
from stateless import as_type, supply


console = as_type(Console)(MockConsole())
effect = supply(console)(say_hello)()
run(effect)
```
Using `as_type`, our type checker has correctly inferred that the `Need[Console]` ability yielded by `say_hello` was eliminated by `supply(console)`.

### Async
The `Async` ability is used to run code asynchronously, either with `asyncio` or `concurrent.futures`.

To use the result of an `asyncio` coroutine in an effect, use the `stateless.wait` function. Its defined as:


```python
from typing import Awaitable

from stateless import Depend, Async


def wait[R](target: Awaitable[R]) -> Depend[Async, R]: ...
```
In words, `wait` translates an `Awaitable` into an `Effect` that depends on the `Async` ability.

For example:
```python
from stateless import wait, Async, Depend


async def do_io() -> str: ...


def use_io() -> Depend[Async, str]:
    result = yield from wait(do_io())
    return result
```

Recall that the signature of `stateless.run` is:


```python
from stateless import Async


def run[R](effect: Effect[Async, Exception, R]) -> R: ...
```

`stateless` has another run function, `run_async`. that gives us a hint how this works:


```python
from stateless import Async


async def run_async(effect: Effect[Async, Exception, R]) -> R: ...
```

`run_async` simply awaits `asyncio` coroutines yielded by effects. The reason `stateless.run` does not need the `Async` effect handled is because `stateless.run` just calls `asyncio.run(run_async(effect))`.
This also means that it is always safe to call e.g `asyncio.get_running_loop` from functions that return effects.


To run effects in other process/threads, use the `stateless.fork` decorator, defined as:


```python
from concurrent.futures import Executor
from stateless import Task, Depend, Need, Executor, Try


def fork[**P, R](f: Callable[P, Try[Exception, R]]) -> Callable[P, Depend[Need[Executor], Task[R]]]: ...
```

`stateless.Task` is a type that represents an effect executing in a another process or thread. `stateless.wait` is in fact overloaded to allow you to access the result of a task:


```python
from concurrent.futures import Executor
from stateless import fork, wait, Success, Depend, Need, Async


def do_something() -> Success[float]: ...


def do_something_async() -> Depend[Need[Executor] | Async, float]:
    task = yield from fork(do_something)()
    result = yield from wait(task)
    return result
```

To handle the `Need[Executor]` ability yielded by `fork`, use `concurrent.futures.ThreadPoolExecutor` or `concurrent.futures.ProcessPoolExecutor`. Since these are subtypes of `concurrent.futures.Executor`, you may need to use `stateless.as_type` depending on the type inference algorithm used by your type checker:

```python
from concurrent.futures import ThreadPoolExecutor, Executor
from stateless import as_type, supply, run

executor = as_type(Executor)(ThreadPoolExecutor())
with executor:
    effect = supply(executor)(do_something_async)()
    run(effect)
```

`fork` will simply call `stateless.run` in the remote process/thread, so all abilities of `f` must be handled before forking.

Moreover, all unhandled errors yielded by `f` will be raised in the remote thread/process, so if you want to handle errors from forked effects in the main process/thread, you need to use `stateless.catch` before forking:


```python
def may_fail() -> Try[OSError, str]: ...


def run_may_fail() -> Depend[Need[Executor], str]:
    task = yield from fork(catch(OSError)(may_fail))()
    result = yield from wait(task)
    reveal_type(result)  # Revealed type is: str | OSError
    match result:
        case OSError():
            return 'default value'
        case _:
            return result
```

## Repeating and Retrying Effects

A `stateless.Schedule` is a type with an `__iter__` method that returns an effect producing an iterator of `timedelta` instances. It's defined like:

```python
from typing import Protocol, Iterator
from datetime import timedelta

from stateless import Depend, Ability


class Schedule[A: Ability]:
    def __iter__(self) -> Depend[A, Iterator[timedelta]]:
        ...
```
The type parameter `A` is present because some schedules may require abilities to complete.

The `stateless.schedule` module contains a number of of helpful implementations of `Schedule`, for example `spaced` or `recurs`.

Schedules can be used with the `repeat` decorator, which takes schedule as its first argument and repeats the decorated function returning an effect until the schedule is exhausted or an error occurs:

```python
from datetime import timedelta

from stateless import repeat, success, Success, supply, run
from stateless.schedule import recurs, spaced
from stateless.time import Time


@repeat(recurs(2, spaced(timedelta(seconds=2))))
def f() -> Success[str]:
    return success("hi!")

time = Time()
effect = supply(time)(f)()
result = run(effect)
print(result)  # outputs: ("hi!", "hi!")
```
Effects created through repeat depends on the `Need[stateless.Time]` ability because it needs to sleep between each execution of the effect.

Schedules are a good example of a pattern used a lot in `stateless`: Classes with an `__iter__` method that returns effects.

This is a useful pattern because such objects can be yielded from in functions returning effects multiple times where a new generator will be instantiated every time:

```python
def this_works() -> Success[timedelta]:
    schedule = spaced(timedelta(seconds=2))
    deltas = yield from schedule
    deltas_again = yield from schedule  # safe!
    return deltas
```

For example, `repeat` needs to yield from the schedule given as its argument to repeat the decorated function. If the schedule was just a generator it would only be possible to yield from the schedule the first time `f` in this example was called.

`stateless.retry` is like `repeat`, except that it returns successfully.
when the decorated function yields no errors, or fails when the schedule is exhausted:

```python
from datetime import timedelta

from stateless import retry, throw, Try, throw, success, supply, run
from stateless.schedule import recurs, spaced
from stateless.time import Time


fail = True


@retry(recurs(2, spaced(timedelta(seconds=2))))
def f() -> Try[RuntimeError, str]:
    global fail
    if fail:
        fail = False
        return throw(RuntimeError('Whoops...'))
    else:
        return success('Hooray!')

time = Time()
effect = supply(time)(f)()
result = run(effect)
print(result)  # outputs: 'Hooray!'
```

## Memoization

Effects can be memoized using the `stateless.memoize` decorator:


```python
from stateless import memoize, Depend, supply, run, Need, supply
from stateless.console import Console, print_line


@memoize
def f() -> Depend[Need[Console], str]:
    yield from print_line('f was called')
    return 'done'


def g() -> Depend[Need[Console], tuple[str, str]]:
    first = yield from f()
    second = yield from f()
    return first, second


console = Console()
effect = supply(console)(f)()
result = run(effect) # outputs: 'f was called' once, even though the effect `f()` was yielded from twice

print(result)  # outputs: ('done', 'done')
```
`memoize` works like [`functools.lru_cache`](https://docs.python.org/3/library/functools.html#functools.lru_cache), in that the memoized effect
is cached based on the arguments of the decorated function. In fact, `memoize` takes the same parameters as `functools.lru_cache` (`maxsize` and `typed`) with the same meaning.
# Known Issues

See the [issues](https://github.com/suned/stateless/issues) page.

# Why Generators?

Every functional effect system has the same two-step shape:

1. Your code describes a side-effect it needs performed, and pauses.
2. Something else performs the side-effect, and your code resumes from where it
   paused with the result.

Step 2 is the interesting part. How does a paused function get resumed?

## The callback approach

The oldest answer is that your code hands over a function to be called with the
result. If `stateless` worked this way, `say_hello` would look something like
this (this is not real `stateless` code):

```python
def say_hello() -> IO[None]:
    return Input("What's your name?").bind(
        lambda name: Print(f"Hello, {name}!")
    )
```

`bind` means "when you have the result, call this function with it". The
function you pass is the rest of your program.

This works, and it has a real advantage: it needs no special language features.
It's all just functions and objects.

But Python programmers have seen where it leads, because it's how asynchronous
code was written before `async`/`await`: every step you add is another layer of
nesting, and reading the code means reading it inside-out. Languages that lean
on this pattern add syntax to hide the nesting: Haskell has
[do notation](https://en.wikibooks.org/wiki/Haskell/do_notation), Scala has
[for comprehensions](https://docs.scala-lang.org/tour/for-comprehensions.html).
Python has nothing comparable.

There's a second problem, which shows up as soon as you need two kinds of
side-effect in the same function, such as reading a file that might fail. The
`bind` machinery is defined per effect type, so combining two of them means
either writing the wrapping and unwrapping by hand at every step, or reaching
for a mechanism that stacks them for you (in Haskell these are called
[monad transformers](https://en.wikibooks.org/wiki/Haskell/Monad_transformers)).
Those mechanisms work, but they're fiddly in practice: the order you stack them
in changes the behaviour, the types get long, and adding a third effect tends to
mean touching code that had nothing to do with it.

And in Python there's a cost on top of all that. Every step of every effect is a
function call, and function calls in CPython are not cheap.

## The generator approach

`stateless` gets the same result without writing any callbacks. When an effect
yields an ability, Python suspends the generator, and the handler resumes it by
sending the result back in:

```python
def say_hello() -> Depend[Need[Console], None]:
    console = yield from need(Console)
    console.print("Hello, world!")
```

Everything after the `yield from` *is* the callback. You just didn't have to
write it, because the generator frame already holds it for you. That's the whole
trick, and the rest follows from it:

- Effects read top-to-bottom, like ordinary Python.
- A function that needs two abilities lists both in its type and yields from
  each. There's nothing to stack and nothing to unwrap.
- No chain of closures per effect, and no trampoline needed to keep the stack
  from growing.

## Isn't this just a monad?

Essentially yes, and deliberately so.

The callback version above has a name in the literature: it's the *free monad*.
What `stateless` does is the same construction, with the paused computation
stored in a generator frame instead of a chain of closures. If you're
comfortable with the terminology: `stateless` effects are a `Freer` monad, and
`yield from` does the work of `bind`.

Both approaches can express the same things. What separates them is how much you
have to write and what it costs to run. Generators buy readable effectful code,
effect composition with no stacking machinery, and far fewer Python-level
function calls. Those are good reasons to prefer them.

If you've never come across monads, none of this section matters. You don't need
any of that vocabulary to use `stateless`, which is rather the point.

## One limitation worth knowing about

A Python generator can be resumed, but it can't be forked: there's no way to run
the same paused effect forward twice along two different paths.

So handlers in `stateless` resume a computation at most once. Handlers that need to
resume more than once can't be expressed. For example, you can't write a handler
for a "choose between these two values" ability that explores both branches and
collects every result. Effect systems built on first-class continuations can do
this; generators can't.

This is a deliberate trade, and it's the reason the literature describes this
style as *one-shot* algebraic effects.


# Background

- [Do be do be do (Lindley, McBride and McLaughlin)](https://arxiv.org/pdf/1611.09259.pdf)

- [Handlers of Algebraic Effects (Plotkin and Pretnar)](https://homepages.inf.ed.ac.uk/gdp/publications/Effect_Handlers.pdf)

- [One-Shot Algebraic Effects as Coroutines (Kawahara and Kameyama)](https://link.springer.com/chapter/10.1007/978-3-030-57761-2_8) (with an implementation in [ruby](https://github.com/nymphium/ruff) and [lua](https://github.com/Nymphium/eff.lua))

# Similar Projects

- [Abilities in the Unison language](https://www.unison-lang.org/)

- [Effects in OCaml 5.0](https://v2.ocaml.org/manual/effects.html)

- [Frank language](https://github.com/frank-lang/frank)

- [Koka language](https://koka-lang.github.io/koka/doc/index.html)

- [Eff language](https://www.eff-lang.org/)

- [Effekt language](https://effekt-lang.org/)

- [flix language](https://flix.dev/)
