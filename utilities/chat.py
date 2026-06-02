from uuid import uuid4


async def format_agent_response(agent, messages, langfuse_handler):
    """Stream response from agent and return the final content"""

    response_text = ""
    request_thread_id = f"session_{uuid4().hex}"
    async for chunk in agent.astream(
        {"messages": messages},
        config={"configurable": {"thread_id": request_thread_id}, "callbacks": [langfuse_handler]},
        stream_mode="values"
    ):
        if 'messages' in chunk and chunk['messages']:
            latest_message = chunk['messages'][-1]
            if hasattr(latest_message, 'content'):
                response_text = latest_message.content

    return response_text
