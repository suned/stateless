# stateless

Statically typed, purely functional effects for Python.

# Motivation
Programming with side-effects is hard: To reason about a unit in your code, like a function, you need to know what the functions it calls are doing to the state of the program, and understand how that affects what you're trying to achieve.

Programming without side-effects is _less_ hard: To reason about a unit in you code, like a function, you can focus on what _that_ function is doing, since the functions it calls don't affect the state of the program in any way, except for returning values.

But of course side-effects can't be avoided, since what we ultimately care about in programming are just that: The side effects, such as printing to the console or writing to a database.

Functional effect systems like `stateless` aim to make programming with side-effects less hard. We do this by separating the specification of side-effects from the interpretation, such that functions that need to perform side effects do so indirectly via the effect system.

As a result, "business logic" code never performs side-effects, which makes it easier to reason about, test and re-use.

# Guide


## Effects, Abilities and Runtime

When programming with `stateless` you will describe your program's side-effects using the `stateless.Effect` type. This is in fact just a type alias:


```python
from typing import Generator, Type


type Effect[A, E: Exception, R] = Generator[Type[A] | E, A, R]
```
 In other words, `Effect` takes three type parameters: `A`, `E` and `R`. Let's break that down:

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
Cool. Okay maybe not. But one thing to note is that the `A` type parameter of `Effect` and `Runtime` work together to ensure type safe dependency injection of abilities: You can't forget to provide a dependency to an effect without getting a type error.

Let's look at a bigger example. The main point of a purely functional effect system is to enable side-effects such as IO in a purely functional way. So let's implement some abilities for doing side-effects.

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

    content = files.read(path)  # type-checker error!
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
    
    content = files.read(path)
    console.print(content)
```
`depend` is also a good example of how you can build complex effects using functions that return simpler effects using `yield from`:
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

Besides `Effect` and `Depend`, `stateless` provides you with a few other type aliases that can save you a bit of typing. Firstly success which is just defined as:


```python
from typing import Never


type Success[R] = Effect[Never, Never, R]
```

for effects that don't fail and don't require abilities (can be easily instantiated using the `stateless.success` function).

Secondly the `Try` type alias, defined as:


```python
from typing import Never


type Try[E, R] = Effect[Never, E, R]
```
For effects that do not require abilities, but might fail.

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

At a slightly higher level you can use `stateless.throws` that just catches exceptions and yields them as an effect

```python
from stateless import Depend, throws


@throws(OSError)
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

## Parallel Effects
Two challenges present themselves when running generator based effects in parallel:

- Generators aren't thread-safe.
- Generators can't be pickled.

Hence, instead of sharing effects between threads and processes to run them in parallel, `stateless` gives you tools to share _functions_ that return effects plus _arguments_ to those functions between threads and processes.

`stateless` calls a function that returns an effect plus arguments to pass to that function a _task_, represented by the `stateless.parallel.Task` class.

`stateless` provides two decorators for instantiating `Task` instances: `stateless.parallel.thread` and `stateless.parallel.process`. Their signatures are:


```python
from typing import Callable

from stateless import Effect
from stateless.parallel import Task


def process[**P, A, E: Exception, R](f: Callable[P, Effect[A, E, R]]) -> Callable[P, Task[A, E, R]]:
    ...

def thread[**P, A, E: Exception, R](f: Callable[P, Effect[A, E, R]]) -> Callable[P, Task[A, E, R]]:
    ...
```
Decorating functions with `stateless.parallel.thread` indicate to `stateless` your intention for the resulting task to be run in a separate thread. Decorating functions with `stateless.parallel.process` indicate your intention for the resulting task to be run in a separate process.

Because of the [GIL](https://en.wikipedia.org/wiki/Global_interpreter_lock), using `stateless.parallel.thread` only makes sense for functions returning effects that are [I/O bound](https://en.wikipedia.org/wiki/I/O_bound). For CPU bound effects, you will want to use `stateless.parallel.process`.

To run effects in parallel, you use the `stateless.parallel` function. It's signature is roughly:


```python
from stateless import Effect
from stateless.parallel import Parallel


def parallel[A, E: Exception, R](*tasks: Task[A, E, R]) -> Effect[A | Parallel, E, tuple[R, ...]]:
    ...
```
(in reality `parallel` is overloaded to correctly union abilities and errors, and reflect the result types of each effect in the result type of the returned effect.)

In words, `parallel` accepts a variable number of tasks as its argument, and returns a new effect that depends on the `stateless.parallel.Parallel` ability. When executed, the effect returned by `parallel` will run the tasks given as its arguments concurrently.


Here is a full example:
```python
from stateless import parallel, Success, success, Depend
from stateless.parallel import thread, process, Parallel


def sing() -> Success[str]:
    return success("🎵")


def duet() -> Depend[Parallel, tuple[str, str]]:
    result = yield from parallel(
        thread(sing)(),
        process(sing)()
    )
    return result
```
When using the `Parallel` ability, you must use it as a context manager, because it manages multiple resources to enable concurrent execution of effects:
```python
from stateless import Runtime
from stateless.parallel import Parallel


with Parallel() as ability:
    print(Runtime().use(ability).run(duet()))  # outputs: ("🎵", "🎵")
```

In this example the first `sing` invocation will be run in a separate thread process because its wrapped with `thread`, and the second `sing` invocation will be run in a separate process because it's wrapped by `process`. Note that although `thread` and `process` are strictly speaking decorators, they don't return `stateless.Effect` instances. For this reason, it's probably not a good idea to use them as `@thread` or `@process`, since this
reduces the re-usability of the decorated function. Use them at the call site as shown in the example instead.

`stateless.parallel.Task` _does_ however implement `__iter__` to return the result of the decorated function, so you _can_ yield from them if necessary:

```python
from stateless import Success, thread


def sing_more() -> Success[str]:
    # This is rather pointless, 
    # but helps you out if you for some 
    # reason have used @thread instead of thread(...)
    note = yield from thread(sing)()
    return note * 2  
```
If you need more control over the resources managed by `stateless.parallel.Parallel`, you can pass them as arguments:
```python
from multiprocessing.pool import ThreadPool
from multiprocessing import Manager

from stateless.parallel import Parallel


with (
    Manager() as manager,
    manager.Pool() as pool,
    ThreadPool() as thread_pool, 
    Parallel(pool, thread_pool) as parallel
):    
    ...
```
The process pool used to execute `stateless.parallel.Task` instances needs to be run with a manager because it needs to be sent to the process executing the task in case it needs to run more
effects in other processes.

Note that if you pass in in the thread pool and proxy pool as arguments, `stateless.parallel.Parallel` will not exit them for you when it itself exits: you need to manage their state yourself.


You can of course subclass `stateless.parallel.Parallel` to change the interpretation of this ability (for example in tests). The two main functions you'll want to override is `run_thread_tasks` and `run_cpu_tasks`:

```python
from stateless import Runtime, Effect
from stateless.parallel import Parallel, Task


class MockParallel(Parallel):
    def __init__(self):
        pass

    def run_cpu_tasks(self, 
                 runtime: Runtime[object], 
                 tasks: Sequence[Task[object, Exception, object]]) -> Tuple[object, ...]:
        return tuple(runtime.run(iter(task)) for task in tasks)
    
    def run_thread_tasks(self
                    runtime: Runtime[object],
                    effects: Sequence[Effect[object, Exception, object]]) -> Tuple[object, ...]:
        return tuple(runtime.run(iter(task)) for task in tasks)
```
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

`stateless.retry` is like `repeat`, except that it returns succesfully
when the decorated function yields no errors, or fails when the schedule is exhausted:

```python
from datetime import timedelta

from stateless import retry, throw, Try, throw, success, Runtime
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


print(Runtime().use(Time()).run(f()))  # outputs: 'Hooray!'
```

## Memoization

Effects can be memoized using the `stateless.memoize` decorator:


```python
from stateless import memoize, Depend
from stateless.console import Console, print_line


@memoize
def f() -> Depend[Console, str]:
    yield from print_line('f was called')
    return 'done'


def g() -> Depend[Console, tuple[str, str]]:
    first = yield from f()
    second = yield from f()
    return first, second


result = Runtime().use(Console()).run(f())  # outputs: 'f was called' once, even though the effect was yielded twice

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

- [One-Shot Algebraic Effects as Coroutines (Kawahara and Kameyama)](https://link.springer.com/chapter/10.1007/978-3-030-57761-2_8)

# Similar Projects

- [Abilities in the Unison language](https://www.unison-lang.org/)

- [Frank language](https://github.com/frank-lang/frank)


