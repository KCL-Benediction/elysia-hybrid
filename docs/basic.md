# Basic Example

## Setup

Let's assume we have access to the following Weaviate collections:

- `ecommerce`: a fashion dataset with fields such as `price`, `category`, `description`, etc.

- `ml_wikipedia`: a collection of long Wikipedia articles related to machine learning, with fields such as `categories`, `content`, `title` etc.

- `example_verba_github_issues`: Github issues data for the repository [Verba](https://github.com/weaviate/Verba), with fields such as `issue_author`, `issue_content`, `issue_updated_at` etc.

These Weaviate collections are those which we want to search over using Elysia.

You need to specify what models you want to use, as well as any API keys. To set up the models, you can use `configure`. For example, if you want to use the GPT-4o family of models:

### LM Setup

```python
from elysia import configure
configure(
    base_model="gpt-4o-mini",
    base_provider="openai",
    complex_model="gpt-4o",
    complex_provider="openai",
)
```
You need to specify both a `base_model` and a `complex_model`, as well as their providers. This hooks into LiteLLM through DSPy, [so any LiteLLM supported models and providers will work](https://docs.litellm.ai/docs/providers).

### API Key Setup

To configure your API keys, you can either specify in the `.env` of your root directory, or pass these values into the `configure`. To add API keys into your environment, they need to follow the basic guidelines of how the API keys should be for LiteLLM. In this example, an OpenAI API key is required, which should be called `OPENAI_API_KEY`, seen in the [corresponding LiteLLM page](https://docs.litellm.ai/docs/providers/openai).

E.g. your `.env` file looks like:
```bash
OPENAI_API_KEY=sk-... # add your API key here
```

Or you can manually add this to the `configure`:
```python
configure(
    openai_api_key="sk-..." # add your API key here
)
```
The same API key format should be followed for any API keys required by your Weaviate cluster, for example, for the vectoriser you want to use.

If interfacing with your Weaviate collections, then you need to also have your Weaviate cluster URL and API key inside of your environment, respectively named `WCD_URL` and `WCD_API_KEY`, i.e.
```bash
WCD_URL=... # replace with your cluster URL
WCD_API_KEY=... # replace with your API key
```
or in the same way, pass these into the `configure` function
```python
configure(
    wcd_url="..." # add your cluster URL
    wcd_api_key_="..." # add your API key here
)
```


**TIP:** To use [OpenRouter](https://openrouter.ai/) instead of the generic provider, set the provider to e.g. `openrouter/openai`.


## Processing the Collections

To use collections with Elysia, you first need to *preprocess* the collections, which gets an LLM summary, field statistics and field mappings of your collections. This is necessary so that the query agent can understand the schema of your collection to create custom filters and more.

So for this example, we want to preproces
```python
from elysia import preprocess
preprocess(
    collection_names = ["ecommerce", "ml_wikipedia", "example_verba_github_issues"],
    verbose=True
)
```
 
## Running Elysia

To run the Elysia decision tree, using the default setup, just call the `Tree` object!

```python
from elysia import Tree
tree = Tree()
response, objects = tree("what were the 10 most recent Github issues?")
```

The Elysia decision tree will return the text response from the models, as well as any retrieved objects (anything that was added to the environment during this call).

```python
print(response)
```
```
I will now query the GitHub issues collection to retrieve the 10 most recent issues for you. I applied a descending sort on the "issue_created_at" field to retrieve the 10 most recent issues. I will now summarize the 10 most recent GitHub issues for you. The latest GitHub issues reflect ongoing discussions and developments within the Verba project. Notable entries include a closed issue regarding the use of specific model inputs, a report on a breaking change affecting the code chunker functionality, and requests for enhancements like custom JSON support and improved metadata handling during file uploads. The issues also highlight user concerns about application performance when processing large document uploads and the integration of external language models. Overall, these issues illustrate a dynamic environment with active contributions and feedback from the community.
```
```python
print(objects)
```
```
[[{'issue_id': 2843638219.0,
    'issue_content': "If you set OLLAMA_MODEL and OLLAMA_EMBED_MODEL they will be the ones suggested instead of the first on Ollama's list.",
    'issue_created_at': '2025-02-10T21:06:00Z',
    'issue_labels': [],
    'issue_url': 'https://github.com/weaviate/Verba/pull/372',
    'issue_comments': 0.0,
    'issue_title': 'use OLLAMA_MODEL OLLAMA_EMBED_MODEL as input suggestion when using Ollama',
    'issue_author': 'dudanogueira',
    'issue_updated_at': '2025-02-27T10:38:02Z',
    'issue_state': 'closed',
    'uuid': 'bc56b4b2fc6a541c94969721bd895a7c',
    'ELYSIA_SUMMARY': ''},
   {'issue_id': 2833900985.0,
    'issue_content': '## Description\nNo specifiy error message,  the imports just fail with "failed to import" nothing more.\n## Installation\n- [ ] pip install goldenverba\n- [ ] pip install from source\n- [X] Docker installation\nIf you installed via pip, please specify the version:\n## Weaviate Deployment\n- [ ] Local Deployment\n- [X] Docker Deployment\n- [ ] Cloud Deployment\n## Configuration\nReader: -\nChunker: Code\nEmbedder:\nRetriever:\nGenerator:\n## Steps to Reproduce\nSetup verba freshly with ollama and the to this time current master state and build it.\nFor proof that it works withouth the comit, freshly setup the clone repo with detached head to 5badcfb73b0b0f3afe8a19940874956ef75ec99d , so one commit before the mentioned problematic commit.\nimport now any python code (I assume other codes are broken aswell, as the change from python to c did not change anything) and observe the generic and prolematic failure message of importing the file.\nollama console also outputs "chunking" and after that "failed" and nothing else, so the last stept to attempt before failing is the chunker.\n## Additional context\nrevert the commit and observe he code chunker to work again.\nI have not looked into made commit for problematic code, but found the problem by having the repo pulled before the code earlier with working conditions, and later resetup the hole withouth changing anything to my docker-compose file which then bricks the code chunker.',
    'issue_url': 'https://github.com/weaviate/Verba/issues/371',
    'issue_comments': 0.0,
    'issue_labels': [],
    'issue_created_at': '2025-02-05T20:29:08Z',
    'issue_title': 'last commit bbe2b3937bef45c3b151702b77fdf4a3d2a452c5 breaks "code" chunker functionality',
    'issue_author': 'BloodyHellcat',
    'issue_updated_at': '2025-02-10T09:02:38Z',
    'issue_state': 'closed',
    'uuid': '2042751445e95f8eb65eb4e860b9e102',
    'ELYSIA_SUMMARY': ''},
...
    'issue_author': 'thomashacker',
    'issue_updated_at': '2025-01-15T11:06:08Z',
    'issue_state': 'closed',
    'uuid': '05dae4214e9050a59d4e9985892cdc10',
    'ELYSIA_SUMMARY': ''}]])
```