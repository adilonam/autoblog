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

@app.post("/stream/")
async def generate_response(request: PromptRequest):
    
    _data =[]

    for j in  request.prompt:
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
    print("Received data ::: " , _data)
    try:
        client = Groq(api_key=groq_api_key)

        completion = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=_data,
        temperature=1,
        max_tokens=1024*1,
        top_p=1,
        stream=True,  # Enable streaming
        stop=None,
        )

        async def response_stream():
            for chunk in completion:
                content = chunk.choices[0].delta.content
                if content:
                    yield content + "\n"
                # await asyncio.sleep(5) 

        return StreamingResponse(response_stream(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fast_api:app", host="0.0.0.0", port=8000, reload=True)