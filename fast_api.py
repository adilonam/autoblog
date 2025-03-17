import time
import os

from groq import Groq
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.responses import StreamingResponse

load_dotenv()

groq_api_key = os.getenv('GROQ_API_KEY')
app = FastAPI()



class PromptRequest(BaseModel):
    prompt: str

@app.post("/stream/")
async def generate_response(request: PromptRequest):
    try:
        client = Groq(api_key=groq_api_key)

        completion = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {
                "role": "system",
                "content": f"You are an assistant"
            },
            {
                "role": "user",
                "content": f"{request.prompt}"
            }
        ],
        temperature=1,
        max_tokens=1024*1,
        top_p=1,
        stream=True,  # Enable streaming
        stop=None,
        )

        def response_stream():
            for chunk in completion:
                time.sleep(0.1)
                content = chunk.choices[0].delta.content
                if content is not None:
                    yield content

        return StreamingResponse(response_stream(), media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fast_api:app", host="0.0.0.0", port=8000, reload=True)