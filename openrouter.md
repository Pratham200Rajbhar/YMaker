curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "z-ai/glm-4.5-air:free",
    "messages": [
      {
        "role": "user",
        "content": "How many r'\''s are in the word '\''strawberry'\''?"
      }
    ],
    "reasoning": {
      "enabled": false
    }
  }'

{"id":"gen-1778184802-C1BFjtT7NZc9ozE18LYG","object":"chat.completion","created":1778184802,"model":"z-ai/glm-4.5-air:free","provider":"Z.AI","system_fingerprint":null,"choices":[{"index":0,"logprobs":null,"finish_reason":"stop","native_finish_reason":"stop","message":{"role":"assistant","content":"There are three **r**'s in the word 'strawberry'.","refusal":null,"reasoning":null}}],"usage":{"prompt_tokens":22,"completion_tokens":17,"total_tokens":39,"cost":0,"is_byok":false,"prompt_tokens_details":{"cached_tokens":17,"cache_write_tokens":0,"audio_tokens":0,"video_tokens":0},"cost_details":{"upstream_inference_cost":0,"upstream_inference_prompt_cost":0,"upstream_inference_completions_cost":0},"completion_tokens_details":{"reasoning_tokens":0,"image_tokens":0,"audio_tokens":0}}}%           