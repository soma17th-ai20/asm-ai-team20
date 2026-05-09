import yaml


def load_prompts():
    with open("prompts.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


PROMPTS = load_prompts()