import contextvars
import functools
import inspect
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Callable, Dict, Optional, Type, TypeVar, cast, Set

__all__ = ["Injector"]


@dataclass
class Factory:
    factory: Optional[Callable[[], Any]]
    resolved_types: Set[Type]


T = TypeVar("T")
FactoryMap = Dict[Type[T], Factory]
ComponentMap = Dict[Type[T], T]

UNSET = object()


class Context:
    def __init__(self, injector: "Injector") -> None:
        self._factories = injector._factories
        self._components = injector._components

    def __enter__(self) -> None:
        self._factories_token = self._factories.set(self._factories.get().copy())
        self._components_token = self._components.set(self._components.get().copy())

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[Exception],
        traceback: Optional[TracebackType],
    ) -> None:
        self._components.reset(self._components_token)
        self._factories.reset(self._factories_token)


class Injector:
    _factories: contextvars.ContextVar
    _components: contextvars.ContextVar

    def __init__(self) -> None:
        self._factories = contextvars.ContextVar("factories", default={})
        self._components = contextvars.ContextVar("components", default={})

    def _register_type_factory(
        self,
        type_: Type[T],
        factory_function: Optional[Callable[[], T]],
        *,
        bases: bool = True,
        overwrite_bases: bool = True
    ) -> Factory:
        factories: FactoryMap = self._factories.get()
        components: FactoryMap = self._components.get()

        factories[type_] = factory = Factory(factory_function, {type_})

        if bases:
            types = type_.mro()
            for type_ in types:
                apply = overwrite_bases or type_ not in factories
                if inspect.isclass(type_) and apply:
                    factory.resolved_types.add(type_)
                    factories[type_] = factory

                    if overwrite_bases and type_ in components:
                        del components[type_]

        return factory

    def register_factory(
        self,
        factory: Callable[[], Any],
        *,
        bases: bool = True,
        overwrite_bases: bool = True
    ) -> None:
        if inspect.isclass(factory):
            type_ = cast(Type[Any], factory)
        else:
            type_ = inspect.signature(factory).return_annotation
            if type_ is inspect.Signature.empty:
                raise ValueError(
                    "Please add a return type annotation to your factory function."
                )

        self._register_type_factory(
            type_, factory, bases=bases, overwrite_bases=overwrite_bases
        )

    def register(
        self, component: Any, *, bases: bool = True, overwrite_bases: bool = True
    ) -> None:
        factory = self._register_type_factory(
            type(component), None, bases=bases, overwrite_bases=overwrite_bases
        )

        components: ComponentMap = self._components.get()
        for type_ in factory.resolved_types:
            components[type_] = component

    def get_component(self, type_: Type[T]) -> T:
        components: ComponentMap = self._components.get()
        if type_ in components:
            return cast(T, components[type_])

        factories: FactoryMap = self._factories.get()
        factory = factories[type_]
        factory_function = factory.factory
        assert factory_function is not None
        component = cast(T, factory_function())

        components.update({type_: component for type_ in factory.resolved_types})

        return component

    def scope(self) -> Context:
        return Context(self)

    def inject(self, f: Callable[..., T]) -> Callable[..., T]:
        sig = inspect.signature(f)

        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            factories = self._factories.get()
            bound = sig.bind_partial(*args, **kwargs)

            for name, param in sig.parameters.items():
                if (
                    name in bound.arguments
                    or param.annotation is inspect.Parameter.empty
                ):
                    continue

                if param.annotation in factories:
                    bound.arguments[name] = self.get_component(param.annotation)

            bound.apply_defaults()
            return f(*bound.args, **bound.kwargs)

        return wrapper
