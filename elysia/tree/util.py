import ast
from typing import Any

# dspy requires a 'base' LM but this should not be used
import dspy
from pympler import asizeof
from logging import Logger

# globals
from elysia.objects import (
    Response,
    Return,
    Tool,
    Update,
    Status,
)

# Objects
from elysia.tree.objects import TreeData
from elysia.util.objects import TrainingUpdate, TreeUpdate
from elysia.util.elysia_chain_of_thought import ElysiaChainOfThought
from elysia.util.reference import create_reference
from elysia.tree.prompt_templates import (
    construct_decision_prompt,
    FollowUpSuggestionsPrompt,
)

# Settings
from elysia.config import Settings, load_base_lm


class RecursionLimitException(Exception):
    pass


class Decision:
    def __init__(
        self,
        function_name: str,
        function_inputs: dict,
        reasoning: str,
        impossible: bool,
        end_actions: bool,
        last_in_tree: bool = False,
    ):
        self.function_name = function_name
        self.function_inputs = function_inputs
        self.reasoning = reasoning
        self.impossible = impossible
        self.end_actions = end_actions
        self.last_in_tree = last_in_tree


class DecisionNode:
    def __init__(
        self,
        id: str,
        instruction: str,
        options: dict[str, dict[str, str | bool | Tool | None]],
        root: bool = False,
        logger: Logger = None,
    ):
        self.id = id
        self.instruction = instruction
        self.options = options
        self.root = root
        self.logger = logger

    def _get_options(self):
        return self.options

    def add_option(
        self,
        id: str,
        description: str,
        inputs: dict,
        action: Tool | None = None,
        end: bool = True,
        status: str = "",
        next: str | None = None,
    ):
        if status == "":
            status = f"Running {id}..."

        self.options[id] = {
            "description": description,
            "inputs": inputs,
            "action": action,
            "end": end,
            "status": status,
            "next": next,
        }

    def remove_option(self, id: str):
        if id in self.options:
            del self.options[id]

    def _options_to_json(self, available_tools: list[str]):
        """
        Options that get shown to the LLM.
        Remove any that are empty branches.
        """
        out = {}
        for node in self.options:
            if node not in available_tools:  # empty branch
                continue

            out[node] = {
                "function_name": node,
                "description": self.options[node]["description"],
                "inputs": self.options[node]["inputs"],
            }
        return out

    def decide_from_route(self, route: str):
        """
        Decide from a route.
        """
        possible_nodes = self._get_options()

        next_route = route[0]
        if next_route not in possible_nodes:
            raise Exception(
                f"Next node in training route ({next_route}) not in possible nodes ({possible_nodes})"
            )

        route = route[1:]
        completed = len(route) == 0

        return (
            Decision(
                function_name=next_route,
                reasoning=f"Decided to run {next_route} from route {route}",
                impossible=False,
                function_inputs={},
                end_actions=completed,
            ),
            route,
        )

    async def __call__(
        self,
        tree_data: TreeData,
        lm: dspy.LM = None,
        available_tools: list[str] = [],
        **kwargs,
    ):
        options = self._options_to_json(available_tools)
        if len(options) == 0:
            raise RuntimeError(
                "No available tools to call! Make sure you have added some tools to the tree. "
                "Or the .is_tool_available() method is returning True for at least one tool."
            )
        for option in options:
            if options[option]["inputs"] == {}:
                options[option]["inputs"] = "No inputs are needed for this function."

        decision_executor = ElysiaChainOfThought(
            construct_decision_prompt(self._get_options()),
            tree_data=tree_data,
            environment=True,
            collection_schemas=True,
            tasks_completed=True,
            message_update=True,
        )
        # decision_executor = self._load_model(decision_executor)
        # decision_executor = dspy.asyncify(decision_executor)

        self.logger.debug(f"Available options: {list(options.keys())}")

        output = await decision_executor.aforward(
            instruction=self.instruction,
            tree_count=tree_data.tree_count_string(),
            available_actions=options,
            lm=lm,
        )

        decision = Decision(
            output.function_name,
            output.function_inputs,
            output.reasoning,
            output.impossible,
            output.end_actions and self.options[output.function_name]["end"],
        )

        results = [
            TrainingUpdate(
                model="decision",
                inputs=tree_data.to_json(),
                outputs={k: v for k, v in output.__dict__["_store"].items()},
            ),
            TreeUpdate(
                from_node=self.id,
                to_node=output.function_name,
                reasoning=output.reasoning,
                last_in_branch=True,
            ),
            Status(self.options[output.function_name]["status"]),
        ]

        if output.function_name != "text_response":
            results.append(Response(output.message_update))

        return decision, results

    def detailed_memory_usage(self) -> dict:
        """
        Returns a detailed breakdown of memory usage for all objects in the DecisionNode.

        Returns:
            dict: Dictionary containing memory sizes (in bytes) for each component
        """
        memory_usage = {}

        # Core attributes
        memory_usage["id"] = asizeof.asizeof(self.id)
        memory_usage["instruction"] = asizeof.asizeof(self.instruction)
        memory_usage["root"] = asizeof.asizeof(self.root)

        # Decision-related data - break down each option
        memory_usage["options"] = {}
        for option_id, option in self.options.items():
            memory_usage["options"][option_id] = {
                "description": asizeof.asizeof(option["description"]),
                "inputs": asizeof.asizeof(option["inputs"]),
                "action": asizeof.asizeof(option["action"]),
                "end": asizeof.asizeof(option["end"]),
                "status": asizeof.asizeof(option["status"]),
                "next": asizeof.asizeof(option["next"]),
            }

        # Calculate total
        memory_usage["total"] = sum(
            (
                v
                if isinstance(v, int)
                else (
                    sum(
                        (
                            sv
                            if isinstance(sv, int)
                            else sum(sv.values()) if isinstance(sv, dict) else 0
                        )
                        for sv in v.values()
                    )
                    if isinstance(v, dict)
                    else 0
                )
            )
            for v in memory_usage.values()
        )

        return memory_usage


# TODO: move these methods to the main tree, perhaps?
#       and each of these methods could do the auxiliary tasks e.g. updating environment, conversation history, etc.
# TODO: but could we also clean up the tree by moving things to different classes?
class TreeReturner:
    """
    Class to parse the output of the tree to the frontend.
    """

    def __init__(
        self,
        user_id: str,
        conversation_id: str,
        tree_index: int = 0,
    ):
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.tree_index = tree_index

    def set_tree_index(self, tree_index: int):
        self.tree_index = tree_index

    async def __call__(
        self,
        result: Return | TreeUpdate,
        query_id: str,
        last_in_tree: bool = False,
    ):
        if isinstance(result, Update):
            return await result.to_frontend(self.conversation_id, query_id)

        if isinstance(result, Return):
            return await result.to_frontend(
                self.user_id, self.conversation_id, query_id
            )

        if isinstance(result, TreeUpdate):
            return await result.to_frontend(
                self.user_id,
                self.conversation_id,
                query_id,
                self.tree_index,
                last_in_tree,
            )


class BranchVisitor(ast.NodeVisitor):
    def __init__(self):
        self.branches = []

    def _evaluate_constant(self, node):
        """Convert AST Constant node to its actual value."""
        return node.value

    def _evaluate_dict(self, node):
        """Convert AST Dict node to a regular Python dictionary."""
        if isinstance(node, ast.Dict):
            return {
                self._evaluate_constant(key): self._evaluate_constant(value)
                for key, value in zip(node.keys, node.values)
            }
        return None

    def visit_Call(self, node):
        # Check if the call is creating a Branch object
        if isinstance(node.func, ast.Name) and node.func.id == "Branch":
            # Extract the updates dictionary from the Branch constructor
            if node.args:
                dict_node = node.args[0]
                evaluated_dict = self._evaluate_dict(dict_node)
                if evaluated_dict:
                    self.branches.append(evaluated_dict)
        self.generic_visit(node)


async def get_follow_up_suggestions(
    tree_data: TreeData, current_suggestions: list[str], config: Settings
):

    # load dspy model for suggestor
    follow_up_suggestor = dspy.Predict(FollowUpSuggestionsPrompt)

    # get prediction
    prediction = await follow_up_suggestor.aforward(
        user_prompt=tree_data.user_prompt,
        reference=create_reference(),
        conversation_history=tree_data.conversation_history,
        environment=tree_data.environment.to_json(),
        data_information=tree_data.output_collection_metadata(with_mappings=False),
        old_suggestions=current_suggestions,
        lm=load_base_lm(config),
    )
    config.logger.debug(f"Follow-up suggestions: {prediction.suggestions}")

    return prediction.suggestions
