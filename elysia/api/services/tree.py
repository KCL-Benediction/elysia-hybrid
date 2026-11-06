import asyncio
import datetime
import os
from copy import deepcopy
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

from elysia.config import Settings
from elysia.tree.tree import Tree
from elysia.util.client import ClientManager

# from elysia.tools.fun.dnd import SetTheScene, ActionConsequence, DiceRoll


class TreeManager:
    """
    Manages trees (different conversations) for a single user.
    Designed to be used with the Elysia API, or a manager for multiple Elysia decision trees.

    You can initialise the TreeManager with particular config options.
    Or, upon adding a tree, you can set a specific style, description and end goal for that tree.
    """

    def __init__(
        self,
        user_id: str,
        style: str = "",
        agent_description: str = "",
        end_goal: str = "",
        branch_initialisation: str = "one_branch",
        settings: Settings | None = None,
    ):
        """
        Args:
            user_id (str): Required. A unique identifier for the user being managed within this TreeManager.
            style (str | None): Optional. A writing style for all trees managed by this TreeManager.
            agent_description (str | None): Optional. A description of the agent for all trees managed by this TreeManager.
            end_goal (str | None): Optional. A goal for all trees managed by this TreeManager.
            branch_initialisation (str | None): Optional. A branch initialisation for all trees managed by this TreeManager.
                Defaults to "one_branch", which contains 'Query', 'Aggregate' and 'Summarize' tools.
                Other options are "multi_branch", which contains 'Query' and 'Aggregate' in a separate branch,
                and "empty", which contains no tools (only a base branch), designed to add more tools to.
            settings (Settings | None): Optional. A settings for all trees managed by this TreeManager.
        """
        self.trees = {}
        self.user_id = user_id
        self.tree_timeout = datetime.timedelta(
            minutes=int(os.environ.get("USER_TREE_TIMEOUT", 10))
        )

        if settings is None:
            self.settings = Settings()
            self.settings.set_from_env()
        else:
            self.settings = settings

        self.style = style
        self.agent_description = agent_description
        self.end_goal = end_goal
        self.branch_initialisation = branch_initialisation

    def add_tree(
        self,
        conversation_id: str,
        settings: Settings | None = None,
        style: str | None = None,
        agent_description: str | None = None,
        end_goal: str | None = None,
        branch_initialisation: str | None = None,
        low_memory: bool = False,
    ):
        """
        Add a tree to the TreeManager.
        The decision tree can be initialised with specific config options, such as style, agent description and end goal.
        As well as a Settings object, which chooses options such as the LLM models, API keys and more.

        Args:
            conversation_id (str): Required. A unique identifier for the conversation.
            settings (Settings | None): Optional. A Settings object for the tree.
                Defaults to the Settings object used to initialise the TreeManager.
            style (str | None): Optional. A style for the tree.
                Defaults to the style used to initialise the TreeManager.
            agent_description (str | None): Optional. An agent description for the tree.
                Defaults to the agent description used to initialise the TreeManager.
            end_goal (str | None): Optional. An end goal for the tree.
                Defaults to the end goal used to initialise the TreeManager.
            branch_initialisation (str | None): Optional. A branch initialisation for the tree.
                Defaults to the branch initialisation used to initialise the TreeManager.
            low_memory (bool): Optional. Whether to use low memory mode for the tree.
                Controls the LM history being saved in the tree, and some other variables.
                Defaults to False.
        """

        if settings is None:
            settings = self.settings

        if style is None:
            style = self.style

        if agent_description is None:
            agent_description = self.agent_description

        if end_goal is None:
            end_goal = self.end_goal

        if branch_initialisation is None:
            branch_initialisation = "one_branch"

        if not self.tree_exists(conversation_id):

            self.trees[conversation_id] = {
                "tree": Tree(
                    conversation_id=conversation_id,
                    user_id=self.user_id,
                    settings=settings,
                    style=style,
                    agent_description=agent_description,
                    end_goal=end_goal,
                    branch_initialisation=branch_initialisation,
                    low_memory=low_memory,
                ),
                "last_request": datetime.datetime.now(),
                "event": asyncio.Event(),
            }
            self.trees[conversation_id]["event"].set()

            # self.trees[conversation_id]["tree"].change_style(
            #     "Poetic, flamboyant, engaging, you are a dungeon master! Crafting worlds."
            # )
            # self.trees[conversation_id]["tree"].change_agent_description(
            #     """
            #     You are a dungeon master, crafting a story for the player.
            #     Your job is to describe what happens in this fantasy world, and interact with the player.
            #     They may choose actions, or they may require you to prompt them for more information.
            #     Sometimes, their action may not be descriptive enough, so before choosing any actions, you should ask them to be more specific.
            #     Then combine these responses to call on the appropriate tools and use them to create stories.
            #     Do not create anything yourself, you just call the correct tools with the correct arguments.
            #     """,
            # )
            # self.trees[conversation_id]["tree"].change_end_goal(
            #     "The player/the user's answer has been asked to be more specific, "
            #     "or all the actions outlined in the `user_prompt` have been completed. "
            #     "Either the scene has been set, or the story has evolved. "
            # )

            # self.trees[conversation_id]["tree"].add_tool(SetTheScene)
            # self.trees[conversation_id]["tree"].add_tool(ActionConsequence)
            # self.trees[conversation_id]["tree"].add_tool(DiceRoll)
            # self.trees[conversation_id]["tree"].change_agent_description(
            #     "You are a travel agent. You are given a user prompt and you need to help the user plan their trip. "
            #     "You should always start by finding the destination before doing anything else. "
            #     "Once you have the destination, you can find the best hotels and attractions for the user. "
            #     "When searching for hotels or attractions, you should always use the `destination_id` which matches the original destination you retrieved, "
            #     "instead of the location itself."
            # )
            # self.trees[conversation_id]["tree"].change_end_goal(
            #     "You have a complete set of hotels and attractions for the user's destination. "
            #     "You should finish the conversation with a full summary and itenary of the trip. "
            # )

    def tree_exists(self, conversation_id: str):
        """
        Check if a tree exists in the TreeManager.

        Args:
            conversation_id (str): The conversation ID which may contain the tree.

        Returns:
            bool: True if the tree exists, False otherwise.
        """
        return conversation_id in self.trees

    def get_tree(self, conversation_id: str):
        """
        Get a tree from the TreeManager.

        Args:
            conversation_id (str): The conversation ID which contains the tree.

        Returns:
            Tree: The tree associated with the conversation ID.
        """

        return self.trees[conversation_id]["tree"]

    def get_event(self, conversation_id: str):
        """
        Get the asyncio.Event for a tree in the TreeManager.
        This is cleared when the tree is processing, and set when the tree is idle.
        This is used to block the API from sending multiple requests to the tree at once.

        Args:
            conversation_id (str): The conversation ID which contains the tree.

        Returns:
            asyncio.Event: The event for the tree.
        """
        return self.trees[conversation_id]["event"]

    def configure(self, conversation_id: str | None = None, **kwargs):
        """
        Configure the settings for a tree in the TreeManager.

        Args:
            conversation_id (str | None): The conversation ID which contains the tree.
            **kwargs: The keyword arguments to pass to the Settings.configure() method.
        """
        if conversation_id is None:
            self.settings.configure(**kwargs)
        else:
            self.trees[conversation_id]["tree"].settings.configure(**kwargs)

    def change_style(self, style: str, conversation_id: str | None = None):
        """
        Change the style for a tree in the TreeManager.

        Args:
            style (str): The new style for the tree.
            conversation_id (str | None): Optional. The conversation ID which contains the tree.
                If not supplied, the style will be changed on all trees.
        """
        if conversation_id is None:
            self.style = style
        else:
            if conversation_id not in self.trees:
                raise ValueError(f"Tree {conversation_id} not found")

            self.trees[conversation_id]["tree"].change_style(style)

    def change_agent_description(
        self, agent_description: str, conversation_id: str | None = None
    ):
        """
        Change the agent description for a tree in the TreeManager.

        Args:
            agent_description (str): The new agent description for the tree.
            conversation_id (str | None): Optional. The conversation ID which contains the tree.
                If not supplied, the agent description will be changed on all trees.
        """
        if conversation_id is None:
            self.agent_description = agent_description
        else:
            if conversation_id not in self.trees:
                raise ValueError(f"Tree {conversation_id} not found")

            self.trees[conversation_id]["tree"].change_agent_description(
                agent_description
            )

    def change_end_goal(self, end_goal: str, conversation_id: str | None = None):
        """
        Change the end goal for a tree in the TreeManager.

        Args:
            end_goal (str): The new end goal for the tree.
            conversation_id (str | None): Optional. The conversation ID which contains the tree.
                If not supplied, the end goal will be changed on all trees.
        """
        if conversation_id is None:
            self.end_goal = end_goal
        else:
            if conversation_id not in self.trees:
                raise ValueError(f"Tree {conversation_id} not found")

            self.trees[conversation_id]["tree"].change_end_goal(end_goal)

    def change_branch_initialisation(
        self, branch_initialisation: str, conversation_id: str | None = None
    ):
        """
        Change the branch initialisation for a tree in the TreeManager.

        Args:
            branch_initialisation (str): The new branch initialisation for the tree.
            conversation_id (str | None): Optional. The conversation ID which contains the tree.
                If not supplied, the branch initialisation will be changed on all trees.
        """
        if conversation_id is None:
            self.branch_initialisation = branch_initialisation
        else:
            if conversation_id not in self.trees:
                raise ValueError(f"Tree {conversation_id} not found")

            self.trees[conversation_id]["tree"].set_branch_initialisation(
                branch_initialisation
            )

    async def process_tree(
        self,
        query: str,
        conversation_id: str,
        query_id: str,
        training_route: str = "",
        collection_names: list[str] = [],
        client_manager: ClientManager | None = None,
    ):
        """
        Process a tree in the TreeManager.
        This is an async generator which yields results from the tree.async_run() method.

        Args:
            query (str): Required. The user input/prompt to process in the decision tree.
            conversation_id (str): Required. The conversation ID which contains the tree.
            query_id (str): Required. A unique identifier for the query.
            training_route (str): Optional. The training route, a string of the form "tool1/tool2/tool1" etc.
                See the `tree.async_run()` method for more details.
            collection_names (list[str]): Optional. A list of collection names to use in the query.
                If not supplied, all collections will be used.
            client_manager (ClientManager | None): Optional. A client manager to use for the query.
                If not supplied, a new ClientManager will be created.
        """

        tree: Tree = self.get_tree(conversation_id)
        self.update_tree_last_request(conversation_id)

        # wait for the tree to be idle
        await self.trees[conversation_id]["event"].wait()

        # clear the event, set it to working
        self.trees[conversation_id]["event"].clear()

        async for yielded_result in tree.async_run(
            query,
            collection_names=collection_names,
            client_manager=client_manager,
            query_id=query_id,
            training_route=training_route,
            close_clients_after_completion=False,
        ):
            yield yielded_result
            self.update_tree_last_request(conversation_id)

        # set the event to idle
        self.trees[conversation_id]["event"].set()

    def check_tree_timeout(self, conversation_id: str):
        # if tree not found, return True
        if conversation_id not in self.trees:
            return True

        # Remove any trees that have not been active in the last USER_TREE_TIMEOUT minutes
        if (
            "last_request" in self.trees[conversation_id]
            and datetime.datetime.now() - self.trees[conversation_id]["last_request"]
            > self.tree_timeout
        ):
            return True

        return False

    def update_tree_last_request(self, conversation_id: str):
        self.trees[conversation_id]["last_request"] = datetime.datetime.now()

    def check_all_trees_timeout(self):
        convs_to_remove = []
        for i, conversation_id in enumerate(self.trees):
            if self.check_tree_timeout(conversation_id):
                convs_to_remove.append(conversation_id)

        for conversation_id in convs_to_remove:
            del self.trees[conversation_id]
