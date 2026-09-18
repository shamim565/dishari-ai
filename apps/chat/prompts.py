from apps.chat.context import build_system_prompt

MAX_HISTORY = 8


def chat_messages(journey, request, lang, history, user_message):
    messages = [{"role": "system", "content": build_system_prompt(journey, request, lang)}]
    for item in history[-MAX_HISTORY:]:
        messages.append({"role": item.role, "content": item.content})
    messages.append({"role": "user", "content": user_message})
    return messages
