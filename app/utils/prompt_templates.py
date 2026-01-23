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
3. 同时提供英文句子和对应的中文翻译
4. 每个句子长度不超过200个字符

单词列表：{words}

返回JSON格式（必须是有效的JSON）：
{{
  "sentences": [
    {{
      "english": "英文句子",
      "chinese": "中文翻译",
      "words_used": ["word1", "word2"]
    }}
  ]
}}

请只返回JSON，不要包含其他文字。
"""

TRANSLATION_GRADING_PROMPT = """请判断用户的英语翻译是否合格。

中文原句：{source_text}
用户译文：{user_translation}
必须包含的关键词：{required_words}

评判标准：
1. 意思准确表达了中文原句。
2. 语法基本正确。
3. 必须包含上述所有的关键词（允许变形，如复数、时态变化）。

返回JSON格式（必须是有效的JSON）：
{{
  "correct": true
}}

请只返回JSON，不要包含其他文字。
"""
