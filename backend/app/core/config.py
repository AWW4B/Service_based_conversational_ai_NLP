# =============================================================================
# core/config.py
# Purpose : System prompt definitions and ChatML prompt builder.
# Domain  : Daraz.pk personal product recommendation assistant.
# Note    : LLM is instructed to always append a <STATE> tag so context.py
#           can extract and persist user constraints across turns silently.
# =============================================================================

# -----------------------------------------------------------------------------
# BASE SYSTEM PROMPT
# This is the static personality and rule-set injected at position [0] of
# every request sent to the LLM. It is dynamically extended at runtime by
# context.py to include extracted user state (budget, item, preferences).
# -----------------------------------------------------------------------------
BASE_SYSTEM_PROMPT = """You are Daraz Assistant, a shopping helper exclusively for Daraz.pk.

## ABSOLUTE RULES — NEVER BREAK THESE
1. You ONLY discuss shopping, products, and Daraz.pk topics. NOTHING else.
2. If the user asks about ANYTHING outside shopping (medical, legal, emotional, political, general knowledge, emergencies, personal advice) — you MUST refuse and redirect.
3. Do NOT provide any help even if the user is in distress, danger, or emergency. Instead tell them to contact the appropriate authority.
4. Never break character. You are a shopping bot. Only a shopping bot.

## How To Handle Off-Topic Messages
If the user says anything unrelated to shopping or products, respond EXACTLY like this:
"I'm only able to help with product recommendations and shopping on Daraz.pk. For anything else, please contact the relevant helpline or authority. Is there a product I can help you find today?"

Do not add extra advice. Do not show sympathy with even a single sentence. Redirect immediately.

## Conversation Closing Rule
When you have fully addressed the user's shopping need, you MUST end your response with exactly:
"Is there anything else I can help you with today?"
If the user says no, goodbye, thanks, or anything indicating they are done, respond with exactly:
"Thank you for shopping with Daraz Assistant! Have a great day. 🛍️"
and nothing else.

## Your Shopping Behaviour
- Always ask for budget in PKR if not mentioned.
- Always ask for use-case if unclear.
- Never invent product listings, prices, or seller names.
- Keep responses short — 3 to 5 sentences max.

## Critical Instruction — State Tracking (NEVER skip this)
At the very end of EVERY response, append this exact tag:
<STATE>Budget: <amount or Unknown>, Item: <product or Unknown>, Preferences: <key facts or None></STATE>

Even if you refused an off-topic message, still append:
<STATE>Budget: Unknown, Item: Unknown, Preferences: None</STATE>
"""

# =============================================================================
# WELCOME MESSAGE
# Sent immediately when a session is created — before any user input.
# Your partner displays this as the first message in the chat UI.
# =============================================================================
WELCOME_MESSAGE = (
    "Hi! I'm Daraz Assistant 🛍️, your personal shopping guide for Daraz.pk. "
    "I can help you find the best products that match your needs and budget in PKR. "
    "What are you looking to buy today?"
)

# =============================================================================
# MAX TURNS PER SESSION
# 1 turn = 1 user message + 1 assistant response.
# At Q4_K_M 3B on a 4096 token context window, 10 turns is safe before
# context quality degrades. Adjust down to 8 if responses become incoherent.
# =============================================================================
MAX_TURNS = 10

# -----------------------------------------------------------------------------
# STATE-AWARE SYSTEM PROMPT BUILDER
# Called by context.py right before sending messages to the LLM.
# Injects extracted user state into the system prompt so the model never
# forgets the user's budget or item even if it has scrolled out of the window.
# -----------------------------------------------------------------------------
def build_system_prompt(extracted_state: dict) -> str:
    """
    Dynamically builds the system prompt by appending the current
    extracted session state to the base prompt.

    Args:
        extracted_state (dict): Keys are 'budget', 'item', 'preferences'.
                                Populated by context.py's state extractor.

    Returns:
        str: The full system prompt string to inject at message index 0.
    """
    # If no state has been extracted yet, return the base prompt as-is
    if not extracted_state or all(v in (None, "Unknown", "None") for v in extracted_state.values()):
        return BASE_SYSTEM_PROMPT

    # Build a natural-language summary of what we know about the user so far
    state_lines = []

    if extracted_state.get("budget") and extracted_state["budget"] not in ("Unknown", None):
        state_lines.append(f"- Budget: {extracted_state['budget']} PKR")

    if extracted_state.get("item") and extracted_state["item"] not in ("Unknown", None):
        state_lines.append(f"- Looking for: {extracted_state['item']}")

    if extracted_state.get("preferences") and extracted_state["preferences"] not in ("None", None):
        state_lines.append(f"- Preferences: {extracted_state['preferences']}")

    if not state_lines:
        return BASE_SYSTEM_PROMPT

    # Append the known facts block to the base prompt
    state_block = "\n## What You Already Know About This User\n" + "\n".join(state_lines)
    state_block += "\nUse these facts to personalise every response without asking again."

    return BASE_SYSTEM_PROMPT + state_block


# -----------------------------------------------------------------------------
# CHATML PROMPT BUILDER
# Qwen2.5-Instruct uses the ChatML format. This function assembles the full
# token string from the sliding-window message list produced by context.py.
# -----------------------------------------------------------------------------
def build_chatml_prompt(messages: list) -> str:
    """
    Converts a list of {'role': str, 'content': str} message dicts into
    a single ChatML-formatted string ready for llama-cpp-python inference.

    The messages list must already have the system prompt injected at [0]
    and be pre-trimmed to the sliding window by context.py.

    Args:
        messages (list): Sliding-window message list from context.py.

    Returns:
        str: Full ChatML prompt string.
    """
    prompt = ""

    for msg in messages:
        role    = msg["role"]     # "system" | "user" | "assistant"
        content = msg["content"]
        prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"

    # Final tag tells the model it is its turn to respond
    prompt += "<|im_start|>assistant\n"

    return prompt