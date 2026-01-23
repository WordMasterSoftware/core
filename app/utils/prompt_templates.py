"""大模型 Prompt 模板"""

WORD_TRANSLATION_PROMPT = """请为以下英语单词提供详细信息，以JSON格式返回：

要求：
1. 中文释义（最常用的1-2个意思）
2. 国际音标
3. 词性（如n., v., adj.等）
4. 2个实用例句（英文）
5. 每个句子长度不超过100个字符

单词列表：{words}

返回格式（必须是有效的JSON）：
{{
  "单词": {{
    "chinese": "中文释义",
    "phonetic": "音标",
    "part_of_speech": "词性",
    "sentences": ["例句1", "例句2"]
  }}
}}

请只返回JSON，不要包含其他文字。
"""

EXAM_GENERATION_PROMPT = """从以下单词中随机选择{count}个，造{sentence_count}个句子。

要求：
1. 每个句子使用1-2个给定单词
2. 句子难度适中，符合日常使用场景
3. 不要直接给出中文翻译
4. 每个句子长度不超过200个字符

单词列表：{words}

返回JSON格式（必须是有效的JSON）：
{{
  "sentences": [
    {{
      "english": "英文句子",
      "words_used": ["word1", "word2"]
    }}
  ]
}}

请只返回JSON，不要包含其他文字。
"""

TRANSLATION_GRADING_PROMPT = """请判断用户的中文翻译是否正确理解了英文原句的意思。

英文原句：{english_sentence}
用户翻译：{user_translation}

评判标准：
1. 是否表达了核心意思
2. 允许用词不同，但意思需一致
3. 不要求完全逐字翻译

返回JSON格式（必须是有效的JSON）：
{{
  "correct": true,
  "feedback": "简短评语"
}}

请只返回JSON，不要包含其他文字。
"""
