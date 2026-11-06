# Environment

The environment is a persistent object across all actions, tools and decisions performed within the Elysia decision tree. It can be used to store global information, such as retrieved objects or information that needs to be seen across all tools and actions.

## Overview

The 'Environment' variable contains all objects returned from any tools called by the Elysia decision tree. In essence, it is a dictionary which is keyed by two variables:

- `tool_name` (str): the name of the tool used to add this field to the environment
- `name` (str): a subkey of `tool_name`, a unique `name` associated to the returns from that tool. E.g. a collection name from a retrieval.

And when these items are accessed, it is a *list of dictionaries*, where each dictionary contains two subfields:

- `objects` (list[dict])
- `metadata` (dict)

where each item in `objects` is a list of objects retrieved during the call of that tool. Each set of objects has its own corresponding metadata. 

For example, if Elysia calls the 'Query' tool, then the `tool_name` is `"query"` and the `name` is the name of the collection queried. Each list of objects has metadata associated with the query used to retrieve the data. So each list of objects has unique metadata.


## Interacting with the Environment

For a full breakdown of all the methods, [see the Environment reference page](../Reference/Objects.md#elysia.tree.objects.Environment).

### Automatic Assignment

When yielding a `Result` object from a Tool, the result's `to_json()` method will return a list of dictionaries which automatically gets created or appended to the objects field in `environment[tool_name][name]`. The metadata are added at the same point.

This calls the `.add()` method on the environment using the `Result` object.

### `.add()` and `.add_objects()`

When calling a tool, you can specifically add a `Result` object to the environment via 
```python
environment.add(Result, tool_name)
```
The corresponding `to_json()` method in the `Result` is used to obtain the objects which get added.

You can also have more control over which objects get added specifically by using
```python
environment.add_objects(objects, metadata, tool_name, name)
```
where `objects` is a list of dictionaries, `metadata` is a dictionary and `tool_name` and `name` are string identifiers.

### `.replace()`

Change an item in the environment with another item 
```python
environment.replace(tool_name, name, objects, metadata, index)
```
either replace the entire list of items (objects + metadatas) or a single item at a particular index. `index` will only replace a particular item at that location, or if `None` (default) will replace the entire list.

### `.find()`

You can use
```python
environment.find(tool_name, name, index)
```
Which is an easy way to retrieve objects from the environment associated with the `tool_name` and `name` string identifiers.
`index` is a parameter which finds the corresponding location of an item for these identifiers. Defaults to `None`, in which case it returns a list of all items.

This is essentially just an alias to `environment.environment[tool_name][name][index]`.

### `.remove()`

Items (objects + metadata) in the environment can be removed via
```python
environment.remove(tool_name, name, index)
```
which uses the `tool_name` and `name` string identifiers to find the corresponding item.
The `index` parameter will remove the objects and metadata associated only with that position in the list. E.g., if `index=-1`, then the most recent entry in the list will be deleted. This defaults to `None`, in which case the entire set of objects for `tool_name` and `name` are removed. You can, of course, check the length of items beforehand via `len(environment.find(tool_name, name))` and use that to define the index. Will raise an `IndexError` if that index does not exist.

## The Hidden Environment

Within the environment there is also a dictionary, `environment.hidden_environment`, designed to be used as a store of data that is not shown to the LLM.
You can save any type of object within this dictionary as it does not need to be converted to string to converted to LLM formatting.

For example, this could be used to save raw retrieval objects that are not converted to their simple object properties, so you can still access the metadata output from the retrieval method that you otherwise wouldn't save inside the object metadata.

## Some Quick Usecases

- You may want to create a tool that only runs when the environment is non empty, so the `run_if_true` method of the tool [(see here for details)](creating_your_own_tools.md#run_if_true) returns `not tree_data.environment.is_empty()`.
- Your tool may not want to return any objects to the frontend, so instead of returning specific `Result` objects, you could modify the environment via `.add_objects()`, `.replace()` and `.remove()`. This stores 'private' variables that are not seen by the user unless they can manually inspect the environment.