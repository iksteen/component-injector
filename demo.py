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


# Create an injector registry for our project.
injector = Injector()


# If something that resembles a gizmo is registered in the
# component injector, insert it into the arguments if it's
# not explicitly provided.
@injector.inject
def gizmo_consumer(prefix: str, *, g: GizmoInterface) -> None:
    print(f"{prefix} {g} says: {g.greeting()}")


# Add our genuine gizmo to the component injector's registry.
injector.register(OriginalGizmo())

# Call our gizmo consumer without any arguments. The injector will
# provide our original gizmo as the 'g' parameter.
gizmo_consumer("OG")

# Create a new local scope.
with injector.scope():
    # Since the alternative gizmo works well enough in this situation,
    # register it with the injector.
    injector.register(AlternativeGizmo())

    # This time the, the injector will inject our alternative gizmo.
    gizmo_consumer("AG")

# When exiting the previous scope, the injector will now provide us with
# the original gizmo again.
gizmo_consumer("OG")
