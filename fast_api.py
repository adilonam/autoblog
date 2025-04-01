import asyncio
import time
import os
from fastapi import Request
from groq import Groq
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.responses import StreamingResponse
from typing import List
import re
load_dotenv()

groq_api_key = os.getenv('GROQ_API_KEY')
app = FastAPI()


class PromptRequest(BaseModel):
    prompt: List[dict]

def preprocess_data(data: List[dict]) -> List[dict]:
    _data =[]

    for j in  data:
        element = {}
        element['role'] = j['role']
        element['content'] = ""

        if isinstance(j['content'], str):
            element['content'] = j['content']
        else:
            for c in j['content']:
                if c['type'] == "text":
                    element['content'] += c['text']

        if  element['content']:
            _data.append(element)
    return _data

async def create_completion(client, model_name, messages):
    # Add a system message to handle specific user queries
    system_message = {
        "role": "system",
        "content": "If the user asks for your name, respond with 'Ready Ape R1'. If the user asks for the model name used to answer, respond with 'ready-ape-r1'."
    }
    messages.insert(0, system_message)
    return  client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=1,
        max_tokens=1024,
        top_p=1,
        stream=False,  # Normal response
        stop=None,
    )

@app.post("/stream/")
async def generate_response(request: PromptRequest, email: str = None):
    messages = preprocess_data(request.prompt)

    # Define models in a list for easy modification
    models = [
        {"name": "gemma2-9b-it", "alias": "Gemma2"},
        {"name": "llama3-8b-8192", "alias": "LLama3-8b"},
        {"name": "deepseek-r1-distill-llama-70b", "alias": "DeepSeek"},
        {"name": "qwen-2.5-32b", "alias": "qwen-2.5"},
       
    ]
    model_judge = "llama-3.3-70b-versatile"

    # Dynamically generate the model judge prompt based on the number of models
    model_judge_prompt = (
        f"""
        - You are an AI assistant tasked with evaluating and selecting the best response from {len(models)} provided answers.
        - Your goal is to either choose the single most appropriate response or merge the responses to create a more comprehensive and accurate answer.
        - Consider clarity, relevance, and completeness when making your decision.
        - After evaluation, provide your answer in the following format:
        """
        + "".join(
            [f"<response{i}>weight{i}</response{i}>" for i in range(1, len(models) + 1)]
        )
        + "<decision>pick|merge</decision><result>final_answer</result>"
        + "- After evaluation, provide your final answer directly without indicating that it was chosen or merged from multiple responses in the result section."
    )
    try:
        client = Groq(api_key=groq_api_key)

        # Generate responses from all models
        responses = []
        tasks = [
            create_completion(client, model["name"], messages)
            for model in models
        ]
        results = await asyncio.gather(*tasks)
        for model, result in zip(models, results):
            responses.append({"alias": model["alias"], "content": result.choices[0].message.content})

        # Combine responses into a single input for the judging model
        combined_responses = [{"role": "user", "content": r["content"]} for r in responses]

        model_judge_messages = [
            {"role": "system", "content": model_judge_prompt},* messages,
            {"role": "user", "content": "Please evaluate the following responses:"},
        ] + combined_responses

        # Use a fourth model to judge or merge the responses
        judging_completion = client.chat.completions.create(
            model=model_judge,
            messages=model_judge_messages,
            temperature=0,
            max_tokens=1024 *4,
            top_p=1,
            stream=False,
            stop=None,
        )

        judge_response = judging_completion.choices[0].message.content
        print(f"======= New Request from: {email} ======")
        print("## user prompt:", messages)
        for response in responses:
            print(f"## {response['alias']} response:", response["content"])
        print(f"## Model Judge {model_judge} response:", judge_response)

        try:
            result_value = re.search(r"<result>(.*?)</result>", judge_response, re.DOTALL).group(1)
            decision_value = re.search(r"<decision>(.*?)</decision>", judge_response).group(1)
            for i, response in enumerate(responses, start=1):
                weight = re.search(rf"<response{i}>(.*?)</response{i}>", judge_response).group(1)
                print(f"## {response['alias']} weight:", weight)
        except AttributeError:
            raise HTTPException(status_code=500, detail="Required tag not found in the judge response")

        print(f"## Judge {model_judge} decision:", decision_value)
        print("## Result:", result_value)

        async def response_stream():
            for word in result_value.split():
                yield word + " "
            await asyncio.sleep(0.2)  # Simulate delay for streaming

        return StreamingResponse(response_stream(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))





@app.post("/stream/title/")
async def generate_response(request: PromptRequest):
    messages = preprocess_data( request.prompt)

    try:
        client = Groq(api_key=groq_api_key)

        completion = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=messages,
        temperature=0.3,
        max_tokens=1024*1,
        top_p=1,
        stream=True,  # Enable streaming
        stop=None,
        )

        async def response_stream():
            for chunk in completion:
                content = chunk.choices[0].delta.content
                if content:
                    yield content 

        return StreamingResponse(response_stream(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fast_api:app", host="0.0.0.0", port=8000, reload=True)