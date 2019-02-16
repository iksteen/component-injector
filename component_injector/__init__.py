import contextvars
import functools
import inspect
from types import TracebackType
from typing import Any, Callable, Dict, Optional, Type, TypeVar, cast

__all__ = ["Injector"]


T = TypeVar("T")
ComponentMap = Dict[Type[T], T]
UNSET = object()


class Context:
    def __init__(self, injector: "Injector") -> None:
        self._components = injector._components

    def __enter__(self) -> None:
        self.components_token = self._components.set(self._components.get().copy())

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[Exception],
        traceback: Optional[TracebackType],
    ) -> None:
        self._components.reset(self.components_token)


class Injector:
    _components: contextvars.ContextVar

    def __init__(self) -> None:
        self._components = contextvars.ContextVar("components", default={})

    def register(
        self, component: Any, *, bases: bool = True, overwrite_bases: bool = True
    ) -> None:
        components: ComponentMap = self._components.get()

        type_ = type(component)
        components[type_] = component

        if bases:
            types = type_.mro()
            for type_ in types:
                apply = overwrite_bases or type_ not in components
                if inspect.isclass(type_) and apply:
                    components[type_] = component

    def get_component(self, type_: Type[T]) -> T:
        components: ComponentMap = self._components.get()
        return cast(T, components[type_])

    def scope(self) -> Context:
        return Context(self)

    def inject(self, f: Callable[..., T]) -> Callable[..., T]:
        sig = inspect.signature(f)

        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            components = self._components.get()
            bound = sig.bind_partial(*args, **kwargs)
            for name, param in sig.parameters.items():
                if (
                    name in bound.arguments
                    or param.annotation is inspect.Parameter.empty
                ):
                    continue
                component = components.get(param.annotation, UNSET)
                if component is not UNSET:
                    bound.arguments[name] = component
            bound.apply_defaults()
            return f(*bound.args, **bound.kwargs)

        return wrapper
