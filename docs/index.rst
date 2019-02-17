component-injector
==================

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

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   components
   factories
   scopes

.. toctree::
   :maxdepth: 2
   :caption: Modules:

   component_injector

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
