Factories
=========

If constructing your component is expensive and you only want to
instantiate it if it's really necessary you can add a factory function
to the injector which will only be called when the component is needed.

When registering a factory function, make sure the return type
annotation matches the type of the component you want to inject.

Demonstration::

   import time
   from component_injector import Injector

   injector = Injector()

   class CheapComponent:
      pass

   class ExpensiveComponent:
      pass

   def expensive_factory() -> ExpensiveComponent:
      time.sleep(1)
      return ExpensiveComponent()

   injector.register(CheapComponent())
   injector.register_factory(expensive_factory)

   @injector.inject
   def consumer_1(c1: CheapComponent):
      pass

   @injector.inject
   def consumer_2(c1: CheapComponent, c2: ExpensiveComponent):
      pass

   # This will not create the expensive components.
   consumer_1()

   # ExpensiveComponent will not be instantiated until needed.
   consumer_2()

   # Needing it again will use the same instance created before.
   consumer_2()

Asynchronous factories
----------------------

If you register a factory that returns an `Awaitable`, you can use it
to inject the resolved component into a coroutine::

   import asyncio
   from component_injector import Injector

   class Component:
      pass

   async def factory() -> Component:
      await asyncio.sleep(1)
      return Component()

   injector = Injector()
   injector.register_factory(factory)

   @injector.inject
   async def consumer(c: Component):
      pass

   loop = asyncio.get_event_loop()
   loop.run_until_complete(consumer())
