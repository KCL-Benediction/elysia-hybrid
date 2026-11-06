import dspy
import pytest
from elysia.config import Settings, configure, reset_settings
from elysia.tree.tree import Tree


class TestTreeConfig:

    def reset_global_settings(self):
        reset_settings()

    def test_change_llm_in_tree_global(self):
        """
        When using global settings, is the change reflected in the tree?
        """

        # create a Tree (uses global settings by default)
        tree = Tree(debug=False)

        # should raise an error, no models set
        # TODO: settings from test_settings is overriding this, so error not being raised????
        assert isinstance(tree.get_lm("base"), dspy.LM)
        assert isinstance(tree.get_lm("complex"), dspy.LM)
        assert tree.base_lm is None
        assert tree.complex_lm is None

        # change the base model
        configure(base_model="gpt-4o-mini", base_provider="openai")

        # should now be changed (no error)
        base_lm_loaded_in_tree = tree.get_lm("base")  # should be a dspy.LM

        assert isinstance(base_lm_loaded_in_tree, dspy.LM)
        assert base_lm_loaded_in_tree.model == "openai/gpt-4o-mini"
        assert tree.settings.BASE_MODEL == "gpt-4o-mini"
        assert tree.settings.BASE_PROVIDER == "openai"
        assert tree.settings.BASE_MODEL_LM is None

        # change the complex model
        configure(complex_model="gpt-4o", complex_provider="openai")

        # should now be changed (no error)
        complex_lm_loaded_in_tree = tree.get_lm("complex")

        assert isinstance(complex_lm_loaded_in_tree, dspy.LM)
        assert complex_lm_loaded_in_tree.model == "openai/gpt-4o"
        assert tree.settings.COMPLEX_MODEL == "gpt-4o"
        assert tree.settings.COMPLEX_PROVIDER == "openai"
        assert tree.settings.COMPLEX_MODEL_LM is None

        self.reset_global_settings()

    def test_change_llm_in_tree_local(self):
        """
        When using local settings, global settings should NOT be reflected in the tree
        """
        settings = Settings()

        # create a Tree with local settings obj
        tree = Tree(settings=settings)

        # should raise an error, no models set
        with pytest.raises(ValueError):
            tree.get_lm("base")
            tree.get_lm("complex")

        # change the models by global configure
        configure(
            base_model="gpt-4o-mini",
            base_provider="openai",
            complex_model="gpt-4o",
            complex_provider="openai",
        )

        # should still error
        with pytest.raises(ValueError):
            tree.get_lm("base")
            tree.get_lm("complex")

        # change the models by local configure
        settings.configure(
            base_model="gpt-4o-mini",
            base_provider="openai",
            complex_model="gpt-4o",
            complex_provider="openai",
        )

        # should now be no errors
        base_lm_loaded_in_tree = tree.get_lm("base")
        assert isinstance(base_lm_loaded_in_tree, dspy.LM)
        assert base_lm_loaded_in_tree.model == "openai/gpt-4o-mini"
        assert tree.settings.BASE_MODEL == "gpt-4o-mini"
        assert tree.settings.BASE_PROVIDER == "openai"
        assert tree.settings.BASE_MODEL_LM is None

        complex_lm_loaded_in_tree = tree.get_lm("complex")
        assert isinstance(complex_lm_loaded_in_tree, dspy.LM)
        assert complex_lm_loaded_in_tree.model == "openai/gpt-4o"
        assert tree.settings.COMPLEX_MODEL == "gpt-4o"
        assert tree.settings.COMPLEX_PROVIDER == "openai"
        assert tree.settings.COMPLEX_MODEL_LM is None

        self.reset_global_settings()

    def test_change_llm_with_debug(self):
        """
        When using debug, the models should be loaded into the Tree and not changed
        """
        settings = Settings()

        # create a Tree with local settings obj, should error as cant load models
        with pytest.raises(ValueError):
            tree = Tree(settings=settings, debug=True)

        # change the models by global configure
        settings.configure(
            local=True,
            base_model="gpt-4o-mini",
            base_provider="openai",
            complex_model="gpt-4o",
            complex_provider="openai",
        )

        # should now be changed (no error)
        tree = Tree(settings=settings, debug=True)

        base_lm_loaded_in_tree = tree.get_lm("base")
        assert isinstance(base_lm_loaded_in_tree, dspy.LM)
        assert base_lm_loaded_in_tree.model == "openai/gpt-4o-mini"
        assert tree.settings.BASE_MODEL == "gpt-4o-mini"
        assert tree.settings.BASE_PROVIDER == "openai"

        complex_lm_loaded_in_tree = tree.get_lm("complex")
        assert isinstance(complex_lm_loaded_in_tree, dspy.LM)
        assert complex_lm_loaded_in_tree.model == "openai/gpt-4o"
        assert tree.settings.COMPLEX_MODEL == "gpt-4o"
        assert tree.settings.COMPLEX_PROVIDER == "openai"

        assert "BASE_MODEL_LM" in dir(tree.settings)
        assert isinstance(tree.settings.BASE_MODEL_LM, dspy.LM)
        assert "COMPLEX_MODEL_LM" in dir(tree.settings)
        assert isinstance(tree.settings.COMPLEX_MODEL_LM, dspy.LM)

        self.reset_global_settings()


if __name__ == "__main__":
    test = TestTreeConfig()
    test.test_change_llm_in_tree_global()
