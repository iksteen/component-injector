import contextvars
import functools
import inspect
from dataclasses import dataclass
from types import TracebackType
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    Type,
    TypeVar,
    cast,
    Set,
    Union,
    List,
    Iterable,
    Awaitable,
    Tuple,
)

__all__ = ["Injector"]


T = TypeVar("T")
ComponentMap = Dict[Type[T], T]


@dataclass
class Factory:
    factory: Optional[Callable[[], Any]]
    resolved_types: Set[Type]
    scope: Optional[ComponentMap] = None


FactoryMap = Dict[Type[T], Factory]

UNSET = object()


class ComponentStack:
    def __init__(self, layers: Optional[List[ComponentMap]] = None) -> None:
        if layers is not None:
            self._layers = layers
        else:
            self._layers = [{}]

    @property
    def layer(self) -> ComponentMap:
        return self._layers[0]

    def stack(self) -> "ComponentStack":
        return ComponentStack([{}, *self._layers])

    def __contains__(self, key: Type[T]) -> bool:
        try:
            self.__getitem__(key)
            return True
        except KeyError:
            return False

    def __getitem__(self, key: Type[T]) -> T:
        for layer in self._layers:
            if key in layer:
                value = layer[key]
                if value is UNSET:
                    raise KeyError(key)
                return cast(T, value)
        raise KeyError(key)

    def __setitem__(self, key: Type[T], value: T) -> None:
        self._layers[0][key] = value

    def __delitem__(self, key: Type[T]) -> None:
        self._layers[0][key] = UNSET

    def update(self, values: ComponentMap) -> None:
        self._layers[0].update(values)


class Context:
    def __init__(self, injector: "Injector") -> None:
        self._factories = injector._factories
        self._components = injector._components

    def __enter__(self) -> None:
        self._factories_token = self._factories.set(self._factories.get().copy())
        self._components_token = self._components.set(self._components.get().stack())

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
        self._components = contextvars.ContextVar(
            "components", default=ComponentStack()
        )

    def _register_type_factory(
        self,
        type_: Type[T],
        factory_function: Optional[Callable[[], T]],
        *,
        bases: bool = True,
        overwrite_bases: bool = True,
        persistent: bool = True,
    ) -> Factory:
        factories: FactoryMap = self._factories.get()
        components: ComponentStack = self._components.get()

        if persistent:
            factory = Factory(factory_function, {type}, components.layer)
        else:
            factory = Factory(factory_function, {type})
        factories[type_] = factory

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
        overwrite_bases: bool = True,
        persistent: bool = False,
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
            type_,
            factory,
            bases=bases,
            overwrite_bases=overwrite_bases,
            persistent=persistent,
        )

    def _get_component_scope(
        self, factory: Factory
    ) -> Union[ComponentMap, ComponentStack]:
        if factory.scope is not None:
            return factory.scope
        else:
            return cast(ComponentStack, self._components.get())

    def register(
        self, component: Any, *, bases: bool = True, overwrite_bases: bool = True
    ) -> None:
        factory = self._register_type_factory(
            type(component), None, bases=bases, overwrite_bases=overwrite_bases
        )

        component_scope = self._get_component_scope(factory)
        component_scope.update({type_: component for type_ in factory.resolved_types})

    def _build_component(
        self, type_: Type[T]
    ) -> Tuple[Optional[Factory], Union[T, Awaitable[T]]]:
        components: ComponentStack = self._components.get()
        if type_ in components:
            return None, components[type_]

        factories: FactoryMap = self._factories.get()
        factory = factories[type_]

        factory_function = factory.factory
        assert factory_function is not None
        return factory, factory_function()

    def get_component(self, type_: Type[T]) -> T:
        factory, component = self._build_component(type_)

        if inspect.isawaitable(component):
            raise RuntimeError("Using an awaitable factory in synchronous code.")

        if factory is not None:
            component_scope = self._get_component_scope(factory)
            component_scope.update(
                {type_: component for type_ in factory.resolved_types}
            )

        return cast(T, component)

    async def get_component_async(self, type_: Type[T]) -> T:
        factory, component_or_awaitable = self._build_component(type_)

        if inspect.isawaitable(component_or_awaitable):
            component = await cast(Awaitable[T], component_or_awaitable)
        else:
            component = cast(T, component_or_awaitable)

        if factory is not None:
            component_scope = self._get_component_scope(factory)
            component_scope.update(
                {type_: component for type_ in factory.resolved_types}
            )

        return component

    def scope(self) -> Context:
        return Context(self)

    def inject(self, f: Callable[..., T]) -> Callable[..., T]:
        sig = inspect.signature(f)

        def bind_arguments(
            args: Iterable[Any], kwargs: Dict[str, Any]
        ) -> Tuple[inspect.BoundArguments, Dict[str, Any]]:
            factories = self._factories.get()
            bound = sig.bind_partial(*args, **kwargs)
            components = {}

            for name, param in sig.parameters.items():
                if (
                    name in bound.arguments
                    or param.annotation is inspect.Parameter.empty
                ):
                    continue

                if param.annotation in factories:
                    components[name] = param.annotation

            return bound, components

        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            bound, bind_components = bind_arguments(args, kwargs)
            bound.arguments.update(
                {
                    name: self.get_component(type_)
                    for name, type_ in bind_components.items()
                }
            )
            bound.apply_defaults()
            return f(*bound.args, **bound.kwargs)

        @functools.wraps(f)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            bound, bind_components = bind_arguments(args, kwargs)
            bound.arguments.update(
                {
                    name: await self.get_component_async(type_)
                    for name, type_ in bind_components.items()
                }
            )
            bound.apply_defaults()
            return await cast(Awaitable[T], f(*bound.args, **bound.kwargs))

        if inspect.iscoroutinefunction(f):
            return async_wrapper
        else:
            return wrapper
