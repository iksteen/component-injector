Components
==========

Adding components, which are instantiated classes, to the injector and
injecting them in your function arguments are the most basic
functionality the injector.

A small demonstration::

   from component_injector import Injector

   # Define a component to inject.
   class MyFirstComponent:
      def __init__(self):
         print("Initializing MyFirstComponent.")

   # Create an injector namespace.
   injector = Injector()

   # Instantiate the component and register it with the injector.
   component = MyFirstComponent()
   injector.register(component)

   # Define a function that uses the component and connect it to
   # the injector.
   @injector.inject
   def my_component_consumer(component: MyFirstComponent):
      print(component)

   # Calling the consumer without specifying the `component`
   # argument will trigger the injector to add it automatically.
   my_component_consumer()
