# ai_agent

자연어 요청을 함수 호출 계획 JSON으로 변환하는 Python 모듈이다.  
이번 단계의 책임은 "의도 해석 + 함수명/파라미터 생성 + dummy 실행"까지다.

## 이 모듈이 하는 일

- 사용자 자연어 요청을 해석한다.
- 아래 4개 함수 중 하나를 선택한다.
- 함수 호출 계획 JSON을 만든다.
- dummy 함수로 전체 flow를 검증한다.

지원 함수:

- `get_interest_keywords`
- `create_interest_keyword`
- `delete_interest_keyword`
- `get_recent_interest_notices`

세부 규칙은 [docs/agentic_flow.md](../docs/agentic_flow.md) 기준이다.

## 통합 시 먼저 볼 파일

- [service.py](./service.py): 통합 기준 진입점
- [types.py](./types.py): plan/result 구조
- [fallback.py](./fallback.py): 규칙 기반 파서
- [llm.py](./llm.py): Upstage 호출 계층

## 통합 기준 인터페이스

가장 단순한 진입점은 두 개다.

- `run_agentic_flow(prompt, use_llm=True, fallback_on_error=True)`
- `AgenticFlowService.run(prompt)`

반환 결과에는 아래가 포함된다.

- `planner`: `upstage` 또는 `fallback`
- `plan`: 함수 호출 계획
- `results`: dummy 함수 실행 결과

`plan` 구조:

```json
{
  "should_call_function": true,
  "calls": [
    {
      "function_name": "create_interest_keyword",
      "arguments": {
        "keyword": "장학금"
      }
    }
  ],
  "message": "관심사 키워드 등록 요청으로 해석했습니다."
}
```

## 가장 흔한 사용 방식

```python
from ai_agent.service import run_agentic_flow

result = run_agentic_flow("장학금 키워드 추가해줘", use_llm=False)
print(result.to_dict())
```

서비스 객체를 직접 쓸 수도 있다.

```python
from ai_agent.service import AgenticFlowService

service = AgenticFlowService(use_llm=True, fallback_on_error=True)
result = service.run("최근 하루 동안 스크랩된 공지 보여줘")
```

## 환경 변수

`.env` 파일은 저장소 루트에 둔다.

필수:

- `SECRET_KEY`: Upstage API secret key

선택:

- `UPSTAGE_MODEL`: 기본값 `solar-pro2`
- `UPSTAGE_CHAT_COMPLETIONS_URL`: 기본값 `https://api.upstage.ai/v1/solar/chat/completions`
- `UPSTAGE_TIMEOUT_SECONDS`: 기본값 `20`

예시:

```env
SECRET_KEY=your_upstage_secret_key
UPSTAGE_MODEL=solar-pro2
UPSTAGE_CHAT_COMPLETIONS_URL=https://api.upstage.ai/v1/solar/chat/completions
UPSTAGE_TIMEOUT_SECONDS=20
```

동작 우선순위:

1. `use_llm=True`이고 `SECRET_KEY`가 있으면 Upstage 호출 시도
2. 호출 실패 시 fallback 파서 사용
3. 외부 호출 없이 테스트하려면 `use_llm=False` 또는 `--no-llm`

## 로컬 실행

저장소 루트에서:

```bash
python3 -m ai_agent.main "장학금 키워드 추가해줘" --no-llm
```

`ai_agent/` 폴더 안에서:

```bash
python3 main.py "장학금 키워드 추가해줘" --no-llm
```

## 테스트

```bash
python3 -m unittest ai_agent.tests.test_ai_agent
```
