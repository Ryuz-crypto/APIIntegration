import json
import re

from app.models.api_sample import ApiSample
from app.schemas.samples import ApiCodeExamples, ApiSampleRead, ApiTraceRead

SECRET_KEY = re.compile(
    r"(authorization|password|passwd|secret|token|api.?key|cookie|csrf)", re.IGNORECASE
)


def sanitize(value):
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if SECRET_KEY.search(str(key)) else sanitize(nested)
            for key, nested in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def build_trace(sample: ApiSample) -> ApiTraceRead:
    params = sanitize(sample.request_params)
    payload = sanitize(sample.payload)
    path = sample.path
    method = sample.method.upper()
    params_json = json.dumps(params, ensure_ascii=False, indent=2)
    curl = (
        f"curl -X {method} \"$ORCHESTRATOR_URL{path}\" \\\n"
        '  -H "X-Auth-Token: $EDGECONNECT_API_KEY"'
    )
    if params:
        curl += f" \\\n  --data '{json.dumps(params, ensure_ascii=False)}'"
    python = (
        "import os\nimport requests\n\n"
        f"url = os.environ['ORCHESTRATOR_URL'] + {path!r}\n"
        "headers = {'X-Auth-Token': os.environ['EDGECONNECT_API_KEY']}\n"
        f"params = {params_json}\n"
        f"response = requests.request({method!r}, url, headers=headers, "
        f"{'json' if method in {'POST', 'PUT', 'PATCH'} else 'params'}=params, timeout=20)\n"
        "response.raise_for_status()\nprint(response.json())"
    )
    body_line = f"  body: JSON.stringify({params_json}),\n" if params and method != "GET" else ""
    javascript = (
        f"const response = await fetch(`${{ORCHESTRATOR_URL}}{path}`, {{\n"
        f'  method: "{method}",\n'
        "  headers: { 'X-Auth-Token': EDGECONNECT_API_KEY, "
        "'Content-Type': 'application/json' },\n"
        f"{body_line}"
        "});\nif (!response.ok) throw new Error(`HTTP ${response.status}`);\n"
        "console.log(await response.json());"
    )
    return ApiTraceRead.model_validate(
        {
            **ApiSampleRead.model_validate(sample, from_attributes=True).model_dump(),
            "payload": payload,
            "sanitized_payload": payload,
            "request_params": params,
            "extracted_values": sanitize(sample.extracted_values),
            "code_examples": ApiCodeExamples(
                curl=curl,
                python=python,
                javascript=javascript,
            ),
        }
    )
