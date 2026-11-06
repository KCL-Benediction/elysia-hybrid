
# Setting up Elysia

Elysia _requires_ setting up your LMs and API keys for the decision tree functionality to work. Additionally, to use Elysia to its full potential (adaptively searching and retrieving Weaviate data), it requires a _preprocessing_ step.

## Model Setup

### Global Model Setup

Elysia will automatically recognise what API keys are in the `.env` file ([more on this later](#environment-setup)). To configure different LMs as default for all functions within Elysia, you can use the global [`configure` function](Reference/Settings.md#elysia.config.configure). For example, to use the GPT family of models, you can set:

```python
from elysia import configure

configure(
    base_model="gpt-4.1-mini",
    base_provider="openai",
    complex_model="gpt-4.1",
    complex_provider="openai",
    openai_api_key="..." # replace with your API key
)
```
The `configure` function requires setting a _base model_ (for simpler tasks/tasks that want to be quicker, such as the decision agent) and a _complex model_ which is used for more difficult tasks (such as some tools). Both require separately setting a provider; in this case `openai`.

Elysia uses DSPy under the hood, which uses [LiteLLM](https://www.litellm.ai/), to interact with LMs. For the full list of providers and models, see the [LiteLLM docs](https://docs.litellm.ai/docs/providers).

Each provider will require its own API key. We recommend to use [OpenRouter](https://openrouter.ai/) to get access to a plethora of models. In this case, you can set the _providers_ to e.g. `openrouter/openai`. The recommended models for Elysia are Google's Gemini family of models, accessible through [Google AI Studio](https://aistudio.google.com/) or OpenRouter.

To revert back to the original defaults, you can run:
```python
from elysia import smart_setup
smart_setup()
```

### Local Model Setup

Additionally, you can create your own `Settings` object which can be passed to any of the Elysia functions that use LMs to have a separate settings instance for each initialisation.

```python
from elysia import Settings
my_settings = Settings()
```

Which you can then configure manually, either by `my_settings.configure(...)` (which takes exactly the same arguments as `configure`), or by using `my_settings.smart_setup()`, which uses recommended models based on the API keys and/or models set in the `.env` file, prioritising Gemini 2.0 Flash for the base and complex model.

[See the reference page for more details.](Reference/Settings.md#elysia.config.Settings)

### Environment Setup

You can set everything in advance via creating a `.env` file in the root directory of your working directory, including the models, providers, and api keys. For example:

```
BASE_MODEL=gpt-4.1-mini
BASE_PROVIDER=openai
COMPLEX_MODEL=gpt-4.1
COMPLEX_PROVIDER=anthropic
OPENAI_API_KEY=... # replace with your OpenAI API key
```

Then, the global `settings` object will always use these values, and the `smart_setup()` or `my_settings.smart_setup()` (local settings object) will use these models and providers instead of the recommended ones.

## Weaviate Integration

To use Elysia with Weaviate, you need to specify your Weaviate cluster details. These can be set via the Weaviate Cluster URL (`WCD_URL`) and the Weaviate Cluster API Key (`WCD_API_KEY`). To set these values, you can use `configure` on the settings:
```python
from elysia import configure
configure(
    wcd_url=..., # replace with your WCD_URL
    wcd_api_key=... # replace with your WCD_API_KEY
)
```
or by setting them as environment variables
```
WCD_URL=... # replace with your WCD_URL
WCD_API_KEY=... # replace with your WCD_API_KEY
```

Additionally, you need to _preprocess_ your collections for Elysia to use the built in Weaviate-based tools, see below for details.

*Note: using a local Weaviate instance is currently not supported. This is coming soon! [You can sign up for a 14-day sandbox for free.](https://weaviate.io/deployment/serverless)

## Preprocessing Collections

[The `preprocess` function](Reference/Preprocessor.md) must be used on the Weaviate collections you plan to use within Elysia. 

```python
from elysia import preprocess
preprocess("<your_collection_name>")
```

Preprocessing does several things:

- Creates an LLM generated summary of the collection, including descriptions of the fields in the dataset.
- Creates 'mappings', so that fields in the collection can be mapped to frontend-specific fields. This enables the Elysia frontend app to display items from the collection when retrieved in the app.
- Calculates summary statistics, such as the mean, maximum and minimum values of number fields, as well as statistics for other fields.
- Collects other metadata such as any named vectors, what index types are used, if the inverted index is configured to index e.g. creation time.

Since preprocessing uses LLM created summaries of the collections, you must configure your models in advance. [See above for details](#model-setup).

### Running the Preprocessing Function

You have access to two functions, `preprocess_async`, which must be awaited, and `preprocess`, which is a sync wrapper for its async sister. The basic arguments for either function are:

- **`collection_names`** (*list[str])*: The names of the collections to preprocess.
- **`client_manager`** *(ClientManager)*: The client manager to use.
    The ClientManager class is how Elysia interacts with Weaviate client.
    If you are unsure of this, do not provide this argument, it will default to the Weaviate cluster you selected via the `Settings`, or via `configure`/environment variables.

As well, the LLM requires a number of objects retrieved from the collection, at random, to help provide its summary. Since objects in collections vary greatly in token size (and hence LLM compute time/cost), you can adjust the following parameters to change how many objects are used for this sample.

- **`min_sample_size`** *(int)*: The minimum number of objects in the sample.
- **`max_sample_size`** *(int)*: The maximum number of objects to sample.
- **`num_sample_tokens`** *(int)*: The maximum number of tokens in the sample objects used to evaluate the summary.

The `num_sample_tokens` parameter controls how many objects are actually used. Provided it is between `min_sample_size` and `max_sample_size`, the preprocessor will select the closest number of objects that are estimated to be in total `num_sample_tokens` tokens.

Additionally, you have:
- **`settings`** *(Settings)*: The settings to use.
- **`force`** *(bool)*: Whether to force the preprocessor to run even if the collection already exists.

### Additional Functions

You can also use [`preprocessed_collection_exists`](Reference/Preprocessor.md#elysia.preprocess.collection.preprocessed_collection_exists), which returns True/False if the collection has been preprocessed (and it can be accessed within the Weaviate cluster):

```python
from elysia import preprocessed_collection_exists
preprocessed_collection_exists(collection_name = ...)
```
which returns True/False if the preprocess exists within this Weaviate cluster

You can use [`edit_preprocessed_collection`](Reference/Preprocessor.md#elysia.preprocess.collection.edit_preprocessed_collection) to update the values manually:
```python
from elysia import edit_preprocessed_collection
properties = edit_preprocessed_collection(
    collection_name = ...,
    named_vectors = ...,
    summary = ...,
    mappings = ...,
    fields = ...
)
```
which will change the LLM generated values with manually input values. Any fields not provided will not be updated.

You can use [`delete_preprocessed_collection`](Reference/Preprocessor.md#elysia.preprocess.collection.delete_preprocessed_collection) which will delete the cached preprocessed metadata.

```python
delete_preprocessed_collection(collection_name = ...) 
```
which permanently deletes the preprocessed collection (not the original collection). You will need to rerun preprocess for the original collection to be used for the Weaviate integration in Elysia again.
