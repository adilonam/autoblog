import asyncio
import time
import os

from groq import Groq
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.responses import StreamingResponse
from typing import List

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


model_judge_prompt = """
- You are an AI assistant tasked with evaluating and selecting the best response from three provided answers.
- Your goal is to either choose the single most appropriate response or merge the responses to create a more comprehensive and accurate answer.
- Consider clarity, relevance, and completeness when making your decision.
- After evaluation, provide your answer in the following format:
    <response1>weight1</response1><response2>weight2</response2><response3>weight3</response3><decision>pick|merge</decision><result>final_answer</result>
"""




@app.post("/stream/")
async def generate_response(request: PromptRequest):
    print("Received request ::: ", request.prompt)
    messages = preprocess_data(request.prompt)
    model1 = "gemma2-9b-it"
    model2 = "llama3-8b-8192"
    model3 = "deepseek-r1-distill-llama-70b"

    model_judge = "llama-3.3-70b-versatile"

    try:
        client = Groq(api_key=groq_api_key)

        # Generate responses from three models
        response1 = client.chat.completions.create(
            model=model1,
            messages=messages,
            temperature=1,
            max_tokens=1024,
            top_p=1,
            stream=False,  # Normal response
            stop=None,
        )

        response2 = client.chat.completions.create(
            model=model2,
            messages=messages,
            temperature=1,
            max_tokens=1024,
            top_p=1,
            stream=False,  # Normal response
            stop=None,
        )

        response3 = client.chat.completions.create(
            model=model3,
            messages=messages,
            temperature=1,
            max_tokens=1024,
            top_p=1,
            stream=False,  # Normal response
            stop=None,
        )

        # Combine responses into a single input for the judging model
        combined_responses = [
            {"role": "user", "content": response1.choices[0].message.content},
            {"role": "user", "content": response2.choices[0].message.content},
            {"role": "user", "content": response3.choices[0].message.content},
        ]

        

        model_judge_messages = [
            {"role": "system", "content": model_judge_prompt},
            {"role": "user", "content": "Please evaluate the following responses:"},
        ] + combined_responses




        # Use a fourth model to judge or merge the responses with streaming
        judging_completion = client.chat.completions.create(
            model=model_judge,
            messages=model_judge_messages,
            temperature=1,
            max_tokens=1024,
            top_p=1,
            stream=True,  # Enable streaming
            stop=None,
        )

        async def response_stream():
            stop_think = False
            start_think = False
            for chunk in judging_completion:
                content = chunk.choices[0].delta.content
                if content :
                    yield content

        return StreamingResponse(response_stream(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fast_api:app", host="0.0.0.0", port=8000, reload=True)