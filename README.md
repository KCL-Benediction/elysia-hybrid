
# Elysia Python Client + API

Welcome to Elysia, the agentic platform for searching and retrieving data in Weaviate. Elysia is also designed to handle any custom tools, and it will be automatically handled by a decision agent.

[View the docs](https://weaviate.github.io/elysia/)

## Installation (bash) (Linux/MacOS)

From your bash terminal, clone the repository via
```bash
git clone https://github.com/weaviate/elysia
```
move to the working directory
```bash
cd elysia
```
Create a virtual environment with Python (version 3.10 - 3.12, see installation instructions for [brew](https://formulae.brew.sh/formula/python@3.12) or [ubuntu](https://ubuntuhandbook.org/index.php/2023/05/install-python-3-12-ubuntu/)).
```bash
python3.12 -m venv .venv
source .venv/bin/activate
```
and then install Elysia via pip
```bash
pip install -e .
```
Done! You can now use the Elysia python package

### Running the Backend
Just simply run
```bash
elysia start
```
and the backend will start on [localhost:3000](localhost:3000) by default.

### Frontend Installation

From the directory you just cloned, (i.e. inside `elysia/`). You need to clone the [frontend repository](https://github.com/weaviate/elysia-frontend) (give it a star!) via
```bash
git clone https://github.com/weaviate/elysia-frontend
```
navigate inside the frontend repository via
```bash
cd elysia-frontend
```
and install and run the node server via
```bash
npm install
npm run dev
```
By default this will run the app on [localhost:8000](localhost:8000). Visit this to use the app!

### Configuring the Environment

To use Elysia with Weaviate, i.e. for agentic searching and retrieval, you need a Weaviate cluster api key and URL
```
WCD_URL=...
WCD_API_KEY=...
```
Elysia will automatically detect these when running locally, and this will be the default Weaviate cluster for all users logging into the Elysia app. But these can be configured on a user-by-user basis.

Whichever vectoriser you use for your Weaviate collection you will need to specify your corresponding API key, e.g.
```
OPENAI_API_KEY=...
```
These will automatically be added to the headers for the Weaviate client.

Same for whichever model you choose for the LLM in Elysia, so if you are using GPT-4o, for example, specify an `OPENAI_API_KEY`.

The 'default' config for Elysia is to use [OpenRouter](https://openrouter.ai/) to give easy access to a variety of models. So this requires
```
OPENROUTER_API_KEY=...
```
and OpenAI as the vectorisers for the alpha datasets, so you need `OPENAI_API_KEY` too.

## Basic Usage

For a comprehensive overview of how to get started with Elysia, [view the documentation here](https://weaviate.github.io/elysia/basic_example/).

The simplest way to use Elysia would be to configure your API keys via the environment variables above, and then run, for example
```python
from elysia import settings, Tree
settings.default_models()

tree = Tree()
tree(
    "how many t-shirts are in my shopping dataset?"
)
```

The `settings.default_models()` gives the recommended configuration for Elysia - using Gemini 2.0 Flash for both the base model and the complex model, both via OpenRouter.