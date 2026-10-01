import os
import traceback
from io import StringIO
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CodeRequest(BaseModel):
    code: str


class ErrorAnalysis(BaseModel):
    error_lines: list[int]


def execute_python_code(code: str) -> dict:
    old_stdout = sys.stdout
    sys.stdout = StringIO()

    try:
        exec(code, {})
        output = sys.stdout.getvalue()
        return {
            "success": True,
            "output": output,
        }

    except Exception:
        output = traceback.format_exc()
        return {
            "success": False,
            "output": output,
        }

    finally:
        sys.stdout = old_stdout


def analyze_error_with_ai(code: str, error_traceback: str) -> list[int]:
    token = os.environ.get("AIPIPE_TOKEN")

    if not token:
        raise RuntimeError("AIPIPE_TOKEN is not configured")

    client = OpenAI(
        api_key=token,
        base_url="https://aipipe.org/openai/v1",
    )

    prompt = f"""
Analyze the Python code and its traceback.

Your task is to identify the exact source-code line number(s)
where the error occurred.

Return ONLY valid JSON in this exact format:
{{"error_lines":[3]}}

CODE:
{code}

TRACEBACK:
{error_traceback}
"""

    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
            {
                "role": "system",
                "content": "Return only the requested JSON object."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    result = ErrorAnalysis.model_validate_json(content)

    return result.error_lines


@app.post("/code-interpreter")
def code_interpreter(request: CodeRequest):
    execution = execute_python_code(request.code)

    if execution["success"]:
        return {
            "error": [],
            "result": execution["output"],
        }

    error_lines = analyze_error_with_ai(
        request.code,
        execution["output"],
    )

    return {
        "error": error_lines,
        "result": execution["output"],
    }