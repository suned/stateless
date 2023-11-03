# stateless

Statically typed, purely functional algebraic effects for Python.

# Concepts


## Effects, Abilities and Runtime

`stateless` is a purely functional effect system. The main point of a purely functional effect system is to enable you to work with side-effects such as doing IO in a purely functional way.

When programming with `stateless` you will describe your program's side-effects using the `stateless.Effect` type. This is in fact just a type alias:


```python
from typing import Generator, Type


type Effect[A, E: Exception, R] = Generator[Type[A] | E, A, R]
```
 In other words, `Effect` takes three type parameters: `A`, `E` and `R`. Lets break that down:

 The `A` in `Effect` stands for "Ability". This is the type of value that an effect depends on in order to produce its result.

 The `E` parameter of `Effect` stands for "Error". This the type of errors that an effect might fail with.

 Finally, `R` stands for "Result". This is the type of value that an `Effect` will produce if no errors occur.



Lets start with a very simple example of an `Effect`:
```python
from typing import Never

from stateless import Effect


def hello_world() -> Effect[str, Never, None]:
    message = yield str
    print(message)
```

When `hello_world` returns an `Effect[str, Never, None]`, it means that it depends on a `str` instance being sent to produce its value (`A` is parameterized with `str`). It can't fail (`E` is parameterized with `Never`), and it doesn't produce a value (`R` is parameterized with `None`).

`Never` is quite frequently used as the parameter for `E`, so `stateless` also supplies a type alias `Depend` with just that:

```python
from typing import Never

from stateless import Effect


type Depend[A, R] = Effect[A, Never, R]
```

So `hello_world` could also have been written:


```python
from stateless import Depend


def hello_world() -> Depend[str, None]:
    message = yield str
    print(message)
```

To run an `Effect`, you need an instance of `stateless.Runtime`. `Runtime` has just two methods: `use` and `run`. Let's look at their definitions:


```python
from stateless import Effect


class Runtime[A]:
    def use[A2](self, ability: A2) -> Runtime[A | A2]:
        ...
    
    def run[E: Exception, R](self, effect: Effect[A, E, R]) -> R:
        ...
```
The type parameter `A` of runtime again stands for "Ability". This is the type of abilities that this `Runtime` instance can provide.

`Runtime.use` takes an instance of `A`, the ability type, to be sent to the effect passed to `run` upon request (i.e when its type is yielded by the effect).

`Runtime.run` returns the result of running the `Effect` (or raises an exception if the effect fails).

Let's run `hello_world`:

```python
from stateless import Runtime


runtime = Runtime().use(b"Hello, world!")
runtime.run(hello_world())  # type-checker error!
```
Whoops! We accidentally provided an instance of `bytes` instead of `str`, which was required by `hello_world`. Let's try again:

```python
from stateless import Runtime


runtime = Runtime().use("Hello, world!")
runtime.run(hello_world()) # outputs: Hello, world!
```
Cool. Okay maybe not. But one thing to note is that the `A` type parameter of `Effect` and `Runtime` work together to ensure type safe dependency injection of abilities.

Let's look at a bigger example. The main point of a purely functional effect system is to enable side-effects such as IO in a purely functional way. So lets implement some abilities for doing side-effects.

We'll start with an ability we'll call `Console` for writing to the console:

```python
class Console:
    def print(self, line: str) -> None:
        print(line)
```
We can use `Console` with `Effect` as an ability:

```python
from stateless import Depend


def say_hello() -> Depend[Console, None]:
    console = yield Console
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
    ...
```
Note that `A` is parameterized with `Console | Files` since `print_file` depends on both `Console` and `Files` (ie it will yield both classes).

Let's add a body for `print_file`:

```python
from stateless import Depend


def print_file(path: str) -> Depend[Console | Files, None]:
    files = yield Files
    console = yield Console

    content = files.read("foo.txt")  # type-checker error!
    console.print(content)
```
That's a bit annoying. Since the "send" type of our generator can be both `Files` and `Console`, our type-checker doesn't know which type is going to sent to `print_files` from `Runtime` at which point.

To fix this we need to use the `stateless.depend` function. It's defined like this:

```python
from typing import Type

from stateless import Depend


def depend[A](ability: Type[A]) -> Depend[A, A]:
    return (yield ability)
```
So `depend` just yields the ability for us, and then returns the instance that will eventually be sent from `Runtime`.

Let's use that to fix `print_file`:

```python
from stateless import Depend, depend


def print_file(path: str) -> Depend[Console | Files, None]:
    files = yield from depend(Files)
    console = yield from depend(Console)
    
    content = files.read("foo.txt")
    console.print(content)
```
`depend` is also a good example of how you can build complex effects using functions that return simpler effects using `yield from`:
```python
from stateless import Depend, depend


def get_str() -> Depend[str, str]:
    s = yield from depend(str)
    return s


def get_int() -> Depend[str | int, tuple[str, int]]:
    s = yield from f()
    i = yield from depend(int)
    
    return (s, i)
```

It will often make sense to use an `abc.ABC` as your ability type to enforce programming towards the interface and not the implementation. If you use `mypy` however, note that [using abstract classes where `typing.Type` is expected is a type-error](https://github.com/python/mypy/issues/4717), which will cause problems if you pass an abstract type to `depend`. We recommend disabling this check, which will also likely be the default for `mypy` in the future. 

you can of course run `print_file` with `Runtime`:


```python
from stateless import Runtime


runtime = Runtime().use(Files()).use(Console())
runtime.run(print_file('foo.txt'))
```
Again, if we forget to supply an ability for `runtime` required by `print_file`, we'll get a type error.

Of course the main purpose of dependency injection is to vary the injected ability to change the behavior of the effect. For example, we
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


console: Console = MockConsole()
files: Files = MockFiles('mock content'.)

runtime = Runtime().use(console).use(files)
runtime.run(print_file('foo.txt'))
```

Our type-checker will likely infer the types `console` and `files` to be `MockConsole` and `MockFiles` respectively, so we need to annotate them with the super-types `Console` and `Files`. Otherwise it will cause the inferred type of `runtime` to be `Runtime[MockConsole, MockFiles]` which would not be type-safe when calling `run` with an argument of type `Effect[Console | Files, Never, None]` due to the variance of `collections.abc.Generator`.

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

Unrecoverable errors are errors that there is no point in telling the users of your API about. Depending on the context, `ZeroDivisionError` or `KeyError` might be examples of unrecoverable errors.

The intended use of `E` is to model recoverable errors so that users of your API can handle them with type safety.

Let's use `E` to model the errors of `Files.read_file`:


```python
from stateless import Effect, fail


def read_file(path: str) -> Effect[Files, OSError, str]:
    files = yield Files
    try:
        return files.read_file(path)
    except OSError as e:
        return (yield from fail(e))
```

The signature of `stateless.fail` is

```python
from typing import Never

from stateless import Effect


def fail[E: Exception](e: E) -> Effect[Never, E, Never]:
    ...
```
In words `fail` returns an effect that just yields `e` and never returns. Because of this signature, if you assign the result of `fail` to a variable, you have to annotate it. But there is no meaningful type
to annotate it with. So you're better off using the somewhat strange looking syntax `return (yield from fail(e))`.

At a slightly higher level you can use `stateless.absorb` that just catches exceptions and yields them as an effect

```python
from stateless import Depend, absorb


@absorb(OSError)
def read_file(path: str) -> Depend[Files, str]:
    files = yield Files
    return files.read_file(path)


reveal_type(read_file)  # revealed type is: def (str) -> Effect[Files, OSError, str]
```

Error handling in `stateless` is done using the `stateless.catch` decorator. Its signature is:

```python
from stateless import Effect, Depend


def catch[**P, A, E: Exception, R](
    f: Callable[P, [Effect[A, E, R]]]
) -> Callable[P, Depend[A, E | R]]: 
    ...
```

In words, the `catch` decorator moves the error from the yield type of the `Effect` produced by its argument to the return type of the effect of the function returned from `catch`. This means you can access the potential errors directly in your code:


```python
from stateless import Depend


def handle_errors() -> Depend[Files, str]:
    result: OSError | str = yield from catch(read_file)('foo.txt')
    match result:
        case OSError:
            return 'default value'
        case str():
            return result

```
(You don't need to annotate the type of `result`, it can be inferred by your type checker. We do it here simply because its instructive to look at the types.)

Consequently you can use your type checker to avoid unintentionally unhandled errors, or ignore them with type-safety as you please.

`catch` is a good example of a pattern used in many places in `stateless`: using decorators to change the result of an effect. The reason for this pattern is that generators are mutable objects.

For example, we could have defined catch like this:


```python
def bad_catch(effect: Effect[A, E, R]) -> Depend[A, E | R]:
    ...
```

But with this signature, it would not be possible to implement `bad_catch` without  mutating `effect` as a side-effect, since it's necessary to yield from it to implement catching.

In general, it's not a good idea to write functions that take effects as arguments directly, because it's very easy to accidentally mutate them which would be confusing for the caller:


```python
def f() -> Depend[str, int]:
    ...


def dont_do_this(e: Depend[str, int]) -> Depend[str, int]:
    i = yield from e
    return i


def this_is_confusing() -> Depend[str, tuple[int, int]]:
    e = f()
    r = yield from dont_do_this(e)
    r_again = yield from e  # e was already exhausted, so 'r_again' is None!
    return (r, r_again)
```
A better idea is to write a decorator that accepts a function that returns effects. That way there is no risk of callers passing generators and then accidentally mutating them as a side effect:

```python
def do_this_instead[**P](f: Callable[P, Depend[str, int]]) -> Callable[P, Depend[str, int]]:
    @wraps(f)
    def decorator(*args: P.args, **kwargs: P.kwargs) -> Depend[str, int]:
        i = yield from f(*args, **kwargs)
        return i
    return decorator


def this_is_easy():
    e = f()
    r = yield from do_this_instead(f)()
    r_again = yield from e
    return (r, r_again)

```

## Async Effects

TODO



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

from stateless import repeat, success, Success, Runtime
from stateless.schedule import Recurs, Spaced
from stateless.time import Time


@repeat(Recurs(2, Spaced(timedelta(seconds=2))))
def f() -> Success[str]:
    return success("hi!")


print(Runtime().use(Time()).run(f()))  # outputs: ("hi!", "hi!")
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

retrying: TODO

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

- [One-Shot Algebraic Effects as Coroutines (Kawahara and Kameyama)](https://link.springer.com/chapter/10.1007/978-3-030-57761-2_8)

# Similar Projects

- [Abilities in the Unison language](https://www.unison-lang.org/)

- [Frank language](https://github.com/frank-lang/frank)


