import time
import uuid
from copy import deepcopy

from pydantic import BaseModel

from elysia.util.parsing import format_dict_to_serialisable
from logging import Logger


class Timer:
    """
    Simple class to track the average time taken for an LLM call.
    """

    def __init__(self, timer_names: list[str], logger: Logger):
        self.timers = {
            name: {
                "calls": 0,
                "avg_time": 0,
                "total_time": 0,
                "start_time": None,
                "end_time": None,
            }
            for name in timer_names
        }
        self.logger = logger

    def start_timer(self, timer_name: str):
        self.timers[timer_name]["start_time"] = time.perf_counter()

    def end_timer(self, timer_name: str, call_name: str = ""):
        if self.timers[timer_name]["start_time"] is None:
            self.logger.warning(f"Timer {timer_name} has not been started yet!")
            return

        time_taken = time.perf_counter() - self.timers[timer_name]["start_time"]
        self.update_avg_time(timer_name, time_taken)

        if call_name != "":
            self.logger.info(
                f"Time taken for {call_name} ({timer_name}): {time_taken: .2f} seconds"
            )
        else:
            self.logger.info(f"Time taken for {timer_name}: {time_taken: .2f} seconds")

    def update_avg_time(self, timer_name: str, time_taken: float):
        self.timers[timer_name]["calls"] += 1
        self.timers[timer_name]["total_time"] += time_taken
        self.timers[timer_name]["avg_time"] = (
            self.timers[timer_name]["total_time"] / self.timers[timer_name]["calls"]
        )

    def remove_timer(self, timer_name: str):
        self.timers.pop(timer_name)

    def add_timer(self, timer_name: str):
        self.timers[timer_name] = {
            "calls": 0,
            "avg_time": 0,
            "total_time": 0,
            "start_time": None,
            "end_time": None,
        }


class TreeUpdate:
    """
    Frontend update to represent what nodes have been updated.
    """

    def __init__(
        self,
        from_node: str,
        to_node: str,
        reasoning: str,
        last_in_branch: bool = False,
    ):
        """
        from_node: The node that is being updated from.
        to_node: The node that is being updated to.
        reasoning: The reasoning for the update.
        tree_index: The index of the tree being updated.
        last_in_branch: Whether this is the last update in the branch (whether the tree is complete after this - hardcoded)
              e.g. in query tool, sometimes the query is the end of the tree and sometimes summarise objects is
        """
        self.from_node = from_node
        self.to_node = to_node
        self.reasoning = reasoning
        self.last_in_branch = last_in_branch

    async def to_frontend(
        self,
        user_id: str,
        conversation_id: str,
        query_id: str,
        tree_index: int,
        last_in_tree: bool = False,
    ):
        return {
            "type": "tree_update",
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "conversation_id": conversation_id,
            "query_id": query_id,
            "payload": {
                "node": self.from_node,
                "tree_index": tree_index,
                "decision": self.to_node,
                "reasoning": self.reasoning,
                "reset": last_in_tree and self.last_in_branch,
            },
        }


class TrainingUpdate:
    """
    Sent from the tree to create a DSPy example for the action taken at that step.
    """

    def __init__(
        self,
        model: str,
        inputs: dict,
        outputs: dict,
        extra_inputs: dict = {},
    ):
        self.model = model

        # Format datetime in inputs and outputs
        format_dict_to_serialisable(inputs)
        format_dict_to_serialisable(outputs)

        # Check if any Pydantic base models exist in either inputs or outputs
        # Create copies of inputs and outputs to avoid modifying the original dictionaries
        inputs_copy = deepcopy(inputs)
        outputs_copy = deepcopy(outputs)

        # If so, convert them to a dictionary
        for key, value in inputs_copy.items():
            inputs_copy[key] = self._convert_basemodel(value)
        for key, value in outputs_copy.items():
            outputs_copy[key] = self._convert_basemodel(value)

        self.inputs = {**inputs_copy, **extra_inputs}
        self.outputs = outputs_copy

    def _convert_basemodel(self, value: BaseModel | dict | list):
        if isinstance(value, BaseModel):
            return value.model_dump()
        elif isinstance(value, dict):
            return {k: self._convert_basemodel(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._convert_basemodel(v) for v in value]

    def to_json(self):
        return {"model": self.model, "inputs": self.inputs, "outputs": self.outputs}
