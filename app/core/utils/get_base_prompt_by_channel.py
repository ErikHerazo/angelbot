from app.core import constants


def get_base_prompt_by_channel(channel: str) -> str:
    channel_map = {
        "website": constants.WEBSITE_ASSISTANT_PROMPT,
        "whatsapp": constants.WHATSAPP_ASSISTANT_PROMPT,
        "instagram": constants.INSTAGRAM_ASSISTANT_PROMPT,
        "flow": constants.FLOW_FORM_ASSISTANT_PROMPT,
    }

    print(f"============ CHANNEL: {channel}")
    return channel_map.get(channel, constants.WEBSITE_ASSISTANT_PROMPT).strip()
