# Customising the Elysia Decision Tree

If you haven't followed [the basic guide](basic.md) yet, check that out first before you go into more detail here.

## Setup

Let's configure our LMs and import the necessary files to get started, assuming our collections are already [preprocessed to be used](preprocess.md).

```python
from elysia import configure

configure(
    base_model="gpt-4o-mini",
    base_provider="openai",
    complex_model="gpt-4o",
    complex_provider="openai",
)
```
This requires setting your `OPENAI_API_KEY` in the environment, or passing this as an argument to configure. And if you are interfacing with your Weaviate collections to search data, your Weaviate cluster API key and URL.


### Local Settings

Additionally, you can create your own `Settings` object which can be passed to either the Elysia `preprocess` function or `Tree` class, to have a separate settings instance for each initialisation.

```python
from elysia import Settings
my_settings = Settings()
```

Which you can then configure manually, either by `my_settings.configure(...)` (which takes exactly the same arguments as `configure`), or by choosing one of the default values:

- `my_settings.set_config_from_env()`: the default initialisation of the global settings, where everything that can be set from the environment is set. Otherwise initialised to `None`.
- `my_settings.default_models()`: the default Elysia config which uses Gemini 2.0 Flash for the base and complex model (unless these models are specified in the environment), and OpenRouter as the provider (unless also specified). This requires an OpenRouter API key.

The local `Settings` class is actually what the default `configure` argument modifies, but it modifies on a global `settings` object which defaults to `set_config_from_env` on initialisation of the Elysia python package. So you can call these same functions on 
```python
from elysia import settings
settings.set_config_from_env() # or similar
```
See the reference page for more details (**WIP not written yet**)

## Adding Tools

Coming soon, when there's more default tools available. For now, see the [tool construction overview](Customising/creating_your_own_tools.md).

## Changing the Style, Agent Description or End Goal

You can initialise these parameters at the startup of the tree, for example
```python
from elysia import Tree
tree = Tree(
    style = "...",
    agent_description = "...",
    end_goal = "..."
)
```
Each of these options is now described.

### Style

You can customise the style of Elysia's text responses by either initialising the decision tree with the `style` argument, 
or creating a tree and then modifying the style later.
```python
tree = Tree()
tree.change_style("Always speak in rhyming couplets.")
```

You should see the changes in Elysia's textual responses!
```python
response, _ = tree("Hi Elysia, how are you?")
print(response)
```
```
## Hello there, it's Elly, I'm doing fine, I hope you are as well, in this rhyme!
```


### Agent Description

The `agent_description` parameter in Elysia assigns the agent a unique identity, which you can use to customise the objective of the agent. 

Change this via `change_agent_description`, e.g.
```python
tree.change_agent_description("You are a travel agent, specialised in creating unique travel plans for customers that interact with you.")
```

### End Goal

The `end_goal` parameter describes to Elysia what criteria it will use to decide when the decision tree should end. Normally, this is something similar to 'When you have either achieved all the user has asked of you, or you can no longer do any actions that have not failed already, and you have no other options to explore.'. But this could be unique to your use case, for example,
```python
tree.change_end_goal("The user has been recommended a hotel, travel options as well as activities to do in the local area. Or, you have exhausted all options. Or, you have asked the user for more clarification about their request.")
```