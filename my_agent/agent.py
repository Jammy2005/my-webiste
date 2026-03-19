from langchain.chat_models import init_chat_model
from langchain.tools import tool
from langchain.messages import AnyMessage
from typing_extensions import TypedDict, Annotated
import operator
from langchain.messages import SystemMessage
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langchain.messages import HumanMessage
from dotenv import load_dotenv
from my_agent.utils.prompts import SYS_PROMPT
load_dotenv()

from pathlib import Path
import operator
from typing import Annotated
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langgraph.prebuilt import ToolNode

class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int
    # tokens_used: int

# load up existing vector dB
BASE_DIR = Path(__file__).resolve().parent
FULL_UP_DIR = BASE_DIR.parent
CHROMA_DIR = FULL_UP_DIR /"chroma_db"

print(CHROMA_DIR)

embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

vector_store = Chroma(
    collection_name="project_dossiers",
    embedding_function=embeddings,
    persist_directory=str(CHROMA_DIR),
)

# IDENTIFY THE MODEL
model = init_chat_model(
    "claude-sonnet-4-6",
    temperature=0
)

# Define tools

@tool
def search_project_docs(query: str) -> str:
    """
    Search the indexed project dossier documents for relevant information.
    Use this when the user asks about project architecture, tech stack,
    limitations, features, tools, workflows, or comparisons between projects.
    """


    results = vector_store.similarity_search(query, k=4)

    if not results:
        return "No relevant documents found."

    formatted_chunks = []
    for i, doc in enumerate(results, start=1):
        project = doc.metadata.get("project", "Unknown project")
        section = doc.metadata.get("section", "Unknown section")
        source = doc.metadata.get("file_name", "Unknown file")

        formatted_chunks.append(
            f"""Result {i}
Project: {project}
Section: {section}
Source: {source}
Content:
{doc.page_content}"""
        )

    return "\n\n" + ("\n\n" + "=" * 80 + "\n\n").join(formatted_chunks)


@tool
def multiply(a: int, b: int) -> int:
    """
    Might make a send Gmail tool
    """
    return a*b


tools = [search_project_docs, multiply]

model_with_tools = model.bind_tools(tools)

def llm_call(state: dict):
    """LLM decides whether to call a tool or not"""

    response = model_with_tools.invoke(
                [
                    SystemMessage(
                        content=SYS_PROMPT
                    )
                ]
                + state["messages"]
            )
    
    # tokens = response.usage_metadata.get("total_tokens", 0)

    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1,
        # "tokens_used": state.get("tokens_used", 0) + tokens
    }

def should_continue(state: MessagesState) -> str:
    last_message = state["messages"][-1]

    # If the model requested tool calls, go to the tool node
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    return END

agent_builder = StateGraph(MessagesState)

agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tools", ToolNode(tools))

agent_builder.add_edge(START, "llm_call")

agent_builder.add_conditional_edges(
    "llm_call",
    should_continue,
    {
        "tools": "tools",
        END: END,
    },
)

agent_builder.add_edge("tools", "llm_call")

agent = agent_builder.compile()

# # messages = [HumanMessage(content="what is 12 + 4?")]

# # # messages = agent.invoke({"messages": messages})
# # # for m in messages["messages"]:
# # #     m.pretty_print()

# # for message_chunk, metadata in agent.stream(
# #     {"messages": messages},
# #     stream_mode="messages",  
# # ):
# #     # print((agent["messages"]))
# #     # print(type(message_chunk))
# #     # print((message_chunk.usage_metadata))
# #     # print()
# #     # if message_chunk.content:
# #     #     print(message_chunk.content, end="", flush=True)
# #     # if message_chunk.usage_metadata is not None:
# #     #     total_tokens = message_chunk.usage_metadata["total_tokens"]
    
# #     # print("total number of tokens used ", total_tokens)

# #     print (metadata)

# if __name__ == "__main__":
#     result = agent.invoke(
#         {
#             "messages": [
#                 HumanMessage(content="ambient email agent project overview")
#             ],
#             "llm_calls": 0,
#         }
#     )

#     for msg in result["messages"]:
#         print(type(msg).__name__)
#         print(msg)
#         print("\n" + "-" * 100 + "\n")