from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel


class QueryData(BaseModel):
    user_id: str
    conversation_id: str
    query_id: str
    query: str
    collection_names: list[str]
    route: Optional[str] = ""
    mimick: Optional[bool] = False


class ViewPaginatedCollectionData(BaseModel):
    user_id: str
    collection_name: str
    page_size: int
    page_number: int
    sort_on: Optional[str] = None
    ascending: Optional[bool] = False
    filter_config: Optional[dict[str, Any]] = {}


# pass optional args as None to get defaults
class InitialiseTreeData(BaseModel):
    user_id: str
    conversation_id: str
    style: Optional[str] = None
    agent_description: Optional[str] = None
    end_goal: Optional[str] = None
    branch_initialisation: Optional[str] = None
    low_memory: Optional[bool] = False
    settings: Optional[dict[str, Any]] = None


class NERData(BaseModel):
    text: str


class TitleData(BaseModel):
    user_id: str
    conversation_id: str
    text: str


class GetObjectData(BaseModel):
    user_id: str
    collection_name: str
    uuid: str


class ObjectRelevanceData(BaseModel):
    user_id: str
    conversation_id: str
    query_id: str
    objects: list[dict]


class ProcessCollectionData(BaseModel):
    user_id: str
    collection_name: str


class DebugData(BaseModel):
    conversation_id: str
    user_id: str


class CollectionMetadataData(BaseModel):
    user_id: str
    collection_name: str


class UserCollectionsData(BaseModel):
    user_id: str


class AddFeedbackData(BaseModel):
    user_id: str
    conversation_id: str
    query_id: str
    feedback: int


class RemoveFeedbackData(BaseModel):
    user_id: str
    conversation_id: str
    query_id: str


class GetUserRequestsData(BaseModel):
    user_id: str


class FeedbackMetadataData(BaseModel):
    user_id: str


class InstantReplyData(BaseModel):
    user_id: str
    user_prompt: str


class FollowUpSuggestionsData(BaseModel):
    user_id: str
    conversation_id: str


# TODO: hash the api keys
class Config(BaseModel):
    settings: dict[str, Any]
    style: str
    agent_description: str
    end_goal: str
    branch_initialisation: str
    config_id: Optional[str] = None


class InitialiseUserData(BaseModel):
    user_id: str
    default_models: bool
    settings: Optional[dict[str, Any]] = None
    style: Optional[str] = "Informative, polite and friendly."
    agent_description: Optional[str] = (
        "You search and query Weaviate to satisfy the user's query, providing a concise summary of the results."
    )
    end_goal: Optional[str] = (
        "You have satisfied the user's query, and provided a concise summary of the results. "
        "Or, you have exhausted all options available, or asked the user for clarification."
    )
    branch_initialisation: Optional[Literal["one_branch", "multi_branch", "empty"]] = (
        "one_branch"
    )


class DefaultModelsUserData(BaseModel):
    user_id: str


class DefaultModelsTreeData(BaseModel):
    user_id: str
    conversation_id: str


class EnvironmentSettingsUserData(BaseModel):
    user_id: str


class ChangeConfigUserData(BaseModel):
    user_id: str
    settings: Optional[dict[str, Any]] = None
    style: Optional[str] = None
    agent_description: Optional[str] = None
    end_goal: Optional[str] = None
    branch_initialisation: Optional[str] = None


class ChangeConfigTreeData(BaseModel):
    user_id: str
    conversation_id: str
    settings: Optional[dict[str, Any]] = None
    style: Optional[str] = None
    agent_description: Optional[str] = None
    end_goal: Optional[str] = None
    branch_initialisation: Optional[Literal["one_branch", "multi_branch", "empty"]] = (
        None
    )


class SaveConfigData(BaseModel):
    user_id: str
    config_id: str
    config: Config


class LoadConfigUserData(BaseModel):
    user_id: str
    config_id: str
    include_atlas: bool
    include_branch_initialisation: bool
    include_settings: bool


class LoadConfigTreeData(BaseModel):
    user_id: str
    conversation_id: str
    config_id: str
    include_atlas: bool
    include_branch_initialisation: bool
    include_settings: bool


class ListConfigsData(BaseModel):
    user_id: str


# class ChangeAtlasUserData(BaseModel):
#     user_id: str
#     atlas: dict[str, str]


# class ChangeAtlasTreeData(BaseModel):
#     user_id: str
#     conversation_id: str
#     atlas: dict[str, str]
