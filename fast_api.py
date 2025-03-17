import os

from groq import Groq
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

groq_api_key = os.getenv('GROQ_API_KEY')
app = FastAPI()



class PromptRequest(BaseModel):
    prompt: str

@app.post("/generate/")
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
        max_tokens=1024*4,
        top_p=1,
        stream=False,  
        stop=None,
        )

        return {"response": completion.choices[0].message.content.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fast_api:app", host="0.0.0.0", port=8000, reload=True)