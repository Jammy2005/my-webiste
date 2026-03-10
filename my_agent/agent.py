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

class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int
    # tokens_used: int

# IDENTIFY THE MODEL
model = init_chat_model(
    "gpt-4o",
    temperature=0
)

# Define tools
@tool
def multiply(a: int, b: int) -> int:
    """
    Might make a send Gmail tool
    """
    return None


def llm_call(state: dict):
    """LLM decides whether to call a tool or not"""

    response = model.invoke(
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

agent_builder = StateGraph(MessagesState)

agent_builder.add_node("llm_call", llm_call)

agent_builder.add_edge(START, "llm_call")

agent_builder.add_edge("llm_call", END)

# compile the agent
agent = agent_builder.compile()


messages = [HumanMessage(content="what is 12 + 4?")]

# messages = agent.invoke({"messages": messages})
# for m in messages["messages"]:
#     m.pretty_print()

for message_chunk, metadata in agent.stream(
    {"messages": messages},
    stream_mode="messages",  
):
    # print((agent["messages"]))
    # print(type(message_chunk))
    # print((message_chunk.usage_metadata))
    # print()
    # if message_chunk.content:
    #     print(message_chunk.content, end="", flush=True)
    # if message_chunk.usage_metadata is not None:
    #     total_tokens = message_chunk.usage_metadata["total_tokens"]
    
    # print("total number of tokens used ", total_tokens)

    print (metadata)