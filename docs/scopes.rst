Scopes
======

A scope can be used to provide components (or factories) that are only
valid in a certain context. f.e. If you use the injector with a web
framework, you can add request-specific components to the injector in
a separate scope as to not pollute the global scope.

Note that scopes are based on python's `contextvars`. This means they
are thread safe when using the backported package for python 3.6. On
python 3.7 and newer, they are also safe to use with `asyncio` tasks
as well.

Basic usage
-----------

Basic example::

   from component_injector import Injector

   # The configuration is a global component and will be added and
   # available from the root scope.
   class Config:
      loglevel = "DEBUG"

   # This class describes the current request and is request-specific.
   class Request:
      def __init__(self, method, path):
         self.method = method
         self.path = path

   injector = Injector()

   @injector.inject
   def handle_request(config: Config, request: Request):
      if config.loglevel == "DEBUG":
         print(request.method, request.path)

   # Register our global configuration component.
   injector.register(Config())

   # When receiving a request, set up a new scope:
   with injector.scope():
      injector.register(Request("GET", "/index.html"))
      handle_request()

   # This will fail, after leaving the scope the request was removed
   # from the injector.
   handle_request()

Persistent factories
--------------------

By default, the components created by factories are added to the current
scope and removed when exiting the scope. It is however possible to
instruct the injector to store the component in the same scope as the
factory. You can do this by setting the `persistent` flag to `True`
when adding the factory::

   from component_injector import Injector

   class Component:
      pass

   injector = Injector()

   @injector.inject
   def consume(c: Component):
      return c

   injector.register_factory(Component)

   # Set up a new scope:
   with injector.scope():
      # Call the consumer, triggering the factory.
      c1 = consume()
      # Ensure the same component is injected again.
      assert c1 is consume()

   # After exiting the scope, the component will be cleaned up. Calling
   # the consumer again will trigger the factory once more.
   with injector.scope():
      assert c1 is not consume()

   # Now, let's re-add the factory but this time make it persistent.
   injector.register_factory(Component, persistent=True)

   # Set up a new scope and call the consumer. This will create the
   # component and insert it into the root scope as that is where the
   # factory is located.
   with injector.scope():
      c1 = consume()

   # Even after leavig the scope the component was created in, the
   # component persists because the factory is part of the root scope.
   assert c1 is consume()

Re-entering scopes
------------------

If needed, you can re-enter a specific scope as well::

   from component_injector import Injector

   class Component:
      def __init__(self, msg):
         self.msg = msg

   injector = Injector()

   @injector.inject
   def consumer(c: Component):
      return c.msg

   with injector.scope() as ctx:
      injector.register(Component("Initial scope"))

      assert consumer() == "Initial scope"

      with injector.scope():
         injector.register(Component("Secondary scope"))

         assert consumer() == "Secondary scope"

         # Re-enter initial scope
         with ctx:
             assert consumer() == "Initial scope"

         # We're now back in the secondary scope.
         assert consumer() == "Secondary scope"


