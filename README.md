# component-injector
> A modern component / dependency injector for python 3.6+.

This library provides a framework-agnostic component (or dependency)
injector that injects registered components into your function calls.
The components to insert are identified by looking at the called
function argument annotations.

When registering a component, all its base classes are registered as
well unless you explicitly disable that. You can also choose to only
register base classes that are not already registered with the
injector.

It provides local scopes where you can register additional components
or override existing components. After exiting the scope, the registry
will return to the state it was in before entering the scope.

## Compatibility

`component-injector` is compatible with python 3.6+ using the
backported `contextvars` package.

The scopes are thread-safe and when using python 3.7 also safe for for
use with asyncio tasks.

## Installation

`component-injector` is available from pypi:

```sh
pip install component-injector
```

## Usage example

Here's a small demo on how to use the injector:

```
from component_injector import Injector

injector = Injector()

class O:
    pass

@injector.inject
def consumer_of_o(o: O) -> None:
    print(o)

injector.register(O())
consumer_of_o()  # 'o' wil be the registered instance.

consumer_of_o(O())  # 'o' will be this new instance.
```

_For more examples and usage, please refer to
[demo.py](https://github.com/iksteen/component-injector/blob/master/demo.py)
and
[async_demo.py](https://github.com/iksteen/component-injector/blob/master/async_demo.py)._

## Development setup

For development purposes, you can clone the repository and use
[poetry](https://poetry.eustace.io/) to install and maintain the
dependencies. There is no test suite. The project comes with a set of
pre-commit hooks that can format (isort, black) and check your code
(mypy, flake8) automatically.

```sh
git clone git@github.com:iksteen/component-injector.git
cd component-injector
poetry run pre-commit install
```

## Release History

* 1.0.2
    * Fix bug where already bound arguments were overwritten.

* 1.0.1
    * Fix links to examples.

* 1.0.0
    * Initial Release.

## Meta

Ingmar Steen – [@iksteen](https://twitter.com/iksteen)

Distributed under the MIT license. See ``LICENSE`` for more information.

[https://github.com/iksteen/](https://github.com/iksteen/)

## Contributing

1. Fork it (<https://github.com/iksteen/component-injector/fork>)
2. Create your feature branch (`git checkout -b feature/fooBar`)
3. Commit your changes (`git commit -am 'Add some fooBar'`)
4. Push to the branch (`git push origin feature/fooBar`)
5. Create a new Pull Request
