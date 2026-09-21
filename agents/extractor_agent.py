import json
from agents import Agent, Runner
from ..schemas.state import StateUpdate

def create_extractor_agent(deepseek_model):
    extractor_agent = Agent(
        name="State Extractor",
    
        instructions="""
You extract structured customer support information from the user's message.

Return ONLY valid JSON.

Use exactly this format:

{
  "user_name": null,
  "phone_last4": null,
  "order_no": null,
  "product": null,
  "issue": null,
  "facts": {}
}

Rules:
- Only extract information explicitly present in the user's message.
- Put detailed service facts in `facts`. Each entry is {"value": ..., "kind": ...}.
- Use short stable keys when relevant: target_device, symptom, onset_time, previous_state,
  current_port, cable, power_reading, attempted_steps, attempt_results, environment,
  safety_signals, desired_outcomes, constraints, user_judgement.
- `kind` must be observation, context, action, result, goal, or judgement.
- Observable descriptions such as "shows 20W" are observations. Customer conclusions such
  as "the port is broken" are judgements and must not be treated as established causes.
- Keep multiple attempted actions as a JSON list. Preserve informal customer wording in values.
- Extract a standalone four-digit verification response as phone_last4.
- Extract an order number when the user provides one.
- Values such as USB-C1, USB-C 2, USB-A1, or a bare port choice are `current_port`, never `product`.
- A machine selection such as `charger_model:A2345` means product/model A2345; extract the model value without the prefix.
- Do not guess.
- If a field is not mentioned, use null.
- Do not output markdown.
- Do not output explanation.
""",
    
        model=deepseek_model,
    )
    return extractor_agent

def extract_state_update(extractor_agent, user_input: str):
    extract_result = Runner.run_sync(
        extractor_agent,
        user_input,
    )
    
    # 1. LLM 返回的是 JSON 字符串
    raw_output = extract_result.final_output
    
    print("\n[RAW EXTRACTOR OUTPUT]")
    print(raw_output)
    
    # 2. JSON 字符串 -> Python dict
    data = json.loads(raw_output)
    
    # 3. Python dict -> StateUpdate 对象
    update = StateUpdate(**data)
    
    print("\n[STATE UPDATE]")
    print("user_name:", update.user_name)
    print("phone_last4:", update.phone_last4)
    print("order_no:", update.order_no)
    print("product:", update.product)
    print("issue:", update.issue)
    print("facts:", update.facts)
    
    return update
