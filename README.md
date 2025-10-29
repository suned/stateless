# stateless

Statically typed, purely functional effects for Python.

# Motivation
Programming with side-effects is hard: To reason about a unit in your code, like a function, you need to know what the other units in the program are doing to the program state, and understand how that affects what you're trying to achieve.

Programming without side-effects is _less_ hard: To reason about a unit in you code, like a function, you can focus on what _that_ function is doing, since the units it interacts with don't affect the state of the program in any way.

But of course side-effects can't be avoided, since what we ultimately care about in programming are just that: The side effects, such as printing to the console or writing to a database.

Functional effect systems like `stateless` aim to make programming with side-effects less hard. We do this by separating the specification of side-effects from the interpretation, such that functions that need to perform side effects do so indirectly via the effect system.

As a result, "business logic" code never performs side-effects, which makes it easier to reason about, test and re-use.

# Quickstart

```python
from typing import Any, Never
from stateless import Effect, Need, need, throws, catch, run


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


# Effects are generators that yield abilities that can handled up the call stack.
# An example ability might be `stateless.Need` that is used for type-safe dependency injection.
def print_(value: Any) -> Effect[Need[Console], Never, None]:
    console = yield from need(Console)
    console.print(value)


# Effects can yield exceptions. 'stateless.throws' will catch exceptions
# for you and yield them to other functions so you can handle them with
# type safety. The return type of the decorated function in this
# example is: ´Effect[Need[Files], OSError, str]'
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


# Effects are run using `stateless.run`.
# The `Need` ability is handled using `stateless.supply`.
# Before an effect can be executed with `run`, it must have
# all of its abilities handled.
effect = supply(Files(), Console())(print_file)('foo.txt')
run(effect)
```

# Guide


## Effects & Abilities & Handlers
`stateless` is a functional effect system for Python built around a pattern using [generator functions](https://docs.python.org/3/reference/datamodel.html#generator-functions). When programming with `stateless` you will describe your program's side-effects using the `stateless.Effect` type. `Effect` is in fact just a type alias for a generator:


```python
from typing import Any, Generator
from stateless import Ability


type Effect[A: Ability, E: Exception, R] = Generator[A | E, Any, R]
```
 In other words, an `Effect` is a generator that can yield classes of type `A` or exceptions of type `E`, can be sent anything, and returns results of type `R`. Let's break that down a bit further:

-  The type parameter `A` stands for _"Ability"_. This is the type of value, or types of values, that an effect depends on in order to produce its result.

 - The type parameter `E` stands for _"Error"_. This the type of errors that an effect might fail with.

 - The type parameter `R` stands for _"Result"_. This is the type of value that an `Effect` will produce if no errors occur.


Lets start by defining a simple ability. `stateless.Ability` is defined as:

```python
class Ability[R]:
    ...
```
The `R` type parameter represents the expected result type of handling the effect. For example:

```python
from dataclasses import dataclass

from stateless import Ability

@dataclass
class Greet(Ability[str]):
    name: str
```

When `Greet` inherits from `Ability[str]`, it means that when a function yields an instance of `Greet`, it expects to be sent a `str` value back.

Let's use `Greet`:

```python
from typing import Never

from stateless import Effect


def hello_world() -> Effect[Greet, Never, None]:
    greeting = yield Greet(name="world")
    print(greeting)
```

When `hello_world` returns an `Effect[Greet, Never, None]`, it means that it depends on the `Greet` ability (`A` is parameterized with `Greet`). It can't fail (`E` is parameterized with `Never`), and it doesn't produce a value (`R` is parameterized with `None`).

To run an `Effect` that depends on abilities, you need to handle the abilities. Abilities are handled using `stateless.Handler`, defined as:

```python
class Handler[A: Ability]:
    def __call__[**P, A2: Ability, E: Exception, R](
        self,
        f: Callable[P, Effect[A | A2, E, R]]
    ) -> Callable[P, Effect[A2, E, R]]:
    ...
```

Just like the paramater `A` of `Effect`, The type parameter `A` of `Handler` stands for "Ability". This is the type of abilities that this `Handler` instance can handle.

`Handler.__call__` is a decorator that accepts a function that returns a `stateless.Effect` that depends on abilities `A` and `A2`, and returns a new function that returns
an effect that only depends on ability `A2`. In other words, the ability `A` is handled by `Handler` and the decorated function now produces an effect that no longer depends on `A`.

For example, we can use `Handler` to handle the `Greet` ability required by `hello_world`. `stateless.handle` is a straight-forward way to create handlers:

```python
from stateless import handle


def greet(ability: Greet) -> str:
    return f"Hello, {ability.name}!"


effect = handle(greet)(hello_world)()
reveal_type(effect)  # revealed type is: Effect[Never, Never, None]
```

> [!NOTE]
> `stateless.handle` depends on type annotations of the handler function to match abilities with handler functions. To use `stateless.handle` you must annotate the argument of the handler function with an appropriate ability.

We can see in the revealed type how `handle(greet)` has eliminated the `Greet` ability from the effect returned by `hello_world`, and the type is now `Never`, meaning the new effect does not require any abilities.

To run effects you'll use `stateless.run`. Its type signature is:


```python
def run[R](effect: Effect[Async, Exception, R]) -> R:
    ...
```

In words: the effect passed to `run` must have had all of its abilities handled (except the built-in `Async` ability. Don't worry about this for now, we'll explain it later). The result of running `effect` is the result type `R`.

If we try to do:
```python
from stateless import run


run(hello_world())  # type-checker error!
```

We'll get a type-checker error since we can't run an effect with unhandled abilities.

Lets try this instead:

```python
effect = handle(greet)(hello_world)()
run(effect)  # outputs: Hello, world!
```
Cool. Okay maybe not. The `hello_world` example is obviously contrived. There's no real benefit to sending `greeting` to `hello_world` via `yield` over just providing it as a regular function argument. The example is included here just to give you a rough idea of how the different pieces of `stateless` fit together.

## Error Handling

So far we haven't used the error type `E` for anything: We've simply parameterized it with `typing.Never`. We've claimed that this means that the effect doesn't fail. This is of course not literally true, as exceptions can still occur even if we parameterize `E` with `Never.`

Take the `Files` ability from the previous section for example. Reading from the file system can of course fail for a number of reasons, which in Python will result in a subtype of `OSError` being raised. So calling for example `print_file` might raise an exception:

```python
from stateless import Depend


def f() -> Depend[Files, None]:
    yield from print_file('doesnt_exist.txt')  # raises FileNotFoundError
```
So what's the point of `E`?

The point is that programming errors can be grouped into two categories: recoverable errors and unrecoverable errors. Recoverable errors are errors that are expected, and that users of the API we are writing might want to know about. `FileNotFoundError` is an example of such an error.

Unrecoverable errors are errors that there is no point in telling the users of your API about.

The intended use of `E` is to model recoverable errors so that users of your API can handle them with type safety.

Let's use `E` to model the errors of `Files.read_file`:


```python
from stateless import Effect, throw


def read_file(path: str) -> Effect[Files, OSError, str]:
    files = yield Files
    try:
        return files.read_file(path)
    except OSError as e:
        return (yield from throw(e))
```

The signature of `stateless.throw` is

```python
from typing import Never

from stateless import Effect


def throw[E: Exception](e: E) -> Effect[Never, E, Never]:
    ...
```
In words `throw` returns an effect that just yields `e` and never returns. Because of this signature, if you assign the result of `throw` to a variable, you have to annotate it. But there is no meaningful type
to annotate it with. So you're better off using the somewhat strange looking syntax `return (yield from throw(e))`.

More conveniently you can use `stateless.throws` that just catches exceptions and yields them as an effect

```python
from stateless import Depend, throws


@throws(OSError)
def read_file(path: str) -> Depend[Need[Files], str]:
    files = yield from need(Files)
    return files.read_file(path)


reveal_type(read_file)  # revealed type is: def (str) -> Effect[Files, OSError, str]
```

Error handling in `stateless` is done using the `stateless.catch` decorator. Its signature is:

```python
from typing import Type
from stateless import Effect, Depend


def catch[**P, A, E: Exception, E2: Exception, R](
    *errors: Type[E]
) -> Callable[
    [Callable[P, Effect[A, E | E2, R]]],
    Callable[P, Effect[A, E2, E | R]]
]:
    ...
```

In words, the `catch` decorator catches errors of type `E` and moves the error from the error type `E` of the `Effect` produced by the decorated function, to the result type `R` of the effect of the return function. This means you can access the potential errors directly in your code:


```python
from stateless import Depend


def handle_errors() -> Depend[Files, str]:
    result: OSError | str = yield from catch(OSError)(read_file)('foo.txt')
    match result:
        case OSError():
            return 'default value'
        case _:
            return result

```
(You don't need to annotate the type of `result`, it can be inferred by your type checker. We do it here simply because its instructive to look at the types.)

Consequently you can use your type checker to avoid unintentionally unhandled errors, or ignore them with type-safety as you please.


`catch` can also catch a subset of errors produced by effects, and pass other errors up the call stack, just like when using regular exceptions. But unlike when using regular exceptions,
your type checker can see and understand which errors are handled where:

```python
def fails_in_multiple_ways() -> Try[FileNotFoundError | PermissionError | IsADirectoryError, str]:
    ...

def handle_subset_of_errors() -> Try[PermissionError, str]:
    result = yield from catch(FileNotFoundError, IsADirectoryError)(fails_in_multiple_ways)()
    match result:
        case FileNotFoundError() | IsADirectoryError():
            return 'default value'
        case _:
            return result
```

This means that:
- You can't neglect to report an error in the signature for `handle_subset_of_errors` since your type checker can tell that `yield from catch(...)(fails_in_multiple_ways)` will still yield `PermissionError`
- You can't neglect to handle errors in your code because your type checker can tell that `result` may be 2 different errors or a string.

## Built in Abilities

### Need

Let's look at a bigger example. The main point of a purely functional effect system is to enable side-effects such as IO in a purely functional way. So let's implement some abilities for doing side-effects.

We'll start with an ability we'll call `Console` for writing to the console:

```python
class Console:
    def print(self, line: str) -> None:
        print(line)
```
We can use `Console` with `Effect` as an ability. Recall that the _"send"_ type of `Effect` is `Any`. In order to tell our type checker that the result of yielding the `Console` class will be a `Console` instance, we can use the `stateless.need` function. Its signature is:

```python
from typing import Type

from stateless import Depend, Need


def depend[A](ability: Type[A]) -> Depend[A, A]:
    ...
```

`stateless.Depend` is a type alias:

```python
from typing import Never


type Depend[A, R] = Effect[A, Never, R]
```
In words, `Depend` is just an effect that depends on `A` and produces no errors.

So `depend` just yields the ability type for us, and then returns the instance that will eventually be sent from `Abilities`.

Let's see that in action with the `Console` ability:

```python
from stateless import Depend, depend


def say_hello() -> Depend[Console, None]:
    console = yield from depend(Console)
    console.print(f"Hello, world!")
```

Let's add another ability `Files` to read rom the file system:


```python
class Files:
    def read(self, path: str) -> str:
        with open(path, 'r') as f:
            return f.read()
```
Putting it all together:

```python
from stateless import Depend


def print_file(path: str) -> Depend[Console | Files, None]:
    files = yield from depend(Files)
    console = yield from depend(Console)

    content = files.read(path)
    console.print(content)
```
Note that for the `Effect` returned by `print_file`, `A` is parameterized with `Console | Files` since `print_file` depends on both `Console` and `Files` (i.e it will yield both classes).

`print_file` is a good demonstration of why the _"send"_ type of `Effect` must be `Any`: Since `print_file` expects to be sent instances of `Console` _or_ `File`, it's not possible for our type-checker to know on which yield which type is going to be sent, and because of the variance of `typing.Generator`, we can't write `depend` in a way that would allow us to type `Effect` with a _"send"_ type other than `Any`.

`print_file` is also an example of how to build complex effects using functions that return simpler effects using `yield from`:


```python
from stateless import Depend, depend


def get_str() -> Depend[str, str]:
    s = yield from depend(str)
    return s


def get_int() -> Depend[str | int, tuple[str, int]]:
    s = yield from get_str()
    i = yield from depend(int)

    return (s, i)
```

you can of course run `print_file` with `Abilities` and `run`:


```python
from stateless import Abilities, run


abilities = Abilities().add(Files()).add(Console())
effect = abilities.handle(print_file)('foo.txt')
run(effect)
```

`Abilities` also allows us to partially provide abilities for an effect:


```python
print_file = Abilities().add(Console()).handle(print_file)
reveal_type(print_file)  # revealed type is: () -> Depend[Files, None]

print_file = Abilities().add(Files()).handle(print_file)
reveal_type(print_file)  # revealed type is: () -> Depend[Never, None]
```

The first time we handle abilities of `print_file`, we only handle the `Console` ability. The result is a function that returns an effect that only depends on `Files`.
The second time we handle abilities of `print_file`, we only handle the `Files` ability. The result is a function that returns an effect that doesn't depend on any abilities.

This feature allows you to provide some abilities locally to a part of your program, hiding implementation details from the rest of your program.

A major purpose of dependency injection is to vary the injected ability to change the behavior of the effect. For example, we
might want to change the behavior of `print_files` in tests:


```python
class MockConsole(Console):
    def print(self, line: str) -> None:
        pass


class MockFiles(Files):
    def __init__(self, content: str) -> None:
        self.content = content

    def read(self, path: str) -> str:
        return self.content


def mock_abilities() -> Abilities[Console | Files]:
    console = MockConsole()
    files = MockFiles("mock content")
    return Abilities().add(console).add(files))

abilities = mock_abilities()
effect = abilities.handle(print_file)('foo.txt')
run(effect)
```

Our type-checker will likely infer the types `console` and `files` to be `MockConsole` and `MockFiles` respectively, So we have moved their initialization to a function with the annotated return type `Abilities[Console | Files`]. Otherwise, our type checker will not be able to infer that `abilities.handle` in fact handles the `Console` and `Files` abilities of `print_file`.

Besides `Effect`, stateless` provides you with a few other type aliases that can save you a bit of typing. Firstly success which is just defined as:

```python
from typing import Never


type Success[R] = Effect[Never, Never, R]
```

for effects that don't fail and don't require abilities (can be easily instantiated using the `stateless.success` function).

Secondly, the `Depend` type alias, defined as:

```python
from typing import Never

type Depend[A, R] = Effect[A, Never, R]
```

for effects that depend on `A` but produces no errors.


Finally the `Try` type alias, defined as:


```python
from typing import Never


type Try[E, R] = Effect[Never, E, R]
```
For effects that do not require abilities, but might produce errors.

Sometimes, instantiating abilities may itself require side-effects. For example, consider a program that requires a `Config` ability:


```python
from stateless import Depend


class Config:
    ...


def main() -> Depend[Config, None]:
    ...
```

Now imagine that you want to provide the `Config` ability by reading from environment variables:


```python
import os

from stateless import Depend, depend


class OS:
    environ: dict[str, str] = os.environ


def get_config() -> Depend[OS, Config]:
    os = yield from depend(OS)
    return Config(
        auth_token=os.environ['AUTH_TOKEN'],
        url=os.environ['URL']
    )
```

To supply the `Config` instance returned from `get_config`, we can use `Abilities.add_effect`:


```python
from stateless import Abilities


Abilities().add(OS()).add_effect(get_config())
```

`Abilities.add_effect` assumes that all abilities required by the effect given as its argument can be provided by `Abilities`. If this is not the case, you'll get a type-checker error:

```python
from stateless import Depend, Abilities


class A:
    pass


class B:
    pass


def get_B() -> Depend[A, B]:
    ...

Abilities().add(A()).add_effect(get_B())  # OK
Abilities().add_effect(get_B())           # Type-checker error!
```

(It will often make sense to use an `abc.ABC` as your ability types to enforce programming towards the interface and not the implementation. If you use `mypy` however, note that [using abstract classes where `typing.Type` is expected is a type-error](https://github.com/python/mypy/issues/4717), which will cause problems if you pass an abstract type to `depend`. We recommend disabling this check, which will also likely be the default for `mypy` in the future.)

### Async

## Repeating and Retrying Effects

A `stateless.Schedule` is a type with an `__iter__` method that returns an effect producing an iterator of `timedelta` instances. It's defined like:

```python
from typing import Protocol, Iterator
from datetime import timedelta

from stateless import Depend


class Schedule[A](Protocol):
    def __iter__(self) -> Depend[A, Iterator[timedelta]]:
        ...
```
The type parameter `A` is present because some schedules may require abilities to complete.

The `stateless.schedule` module contains a number of of helpful implemenations of `Schedule`, for example `Spaced` or `Recurs`.

Schedules can be used with the `repeat` decorator, which takes schedule as its first argument and repeats the decorated function returning an effect until the schedule is exhausted or an error occurs:

```python
from datetime import timedelta

from stateless import repeat, success, Success, Abilities, run
from stateless.schedule import Recurs, Spaced
from stateless.time import Time


@repeat(Recurs(2, Spaced(timedelta(seconds=2))))
def f() -> Success[str]:
    return success("hi!")

effect = Abilities().add(Time()).handle(f)()
result = run(effect)
print(run)  # outputs: ("hi!", "hi!")
```
Effects created through repeat depends on the `Time` ability from `stateless.time` because it needs to sleep between each execution of the effect.

Schedules are a good example of a pattern used a lot in `stateless`: Classes with an `__iter__` method that returns effects.

This is a useful pattern because such objects can be yielded from in functions returning effects multiple times where a new generator will be instantiated every time:

```python
def this_works() -> Success[timedelta]:
    schedule = Spaced(timedelta(seconds=2))
    deltas = yield from schedule
    deltas_again = yield from schedule  # safe!
    return deltas
```

For example, `repeat` needs to yield from the schedule given as its argument to repeat the decorated function. If the schedule was just a generator it would only be possible to yield from the schedule the first time `f` in this example was called.

`stateless.retry` is like `repeat`, except that it returns succesfully
when the decorated function yields no errors, or fails when the schedule is exhausted:

```python
from datetime import timedelta

from stateless import retry, throw, Try, throw, success, Abilities, run
from stateless.schedule import Recurs, Spaced
from stateless.time import Time


fail = True


@retry(Recurs(2, Spaced(timedelta(seconds=2))))
def f() -> Try[RuntimeError, str]:
    global fail
    if fail:
        fail = False
        return throw(RuntimeError('Whoops...'))
    else:
        return success('Hooray!')


effect = Abilities().add(Time()).handel(f)()
result = run(effect)
print(result)  # outputs: 'Hooray!'
```

## Memoization

Effects can be memoized using the `stateless.memoize` decorator:


```python
from stateless import memoize, Depend, Abilities, run
from stateless.console import Console, print_line


@memoize
def f() -> Depend[Console, str]:
    yield from print_line('f was called')
    return 'done'


def g() -> Depend[Console, tuple[str, str]]:
    first = yield from f()
    second = yield from f()
    return first, second


effect = Abilities().add(Console()).handle(f)()
result = run(effect) # outputs: 'f was called' once, even though the effect was yielded twice

print(result)  # outputs: ('done', 'done')
```
`memoize` works like [`functools.lru_cache`](https://docs.python.org/3/library/functools.html#functools.lru_cache), in that the memoized effect
is cached based on the arguments of the decorated function. In fact, `memoize` takes the same parameters as `functools.lru_cache` (`maxsize` and `typed`) with the same meaning.
# Known Issues

See the [issues](https://github.com/suned/stateless/issues) page.

# Algebraic Effects Vs. Monads

All functional effect system work essentially the same way:

1. Programs send a description of the side-effect needed to be performed to the effect system and pause their executing while the effect system handles the side-effect.
2. Once the result of performing the side-effect is ready, program execution is resumed at the point it was paused

Step 2. is the tricky part: how can program execution be resumed at the point it was paused?

[Monads](https://en.wikipedia.org/wiki/Monad_(functional_programming)) are the most common solution. When programming with monads, in addition to supplying the effect system with a description of a side-effect, the programmer also supplies a function to
be called with the result of handling the described effect. In functional programming such a function is called a _continuation_. In other paradigms it might be called a _callback function_.

For example it might look like this:

```python
def say_hello() -> IO[None]:
    return Input("whats your name?").bind(lambda name: Print(f"Hello, {name}!"))
```
One of the main benefits of basing effect systems on monads is that they don't rely on any special language features: its all literally just functions.

However, many programmers find monads awkward. Programming with callback functions often lead to code thats hard for humans to parse, which has ultimately inspired specialized language features for hiding the callback functions with syntax sugar like [Haskell's do notation](https://en.wikibooks.org/wiki/Haskell/do_notation), or [for comprehensions in Scala](https://docs.scala-lang.org/tour/for-comprehensions.html).

Moreover, monads famously do not compose, meaning that when writing code that needs to juggle multiple types of side-effects (like errors and IO), it's up to the programmer to pack and unpack results of various types of effects (or use advanced features like [monad transformers](https://en.wikibooks.org/wiki/Haskell/Monad_transformers) which come with their own set of problems).

Additionally, in languages with dynamic binding such as Python, calling functions is relatively expensive, which means that using callbacks as the principal method for resuming computation comes with a fair amount of performance overhead.

Finally, interpreting monads is often a recursive procedure, meaning that it's necessary to worry about stack safety in languages without tail call optimisation such as Python. This is usually solved using [trampolines](https://en.wikipedia.org/wiki/Trampoline_(computing)) which further adds to the performance overhead.


Because of all these practical challenges of programming with monads, people have been looking for alternatives. Algebraic effects is one the things suggested that address many of the challenges of monadic effect systems.

In algebraic effect systems, such as `stateless`, the programmer still supplies the effect system with a description of the side-effect to be carried out, but instead of supplying a callback function to resume the
computation with, the result of handling the effect is returned to the point in program execution that the effect description was produced. The main drawback of this approach is that it requires special language features to do this. In Python however, such a language feature _does_ exist: Generators and coroutines.

Using coroutines for algebraic effects solves many of the challenges with monadic effect systems:

- No callback functions are required, so readability and understandability of the effectful code is much more straightforward.
- Code that needs to describe side-effects can simply list all the effects it requires, so there is no composition problem.
- There are no callback functions, so no need to worry about performance overhead of calling a large number of functions or using trampolines to ensure stack safety.


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
