import contextvars
import functools
import inspect
from types import TracebackType
from typing import Any, Callable, Dict, Optional, Type, TypeVar, cast

__all__ = ["Injector"]

T = TypeVar("T")
TypeMap = Dict[Type[T], T]
UNSET = object()


class Context:
    def __init__(self, injector: "Injector") -> None:
        self.injector = injector
        self._registry = injector._registry

    def __enter__(self) -> None:
        self.token = self._registry.set(self._registry.get().copy())

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[Exception],
        traceback: Optional[TracebackType],
    ) -> None:
        self._registry.reset(self.token)


class Injector:
    _registry: contextvars.ContextVar

    def __init__(self) -> None:
        self._registry = contextvars.ContextVar("registry", default={})

    def register(
        self, component: Any, *, bases: bool = True, overwrite_bases: bool = True
    ) -> None:
        registry: TypeMap = self._registry.get()

        type_ = type(component)
        registry[type_] = component

        if bases:
            types = type_.mro()
            for type_ in types:
                apply = overwrite_bases or type_ not in registry
                if inspect.isclass(type_) and apply:
                    registry[type_] = component

    def get_component(self, type_: Type[T]) -> T:
        registry: TypeMap = self._registry.get()
        return cast(T, registry[type_])

    def scope(self) -> Context:
        return Context(self)

    def inject(self, f: Callable[..., T]) -> Callable[..., T]:
        sig = inspect.signature(f)

        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            registry = self._registry.get()
            bound = sig.bind_partial(*args, **kwargs)
            for name, param in sig.parameters.items():
                if (
                    name in bound.arguments
                    or param.annotation is inspect.Parameter.empty
                ):
                    continue
                component = registry.get(param.annotation, UNSET)
                if component is not UNSET:
                    bound.arguments[name] = component
            bound.apply_defaults()
            return f(*bound.args, **bound.kwargs)

        return wrapper
