from openai import OpenAI


def build_client(setup):
    kwargs = {"api_key": setup["api_key"], "timeout": 45.0, "max_retries": 1}
    if setup["base_url"]:
        kwargs["base_url"] = setup["base_url"]
    return OpenAI(**kwargs)
