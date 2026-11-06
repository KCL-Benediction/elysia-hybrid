from elysia.objects import Result, Update


class BoringGeneric(Result):
    """
    BoringGeneric return object, e.g. anything that does not fit into the other categories.
    Will be displayed as a table.

    Properties:

    - **anything**: anything
    """

    def __init__(
        self,
        objects: list[dict],
        metadata: dict = {},
        name: str = "generic",
        llm_message: str | None = None,
        unmapped_keys: list[str] = [],
    ):
        Result.__init__(
            self,
            objects=objects,
            payload_type="boring_generic",
            metadata=metadata,
            name=name,
            mapping=None,
            llm_message=llm_message,
            unmapped_keys=unmapped_keys,
        )


class EpicGeneric(Result):
    """
    EpicGeneric return object, e.g. anything generic that will fit into the following properties.

    Properties:

    - title: the title of the information. string
    - subtitle: the subtitle of the information. string
    - content: the content of the information. string/other
    - url: the url of the information. string
    - id: the id of the information. integer/string/other
    - author: the author of the information. string/other
    - timestamp: the timestamp of the information in any format. datetime/string/other
    - tags: the tags of the information. list[string/other]
    - category: some string describing the category of the information, e.g. type of something. string
    - subcategory: some string describing a nested level of category of the data. string
    """

    def __init__(
        self,
        objects: list[dict],
        metadata: dict = {},
        name: str = "generic",
        mapping: dict | None = None,
        llm_message: str | None = None,
        unmapped_keys: list[str] = [],
    ):
        Result.__init__(
            self,
            objects=objects,
            payload_type="epic_generic",
            metadata=metadata,
            name=name,
            mapping=mapping,
            llm_message=llm_message,
            unmapped_keys=unmapped_keys,
        )


class Document(Result):
    """
    Document return object, e.g. a blog post, a news article, a research paper, etc.

    Properties:

    - title: the title of the document. string
    - author: the author or username or creator of the document. string
    - date: any date or time format. datetime/string/other
    - content: the textual content of the document. string/other
    - category: some string describing the category of the document, e.g. type of something. string
    """

    def __init__(
        self,
        objects: list[dict],
        metadata: dict = {},
        name: str = "generic",
        mapping: dict | None = None,
        llm_message: str | None = None,
        unmapped_keys: list[str] = [],
    ):
        Result.__init__(
            self,
            objects=objects,
            payload_type="document",
            metadata=metadata,
            name=name,
            mapping=mapping,
            llm_message=llm_message,
            unmapped_keys=unmapped_keys,
        )


class Ticket(Result):
    """
    Ticket return object, e.g. a support ticket, a customer service ticket, etc.

    Properties:

    - title: the title of the ticket. string
    - subtitle: the subtitle of the ticket. string
    - author: the author of the ticket. string
    - content: the text of the ticket. string
    - created_at: the timestamp of the original creation time/date of the ticket in any format. datetime/string/other
    - updated_at: the timestamp of the last update time/date of the ticket in any format. datetime/string/other
    - url: the url of the ticket. string
    - status: the status of the ticket. string
    - id: the id of the ticket. integer/string/other
    - tags: the tags of the ticket. list[string/other]
    - comments: either the comments of the ticket, or the number of comments. list[string/dict/other] / integer
    """

    def __init__(
        self,
        objects: list[dict],
        metadata: dict = {},
        name: str = "generic",
        mapping: dict | None = None,
        llm_message: str | None = None,
        unmapped_keys: list[str] = [],
    ):
        Result.__init__(
            self,
            objects=objects,
            payload_type="ticket",
            metadata=metadata,
            name=name,
            mapping=mapping,
            llm_message=llm_message,
            unmapped_keys=unmapped_keys,
        )


class Ecommerce(Result):
    """
    Ecommerce return object, e.g. a product, a service, a purchase, etc.

    Properties:

    - name: the name of the product. string
    - description: the description of the product. string
    - price: the price of the product. float/integer/other
    - category: the category of the product. string
    - subcategory: the subcategory of the product. string
    - collection: the collection that the product belongs to. string
    - rating: the rating of the product. float/integer/other
    - reviews: the reviews of the product, or number of reviews. list[string/dict/other] / integer
    - tags: the tags of the product. list[string/other]
    - url: the url of the product. string
    - image: the image of the product. string/other
    - brand: the brand of the product. string
    - id: the id of the product. integer/string/other
    - colors: the color(s) of the product. list[string/other] / string
    - sizes: the size(s) of the product. list[string/other] / string
    """

    def __init__(
        self,
        objects: list[dict],
        metadata: dict = {},
        name: str = "generic",
        mapping: dict | None = None,
        llm_message: str | None = None,
        unmapped_keys: list[str] = [],
    ):
        Result.__init__(
            self,
            objects=objects,
            payload_type="ecommerce",
            metadata=metadata,
            name=name,
            mapping=mapping,
            llm_message=llm_message,
            unmapped_keys=unmapped_keys,
        )


class Message(Result):
    """
    Message return object, e.g. a message, a chat, a conversation, etc.

    Properties:

    - content: the content of the message. string/other
    - author: the author of the message. string
    - timestamp: the timestamp of the message in any format. datetime/string/other
    - conversation_id: the id of the conversation that the message belongs to. integer/string/other
    - message_id: the id of the message itself, within the conversation. integer/string/other
    """

    def __init__(
        self,
        objects: list[dict],
        metadata: dict = {},
        name: str = "generic",
        mapping: dict | None = None,
        llm_message: str | None = None,
        unmapped_keys: list[str] = [],
    ):
        Result.__init__(
            self,
            objects=objects,
            payload_type="message",
            metadata=metadata,
            name=name,
            mapping=mapping,
            llm_message=llm_message,
            unmapped_keys=unmapped_keys,
        )


class Conversation(Result):
    """
    Conversation return object, e.g. a conversation, a chat, a message thread, etc.

    Properties:

    - messages: the messages of the conversation. list[dict] where each dict has the following properties:
        - content: the content of the message. string/other
        - author: the author of the message. string
        - timestamp: the timestamp of the message in any format. datetime/string/other
        - conversation_id: the id of the conversation that the message belongs to. integer/string/other
        - message_id: the id of the message itself, within the conversation. integer/string/other
    - conversation_id: the id of the conversation itself. integer/string/other
    """

    def __init__(
        self,
        objects: list[dict],
        metadata: dict = {},
        name: str = "generic",
        mapping: dict | None = None,
        llm_message: str | None = None,
        unmapped_keys: list[str] = [],
    ):
        Result.__init__(
            self,
            objects=objects,
            payload_type="conversation",
            metadata=metadata,
            name=name,
            mapping=mapping,
            llm_message=llm_message,
            unmapped_keys=unmapped_keys,
        )
