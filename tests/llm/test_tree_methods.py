import pytest
import elysia
from elysia.tree.tree import Tree


class TestTreeMethods:

    def do_query(self, user_prompt: str):
        elysia.config.settings.smart_setup()
        tree = Tree(
            low_memory=False,
        )
        tree.run(
            user_prompt,
            collection_names=[
                "Example_verba_github_issues",
                "Example_verba_slack_conversations",
                "Example_verba_email_chains",
            ],
        )
        return tree

    def test_various_methods(self):

        # set up tree with a basic query
        user_prompt = "What was Edward's last message?"
        tree = self.do_query(user_prompt)

        # check the user prompt is in the conversation history
        assert tree.tree_data.conversation_history[0]["content"] == user_prompt
        assert tree.tree_data.conversation_history[0]["role"] == "user"

        # check some variables are set
        assert tree.tree_data.num_trees_completed > 0
        assert tree.tree_data.user_prompt == user_prompt

        all_decision_history = []
        for iteration in tree.decision_history:
            all_decision_history.extend(iteration)
        assert len(all_decision_history) > 0
        assert "query" in all_decision_history

        # this should have returned something in the environment
        assert "query" in tree.tree_data.environment.environment
        for env_name in tree.tree_data.environment.environment["query"]:
            for returned_object in tree.tree_data.environment.environment["query"][
                env_name
            ]:
                assert "metadata" in returned_object
                assert len(returned_object["objects"]) > 0

        # this should have updated tasks_completed
        assert len(tree.tree_data.tasks_completed) > 0
        prompt_found = False
        for task in tree.tree_data.tasks_completed:
            if task["prompt"] == user_prompt:
                prompt_found = True
                assert len(task["task"]) > 0
                break

        assert prompt_found

        # check the tree resets
        tree.soft_reset()

        # These should not change
        assert len(tree.tree_data.conversation_history) > 0
        assert len(tree.tree_data.tasks_completed) > 0
        assert (
            "query" in tree.tree_data.environment.environment
        )  # environment should not be reset

        # these should be reset
        assert tree.tree_data.num_trees_completed == 0
        assert tree.tree_index == 1

        all_decision_history = []
        for iteration in tree.decision_history:
            all_decision_history.extend(iteration)
        assert len(all_decision_history) == 0

    def test_get_follow_up_suggestions(self):
        tree = self.do_query("What was Edward's last message?")
        suggestions = tree.get_follow_up_suggestions(
            context="make it about messages specifically",
            num_suggestions=5,
        )
        if len(suggestions) != 5:
            print(tree.complex_lm.inspect_history(1))
        assert len(suggestions) == 5
