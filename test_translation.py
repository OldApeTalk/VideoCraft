import os
import srt
import google.generativeai as genai

# 测试翻译逻辑
def test_translation():
    # 读取 Gemini API Key
    if not os.path.exists('Gemini.key'):
        print("请先配置Gemini Key")
        return

    with open('Gemini.key', 'r') as f:
        api_key = f.read().strip()
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash-lite")

    # 读取测试字幕文件
    test_srt_path = r"d:\My_新闻短片\20251115\米歇尔巴赫曼的演讲\English.srt"
    if not os.path.exists(test_srt_path):
        print(f"测试文件不存在: {test_srt_path}")
        return

    with open(test_srt_path, 'r', encoding='utf-8') as f:
        subs = list(srt.parse(f))

    print(f"读取到 {len(subs)} 条字幕")

    # 测试第2批（31-44号字幕）
    batch_contents = []
    for i in range(30, 44):  # 30-43 是0-based索引，对应31-44号字幕
        if i < len(subs):
            batch_contents.append(f"{i+1}. {subs[i].content}")

    print(f"第2批包含 {len(batch_contents)} 条字幕")

    # 创建输入
    numbered_input = '\n\n'.join(batch_contents)

    prompt = f"""You are a professional SRT subtitle translator. Your task is to translate the following SRT subtitles from English to Chinese.

The subtitles are provided in numbered format (1. subtitle, 2. subtitle, etc.). You must return the translated subtitles in the EXACT SAME numbered format.

CRITICAL REQUIREMENTS:
1. Translate EACH AND EVERY subtitle individually and separately
2. Return the EXACT SAME NUMBER of subtitles as input ({len(batch_contents)} subtitles)
3. Maintain the numbered format: "31. translated text", "32. translated text", etc.
4. DO NOT split any single subtitle into multiple subtitles
5. DO NOT merge multiple subtitles into one subtitle
6. DO NOT change the numbering or add/remove any subtitles
7. Preserve the original line breaks and formatting within each subtitle
8. Output ONLY the numbered subtitles, no explanations, comments, or additional text
9. Do NOT add quotation marks around translated text unless they are part of the original meaning
10. Ensure translation quality and natural language

Input subtitles ({len(batch_contents)} subtitles):
{numbered_input}

Return the translated subtitles in the same numbered format with {len(batch_contents)} subtitles:"""

    print("发送API请求...")
    response = model.generate_content(prompt)
    translated_batch = response.text.strip()

    print("API响应:")
    print(translated_batch)

    # 保存调试信息
    with open('test_debug_batch_2.txt', 'w', encoding='utf-8') as f:
        f.write("=== API 响应 ===\n")
        f.write(translated_batch)
        f.write("\n\n=== 输入 ===\n")
        f.write(numbered_input)

    print("调试信息已保存到 test_debug_batch_2.txt")

if __name__ == "__main__":
    test_translation()