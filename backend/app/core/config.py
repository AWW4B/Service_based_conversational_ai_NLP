# =============================================================================
# core/config.py
# =============================================================================

# =============================================================================
# INFERENCE CONSTANTS
# =============================================================================
MAX_TURNS      = 10
MAX_TOKENS     = 256
N_CTX          = 2048
N_THREADS      = 4
N_BATCH        = 1024
TEMPERATURE    = 0.7
TOP_P          = 0.9
REPEAT_PENALTY = 1.1

SLIDING_WINDOW_SIZE = 6

# =============================================================================
# WELCOME MESSAGE
# =============================================================================
WELCOME_MESSAGE = (
    "Hi! I'm Daraz Assistant 🛍️, your personal shopping guide for Daraz.pk — "
    "Pakistan's largest online marketplace. I can help you find the best products "
    "that match your needs and budget in PKR. What are you looking to buy today?"
)

# =============================================================================
# BASE SYSTEM PROMPT
# Clean shopping-only prompt. Refusal logic is handled by the intent
# classifier in engine.py — NOT by rules here. This keeps the model
# focused purely on being a great shopping assistant.
# =============================================================================
BASE_SYSTEM_PROMPT = """You are Daraz Assistant, a helpful shopping guide for Daraz.pk — Pakistan's largest online marketplace.

Your job is to help users find the best products that match their needs and budget in PKR.

## Behaviour
- Be warm, concise, and helpful.
- ALWAYS ask for budget in PKR if not mentioned.
- ALWAYS ask for use-case if the product purpose is unclear.
- Never invent specific product listings, prices, or seller names — recommend categories and key specs instead.
- Keep responses under 4 sentences.
- When the user's shopping request is fully resolved, end your response with: "Is there anything else I can help you with today?"

## STATE TAG — MANDATORY ON EVERY SINGLE RESPONSE
You MUST append this tag at the very end of every response, no exceptions:
<STATE>Budget: <PKR amount or Unknown>, Item: <product or Unknown>, Preferences: <key facts or None>, Resolved: <yes or no></STATE>

Rules:
- Resolved yes = user's request is fully addressed AND you asked the closing question
- Resolved no = conversation is still ongoing
- This tag is stripped automatically and never shown to the user
"""


# =============================================================================
# STATE-AWARE SYSTEM PROMPT BUILDER
# Injects known user facts so they survive the sliding window.
# =============================================================================
def build_system_prompt(extracted_state: dict) -> str:
    """
    Extends base system prompt with extracted session state.

    Args:
        extracted_state (dict): {budget, item, preferences, resolved}

    Returns:
        str: Full system prompt with known facts injected.
    """
    if not extracted_state:
        return BASE_SYSTEM_PROMPT

    facts = []
    if extracted_state.get("budget") not in (None, "Unknown"):
        facts.append(f"- Budget: {extracted_state['budget']} PKR")
    if extracted_state.get("item") not in (None, "Unknown"):
        facts.append(f"- Looking for: {extracted_state['item']}")
    if extracted_state.get("preferences") not in (None, "None"):
        facts.append(f"- Preferences: {extracted_state['preferences']}")

    if not facts:
        return BASE_SYSTEM_PROMPT

    injected = "\n## Already Known About This User (DO NOT ask again)\n"
    injected += "\n".join(facts)
    return BASE_SYSTEM_PROMPT + injected


# =============================================================================
# CHATML PROMPT BUILDER
# =============================================================================
def build_chatml_prompt(messages: list) -> str:
    """
    Converts message list to ChatML string for llama-cpp-python.

    Args:
        messages (list): [{"role": str, "content": str}, ...]

    Returns:
        str: Full ChatML prompt ending with <|im_start|>assistant\n
    """
    prompt = ""
    for msg in messages:
        prompt += f"<|im_start|>{msg['role']}\n{msg['content']}<|im_end|>\n"
    prompt += "<|im_start|>assistant\n"
    return prompt