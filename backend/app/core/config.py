# =============================================================================
# core/config.py
# =============================================================================

MAX_TURNS      = 15
MAX_TOKENS     = 512  # Gives model plenty of room to write the memory tag
N_CTX          = 2048
N_THREADS      = 4
N_BATCH        = 1024
TEMPERATURE    = 0.7
TOP_P          = 0.9
REPEAT_PENALTY = 1.1

SLIDING_WINDOW_SIZE = 10  # Remembers the last 5 full exchanges

WELCOME_MESSAGE = (
    "Hi! I'm Daraz Assistant 🛍️. I can help you find the best products "
    "that match your needs and budget in PKR. What are you looking to buy today?"
)

# =============================================================================
# BASE SYSTEM PROMPT (Self-Guarding)
# =============================================================================
BASE_SYSTEM_PROMPT = """You are Daraz Assistant, a helpful shopping guide for Daraz.pk.
Your job is to help users find the best products matching their needs and budget in PKR.

## Domain Restriction (CRITICAL)
- You MUST ONLY discuss shopping, products, Daraz, and related preferences (colors, sizes, prices).
- If the user asks about politics, coding, medical advice, or anything completely unrelated to shopping, YOU MUST politely refuse and steer them back to shopping. (e.g., "I am a shopping assistant and can only help with Daraz products. What would you like to buy?")
- Short answers like "black", "yes", or "under 5000" are valid shopping responses.

## Behaviour
- Be warm and concise. Keep responses under 4 sentences.
- ALWAYS ask for budget in PKR if not mentioned.

## STATE TAG — MANDATORY ON EVERY SINGLE RESPONSE
You MUST append this exact tag at the very end of your response, no exceptions:
<STATE>Budget: <PKR amount or Unknown>, Item: <product or Unknown>, Preferences: <key facts or None>, Resolved: <yes or no></STATE>
"""

def build_system_prompt(extracted_state: dict) -> str:
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

def build_chatml_prompt(messages: list) -> str:
    prompt = ""
    for msg in messages:
        prompt += f"<|im_start|>{msg['role']}\n{msg['content']}<|im_end|>\n"
    prompt += "<|im_start|>assistant\n"
    return prompt