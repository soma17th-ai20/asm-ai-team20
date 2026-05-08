# ai_agent

`docs/agentic_flow.md` 기준의 Python 구현체다.

핵심 진입점:

- `ai_agent.service.AgenticFlowService`
- `ai_agent.service.run_agentic_flow`

예시:

```bash
# 저장소 루트에서 실행
python3 -m ai_agent.main "장학금 키워드 추가해줘" --no-llm

# ai_agent 폴더 안에서 실행
python3 main.py "장학금 키워드 추가해줘" --no-llm
```

구성:

- `service.py` : 전체 flow 진입점
- `llm.py` : Upstage 기반 계획 생성
- `fallback.py` : 네트워크 없이 동작하는 규칙 기반 파서
- `dispatcher.py` : 함수 호출 계획 실행
- `dummy_functions.py` : mock 함수 구현
- `types.py` : plan/result 데이터 구조
