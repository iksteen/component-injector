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
    context: Optional["Context"] = None


FactoryMap = Dict[Type[T], Factory]

UNSET = object()


class ComponentStack:
    __slots__ = ["_layers", "layer"]

    def __init__(self, layers: Optional[List[ComponentMap]] = None) -> None:
        if layers is None:
            layers = [{}]
        self._layers = layers
        self.layer = layers[0]

    def stack(self) -> "ComponentStack":
        return ComponentStack([{}, *self._layers])

    def __getitem__(self, key: Type[T]) -> T:
        for layer in self._layers:
            if key in layer:
                value = layer[key]
                if value is UNSET:
                    raise KeyError(key)
                return cast(T, value)
        raise KeyError(key)

    def __setitem__(self, key: Type[T], value: T) -> None:
        self.layer[key] = value

    def __delitem__(self, key: Type[T]) -> None:
        self.layer[key] = UNSET

    def update(self, values: ComponentMap) -> None:
        self.layer.update(values)


@dataclass
class ContextData:
    factories: FactoryMap
    components: ComponentStack

    def stack(self) -> "ContextData":
        return ContextData(self.factories.copy(), self.components.stack())


class Context:
    __slots__ = ["_current_context", "_data", "_tokens"]

    _data: ContextData
    _tokens: List[Any]

    def __init__(self, other: Optional["Context"] = None) -> None:
        if other is None:
            self._current_context = contextvars.ContextVar("Context", default=self)
            self._data = ContextData({}, ComponentStack())
        else:
            self._current_context = other._current_context
            self._data = self.current._data.stack()
        self._tokens = []

    def __enter__(self) -> "Context":
        self._tokens.append(self._current_context.set(self))
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[Exception],
        traceback: Optional[TracebackType],
    ) -> None:
        self._current_context.reset(self._tokens.pop())

    @property
    def current(self) -> "Context":
        return self._current_context.get()

    @property
    def components(self) -> ComponentStack:
        return self.current._data.components

    @property
    def factories(self) -> FactoryMap:
        return self.current._data.factories


class Injector:
    """
    Provides a basic injector namespace. It's common to use one
    injector per project.
    """

    __slots__ = ["_context"]

    def __init__(self) -> None:
        self._context = Context()

    def _register_type_factory(
        self,
        type_: Type[T],
        factory_function: Optional[Callable[[], T]],
        *,
        bases: bool = True,
        overwrite_bases: bool = True,
        persistent: bool = True,
    ) -> Factory:
        factories: FactoryMap = self._context.factories
        components: ComponentStack = self._context.components

        if persistent:
            factory = Factory(factory_function, {type}, self._context.current)
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

                    if overwrite_bases:
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
        """
        Register a new factory function with the injector. Not that the
        factory function's return type annotation should be set to the
        type of the component you want to inject.

        :param factory: The factory function. Will be called without
            arguments and should return the instantiated component. If
            the factory returns an Awaitable it can only used to inject
            into coroutine functions.
        :param bases: Besides registering the exact component type,
            also register for all of the component's base classes.
            Defaults to `True`.
        :param overwrite_bases: If any of the component's base classes
            are already registered with the injector, overwrite those
            registrations. Defaults to `True`.
        :param persistent: When materializing the component using the
            factory, insert the component into the scope where the
            factory is registered instead of the current scope.
            Defaults to `False`.
        """

        if inspect.isclass(factory):
            type_ = cast(Type[Any], factory)
        else:
            type_ = inspect.signature(factory).return_annotation
            assert (
                type_ is not inspect.Signature.empty
            ), "Please add a return type annotation to your factory function."

        self._register_type_factory(
            type_,
            factory,
            bases=bases,
            overwrite_bases=overwrite_bases,
            persistent=persistent,
        )

    def _get_factory_context(self, factory: Factory) -> Context:
        if factory.context:
            return factory.context
        else:
            return self._context.current

    def register(
        self, component: Any, *, bases: bool = True, overwrite_bases: bool = True
    ) -> None:
        """
        Register a new component with the injector.

        :param component: The component to register with the injector.
        :param bases: Besides registering the exact component type,
            also register for all of the component's base classes.
            Defaults to `True`.
        :param overwrite_bases: If any of the component's base classes
            are already registered with the injector, overwrite those
            registrations. Defaults to `True`.
        """

        factory = self._register_type_factory(
            type(component), None, bases=bases, overwrite_bases=overwrite_bases
        )

        with self._get_factory_context(factory) as context:
            context.components.update(
                {type_: component for type_ in factory.resolved_types}
            )

    def get_component(self, type_: Type[T]) -> T:
        """
        Get a component from the injector's current scope. Materialize
        it using a factory if necessary.

        Note that it is an error to use this function to get a
        component that has a factory that returns an `Awaitable`.

        :param type_: The type of the component to return.
        :return: The materialized component.
        """

        components = self._context.components
        try:
            return components[type_]
        except KeyError:
            pass

        factory = self._context.factories[type_]
        assert factory.factory is not None

        with self._get_factory_context(factory) as context:
            component = factory.factory()

            assert not inspect.isawaitable(
                component
            ), "Using an awaitable factory in synchronous code."

            context.components.update(
                {type_: component for type_ in factory.resolved_types}
            )

        return cast(T, component)

    async def get_component_async(self, type_: Type[T]) -> T:
        """
        Get a component from the injector's current scope. Materialize
        it using a factory if necessary.

        Use this method if the component's factory function returns an
        `Awaitable`.

        :param type_: The type of the component to return.
        :return: The materialized component.
        """

        components = self._context.components
        try:
            return components[type_]
        except KeyError:
            pass

        factory = self._context.factories[type_]
        assert factory.factory is not None

        with self._get_factory_context(factory) as context:
            component_or_awaitable = factory.factory()

            if inspect.isawaitable(component_or_awaitable):
                component = await cast(Awaitable[T], component_or_awaitable)
            else:
                component = cast(T, component_or_awaitable)

            context.components.update(
                {type_: component for type_ in factory.resolved_types}
            )

        return component

    def scope(self) -> Context:
        """
        Return a context manager that you can use to enter a new scpoe.
        When leaving the scope, any components or factories added to
        the injector will be forgotten.

        :return: The scope context object. You can use this to re-enter
           this scope at a later time if needed.
        """

        return Context(self._context)

    def inject(self, f: Callable[..., T]) -> Callable[..., T]:
        """
        This decorator will connect the injector to a function or
        method. When the resulting function is called, the provided
        arguments will be checked against the function's signature and
        any missing arguments the injector has a component or factory
        those arguments will be filled in.

        :param f: The function or method to inject components into.
        :return: The decorated function.
        """

        sig = inspect.signature(f)

        def bind_arguments(
            args: Iterable[Any], kwargs: Dict[str, Any]
        ) -> Tuple[inspect.BoundArguments, Dict[str, Any]]:
            factories = self._context.factories
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
