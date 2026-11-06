import ast
import asyncio
import inspect
import json
import time
from copy import deepcopy
from typing import Any, Dict, List, Literal

from pympler import asizeof
from rich import print
from rich.console import Console
from rich.panel import Panel

from logging import Logger

import uuid

# Weaviate
from elysia.config import Settings
from elysia.config import settings as environment_settings

# globals
from elysia.tree.util import (
    BranchVisitor,
    DecisionNode,
    TreeReturner,
    Decision,
    get_follow_up_suggestions,
)
from elysia.objects import (
    Completed,
    Result,
    Return,
    Text,
    Tool,
    Warning,
)
from elysia.tools.retrieval.aggregate import Aggregate
from elysia.tools.retrieval.query import Query
from elysia.tools.text.text import FakeTextResponse, Summarizer, TextResponse
from elysia.util.async_util import asyncio_run

# Objects
from elysia.tree.objects import CollectionData, TreeData, Atlas

# Decision Prompt executors
from elysia.util.client import ClientManager
from elysia.config import (
    check_base_lm_settings,
    check_complex_lm_settings,
    load_base_lm,
    load_complex_lm,
)
from elysia.util.objects import Timer, TrainingUpdate, TreeUpdate

# Util
from elysia.util.parsing import remove_whitespace
from elysia.util.collection import retrieve_all_collection_names


class Tree:
    """
    The main class for the Elysia decision tree.
    Calling this method will execute the decision tree based on the user's prompt, and available collections and tools.

    Args:
        branch_initialisation (str): The initialisation method for the branches,
            currently supports some pre-defined initialisations: "multi_branch", "one_branch".
            Set to "empty" to start with no branches and to add them, and the tools, yourself.
        style (str): The writing style of the agent. Automatically set for "multi_branch" and "one_branch" initialisation, but overrided if non-empty.
        agent_description (str): The description of the agent. Automatically set for "multi_branch" and "one_branch" initialisation, but overrided if non-empty.
        end_goal (str): The end goal of the agent. Automatically set for "multi_branch" and "one_branch" initialisation, but overrided if non-empty.
        user_id (str): The id of the user, e.g. "123-456",
            unneeded outside of user management/hosting Elysia app
        conversation_id (str): The id of the conversation, e.g. "123-456",
            unneeded outside of conversation management/hosting Elysia app
        debug (bool): Whether to run the tree in debug mode.
            If True, the tree will save the (dspy) models within the tree.
            Set to False for saving memory.
        settings (Settings): The settings for the tree, an object of elysia.Settings.
            This is automatically set to the environment settings if not provided.
    """

    def __init__(
        self,
        branch_initialisation: Literal[
            "default", "one_branch", "multi_branch", "empty"
        ] = "default",
        style: str = "No style provided.",
        agent_description: str = "No description provided.",
        end_goal: str = "No end goal provided.",
        user_id: str | None = None,
        conversation_id: str | None = None,
        low_memory: bool = False,
        settings: Settings = environment_settings,
    ):
        # Define base variables of the tree
        if user_id is None:
            self.user_id = str(uuid.uuid4())
        else:
            self.user_id = user_id

        if conversation_id is None:
            self.conversation_id = str(uuid.uuid4())
        else:
            self.conversation_id = conversation_id

        assert isinstance(
            settings, Settings
        ), "settings must be an instance of Settings"
        self.settings = settings

        # keep track of the number of trees completed
        self.num_trees_completed = 0

        # Initialise some tree variables
        self.decision_nodes: dict[str, DecisionNode] = {}
        self.decision_history = []
        self.tree_index = -1
        self.suggestions = []
        self.actions_called = {}
        self.query_id_to_prompt = {}
        self.prompt_to_query_id = {}
        self.retrieved_objects = []
        self.store_retrieved_objects = False

        # -- Initialise the tree
        self.set_low_memory(low_memory)

        # Define the inputs to prompts
        self.tree_data = TreeData(
            collection_data=CollectionData(
                collection_names=[], logger=self.settings.logger
            ),
            atlas=Atlas(
                style=style,
                agent_description=agent_description,
                end_goal=end_goal,
            ),
            recursion_limit=5,
        )

        # initialise the timers
        self.timer = Timer(
            timer_names=["base_lm", "complex_lm"],
            logger=self.settings.logger,
        )

        # Set the initialisations
        self.tools = {}
        self.set_branch_initialisation(branch_initialisation)
        self.change_style(style)
        self.change_agent_description(agent_description)
        self.change_end_goal(end_goal)

        self.tools["final_text_response"] = TextResponse()

        # some variables for storing feedback
        self.action_information = []
        self.history = {}
        self.training_updates = []

        # -- Get the root node and construct the tree
        self._get_root()
        self.tree = {}
        self._construct_tree(self.root, self.tree)

        # initialise the returner (for frontend)
        self.returner = TreeReturner(
            user_id=self.user_id,
            conversation_id=self.conversation_id,
        )

        # Print the tree if required
        self.settings.logger.info("Initialised tree with the following decision nodes:")
        for decision_node in self.decision_nodes.values():
            self.settings.logger.info(
                f"  - [magenta]{decision_node.id}[/magenta]: {list(decision_node.options.keys())}"
            )

    def get_tree_lms(self):
        self.base_lm = self.get_lm("base", True) if not self.low_memory else None
        self.complex_lm = self.get_lm("complex", True) if not self.low_memory else None

    def multi_branch_init(self):
        self.add_branch(
            root=True,
            branch_id="base",
            instruction="""
            Choose a base-level task based on the user's prompt and available information.
            You can search, which includes aggregating or querying information - this should be used if the user needs (more) information.
            You can end the conversation by choosing text response, or summarise some retrieved information.
            Base your decision on what information is available and what the user is asking for - you can search multiple times if needed,
            but you should not search if you have already found all the information you need.
            """,
            status="Choosing a base-level task...",
        )
        self.add_tool(branch_id="base", tool=Summarizer)
        self.add_tool(branch_id="base", tool=FakeTextResponse)

        self.add_branch(
            root=False,
            branch_id="search",
            from_branch_id="base",
            instruction="""
            Choose between querying the knowledge base via semantic/keyword search, or aggregating information by performing operations, on the knowledge base.
            Querying is when the user is looking for specific information related to the content of the dataset, requiring a specific search query. This is for retrieving specific information via a _query_, similar to a search engine.
            Aggregating is when the user is looking for a specific operations on the dataset, such as summary statistics of the quantity of some items. Aggregation can also include grouping information by some property and returning statistics about the groups.
            """,
            description=f"""
            Search the knowledge base. This should be used when the user is lacking information for this particular prompt. This retrieves information only and provides no output to the user except the information.
            Choose to query (semantic or keyword search on a knowledge base), or aggregate information (calculate properties/summary statistics/averages and operations on the knowledge bases).
            """,
            status="Searching the knowledge base...",
        )
        self.add_tool(branch_id="search", tool=Query)
        self.add_tool(branch_id="search", tool=Aggregate)

    def one_branch_init(self):
        self.add_branch(
            root=True,
            branch_id="base",
            instruction="""
            Choose a base-level task based on the user's prompt and available information.
            Decide based on the tools you have available as well as their descriptions.
            Read them thoroughly and match the actions to the user prompt.
            """,
            status="Choosing a base-level task...",
        )
        self.add_tool(branch_id="base", tool=Summarizer)
        self.add_tool(branch_id="base", tool=FakeTextResponse)
        self.add_tool(branch_id="base", tool=Query)
        self.add_tool(branch_id="base", tool=Aggregate)

    def empty_init(self):
        self.add_branch(
            root=True,
            branch_id="base",
            instruction="""
            Choose a base-level task based on the user's prompt and available information.
            Decide based on the tools you have available as well as their descriptions.
            Read them thoroughly and match the actions to the user prompt.
            """,
            status="Choosing a base-level task...",
        )

    def clear_tree(self):
        self.decision_nodes = {}

    def set_branch_initialisation(self, initialisation: str | None):
        self.clear_tree()

        if (
            initialisation is None
            or initialisation == ""
            or initialisation == "one_branch"
            or initialisation == "default"
        ):
            self.one_branch_init()
        elif initialisation == "multi_branch":
            self.multi_branch_init()
        elif initialisation == "empty":
            self.empty_init()
        else:
            raise ValueError(f"Invalid branch initialisation: {initialisation}")

        self.branch_initialisation = initialisation

    def set_low_memory(self, low_memory: bool):
        self.low_memory = low_memory
        self.base_lm = self.get_lm("base", True) if not low_memory else None
        self.complex_lm = self.get_lm("complex", True) if not low_memory else None

    def default_models(self):
        self.settings = deepcopy(self.settings)
        self.settings.default_models()

    def configure(self, **kwargs):
        """
        Configure the tree with new settings.
        Wrapper for the settings.configure() method.
        Will not affect any settings preceding this (e.g. in TreeManager).
        """
        self.settings = deepcopy(self.settings)
        self.settings.configure(**kwargs)

    def change_style(self, style: str):
        self.tree_data.atlas.style = style

    def change_agent_description(self, agent_description: str):
        self.tree_data.atlas.agent_description = agent_description

    def change_end_goal(self, end_goal: str):
        self.tree_data.atlas.end_goal = end_goal

    def get_lm(self, model_type: str, force_load: bool = False):
        """
        Return the LMs used by the tree.
        If low_memory is True, the LMs will be loaded in this method.
        Otherwise, the LMs are already loaded in the tree.
        If force_load is True, the LMs will be loaded regardless of the low_memory setting.

        Args:
            model_type (str): The type of model to load.
                Can be "base" or "complex".
            force_load (bool): Whether to force the loading of the LMs.
                Defaults to False.

        Returns:
            (dspy.LM): The LM object.
        """
        if not self.low_memory and not force_load:
            return self.base_lm if model_type == "base" else self.complex_lm
        else:
            return (
                load_base_lm(self.settings)
                if model_type == "base"
                else load_complex_lm(self.settings)
            )

    def _get_root(self):
        for decision_node in self.decision_nodes.values():
            if decision_node.root:
                if "root" in dir(self) and self.root != decision_node.id:
                    raise ValueError("Multiple root decision nodes found")

                self.root = decision_node.id

        if "root" not in dir(self):
            raise ValueError("No root decision node found")

    def _get_function_branches(self, func: Any) -> List[Dict]:
        """Analyzes a function for Branch objects without executing it."""
        source = inspect.getsource(func)
        tree = ast.parse(source.strip())
        visitor = BranchVisitor()
        visitor.visit(tree)
        return visitor.branches

    def _construct_tree(self, node_id: str, tree: dict):
        decision_node = self.decision_nodes[node_id]

        # Define desired key order
        key_order = ["name", "id", "description", "instruction", "reasoning", "options"]

        # Set the base node information
        tree["name"] = node_id.capitalize().replace("_", " ")
        tree["id"] = node_id
        if node_id == self.root:
            tree["description"] = ""
        tree["instruction"] = remove_whitespace(
            decision_node.instruction.replace("\n", "")
        )
        tree["reasoning"] = ""
        tree["options"] = {}

        # Order the top-level dictionary
        tree = {key: tree[key] for key in key_order if key in tree}

        # Initialize all options first with ordered dictionaries
        for option in decision_node.options:
            tree["options"][option] = {
                "description": remove_whitespace(
                    decision_node.options[option]["description"].replace("\n", "")
                )
            }

        # Then handle the recursive cases
        for option in decision_node.options:
            if decision_node.options[option]["action"] is not None:
                func = decision_node.options[option]["action"].__call__
                branches = self._get_function_branches(func)
                if branches:
                    tree["options"][option]["name"] = option.capitalize().replace(
                        "_", " "
                    )
                    tree["options"][option]["id"] = option
                    tree["options"][option]["instruction"] = ""
                    sub_tree = tree["options"][option]
                    for branch in branches:
                        branch_name = branch["name"].lower().replace(" ", "_")
                        if "options" not in sub_tree:
                            sub_tree["options"] = {}
                        sub_tree["options"][branch_name] = branch
                        sub_tree["options"][branch_name]["name"] = branch["name"]
                        sub_tree["options"][branch_name]["id"] = branch_name
                        sub_tree["options"][branch_name]["description"] = branch[
                            "description"
                        ]
                        sub_tree["options"][branch_name]["instruction"] = ""
                        sub_tree["options"][branch_name]["reasoning"] = ""
                        sub_tree = sub_tree["options"][branch_name]
                    sub_tree["options"] = {}

                else:
                    tree["options"][option]["name"] = option.capitalize().replace(
                        "_", " "
                    )
                    tree["options"][option]["id"] = option
                    tree["options"][option]["instruction"] = ""
                    tree["options"][option]["reasoning"] = ""
                    tree["options"][option]["options"] = {}

            elif decision_node.options[option]["next"] is not None:
                tree["options"][option] = self._construct_tree(
                    decision_node.options[option]["next"], tree["options"][option]
                )
            else:
                tree["options"][option]["name"] = option.capitalize().replace("_", " ")
                tree["options"][option]["id"] = option
                tree["options"][option]["instruction"] = ""
                tree["options"][option]["reasoning"] = ""
                tree["options"][option]["options"] = {}

            # Order each option's dictionary
            tree["options"][option] = {
                key: tree["options"][option][key]
                for key in key_order
                if key in tree["options"][option]
            }

        return tree

    async def set_collection_names(
        self,
        collection_names: list[str],
        client_manager: ClientManager,
    ):
        self.settings.logger.info(
            f"Using the following collection names: {collection_names}"
        )

        collection_names = await self.tree_data.set_collection_names(
            collection_names, client_manager
        )

    def _remove_empty_branches(self):
        empty_branches = []
        for branch_id, branch in self.decision_nodes.items():
            if len(branch.options) == 0:
                empty_branches.append(branch_id)

        for branch_id in self.decision_nodes:
            for empty_branch in empty_branches:
                self.decision_nodes[branch_id].remove_option(empty_branch)

        for empty_branch in empty_branches:
            self.settings.logger.warning(
                f"Removing empty branch: {empty_branch}",
                "No tools are attached to this branch, so it has been removed.",
                f"To add a tool to this branch, use .add_tool(tool_name, branch_id={empty_branch})",
            )
            del self.decision_nodes[empty_branch]

        return empty_branches

    def _get_function_inputs(self, tool_name: str, inputs: dict):
        if tool_name in self.tools:
            # any non-provided inputs are set to the default
            default_inputs = self.tools[tool_name].get_default_inputs()
            for default_input_name in default_inputs:
                if default_input_name not in inputs:
                    inputs[default_input_name] = default_inputs[default_input_name]

            # if the inputs match the 'schema' of keys: description, type, default, value, then take the value
            for input_name in inputs:
                if (
                    isinstance(inputs[input_name], dict)
                    and "value" in inputs[input_name]
                ):
                    inputs[input_name] = inputs[input_name]["value"]

            return inputs
        else:
            return {}

    async def _check_rules(self, branch_id: str, client_manager: ClientManager):
        base_lm = self.get_lm("base")
        complex_lm = self.get_lm("complex")

        branch = self.decision_nodes[branch_id]
        nodes_with_rules_met = []
        for function_name, option in branch.options.items():
            if "run_if_true" in dir(self.tools[function_name]):
                rule_met = await self.tools[function_name].run_if_true(
                    tree_data=self.tree_data,
                    client_manager=client_manager,
                    base_lm=base_lm,
                    complex_lm=complex_lm,
                )
                if rule_met:
                    nodes_with_rules_met.append(function_name)

        return nodes_with_rules_met

    def set_conversation_id(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.returner.conversation_id = conversation_id

    def set_user_id(self, user_id: str):
        self.user_id = user_id
        self.returner.user_id = user_id

    def soft_reset(self):
        # conversation history is not reset
        # environment is not reset
        self.recursion_counter = 0
        self.tree_data.num_trees_completed = 0
        self.decision_history = []
        self.num_trees_completed = 0
        self.training_updates = []
        self.tree_data.soft_reset()
        self.action_information = []
        self.tree_index += 1
        self.retrieved_objects = []
        self.returner.set_tree_index(self.tree_index)

    def save_history(self, query_id: str, time_taken_seconds: float):
        """
        What the tree did, results for saving feedback.
        """
        training_update = deepcopy(
            [update.to_json() for update in self.training_updates]
        )
        training_update = json.dumps(training_update)

        self.history[query_id] = {
            "num_trees_completed": self.num_trees_completed,
            "tree_data": deepcopy(self.tree_data),
            "action_information": deepcopy(self.action_information),
            "decision_history": deepcopy(self.decision_history),
            "base_lm_used": self.settings.BASE_MODEL,
            "complex_lm_used": self.settings.COMPLEX_MODEL,
            "time_taken_seconds": time_taken_seconds,
            "training_updates": training_update,
            "initialisation": f"{self.branch_initialisation}",
        }
        # can remove training updates now
        self.training_updates = []

    def set_start_time(self):
        self.start_time = time.time()

    def add_tool(self, tool: Tool, branch_id: str | None = None, **kwargs):
        """
        Add a Tool to a branch.
        The tool needs to be an instance of the Tool class.

        Args:
            branch_id (str): The id of the branch to add the tool to
                If not specified, the tool will be added to the root branch
            tool (Tool): The tool to add
            kwargs (any): Additional keyword arguments to pass to the initialisation of the tool
        """

        if (
            inspect.getfullargspec(tool.__init__).varkw is None
            or inspect.getfullargspec(tool.__call__).varkw is None
        ):
            raise TypeError("tool __init__ and __call__ must accept **kwargs")

        if not inspect.isasyncgenfunction(tool.__call__):
            raise TypeError(
                "__call__ must be an async generator function. "
                "I.e. it must yield objects."
            )

        tool_instance = tool(
            logger=self.settings.logger,
            **kwargs,
        )

        if not isinstance(tool_instance, Tool):
            raise TypeError("tool must be an instance of the Tool class")

        if "__call__" not in dir(tool_instance):
            raise TypeError("tool must be callable (have a __call__ method)")

        if "__init__" not in dir(tool_instance):
            raise TypeError("tool must have an __init__ method")

        if hasattr(tool_instance, "is_tool_available"):
            if not inspect.iscoroutinefunction(tool_instance.is_tool_available):
                raise TypeError(
                    "is_tool_available must be an async function that returns a single boolean value"
                )

        if hasattr(tool_instance, "run_if_true"):
            if not inspect.iscoroutinefunction(tool_instance.run_if_true):
                raise TypeError(
                    "run_if_true must be an async function that returns a single boolean value"
                )

        self.tools[tool_instance.name] = tool_instance

        if branch_id is None:
            branch_id = self.root

        if branch_id not in self.decision_nodes:
            raise ValueError(
                f"Branch {branch_id} not found. Use .add_branch() to add a branch before adding a tool."
            )

        self.decision_nodes[branch_id].add_option(
            id=tool_instance.name,
            description=tool_instance.description,
            inputs=tool_instance.inputs,
            action=self.tools[tool_instance.name],
            end=tool_instance.end,
            status=tool_instance.status,
        )
        self.timer.add_timer(tool_instance.name)

        # reconstruct tree
        self._get_root()
        self.tree = {}
        self._construct_tree(self.root, self.tree)

    def remove_tool(self, tool_name: str, branch_id: str | None = None):
        """
        Remove a Tool from a branch.

        Args:
            tool_name (str): The name of the tool to remove
            branch_id (str): The id of the branch to remove the tool from
                if not specified, the tool will be removed from the root branch
        """
        if branch_id is None:
            branch_id = self.root

        if branch_id not in self.decision_nodes:
            raise ValueError(f"Branch {branch_id} not found.")

        if tool_name not in self.decision_nodes[branch_id].options:
            raise ValueError(f"Tool {tool_name} not found in branch {branch_id}.")

        self.decision_nodes[branch_id].remove_option(tool_name)
        del self.tools[tool_name]
        self.timer.remove_timer(tool_name)

        # reconstruct tree
        self._get_root()
        self.tree = {}
        self._construct_tree(self.root, self.tree)

    def add_branch(
        self,
        branch_id: str,
        instruction: str,
        description: str = "",
        root: bool = False,
        from_branch_id: str = "",
        status: str = "",
    ):
        """
        Add a branch to the tree.

        args:
            branch_id (str): The id of the branch being added
            instruction (str): The general instruction for the branch, what is this branch containing?
                What kind of tools or actions are being decided on this branch?
            description (str): A description of the branch, if it is chosen from a previous branch
            root (bool): Whether this is the root branch, i.e. the beginning of the tree
            from_branch_id (str): The id of the branch that this branch is stemming from
            status (str): The status message to be displayed when this branch is chosen
        """
        if not root and description == "":
            raise ValueError("Description is required for non-root branches.")
        if not root and from_branch_id == "":
            raise ValueError(
                "`from_branch_id` is required for non-root branches. "
                "Set `root=True` to create a root branch or choose where this branch stems from."
            )
        if root and description != "":
            self.settings.logger.warning(f"Description is not used for root branches. ")
            description = ""

        if root and from_branch_id != "":
            self.settings.logger.warning(
                "`from_branch_id` is not used for root branches. "
                "(As this is the root branch, it does not stem from any other branch.)"
                "If you wish this to be stemming from a previous branch, set `root=False`."
            )
            from_branch_id = ""

        if status == "":
            status = f"Running {branch_id}"

        if not root:
            self.decision_nodes[from_branch_id].add_option(
                id=branch_id,
                description=description,
                inputs={},
                action=None,
                end=False,
                status=status,
                next=branch_id,
            )

        decision_node = DecisionNode(
            id=branch_id,
            instruction=instruction,
            options={},
            root=root,
            logger=self.settings.logger,
        )
        self.decision_nodes[branch_id] = decision_node

        # reconstruct tree
        self._get_root()
        self.tree = {}
        self._construct_tree(self.root, self.tree)

    def remove_branch(self, branch_id: str):
        """
        Remove a branch from the tree.

        Args:
            branch_id (str): The id of the branch to remove
        """
        # Validate branch exists
        if branch_id not in self.decision_nodes:
            self.settings.logger.warning(
                f"Branch {branch_id} not found, nothing to remove."
            )
            return

        # Special handling for root node
        if branch_id == self.root:
            self.settings.logger.error("Cannot remove root branch.")
            raise ValueError(
                "Cannot remove the root branch. Create a new tree instead."
            )

        for decision_node_id in self.decision_nodes:
            self.decision_nodes[decision_node_id].remove_option(branch_id)

        if branch_id in self.decision_nodes:
            del self.decision_nodes[branch_id]

        # reconstruct tree
        self._get_root()
        self.tree = {}
        self._construct_tree(self.root, self.tree)

    async def get_follow_up_suggestions(self):
        """
        Get follow-up suggestions for the current user prompt via a base model LLM call.

        E.g., if the user asks "What was the most recent Github Issue?",
            and the results show a message from 'Jane Doe',
            the follow-up suggestions might be "What other issues did Jane Doe work on?"

        Returns:
            list[str]: A list of follow-up suggestions
        """
        suggestions = await get_follow_up_suggestions(
            self.tree_data, self.suggestions, self.settings
        )
        self.suggestions.extend(suggestions)
        return suggestions

    def _update_conversation_history(self, role: str, message: str):
        if message != "":
            # If the first message, create a new message
            if len(self.tree_data.conversation_history) == 0:
                self.tree_data.update_list(
                    "conversation_history", {"role": role, "content": message}
                )
            # If the last message is from the same role, append to the content
            elif self.tree_data.conversation_history[-1]["role"] == role:
                if self.tree_data.conversation_history[-1]["content"].endswith(" "):
                    self.tree_data.conversation_history[-1]["content"] += message
                else:
                    self.tree_data.conversation_history[-1]["content"] += " " + message
            # Otherwise, create a new message
            else:
                self.tree_data.update_list(
                    "conversation_history", {"role": role, "content": message}
                )

    def _update_actions_called(self, result: Result, decision: Decision):
        if self.user_prompt not in self.actions_called:
            self.actions_called[self.user_prompt] = []
            self.actions_called[self.user_prompt].append(
                {
                    "name": decision.function_name,
                    "inputs": decision.function_inputs,
                    "reasoning": decision.reasoning,
                    "output": None,
                }
            )
        if not self.low_memory:
            self.actions_called[self.user_prompt][-1]["output"] = result.objects
        else:
            self.actions_called[self.user_prompt][-1]["output"] = []

    def _update_environment(self, result: Result, decision: Decision):
        """
        Given a yielded result from an action or otherwise, update the environment.
        I.e. the items within the LLM knowledge base/prompt for future decisions/actions
        All Result subclasses have their .to_json() method added to the environment.
        As well, all Result subclasses have their llm_parse() method added to the tasks_completed.
        """

        # add to environment (store of retrieved/called objects)
        self.tree_data.environment.add(result, decision.function_name)

        # make note of which objects were retrieved _this session_ (for returning)
        if self.store_retrieved_objects:
            self.retrieved_objects.append(result.to_json(mapping=False))

        # add to log of actions called
        self.action_information.append(
            {
                "action_name": decision.function_name,
                **{key: value for key, value in result.metadata.items()},
            }
        )

        # add to tasks completed (parsed info / train of thought for LLM)
        self.tree_data.update_tasks_completed(
            prompt=self.user_prompt,
            task=decision.function_name,
            num_trees_completed=self.tree_data.num_trees_completed,
            reasoning=decision.reasoning,
            # retrieved_objects=result.to_json(),
            parsed_info=result.llm_parse(),
        )

        # add to log of actions called
        # TODO: is this the same thing as action_information? but better?
        self._update_actions_called(result, decision)

    async def _evaluate_result(
        self,
        result: Return | Decision | TreeUpdate,
        decision: Decision,
    ):

        if isinstance(result, Result):
            self._update_environment(result, decision)

        if isinstance(result, TrainingUpdate):
            self.training_updates.append(result)

        if isinstance(result, Text):
            self._update_conversation_history("assistant", result.text)
            if self.settings.LOGGING_LEVEL_INT <= 20:
                print(
                    Panel.fit(
                        result.text,
                        title="Assistant response",
                        border_style="cyan",
                        padding=(1, 1),
                    )
                )

        return await self.returner(
            result,
            self.prompt_to_query_id[self.user_prompt],
            last_in_tree=decision.last_in_tree,
        )

    async def _get_available_tools(self, client_manager: ClientManager):
        available_tools = []
        for tool in self.tools.values():
            if not "is_tool_available" in dir(tool):
                available_tools.append(tool.name)
            elif await tool.is_tool_available(
                tree_data=self.tree_data,
                base_lm=self.get_lm("base"),
                complex_lm=self.get_lm("complex"),
                client_manager=client_manager,
            ):
                available_tools.append(tool.name)
        return available_tools

    async def async_run(
        self,
        user_prompt: str,
        collection_names: list[str] = [],
        client_manager: ClientManager | None = None,
        training_route: str = "",
        query_id: str | None = None,
        close_clients_after_completion: bool = True,
        _first_run: bool = True,
        **kwargs,
    ):
        """
        Async version of run() for running Elysia in an async environment.
        See .run() for full documentation.
        """
        # TODO: error handling here

        if client_manager is None:
            client_manager = ClientManager(
                wcd_url=self.settings.WCD_URL,
                wcd_api_key=self.settings.WCD_API_KEY,
                logger=self.settings.logger,
                **self.settings.API_KEYS,
            )

        # Some initial steps if this is the first run (no recursion yet)
        if _first_run:

            self.settings.logger.info(f"Style: {self.tree_data.atlas.style}")
            self.settings.logger.info(
                f"Agent description: {self.tree_data.atlas.agent_description}"
            )
            self.settings.logger.info(f"End goal: {self.tree_data.atlas.end_goal}")

            # Reset the tree (clear temporary data specific to the last user prompt)
            self.soft_reset()

            if query_id is None:
                query_id = str(uuid.uuid4())

            check_base_lm_settings(self.settings)
            check_complex_lm_settings(self.settings)

            # Initialise some objects
            self.set_start_time()
            self.num_trees_completed = 0
            self.query_id_to_prompt[query_id] = user_prompt
            self.prompt_to_query_id[user_prompt] = query_id
            self.tree_data.set_property("user_prompt", user_prompt)
            self._update_conversation_history("user", user_prompt)
            self.user_prompt = user_prompt

            # check and start clients if not already started
            await client_manager.start_clients()

            # Initialise the collections
            # TODO: with client manager error handling, another bool check to see if client manager is active
            # if active, keep collection names empty
            if collection_names == []:
                async with client_manager.connect_to_async_client() as client:
                    collection_names = await retrieve_all_collection_names(client)

            await self.set_collection_names(
                collection_names,
                client_manager,
            )

            # If there are any empty branches, remove them (no tools attached to them)
            self._remove_empty_branches()

            # If training route is provided, split it into a list and set route_active to True
            if training_route != "":
                training_route = training_route.split("/")

            if self.settings.LOGGING_LEVEL_INT <= 20:
                print(
                    Panel.fit(
                        user_prompt,
                        title="User prompt",
                        border_style="yellow",
                        padding=(1, 1),
                    )
                )

        base_lm = self.get_lm("base")

        # Start the tree at the root node
        current_decision_node: DecisionNode = self.decision_nodes[self.root]

        # Loop through the tree until the end is reached
        while True:

            available_tools = await self._get_available_tools(client_manager)
            if len(available_tools) == 0:
                self.settings.logger.error("No tools available to use!")
                raise ValueError(
                    "No tools available to use! "
                    "Check the tool definitions and the `is_tool_available` methods."
                )

            # Evaluate any tools which have hardcoded rules that have been met
            nodes_with_rules_met = await self._check_rules(
                current_decision_node.id, client_manager
            )

            if len(nodes_with_rules_met) > 0:
                for rule in nodes_with_rules_met:
                    rule_decision = Decision(rule, {}, "", False, False)
                    async for result in self.tools[rule](
                        tree_data=self.tree_data,
                        inputs={},
                        base_lm=self.get_lm("base"),
                        complex_lm=self.get_lm("complex"),
                        client_manager=client_manager,
                    ):
                        action_result = await self._evaluate_result(
                            result, rule_decision
                        )
                        if action_result is not None:
                            yield action_result

            # If training, decide from the training route
            if len(training_route) > 0:
                self.settings.logger.info(f"Route that will be used: {training_route}")

                (
                    self.current_decision,
                    training_route,
                ) = current_decision_node.decide_from_route(training_route)
                force_text_response = (
                    self.current_decision.function_name == "text_response"
                )

            # Under normal circumstances decide from the decision node
            else:
                self.timer.start_timer("base_lm")
                self.current_decision, results = await current_decision_node(
                    tree_data=self.tree_data,
                    lm=base_lm,
                    available_tools=available_tools,
                )
                for result in results:
                    action_result = await self._evaluate_result(
                        result, self.current_decision
                    )
                    if action_result is not None:
                        yield action_result

                self.timer.end_timer("base_lm", "Decision Node")

                # Force text response (later) if model chooses end actions
                # but no response will be generated from the node, set flag now
                force_text_response = (
                    not current_decision_node.options[
                        self.current_decision.function_name
                    ]["end"]
                    and self.current_decision.end_actions
                )

            # Set default values for the function inputs for current call
            self.current_decision.function_inputs = self._get_function_inputs(
                self.current_decision.function_name,
                self.current_decision.function_inputs,
            )

            # end criteria, task picked is "text_response" or model chooses to end conversation
            completed = (
                self.current_decision.function_name == "text_response"
                or self.current_decision.end_actions
                or self.current_decision.impossible
            )

            # additional end criteria, recursion limit reached
            if self.tree_data.num_trees_completed > self.tree_data.recursion_limit:
                self.settings.logger.warning(
                    f"Recursion limit reached! ({self.tree_data.num_trees_completed})"
                )
                yield await self.returner(
                    Warning("Decision tree reached recursion limit!"),
                    query_id=self.prompt_to_query_id[user_prompt],
                )
                completed = True

            # assign action function
            action_fn = current_decision_node.options[
                self.current_decision.function_name
            ]["action"]

            # update the decision history
            self.decision_history.append(self.current_decision.function_name)

            # print the current node information
            if self.settings.LOGGING_LEVEL_INT <= 20:
                print(
                    Panel.fit(
                        f"[bold]Node:[/bold] [magenta]{current_decision_node.id}[/magenta]\n"
                        f"[bold]Decision:[/bold] [green]{self.current_decision.function_name}[/green]\n"
                        f"[bold]Reasoning:[/bold] {self.current_decision.reasoning}\n",
                        title="Current Decision",
                        border_style="magenta",
                        padding=(1, 1),
                    )
                )

            # end of current tree
            self.current_decision.last_in_tree = (
                current_decision_node.options[self.current_decision.function_name][
                    "next"
                ]
                is None
            )

            # evaluate the action
            if action_fn is not None:
                self.timer.start_timer(self.current_decision.function_name)
                async for result in action_fn(
                    tree_data=self.tree_data,
                    inputs=self.current_decision.function_inputs,
                    base_lm=self.get_lm("base"),
                    complex_lm=self.get_lm("complex"),
                    client_manager=client_manager,
                ):
                    action_result = await self._evaluate_result(
                        result, self.current_decision
                    )
                    if action_result is not None:
                        yield action_result

                self.timer.end_timer(self.current_decision.function_name)

            # check if the current node is the end of the tree
            if (
                current_decision_node.options[self.current_decision.function_name][
                    "next"
                ]
                is None
                or completed
            ):
                break
            else:
                current_decision_node = self.decision_nodes[
                    current_decision_node.options[self.current_decision.function_name][
                        "next"
                    ]
                ]

        # end of all trees
        if completed:
            self.tree_data.num_trees_completed += 1

            # firstly, if we reached the end of a tree at a node that shouldn't be the end, call text response tool here to respond
            if (
                not current_decision_node.options[self.current_decision.function_name][
                    "end"
                ]
                or force_text_response
            ):
                async for result in self.tools["final_text_response"](
                    tree_data=self.tree_data,
                    inputs={},
                    base_lm=self.get_lm("base"),
                    complex_lm=self.get_lm("complex"),
                ):
                    action_result = await self._evaluate_result(
                        result, self.current_decision
                    )
                    if action_result is not None:
                        yield action_result

            self.save_history(
                query_id=self.prompt_to_query_id[user_prompt],
                time_taken_seconds=time.time() - self.start_time,
            )

            yield await self.returner(
                Completed(), query_id=self.prompt_to_query_id[user_prompt]
            )

            self.settings.logger.info(
                f"[bold green]Model identified overall goal as completed![/bold green]"
            )
            self.settings.logger.info(
                f"Total time taken for decision tree: {time.time() - self.start_time:.2f} seconds"
            )
            self.settings.logger.info(f"Tasks completed:\n")
            for task in self.decision_history:
                if task in self.timer.timers:
                    time_taken = self.timer.timers[task]["avg_time"]
                    self.settings.logger.info(
                        f"     - {task} ([magenta]Avg. {time_taken:.2f} seconds[/magenta])"
                    )
                else:
                    self.settings.logger.info(
                        f"     - {task} ([magenta]Unknown avg. time[/magenta])"
                    )

            if close_clients_after_completion:
                await client_manager.close_clients()

        # otherwise, end of the tree for this iteration, and recursively call process() to restart the tree
        else:
            self.settings.logger.info(
                f"Model did [bold red]not[/bold red] yet complete overall goal! "
            )
            self.settings.logger.debug(
                f"Restarting tree (Recursion: {self.tree_data.num_trees_completed+1}/{self.tree_data.recursion_limit})..."
            )

            # recursive call to restart the tree since the goal was not completed
            self.tree_data.num_trees_completed += 1
            async for result in self.async_run(
                user_prompt,
                collection_names,
                client_manager,
                training_route=training_route,
                query_id=query_id,
                _first_run=False,
            ):
                yield result

    def run(
        self,
        user_prompt: str,
        collection_names: list[str] = [],
        client_manager: ClientManager | None = None,
        training_route: str = "",
        query_id: str | None = None,
        close_clients_after_completion: bool = True,
    ):
        """
        Run the Elysia decision tree.

        Args:
            user_prompt (str): The input from the user.
            collection_names (list[str]): The names of the collections to use.
                If not provided, Elysia will attempt to retrieve all collection names from the client.
            client_manager (ClientManager): The client manager to use.
                If not provided, a new ClientManager will be created.
            training_route (str): The route to use for training.
                Separate tools/branches you want to use with a "/".
                e.g. "query/text_response" will only use the "query" tool and the "text_response" tool, and end the tree there.
            query_id (str): The id of the query.
                Only necessary if you are hosting Elysia on a server with multiple users.
                If not provided, a new query id will be generated.
            close_clients_after_completion (bool): Whether to close the clients after the tree is completed.
                Leave as True for most use cases, but if you don't want to close the clients for the ClientManager, set to False.
        """

        self.store_retrieved_objects = True

        async def run_process():
            async for result in self.async_run(
                user_prompt,
                collection_names,
                client_manager,
                training_route,
                query_id,
                close_clients_after_completion,
            ):
                pass
            return self.retrieved_objects

        async def run_with_live():
            console = Console()

            with console.status("[bold indigo]Thinking...") as status:
                async for result in self.async_run(
                    user_prompt,
                    collection_names,
                    client_manager,
                    training_route,
                    query_id,
                    close_clients_after_completion,
                ):
                    if (
                        result is not None
                        and "type" in result
                        and result["type"] == "status"
                    ):
                        status.update(f"[bold indigo]{result['payload']['text']}")

            return self.retrieved_objects

        if self.settings.LOGGING_LEVEL_INT <= 20:
            yielded_results = asyncio_run(run_with_live())
        else:
            yielded_results = asyncio_run(run_process())

        text = self.tree_data.conversation_history[-1]["content"]

        return text, yielded_results

    def detailed_memory_usage(self) -> dict:
        """
        Returns a detailed breakdown of memory usage for all major objects in the Tree class.

        Returns:
            dict: Dictionary containing memory sizes (in bytes) for each major component
        """
        memory_usage = {}

        # Core data structures
        memory_usage["tree_data"] = asizeof.asizeof(self.tree_data)
        memory_usage["tree_data"] = asizeof.asizeof(self.tree_data)
        memory_usage["tree_data"] = asizeof.asizeof(self.tree_data)
        memory_usage["collection_data"] = asizeof.asizeof(
            self.tree_data.collection_data
        )

        # Decision nodes and tools
        memory_usage["decision_nodes"] = {
            node_id: asizeof.asizeof(node)
            for node_id, node in self.decision_nodes.items()
        }
        memory_usage["tools"] = {
            tool_name: asizeof.asizeof(tool) for tool_name, tool in self.tools.items()
        }

        # History and tracking
        memory_usage["decision_history"] = asizeof.asizeof(self.decision_history)
        memory_usage["history"] = asizeof.asizeof(self.history)
        memory_usage["training_updates"] = asizeof.asizeof(self.training_updates)
        memory_usage["action_information"] = asizeof.asizeof(self.action_information)

        # Mapping dictionaries
        memory_usage["query_mappings"] = {
            "query_id_to_prompt": asizeof.asizeof(self.query_id_to_prompt),
            "prompt_to_query_id": asizeof.asizeof(self.prompt_to_query_id),
        }

        # Calculate total
        memory_usage["total"] = sum(
            (v if isinstance(v, int) else sum(v.values()) if isinstance(v, dict) else 0)
            for v in memory_usage.values()
        )

        return memory_usage

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)
