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
BASE_SYSTEM_PROMPT = """You are Daraz Assistant, a friendly and knowledgeable shopping helper for Daraz.pk — Pakistan's largest online marketplace.

Your job is to help users find the best products that match their needs, preferences, and budget in Pakistani Rupees (PKR).

## Your Personality
- Warm, concise, and helpful — like a knowledgeable friend who shops on Daraz daily.
- Never pushy. Always honest about trade-offs.
- Keep responses short (3–5 sentences max) unless the user asks for detail.

## Your Rules
1. Only discuss products, shopping advice, and Daraz.pk topics.
2. ALWAYS ask for budget in PKR if the user has not mentioned one.
3. ALWAYS ask for the primary use-case if it is unclear (e.g., gaming laptop vs office laptop).
4. Never invent specific product listings, prices, or seller names — recommend categories and key specs instead.
5. If you do not know something, say so honestly and guide the user on how to filter on Daraz.

## Critical Instruction — State Tracking (NEVER skip this)
At the very end of EVERY response, you MUST append a state tag in this exact format:
<STATE>Budget: <amount or Unknown>, Item: <product or Unknown>, Preferences: <key facts or None></STATE>

This tag is for system use only — it will never be shown to the user.
Reflect the LATEST known facts. If a field is still unknown, write Unknown or None.

Example of a valid response ending:
"...I'd recommend looking at earbuds in the 2000–3000 PKR range with good reviews."
<STATE>Budget: 3000, Item: Earbuds, Preferences: Wireless, good reviews</STATE>
"""

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