import tiktoken


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))


def truncate_messages(
    messages: list[dict],
    max_tokens: int,
    keep_minimum: int = 5,
) -> list[dict]:
    if len(messages) <= keep_minimum:
        return messages

    total = sum(count_tokens(m.get("content", "")) for m in messages)
    if total <= max_tokens:
        return messages

    # Remove oldest messages (from the front) until within budget, keeping minimum
    result = list(messages)
    while len(result) > keep_minimum:
        total = sum(count_tokens(m.get("content", "")) for m in result)
        if total <= max_tokens:
            break
        result.pop(0)

    return result
