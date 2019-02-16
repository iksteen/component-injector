import asyncio
from abc import ABC, abstractmethod

from component_injector import Injector


class GizmoInterface(ABC):
    """
    Abstract interface describing how gizmos are supposed to work.
    """

    @abstractmethod
    def greeting(self) -> str:
        """
        Calling this will make the gizmo return a greeting."
        """


class OriginalGizmo(GizmoInterface):
    """
    This is the genuine article.
    """

    def greeting(self) -> str:
        """
        Note: This greeting is one of our trademarks.
        """
        return "Hello, world!"


class AlternativeGizmo(GizmoInterface):
    """
    Cheaper knock-off gizmo.
    """

    def greeting(self) -> str:
        """
        Can't use OG's greeting, it's trademarked.
        """
        return "Hello everyone!"


def alternative_gizmo_factory() -> AlternativeGizmo:
    print("Creating alternative gizmo")
    return AlternativeGizmo()


# Create an injector registry for our project.
injector = Injector()


# If something that resembles a gizmo is registered in the
# component injector, insert it into the arguments if it's
# not explicitly provided.
@injector.inject
def gizmo_consumer(prefix: str, *, g: GizmoInterface) -> None:
    print(f"{prefix} {g} says: {g.greeting()}")


async def gizmo_loop(prefix: str) -> None:
    """
    This asynchronous function will call gizmo_consumer in a loop.
    """
    for i in range(5):
        gizmo_consumer(prefix)
        await asyncio.sleep(1)


async def alternative_gizmo_loop(prefix: str) -> None:
    """
    This will set up a new injector scope, register our knock-off
    gizmo component factory and calls the gizmo loop function defined
    above.
    """
    with injector.scope():
        injector.register_factory(alternative_gizmo_factory)
        await gizmo_loop(prefix)


# Add our genuine gizmo to the component injector's registry.
injector.register(OriginalGizmo())

# Get our event loop.
loop = asyncio.get_event_loop()

loop.run_until_complete(
    asyncio.gather(
        # This task will run in the current scope and should only
        # inject the original gizmo..
        loop.create_task(gizmo_loop("OG")),
        # This task will run concurrently, but differently scoped
        # and should inject our alternative gizmo.
        loop.create_task(alternative_gizmo_loop("AG")),
    )
)
